from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from catalog_extensions import install_support
from catalog_extensions import install


class InstallSupportTestCase(TestCase):
    def test_missing_required_apps_are_reported(self):
        with patch("catalog_extensions.install_support.frappe.get_installed_apps", return_value=["erpnext", "webshop"]):
            missing = install_support.get_missing_required_apps()

        self.assertEqual(missing, ["payments"])

    def test_assert_install_prerequisites_fails_when_required_apps_are_missing(self):
        fake_db = SimpleNamespace(exists=lambda *args, **kwargs: True)

        with (
            patch("catalog_extensions.install_support.frappe.get_installed_apps", return_value=["erpnext", "payments"]),
            patch("catalog_extensions.install_support.frappe.db", fake_db),
        ):
            with self.assertRaises(frappe.ValidationError) as exc:
                install_support.assert_install_prerequisites()

        self.assertIn("webshop", str(exc.exception))

    def test_optional_dependency_warning_is_non_blocking(self):
        fake_db = SimpleNamespace(
            exists=lambda doctype, name=None, *args, **kwargs: True,
            sql=lambda *args, **kwargs: [(1,)],
        )

        def fake_exists(doctype, name=None, *args, **kwargs):
            if doctype == "Print Format" and name == install_support.ORDER_RECEIPT_PRINT_FORMAT:
                return True
            if doctype == "Custom Field":
                return True
            return True

        fake_db.exists = fake_exists

        with (
            patch(
                "catalog_extensions.install_support.frappe.get_installed_apps",
                return_value=["erpnext", "payments", "webshop"],
            ),
            patch("catalog_extensions.install_support.frappe.db", fake_db),
        ):
            warnings = install_support.assert_setup_complete()

        self.assertTrue(any("erpnext_shipping_extended" in warning for warning in warnings))

    def test_run_setup_creates_customer_group_brand_mapping_doctype(self):
        setup_doctypes = SimpleNamespace(
            create_catalog_price_range_doctype=lambda _frappe: None,
            create_default_price_ranges=lambda _frappe: None,
            create_webshop_simple_checkout_settings_doctype=lambda _frappe: None,
            create_customer_group_brand_mapping_doctype=lambda _frappe: None,
        )
        setup_custom_fields = SimpleNamespace(
            setup_item_fields=lambda _frappe: None,
            setup_website_item_fields=lambda _frappe: None,
            sync_item_badge_doctype=lambda _frappe: None,
            setup_performance_indexes=lambda _frappe: None,
        )

        with (
            patch("catalog_extensions.install.assert_install_prerequisites"),
            patch("catalog_extensions.install._import_setup_modules", return_value=(setup_doctypes, setup_custom_fields)),
            patch("catalog_extensions.install.ensure_order_receipt_print_format"),
            patch("catalog_extensions.install.assert_setup_complete", return_value=[]),
            patch.object(setup_doctypes, "create_customer_group_brand_mapping_doctype") as create_mapping,
        ):
            install._run_setup()

        create_mapping.assert_called_once_with(frappe)
