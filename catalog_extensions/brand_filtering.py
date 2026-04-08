import frappe
from frappe import _

from webshop.webshop.doctype.item_review.item_review import get_customer
from webshop.webshop.doctype.webshop_settings.webshop_settings import (
    get_shopping_cart_settings,
)


CACHE_KEY = "catalog_extensions:customer_group_brand_filters"


def _normalize_values(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if v]
    return [value]


@frappe.request_cache
def get_current_customer_group():
    customer = get_customer(silent=True)
    if customer:
        return frappe.get_cached_value("Customer", customer, "customer_group")

    settings = get_shopping_cart_settings()
    return settings.default_customer_group if settings else None


def get_allowed_brands_for_customer_group(customer_group=None):
    customer_group = customer_group or get_current_customer_group()
    if not customer_group:
        return []

    cached = frappe.cache().hget(CACHE_KEY, customer_group)
    if cached is not None:
        return list(cached)

    brands = frappe.get_all(
        "Customer Group Brand Mapping",
        filters={"customer_group": customer_group, "enabled": 1},
        pluck="brand",
        order_by="brand asc",
    )
    brands = [brand for brand in brands if brand]
    frappe.cache().hset(CACHE_KEY, customer_group, brands)
    return brands


@frappe.request_cache
def get_brand_filter_context():
    customer_group = get_current_customer_group()
    allowed_brands = get_allowed_brands_for_customer_group(customer_group)
    return frappe._dict(
        {
            "customer_group": customer_group,
            "allowed_brands": allowed_brands,
            "restricted": bool(allowed_brands),
        }
    )


def apply_brand_filter(field_filters=None):
    filters = dict(field_filters or {})
    context = get_brand_filter_context()

    if not context.restricted:
        return filters, False, context

    allowed = set(context.allowed_brands)
    selected = _normalize_values(filters.get("brand"))

    if selected:
        selected = [brand for brand in selected if brand in allowed]
        if not selected:
            return filters, True, context
        filters["brand"] = selected
    else:
        filters["brand"] = list(context.allowed_brands)

    return filters, False, context


def get_item_brand(item_code):
    brand = frappe.db.get_value("Website Item", {"item_code": item_code}, "brand")
    if brand:
        return brand
    return frappe.db.get_value("Item", item_code, "brand")


def is_item_allowed(item_code):
    context = get_brand_filter_context()
    if not context.restricted:
        return True

    item_brand = get_item_brand(item_code)
    return bool(item_brand and item_brand in set(context.allowed_brands))


def assert_item_allowed(item_code):
    if is_item_allowed(item_code):
        return

    frappe.throw(
        _("This product is not available for your customer group."),
        exc=frappe.PermissionError,
    )


def validate_customer_group_brand_mapping(doc, method=None):
    if not doc.customer_group or not doc.brand:
        return

    if frappe.db.get_value("Customer Group", doc.customer_group, "is_group"):
        frappe.throw(_("Customer Group must be a leaf node for brand mapping."))

    duplicate = frappe.db.exists(
        "Customer Group Brand Mapping",
        {
            "customer_group": doc.customer_group,
            "brand": doc.brand,
            "name": ["!=", doc.name],
        },
    )
    if duplicate:
        frappe.throw(
            _("Brand {0} is already mapped to Customer Group {1}.").format(
                frappe.bold(doc.brand), frappe.bold(doc.customer_group)
            )
        )


def clear_customer_group_brand_filter_cache(doc=None, method=None):
    customer_group = getattr(doc, "customer_group", None) if doc else None
    if customer_group:
        frappe.cache().hdel(CACHE_KEY, customer_group)
    else:
        frappe.cache().delete_key(CACHE_KEY)
