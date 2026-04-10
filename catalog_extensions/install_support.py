import frappe

from catalog_extensions.printing import ORDER_RECEIPT_PRINT_FORMAT

REQUIRED_CORE_APPS = ("erpnext", "payments", "webshop")
OPTIONAL_APPS = ("erpnext_shipping_extended",)
REQUIRED_BASE_DOCTYPES = (
    "Item",
    "Website Item",
    "Website Offer",
    "Payment Request",
    "Sales Order",
    "Sales Invoice",
    "Delivery Note",
    "Brand",
    "Customer Group",
    "Print Format",
)
REQUIRED_SETUP_DOCTYPES = (
    "Catalog Price Range",
    "Webshop Simple Checkout Settings",
    "Customer Group Brand Mapping",
    "Item Badge",
)
REQUIRED_CUSTOM_FIELDS = (
    ("Item", "custom_consumer_discount"),
    ("Item", "badges"),
    ("Website Item", "custom_consumer_discount"),
    ("Website Item", "custom_availability"),
    ("Website Item", "filterable_offers"),
    ("Website Item", "filterable_badges"),
)
REQUIRED_INDEXES = (
    ("Website Offer", "idx_website_offer_filter"),
    ("Item Badge", "idx_item_badge_filter"),
    ("Item Price", "idx_item_price_filter"),
)


def _raise_install_error(message: str) -> None:
    raise frappe.ValidationError(message)


def get_installed_apps() -> list[str]:
    installed = frappe.get_installed_apps() or []
    return [app for app in installed if app]


def is_optional_app_installed(app_name: str) -> bool:
    return app_name in get_installed_apps()


def get_missing_required_apps() -> list[str]:
    installed_apps = set(get_installed_apps())
    return [app for app in REQUIRED_CORE_APPS if app not in installed_apps]


def get_missing_required_doctypes() -> list[str]:
    return [doctype for doctype in REQUIRED_BASE_DOCTYPES if not frappe.db.exists("DocType", doctype)]


def assert_install_prerequisites() -> None:
    missing_apps = get_missing_required_apps()
    if missing_apps:
        _raise_install_error(
            "Catalog Extensions requires these apps to be installed on the site first: "
            + ", ".join(missing_apps)
            + "."
        )

    missing_doctypes = get_missing_required_doctypes()
    if missing_doctypes:
        _raise_install_error(
            "Catalog Extensions is missing required baseline DocTypes from core apps: "
            + ", ".join(missing_doctypes)
            + "."
        )


def get_optional_dependency_warnings() -> list[str]:
    warnings = []
    if not is_optional_app_installed("erpnext_shipping_extended"):
        warnings.append(
            "Optional app 'erpnext_shipping_extended' is not installed. Shipping-rate automation, "
            "pickup automation, and reverse-pickup creation will stay in manual mode."
        )
    return warnings


def verify_setup_artifacts() -> tuple[list[str], list[str]]:
    errors: list[str] = []

    for doctype in REQUIRED_SETUP_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            errors.append(f"Missing DocType: {doctype}")

    for doctype, fieldname in REQUIRED_CUSTOM_FIELDS:
        if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
            errors.append(f"Missing Custom Field: {doctype}.{fieldname}")

    if not frappe.db.exists("Print Format", ORDER_RECEIPT_PRINT_FORMAT):
        errors.append(f"Missing Print Format: {ORDER_RECEIPT_PRINT_FORMAT}")

    for table_name, index_name in REQUIRED_INDEXES:
        rows = frappe.db.sql(
            """
            SELECT 1
            FROM information_schema.STATISTICS
            WHERE table_schema = DATABASE()
              AND table_name = %s
              AND index_name = %s
            """,
            (f"tab{table_name}", index_name),
        )
        if not rows:
            errors.append(f"Missing Index: {index_name} on {table_name}")

    return errors, get_optional_dependency_warnings()


def assert_setup_complete() -> list[str]:
    errors, warnings = verify_setup_artifacts()
    if errors:
        _raise_install_error("Catalog Extensions setup is incomplete: " + "; ".join(errors))
    return warnings


def is_doctype_available(doctype: str) -> bool:
    return bool(doctype and frappe.db.exists("DocType", doctype))
