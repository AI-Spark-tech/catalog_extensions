#!/usr/bin/env python3
"""Automated DocType Setup for Catalog Extensions (script style).

Usage (from bench root):

    ./env/bin/python apps/catalog_extensions/deploy/setup_doctypes.py --site sitename
"""

import os
import sys
import argparse


def get_frappe_connection(site: str):
    """Initialize Frappe connection for the given site."""

    # Add bench root and apps to sys.path based on this file's location
    bench_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if bench_root not in sys.path:
        sys.path.insert(0, bench_root)
    apps_path = os.path.join(bench_root, "apps")
    if apps_path not in sys.path:
        sys.path.insert(0, apps_path)

    try:
        import frappe

        frappe.init(site=site)
        frappe.connect()
        return frappe
    except Exception as e:
        print(f"[ERROR] Cannot connect to Frappe for site {site}: {e}")
        return None


def create_catalog_price_range_doctype(frappe):
    """Create the Catalog Price Range DocType if it doesn't exist."""

    doctype_name = "Catalog Price Range"
    module = "Catalog Extensions"

    if frappe.db.exists("DocType", doctype_name):
        print(f"[INFO] DocType '{doctype_name}' already exists")
        return True

    print(f"[STEP] Creating DocType: {doctype_name}...")

    try:
        doc = frappe.get_doc(
            {
                "doctype": "DocType",
                "name": doctype_name,
                "module": module,
                "custom": 1,
                "autoname": "field:label",
                "fields": [
                    {
                        "fieldname": "label",
                        "label": "Label",
                        "fieldtype": "Data",
                        "reqd": 1,
                        "unique": 1,
                        "in_list_view": 1,
                    },
                    {
                        "fieldname": "from_amount",
                        "label": "From Amount",
                        "fieldtype": "Currency",
                        "in_list_view": 1,
                    },
                    {
                        "fieldname": "to_amount",
                        "label": "To Amount",
                        "fieldtype": "Currency",
                        "in_list_view": 1,
                    },
                    {
                        "fieldname": "sort_order",
                        "label": "Sort Order",
                        "fieldtype": "Int",
                        "in_list_view": 1,
                        "default": "0",
                    },
                    {
                        "fieldname": "enabled",
                        "label": "Enabled",
                        "fieldtype": "Check",
                        "default": "1",
                        "in_list_view": 1,
                    },
                ],
                "permissions": [
                    {
                        "role": "System Manager",
                        "read": 1,
                        "write": 1,
                        "create": 1,
                        "delete": 1,
                    },
                    {
                        "role": "Website Manager",
                        "read": 1,
                        "write": 1,
                        "create": 1,
                        "delete": 1,
                    },
                ],
                "track_changes": 1,
                "engine": "InnoDB",
                "sort_field": "sort_order",
                "sort_order": "ASC",
            }
        )

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        print(f"[SUCCESS] DocType '{doctype_name}' created successfully")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to create DocType: {e}")
        return False


