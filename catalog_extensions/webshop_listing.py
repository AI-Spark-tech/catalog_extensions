import frappe
from frappe.utils import cint

from webshop.webshop.product_data_engine.filters import ProductFiltersBuilder


ALL_PRODUCTS_PATH = "/all-products"


def get_listing_page_context(item_group=None):
    field_filters, attribute_filters = _get_default_listing_filters(item_group=item_group)

    return frappe._dict(
        {
            "body_class": "product-page",
            "field_filters": field_filters,
            "attribute_filters": attribute_filters,
            "page_length": cint(
                frappe.db.get_single_value("Webshop Settings", "products_per_page")
            )
            or 20,
            "search_link": "/product_search",
            "catalog_listing_context": frappe._dict(
                {
                    "is_listing_page": True,
                    "item_group": item_group,
                    "path": frappe.local.request.path if getattr(frappe.local, "request", None) else None,
                }
            ),
        }
    )


def apply_listing_page_context(context, item_group=None):
    listing_context = get_listing_page_context(item_group=item_group)

    for key, value in listing_context.items():
        context[key] = value

    return context


def update_website_context(context):
    path = (context.get("path") or context.get("pathname") or "").rstrip("/") or "/"
    item_group = _get_item_group_from_context(context)

    if path != ALL_PRODUCTS_PATH and not item_group:
        return

    apply_listing_page_context(context, item_group=item_group)


def _get_item_group_from_context(context):
    doc = context.get("doc")
    if getattr(doc, "doctype", None) == "Item Group":
        return doc.name

    if context.get("template") == "templates/generators/item_group.html" and context.get("name"):
        return context.get("name")

    return None


def _get_default_listing_filters(item_group=None):
    settings_engine = ProductFiltersBuilder()
    field_filters = settings_engine.get_field_filters() or []
    attribute_filters = settings_engine.get_attribute_filters() or []

    if not item_group:
        return field_filters, attribute_filters

    item_group_engine = ProductFiltersBuilder(item_group)
    item_group_field_filters = item_group_engine.get_field_filters() or []
    item_group_attribute_filters = item_group_engine.get_attribute_filters() or []

    return (
        _merge_field_filters(field_filters, item_group_field_filters),
        _merge_attribute_filters(attribute_filters, item_group_attribute_filters),
    )


def _merge_field_filters(default_filters, page_filters):
    merged = []
    seen = set()

    for field_filter in list(default_filters or []) + list(page_filters or []):
        if not field_filter or len(field_filter) < 2:
            continue

        field_meta, values = field_filter[0], field_filter[1]
        fieldname = getattr(field_meta, "fieldname", None)
        if not fieldname or fieldname in seen:
            continue

        cleaned_values = [value for value in (values or []) if value]
        if not cleaned_values:
            continue

        merged.append([field_meta, cleaned_values])
        seen.add(fieldname)

    return merged


def _merge_attribute_filters(default_filters, page_filters):
    merged = []
    seen = set()

    for attribute_filter in list(default_filters or []) + list(page_filters or []):
        attribute_name = getattr(attribute_filter, "name", None)
        values = getattr(attribute_filter, "item_attribute_values", None) or []

        if not attribute_name or attribute_name in seen:
            continue

        cleaned_values = [value for value in values if value]
        if not cleaned_values:
            continue

        merged.append(
            frappe._dict(
                {
                    "name": attribute_name,
                    "item_attribute_values": cleaned_values,
                }
            )
        )
        seen.add(attribute_name)

    return merged
