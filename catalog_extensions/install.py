import frappe
import os
import sys

from catalog_extensions.install_support import assert_install_prerequisites, assert_setup_complete
from catalog_extensions.printing import ensure_order_receipt_print_format


def _import_setup_modules():
    """Import setup modules from deploy/ directory (at app root, not inside package)."""
    # Get path to catalog_extensions app root
    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    deploy_path = os.path.join(app_root, "deploy")
    
    if deploy_path not in sys.path:
        sys.path.insert(0, deploy_path)
    
    import setup_doctypes
    import setup_custom_fields
    
    return setup_doctypes, setup_custom_fields


def _run_setup():
    """Ensure all required DocTypes, custom fields, and indexes exist.

    This is safe to run multiple times because the underlying helpers
    check for existing DocTypes/fields/indexes before creating them.
    """
    assert_install_prerequisites()
    setup_doctypes, setup_custom_fields = _import_setup_modules()
    
    # Create Catalog Price Range DocType + default ranges
    setup_doctypes.create_catalog_price_range_doctype(frappe)
    setup_doctypes.create_default_price_ranges(frappe)

    # Create Webshop Simple Checkout Settings singleton DocType
    setup_doctypes.create_webshop_simple_checkout_settings_doctype(frappe)

    # Create Customer Group Brand Mapping DocType used by brand filtering
    setup_doctypes.create_customer_group_brand_mapping_doctype(frappe)

    # Create custom fields on Item, Website Item
    setup_custom_fields.setup_item_fields(frappe)
    setup_custom_fields.setup_website_item_fields(frappe)
    setup_custom_fields.setup_checkout_mode_fields(frappe)

    # Ensure Item Badge child DocType is present
    setup_custom_fields.sync_item_badge_doctype(frappe)

    # Create performance indexes for custom filter queries
    setup_custom_fields.setup_performance_indexes(frappe)

    # Ensure portal-only customer receipt print format exists
    ensure_order_receipt_print_format()
    return assert_setup_complete()


def after_install():
    """Hook: run after app is installed on a site."""
    warnings = _run_setup()
    for warning in warnings:
        frappe.logger("catalog_extensions.install").warning(warning)


def after_migrate():
    """Hook: run after migrations (helps on existing benches/sites)."""
    warnings = _run_setup()
    for warning in warnings:
        frappe.logger("catalog_extensions.install").warning(warning)