def create_webshop_simple_checkout_settings_doctype(frappe):
	"""Create the Webshop Simple Checkout Settings singleton DocType if missing.

	This is used to control webshop checkout behaviour per site without
	manual DocType creation in each environment.
	"""

	doctype_name = "Webshop Simple Checkout Settings"
	module = "Catalog Extensions"
	field_definitions = [
		{
			"fieldname": "enable_simple_checkout",
			"label": "Legacy Webshop Checkout Toggle",
			"fieldtype": "Check",
			"default": "0",
			"hidden": 1,
			"read_only": 1,
			"description": "Legacy compatibility field. Shipping and payment visibility is now controlled directly by the flags below.",
		},
		{
			"fieldname": "hide_shipping_on_webshop",
			"label": "Disable Shipping Section on Cart",
			"fieldtype": "Check",
			"default": "0",
			"description": (
				"Hide shipping and billing selectors on the cart, auto-apply the default address, "
				"and suppress shipping tracking and return flow on order pages."
			),
		},
		{
			"fieldname": "hide_payment_on_webshop",
			"label": "Disable Payment Section on Cart",
			"fieldtype": "Check",
			"default": "0",
			"description": (
				"Hide payment-related cart UI, skip the checkout payment workflow, apply default payment terms, "
				"and suppress payment and refund actions on order pages. Prepaid and COD selection on the cart "
				"become inactive while this is enabled."
			),
		},
		{
			"fieldname": "enable_prepaid",
			"label": "Enable Prepaid",
			"fieldtype": "Check",
			"default": "1",
			"description": "Allow customers to choose prepaid checkout when the payment section is enabled.",
		},
		{
			"fieldname": "enable_cod",
			"label": "Enable Cash on Delivery",
			"fieldtype": "Check",
			"default": "0",
			"description": "Allow customers to choose cash on delivery when the payment section is enabled.",
		},
		{
			"fieldname": "default_payment_mode",
			"label": "Default Payment Mode",
			"fieldtype": "Select",
			"options": "PREPAID\nCOD",
			"default": "PREPAID",
			"description": "Use this payment mode by default when the payment section is enabled and multiple checkout payment modes are available.",
		},
		{
			"fieldname": "default_shipping_address_type",
			"label": "Default Shipping Address Type",
			"fieldtype": "Select",
			"options": "Shipping\nBilling",
			"default": "Shipping",
			"description": "Choose which saved address type should be auto-applied when shipping is hidden.",
		},
		{
			"fieldname": "default_payment_term_template",
			"label": "Default Payment Terms Template",
			"fieldtype": "Link",
			"options": "Payment Terms Template",
			"description": "Automatically apply this payment terms template when payment is hidden.",
		},
		{
			"fieldname": "enable_cancel_order",
			"label": "Enable Cancel Order",
			"fieldtype": "Check",
			"default": "0",
			"description": "Allow the cancel action on order pages when the order state normally permits cancellation.",
		},
	]

	if frappe.db.exists("DocType", doctype_name):
		print(f"[INFO] DocType '{doctype_name}' already exists")
		doctype = frappe.get_doc("DocType", doctype_name)
		existing_fieldnames = {field.fieldname for field in doctype.fields or []}
		fields_changed = False

		for field in doctype.fields or []:
			matching_definition = next(
				(field_def for field_def in field_definitions if field_def["fieldname"] == field.fieldname),
				None,
			)
			if not matching_definition:
				continue
			for key in ("label", "options", "default", "description", "hidden", "read_only"):
				if key in matching_definition and getattr(field, key, None) != matching_definition[key]:
					setattr(field, key, matching_definition[key])
					fields_changed = True

		for field_def in field_definitions:
			if field_def["fieldname"] in existing_fieldnames:
				continue
			doctype.append("fields", field_def)
			fields_changed = True

		if fields_changed:
			doctype.save(ignore_permissions=True)
			frappe.db.commit()
			print(f"[SUCCESS] Updated fields on '{doctype_name}'")

		return True

	print(f"[STEP] Creating DocType: {doctype_name}...")

	try:
		doc = frappe.get_doc(
			{
				"doctype": "DocType",
				"name": doctype_name,
				"module": module,
				"custom": 1,
				"issingle": 1,
				"fields": field_definitions,
				"permissions": [
					{
						"role": "System Manager",
						"read": 1,
						"write": 1,
						"create": 1,
						"delete": 1,
					},
					{
						"role": "Website Manager",
						"read": 1,
						"write": 1,
					},
				],
				"track_changes": 1,
				"engine": "InnoDB",
			}
		)

		doc.insert(ignore_permissions=True)
		frappe.db.commit()

		print(f"[SUCCESS] DocType '{doctype_name}' created successfully")
		return True

	except Exception as e:
		print(f"[ERROR] Failed to create DocType '{doctype_name}': {e}")
		return False


