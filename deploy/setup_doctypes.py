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
        if not create_catalog_price_range_doctype(frappe):
            sys.exit(1)
        create_default_price_ranges(frappe)

        print("=" * 60)
        print("[COMPLETE] DocType setup finished!")
        print("=" * 60)
    finally:
        frappe.destroy()


if __name__ == "__main__":
    main()