def create_customer_group_brand_mapping_doctype(frappe):
    """Create the customer-group to brand mapping DocType if it doesn't exist."""

    doctype_name = "Customer Group Brand Mapping"
    module = "Catalog Extensions"
    field_definitions = [
        {
            "fieldname": "customer_group",
            "label": "Customer Group",
            "fieldtype": "Link",
            "options": "Customer Group",
            "reqd": 1,
            "in_list_view": 1,
            "link_filters": '[["Customer Group", "is_group", "=", 0]]',
        },
        {
            "fieldname": "brand",
            "label": "Brand",
            "fieldtype": "Link",
            "options": "Brand",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "enabled",
            "label": "Enabled",
            "fieldtype": "Check",
            "default": "1",
            "in_list_view": 1,
        },
    ]

    if frappe.db.exists("DocType", doctype_name):
        print(f"[INFO] DocType '{doctype_name}' already exists")
        doctype = frappe.get_doc("DocType", doctype_name)
        existing_fieldnames = {field.fieldname for field in doctype.fields or []}
        fields_added = False

        for field_def in field_definitions:
            if field_def["fieldname"] in existing_fieldnames:
                continue
            doctype.append("fields", field_def)
            fields_added = True

        if fields_added:
            doctype.save(ignore_permissions=True)
            frappe.db.commit()
            print(f"[SUCCESS] Added missing fields to '{doctype_name}'")

        return True

    print(f"[STEP] Creating DocType: {doctype_name}...")

    try:
        doc = frappe.get_doc(
            {
                "doctype": "DocType",
                "name": doctype_name,
                "module": module,
                "custom": 1,
                "autoname": "hash",
                "title_field": "customer_group",
                "fields": field_definitions,
                "permissions": [
                    {
                        "role": "System Manager",
                        "read": 1,
                        "write": 1,
                        "create": 1,
                        "delete": 1,
                    },
                    {
                        "role": "Website Manager",
                        "read": 1,
                        "write": 1,
                        "create": 1,
                        "delete": 1,
                    },
                ],
                "track_changes": 1,
                "sort_field": "modified",
                "sort_order": "DESC",
                "engine": "InnoDB",
            }
        )

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        print(f"[SUCCESS] DocType '{doctype_name}' created successfully")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to create DocType '{doctype_name}': {e}")
        return False


def create_default_price_ranges(frappe):
    """Create default price range records if none exist."""

    print("[STEP] Checking default price ranges...")

    existing = frappe.db.count("Catalog Price Range")
    if existing > 0:
        print(f"[INFO] {existing} price range(s) already exist, skipping defaults")
        return True

    default_ranges = [
        {"label": "Under $25", "from_amount": 0, "to_amount": 25, "sort_order": 1},
        {"label": "$25 - $50", "from_amount": 25, "to_amount": 50, "sort_order": 2},
        {"label": "$50 - $100", "from_amount": 50, "to_amount": 100, "sort_order": 3},
        {"label": "$100 - $250", "from_amount": 100, "to_amount": 250, "sort_order": 4},
        {"label": "Over $250", "from_amount": 250, "to_amount": None, "sort_order": 5},
    ]

    try:
        for range_data in default_ranges:
            doc = frappe.get_doc(
                {
                    "doctype": "Catalog Price Range",
                    **range_data,
                    "enabled": 1,
                }
            )
            doc.insert(ignore_permissions=True)

        frappe.db.commit()
        print(f"[SUCCESS] Created {len(default_ranges)} default price ranges")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to create price ranges: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Automated DocType Setup for Catalog Extensions",
    )
    parser.add_argument("--site", required=True, help="Site name to setup")

    args = parser.parse_args()

    print("=" * 60)
    print("CATALOG EXTENSIONS - DOCTYPE SETUP")
    print("=" * 60)
    print(f"Site: {args.site}")
    print("=" * 60)

    frappe = get_frappe_connection(args.site)
    if not frappe:
        sys.exit(1)

    try:
        try:
            if not create_catalog_price_range_doctype(frappe):
                sys.exit(1)
            create_default_price_ranges(frappe)
            create_webshop_simple_checkout_settings_doctype(frappe)
            create_customer_group_brand_mapping_doctype(frappe)

            print("=" * 60)
            print("[COMPLETE] DocType setup finished!")
            print("=" * 60)
        finally:
            frappe.destroy()

    except Exception as e:
        print(f"[ERROR] Failed to setup DocTypes: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
