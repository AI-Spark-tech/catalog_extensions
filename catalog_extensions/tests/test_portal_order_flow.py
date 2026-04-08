from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from catalog_extensions import api
from catalog_extensions import order_billing
from catalog_extensions import order_fulfillment
from catalog_extensions import simple_checkout
from catalog_extensions.overrides.payment_request import PaymentRequest


class DummyOrder:
    def __init__(self, **values):
        self.doctype = values.get("doctype", "Sales Order")
        self.name = values.get("name", "SO-TEST-0001")
        self.docstatus = values.get("docstatus", 1)
        self.flags = SimpleNamespace(ignore_permissions=False)
        self._values = {
            "status": values.get("status", "To Deliver"),
            "per_delivered": values.get("per_delivered", 0),
            "per_billed": values.get("per_billed", 0),
            "per_picked": values.get("per_picked", 0),
            "advance_paid": values.get("advance_paid", 0),
            "base_grand_total": values.get("base_grand_total", 100),
            "base_rounded_total": values.get("base_rounded_total", 0),
            "order_type": values.get("order_type", "Shopping Cart"),
        }
        self.comments = []
        self.cancelled = False
        self.cancel_side_effect = values.get("cancel_side_effect")

    def get(self, key, default=None):
        return self._values.get(key, default)

    def add_comment(self, comment_type, content):
        self.comments.append((comment_type, content))

    def db_set(self, values):
        for key, value in values.items():
            self._values[key] = value

    def update_status(self, status):
        self._values["status"] = status

    def cancel(self):
        if self.cancel_side_effect:
            raise self.cancel_side_effect
        self.cancelled = True

    def reload(self):
        return self


class DummyShipment:
    def __init__(self, **values):
        self.doctype = values.get("doctype", "Shipment")
        self.name = values.get("name", "SHIP-TEST-0001")
        self.docstatus = values.get("docstatus", 1)
        self.flags = SimpleNamespace(ignore_permissions=False)
        self.comments = []
        self.shipment_delivery_note = values.get("shipment_delivery_note", [])
        self.shipment_parcel = values.get("shipment_parcel", [])
        self._values = {
            "service_provider": values.get("service_provider"),
            "shiprocket_shipment_id": values.get("shiprocket_shipment_id"),
            "status": values.get("status", "Booked"),
            "tracking_status": values.get("tracking_status"),
            "tracking_status_info": values.get("tracking_status_info"),
            "tracking_url": values.get("tracking_url"),
            "awb_number": values.get("awb_number"),
            "normalized_tracking_status": values.get("normalized_tracking_status"),
            "pickup_from_type": values.get("pickup_from_type", "Company"),
            "delivery_to_type": values.get("delivery_to_type", "Customer"),
            "pickup_address_name": values.get("pickup_address_name", "ADDR-PICKUP"),
            "delivery_address_name": values.get("delivery_address_name", "ADDR-DELIVERY"),
            "description_of_content": values.get("description_of_content", "Test shipment"),
            "pickup_date": values.get("pickup_date", "2026-04-06"),
            "value_of_goods": values.get("value_of_goods", 100),
            "pickup_contact_name": values.get("pickup_contact_name"),
            "delivery_contact_name": values.get("delivery_contact_name"),
        }

    def get(self, key, default=None):
        if key == "shipment_delivery_note":
            return self.shipment_delivery_note
        if key == "shipment_parcel":
            return self.shipment_parcel
        return self._values.get(key, default)

    def add_comment(self, comment_type, content):
        self.comments.append((comment_type, content))

    def db_set(self, values):
        for key, value in values.items():
            self._values[key] = value

    def reload(self):
        return self

    def append(self, key, value):
        if key == "shipment_parcel":
            self.shipment_parcel.append(value)
            return
        if key == "shipment_delivery_note":
            self.shipment_delivery_note.append(value)
            return
        raise KeyError(key)


class DummyQuotation:
    def __init__(self, **values):
        self.doctype = "Quotation"
        self.name = values.get("name", "QTN-CART-0001")
        self.docstatus = values.get("docstatus", 0)
        self.flags = SimpleNamespace(ignore_permissions=False)
        self.quotation_to = values.get("quotation_to", "Customer")
        self.party_name = values.get("party_name", "CUST-0001")
        self.customer_name = values.get("customer_name", "Test Customer")
        self.contact_person = values.get("contact_person", "CONT-0001")
        self.contact_email = values.get("contact_email", "customer@example.com")
        self.shipping_address_name = values.get("shipping_address_name", "ADDR-SHIP")
        self.customer_address = values.get("customer_address", "ADDR-BILL")
        self.payment_terms_template = values.get("payment_terms_template")
        self.selling_price_list = values.get("selling_price_list", "Standard Selling")
        self.company = values.get("company", "Test Company")
        self.currency = values.get("currency", "INR")
        self.party_account_currency = values.get("party_account_currency", "INR")
        self.items = values.get("items", [SimpleNamespace(item_code="ITEM-001", qty=1)])
        self._values = {
            "rounded_total": values.get("rounded_total", 100),
            "grand_total": values.get("grand_total", 100),
            "order_type": values.get("order_type", "Shopping Cart"),
        }
        self.saved = False
        self.inserted = False
        self.submitted = False

    def get(self, key, default=None):
        if key == "items":
            return self.items
        return self._values.get(key, getattr(self, key, default))

    def run_method(self, method):
        return None

    def append(self, key, value):
        if key != "items":
            raise KeyError(key)
        self.items.append(SimpleNamespace(**value))

    def insert(self, ignore_permissions=False):
        self.inserted = True
        return self

    def save(self):
        self.saved = True
        return self

    def submit(self):
        self.submitted = True
        self.docstatus = 1
        return self


class PortalOrderFlowTestCase(TestCase):
    @staticmethod
    def fake_exists(expected_doctypes=None, comments_exist=False):
        expected_doctypes = set(expected_doctypes or [])

        def _exists(doctype, filters=None, *args, **kwargs):
            if doctype == "Comment":
                return comments_exist
            return doctype in expected_doctypes

        return _exists

    def make_context(self, order_doc=None, **overrides):
        context = {
            "order_doc": order_doc or DummyOrder(),
            "flow_visibility": {
                "payment_active": True,
                "shipping_active": True,
                "return_active": True,
                "show_shipment_traceability": True,
                "show_return_traceability": True,
            },
            "delivery_notes": [],
            "shipments": [],
            "invoices": [],
            "payment_requests": [],
            "return_delivery_notes": [],
            "draft_return_delivery_notes": [],
            "return_shipments": [],
            "return_records": [],
            "return_invoices": [],
            "draft_return_invoices": [],
            "eligible_return_items": [],
        }
        context.update(overrides)
        return context

    def test_paid_order_can_be_cancelled_before_fulfillment_starts(self):
        order_doc = DummyOrder(per_billed=100, per_picked=0, per_delivered=0)
        context = self.make_context(order_doc=order_doc, invoices=[{"name": "SINV-0001"}])

        self.assertIsNone(api._get_cancel_unavailable_reason(context))
        actions = api._get_order_actions(context, {"payment_received": True, "eligible_return_items_count": 0})
        self.assertTrue(actions["can_cancel"])

    def test_picked_order_cannot_be_cancelled(self):
        order_doc = DummyOrder(per_billed=100, per_picked=25)
        context = self.make_context(order_doc=order_doc)

        self.assertEqual(
            api._get_cancel_unavailable_reason(context),
            "This order is already in fulfillment and can no longer be cancelled online.",
        )

    def test_refund_requires_return_receipt(self):
        context = self.make_context(return_invoices=[{"name": "SINV-RET-0001"}])

        blocked_reason = api._get_refund_unavailable_reason(
            context,
            {"payment_received": True, "has_return_received": False, "refund_settled": False},
        )
        self.assertEqual(
            blocked_reason,
            "Refund can be requested only after the returned items are received.",
        )

        allowed_reason = api._get_refund_unavailable_reason(
            context,
            {"payment_received": True, "has_return_received": True, "refund_settled": False},
        )
        self.assertIsNone(allowed_reason)

    def test_cancel_portal_order_adds_refund_marker_for_paid_order(self):
        order_doc = DummyOrder()
        context = self.make_context(order_doc=order_doc)

        with (
            patch("catalog_extensions.api._get_portal_order_doc", return_value=order_doc),
            patch("catalog_extensions.api._build_portal_order_tracking_context", return_value=context),
            patch("catalog_extensions.api._build_status_signals", return_value={"payment_received": True}),
        ):
            result = api.cancel_portal_order(order_doc.name, order_doc.doctype, reason="Changed mind")

        self.assertTrue(order_doc.cancelled)
        self.assertTrue(result["ok"])
        self.assertIn("Payment Request", order_doc.ignore_linked_doctypes)
        self.assertEqual(len(order_doc.comments), 2)
        self.assertIn("Customer requested cancellation: Changed mind", order_doc.comments[0][1])
        self.assertIn(api.PORTAL_REFUND_REQUEST_MARKER, order_doc.comments[1][1])

    def test_cancel_portal_order_skips_refund_marker_for_unpaid_order(self):
        order_doc = DummyOrder()
        context = self.make_context(order_doc=order_doc)

        with (
            patch("catalog_extensions.api._get_portal_order_doc", return_value=order_doc),
            patch("catalog_extensions.api._build_portal_order_tracking_context", return_value=context),
            patch("catalog_extensions.api._build_status_signals", return_value={"payment_received": False}),
        ):
            api.cancel_portal_order(order_doc.name, order_doc.doctype, reason="Changed mind")

        self.assertTrue(order_doc.cancelled)
        self.assertEqual(len(order_doc.comments), 1)
        self.assertNotIn(api.PORTAL_REFUND_REQUEST_MARKER, order_doc.comments[0][1])

    def test_cancel_portal_order_returns_safe_message_when_payment_links_block_cancellation(self):
        order_doc = DummyOrder(cancel_side_effect=frappe.LinkExistsError)
        context = self.make_context(order_doc=order_doc)

        with (
            patch("catalog_extensions.api._get_portal_order_doc", return_value=order_doc),
            patch("catalog_extensions.api._build_portal_order_tracking_context", return_value=context),
            patch("catalog_extensions.api._build_status_signals", return_value={"payment_received": True}),
        ):
            with self.assertRaises(frappe.ValidationError) as exc:
                api.cancel_portal_order(order_doc.name, order_doc.doctype)

        self.assertIn("linked billing or payment records still need staff review", str(exc.exception))
        self.assertEqual(order_doc.comments, [])

    def test_status_signals_treat_full_advance_as_payment_received(self):
        order_doc = DummyOrder(advance_paid=100, base_grand_total=100, per_billed=0)
        context = self.make_context(order_doc=order_doc)

        signals = api._build_status_signals(context)

        self.assertTrue(signals["payment_received"])
        self.assertTrue(signals["sales_order_fully_paid_in_advance"])

    def test_webshop_order_with_delivery_note_is_not_marked_delivered_without_delivered_shipment(self):
        order_doc = DummyOrder(
            name="SO-TEST-TRACK-0001",
            advance_paid=100,
            base_grand_total=100,
            per_delivered=100,
            status="To Deliver",
        )
        context = self.make_context(
            order_doc=order_doc,
            delivery_notes=[{"name": "DN-TEST-TRACK-0001", "posting_date": "2026-04-06"}],
            shipments=[{"name": "SHIP-TEST-TRACK-0001", "status": "Booked", "tracking_status": None}],
        )

        with patch("catalog_extensions.api.frappe.db.get_value", return_value=None):
            signals = api._build_status_signals(context)
            normalized = api._resolve_normalized_status(context)
            delivered_date = api._get_delivered_date(context)

        self.assertFalse(signals["delivered"])
        self.assertFalse(signals["completed"])
        self.assertIsNone(delivered_date)
        self.assertEqual(normalized["normalized_status_code"], "shipped")

    def test_webshop_order_becomes_delivered_only_from_shipment_delivery_signal(self):
        order_doc = DummyOrder(
            name="SO-TEST-TRACK-0002",
            advance_paid=100,
            base_grand_total=100,
            per_delivered=100,
            status="Completed",
        )
        context = self.make_context(
            order_doc=order_doc,
            delivery_notes=[{"name": "DN-TEST-TRACK-0002", "posting_date": "2026-04-06"}],
            shipments=[
                {
                    "name": "SHIP-TEST-TRACK-0002",
                    "status": "Completed",
                    "tracking_status": "Delivered",
                    "modified": "2026-04-07 10:00:00",
                }
            ],
        )

        with patch("catalog_extensions.api.frappe.db.get_value", return_value=None):
            signals = api._build_status_signals(context)
            normalized = api._resolve_normalized_status(context)
            delivered_date = api._get_delivered_date(context)

        self.assertTrue(signals["delivered"])
        self.assertTrue(signals["completed"])
        self.assertEqual(delivered_date, "2026-04-07 10:00:00")
        self.assertEqual(normalized["normalized_status_code"], "completed")

    def test_webshop_return_window_waits_for_actual_delivery_confirmation(self):
        order_doc = DummyOrder(
            name="SO-TEST-TRACK-0003",
            advance_paid=100,
            base_grand_total=100,
            per_delivered=100,
            status="To Deliver",
        )
        context = self.make_context(
            order_doc=order_doc,
            delivery_notes=[{"name": "DN-TEST-TRACK-0003", "posting_date": "2026-04-06"}],
            shipments=[{"name": "SHIP-TEST-TRACK-0003", "status": "Booked"}],
        )

        with patch("catalog_extensions.api.frappe.db.get_value", return_value=None):
            signals = api._build_status_signals(context)

        self.assertFalse(signals["return_window_open"])
        self.assertIsNone(signals["return_window_end_date"])

    def test_order_billing_creates_invoice_only_for_fully_paid_fully_delivered_webshop_order(self):
        order_doc = DummyOrder(per_delivered=100, advance_paid=100, base_grand_total=100, status="Completed")
        invoice_doc = MagicMock()

        with (
            patch("catalog_extensions.order_billing._has_existing_sales_invoice", return_value=False),
            patch("catalog_extensions.order_billing._has_delivery_completion_marker", return_value=True),
            patch(
                "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
                return_value=invoice_doc,
            ) as make_invoice,
        ):
            order_billing.create_sales_invoice_for_fully_paid_webshop_order(order_doc)

        make_invoice.assert_called_once_with(order_doc.name, ignore_permissions=True)
        invoice_doc.insert.assert_called_once_with(ignore_permissions=True)
        invoice_doc.submit.assert_called_once_with()

    def test_order_billing_skips_invoice_before_full_delivery(self):
        order_doc = DummyOrder(per_delivered=50, advance_paid=100, base_grand_total=100)

        with (
            patch("catalog_extensions.order_billing._has_existing_sales_invoice", return_value=False),
            patch("catalog_extensions.order_billing._has_delivery_completion_marker", return_value=True),
            patch("erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice") as make_invoice,
        ):
            order_billing.create_sales_invoice_for_fully_paid_webshop_order(order_doc)

        make_invoice.assert_not_called()

    def test_order_billing_skips_invoice_until_delivery_completion_marker_exists(self):
        order_doc = DummyOrder(per_delivered=100, advance_paid=100, base_grand_total=100, status="To Deliver")

        with (
            patch("catalog_extensions.order_billing._has_existing_sales_invoice", return_value=False),
            patch("catalog_extensions.order_billing._has_delivery_completion_marker", return_value=False),
            patch("erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice") as make_invoice,
        ):
            order_billing.create_sales_invoice_for_fully_paid_webshop_order(order_doc)

        make_invoice.assert_not_called()

    def test_payment_request_set_as_paid_for_webshop_sales_order_skips_invoice_creation(self):
        pr = object.__new__(PaymentRequest)
        pr.payment_channel = "Card"
        pr.reference_doctype = "Sales Order"
        pr.reference_name = "SO-TEST-0001"
        pr.create_payment_entry = MagicMock(return_value="PE-0001")
        pr.reload = MagicMock()
        pr.db_set = MagicMock()

        sales_order = DummyOrder(name="SO-TEST-0001", order_type="Shopping Cart")

        with patch("catalog_extensions.overrides.payment_request.frappe.get_doc", return_value=sales_order):
            payment_entry = PaymentRequest.set_as_paid(pr)

        self.assertEqual(payment_entry, "PE-0001")
        pr.create_payment_entry.assert_called_once_with()
        pr.reload.assert_called_once_with()
        pr.db_set.assert_called_once_with({"status": "Paid", "outstanding_amount": 0})

    def test_payment_request_set_as_paid_reuses_existing_payment_entry(self):
        pr = object.__new__(PaymentRequest)
        pr.payment_channel = "Card"
        pr.reference_doctype = "Sales Order"
        pr.reference_name = "SO-TEST-0001"
        pr.create_payment_entry = MagicMock()
        pr.reload = MagicMock()
        pr.db_set = MagicMock()

        sales_order = DummyOrder(name="SO-TEST-0001", order_type="Shopping Cart")

        with (
            patch("catalog_extensions.overrides.payment_request.frappe.get_doc", return_value=sales_order),
            patch.object(PaymentRequest, "_get_existing_order_payment_entry", return_value="PE-EXISTING"),
        ):
            payment_entry = PaymentRequest.set_as_paid(pr)

        self.assertEqual(payment_entry, "PE-EXISTING")
        pr.create_payment_entry.assert_not_called()
        pr.db_set.assert_called_once_with({"status": "Paid", "outstanding_amount": 0})

    def test_simple_checkout_place_order_returns_payment_redirect_payload(self):
        quotation = DummyQuotation()
        payment_request = MagicMock()
        payment_request.name = "PR-0001"
        payment_request.get_payment_url.return_value = "/payments/checkout/PR-0001"

        with (
            patch("catalog_extensions.simple_checkout._get_checkout_quotation", return_value=quotation),
            patch("catalog_extensions.simple_checkout._build_payment_request_for_quotation", return_value=payment_request),
            patch("catalog_extensions.simple_checkout._get_existing_sales_order_for_quotation", return_value=None),
        ):
            result = simple_checkout.place_order()

        self.assertEqual(result["checkout_state"], "payment_pending")
        self.assertEqual(result["payment_request"], payment_request.name)
        self.assertEqual(result["redirect_to"], "/payments/checkout/PR-0001")
        self.assertTrue(quotation.saved)

    def test_payment_request_set_as_paid_creates_sales_order_for_quotation_reference(self):
        pr = object.__new__(PaymentRequest)
        pr.payment_channel = "Card"
        pr.reference_doctype = "Quotation"
        pr.reference_name = "QTN-CART-0001"
        pr.create_payment_entry = MagicMock(return_value="PE-0001")
        pr.reload = MagicMock()
        pr.db_set = MagicMock()

        sales_order = DummyOrder(name="SO-TEST-0001", order_type="Shopping Cart")

        def ensure_reference():
            pr.reference_doctype = "Sales Order"
            pr.reference_name = sales_order.name
            return sales_order

        with patch.object(PaymentRequest, "_ensure_sales_order_reference", side_effect=ensure_reference):
            payment_entry = PaymentRequest.set_as_paid(pr)

        self.assertEqual(payment_entry, "PE-0001")
        pr.create_payment_entry.assert_called_once_with()
        pr.db_set.assert_called_once_with({"status": "Paid", "outstanding_amount": 0})

    def test_payment_authorized_reuses_existing_sales_order_for_quotation(self):
        pr = object.__new__(PaymentRequest)
        pr.payment_channel = "Card"
        pr.reference_doctype = "Quotation"
        pr.reference_name = "QTN-CART-0001"
        pr.create_payment_entry = MagicMock(return_value="PE-0001")
        pr.reload = MagicMock()
        pr.db_set = MagicMock()

        cart_settings = SimpleNamespace(enabled=1, payment_success_url=None)
        sales_order = DummyOrder(name="SO-TEST-0001", order_type="Shopping Cart")

        def ensure_reference():
            pr.reference_doctype = "Sales Order"
            pr.reference_name = sales_order.name
            return sales_order

        with (
            patch("catalog_extensions.overrides.payment_request.frappe.get_doc", side_effect=[cart_settings, sales_order]),
            patch.object(PaymentRequest, "_ensure_sales_order_reference", side_effect=ensure_reference),
            patch.object(PaymentRequest, "_get_existing_order_payment_entry", return_value="PE-EXISTING"),
            patch("catalog_extensions.overrides.payment_request.frappe.local", SimpleNamespace(session=SimpleNamespace(user="test@example.com"))),
            patch("catalog_extensions.overrides.payment_request.frappe.session", {}),
            patch("catalog_extensions.order_fulfillment.automate_paid_webshop_order_fulfillment") as automate,
        ):
            redirect_to = PaymentRequest.on_payment_authorized(pr, "Completed")

        self.assertTrue(redirect_to.endswith("/order-success?order_id=SO-TEST-0001"))
        self.assertEqual(pr.reference_doctype, "Sales Order")
        automate.assert_called_once_with(sales_order)

    def test_fulfillment_automation_creates_delivery_note_and_shipment_and_queues_pickup(self):
        order_doc = DummyOrder(name="SO-TEST-0009")
        delivery_note = MagicMock()
        delivery_note.name = "DN-TEST-0001"
        shipment_doc = DummyShipment(
            name="SHIP-TEST-0001",
            shipment_delivery_note=[SimpleNamespace(delivery_note=delivery_note.name)],
            shipment_parcel=[{"weight": 0.5, "count": 1}],
        )

        with (
            patch("catalog_extensions.order_fulfillment._get_delivery_note_doc", return_value=(delivery_note, True)),
            patch("catalog_extensions.order_fulfillment._get_shipment_doc", return_value=(shipment_doc, True)),
            patch(
                "catalog_extensions.order_fulfillment._get_best_service_info",
                return_value={"service_provider": "Shiprocket", "total_price": 99},
            ),
            patch("catalog_extensions.order_fulfillment._queue_dispatch", return_value={"queued": True}),
            patch("catalog_extensions.order_fulfillment.frappe.enqueue") as enqueue_job,
        ):
            result = order_fulfillment.automate_paid_webshop_order_fulfillment(order_doc)

        self.assertEqual(result["delivery_note"], delivery_note.name)
        self.assertEqual(result["shipment"], shipment_doc.name)
        self.assertTrue(result["dispatch_queued"])
        self.assertTrue(result["pickup_queued"])
        enqueue_job.assert_called_once()

    def test_fulfillment_automation_adds_manual_followup_when_no_shipping_service_available(self):
        order_doc = DummyOrder(name="SO-TEST-0010")
        delivery_note = MagicMock()
        delivery_note.name = "DN-TEST-0002"
        shipment_doc = DummyShipment(name="SHIP-TEST-0002")

        with (
            patch("catalog_extensions.order_fulfillment._get_delivery_note_doc", return_value=(delivery_note, True)),
            patch("catalog_extensions.order_fulfillment._get_shipment_doc", return_value=(shipment_doc, True)),
            patch("catalog_extensions.order_fulfillment._get_best_service_info", return_value=None),
            patch("catalog_extensions.order_fulfillment.frappe.db.exists", return_value=False),
        ):
            result = order_fulfillment.automate_paid_webshop_order_fulfillment(order_doc)

        self.assertEqual(result["shipment"], shipment_doc.name)
        self.assertFalse(result["dispatch_queued"])
        self.assertEqual(len(order_doc.comments), 1)
        self.assertIn(order_fulfillment.FULFILLMENT_MARKER, order_doc.comments[0][1])

    def test_shipment_defaults_fill_mandatory_fields_for_blank_parcel_rows(self):
        order_doc = DummyOrder(name="SO-TEST-0011")
        order_doc.items = [SimpleNamespace(item_name="Demo Item", item_code="ITEM-001")]
        delivery_note = DummyOrder(doctype="Delivery Note", name="DN-TEST-0002")
        delivery_note.items = [SimpleNamespace(item_name="Demo Item", item_code="ITEM-001")]
        shipment_doc = DummyShipment(
            name="SHIP-TEST-MANDATORY-0001",
            pickup_date=None,
            description_of_content=None,
            shipment_parcel=[{"weight": None, "count": None, "length": None, "width": None, "height": None}],
        )

        with patch("catalog_extensions.order_fulfillment.nowdate", return_value="2026-04-07"):
            order_fulfillment._ensure_shipment_defaults(shipment_doc, order_doc, delivery_note)

        parcel = shipment_doc.shipment_parcel[0]
        self.assertEqual(shipment_doc.get("pickup_date"), "2026-04-07")
        self.assertEqual(shipment_doc.get("description_of_content"), "Demo Item")
        self.assertEqual(parcel["weight"], 0.5)
        self.assertEqual(parcel["count"], 1)
        self.assertEqual(parcel["length"], 10)
        self.assertEqual(parcel["width"], 10)
        self.assertEqual(parcel["height"], 10)

    def test_shipment_description_uses_first_item_name(self):
        order_doc = DummyOrder(name="SO-TEST-0011")
        order_doc.items = [
            SimpleNamespace(item_name="Primary Item", item_code="ITEM-001"),
            SimpleNamespace(item_name="Secondary Item", item_code="ITEM-002"),
        ]

        self.assertEqual(
            order_fulfillment._get_shipment_content_description(order_doc),
            "Primary Item",
        )

    def test_shipment_validate_hook_fills_missing_parcel_for_sales_shipment(self):
        order_doc = DummyOrder(name="SO-TEST-0011", order_type="Sales")
        delivery_note = DummyOrder(doctype="Delivery Note", name="DN-TEST-0002")
        delivery_note.items = [SimpleNamespace(item_name="Demo Item", item_code="ITEM-001")]
        shipment_doc = DummyShipment(
            name="SHIP-TEST-MANDATORY-0002",
            pickup_date=None,
            description_of_content=None,
            shipment_delivery_note=[SimpleNamespace(delivery_note=delivery_note.name)],
            shipment_parcel=[],
        )

        with (
            patch(
                "catalog_extensions.order_fulfillment.frappe.db.exists",
                side_effect=self.fake_exists({"Delivery Note", "Sales Order"}),
            ),
            patch(
                "catalog_extensions.order_fulfillment.frappe.get_doc",
                side_effect=[delivery_note, order_doc],
            ),
            patch(
                "catalog_extensions.order_fulfillment._get_sales_order_name_for_delivery_note",
                return_value=order_doc.name,
            ),
            patch("catalog_extensions.order_fulfillment.nowdate", return_value="2026-04-07"),
        ):
            order_fulfillment.apply_webshop_shipment_defaults(shipment_doc)

        self.assertEqual(shipment_doc.get("pickup_date"), "2026-04-07")
        self.assertEqual(shipment_doc.get("description_of_content"), "Demo Item")
        self.assertEqual(len(shipment_doc.shipment_parcel), 1)
        self.assertEqual(shipment_doc.shipment_parcel[0]["weight"], 0.5)
        self.assertEqual(shipment_doc.shipment_parcel[0]["count"], 1)

    def test_delivery_note_submit_hook_creates_shipment_for_any_sales_order(self):
        order_doc = DummyOrder(name="SO-TEST-0012", advance_paid=0, base_grand_total=100, order_type="Sales")
        delivery_note = DummyOrder(doctype="Delivery Note", name="DN-TEST-0003")

        with (
            patch(
                "catalog_extensions.order_fulfillment._get_sales_order_name_for_delivery_note",
                return_value=order_doc.name,
            ),
            patch("catalog_extensions.order_fulfillment.frappe.db.exists", return_value=True),
            patch("catalog_extensions.order_fulfillment.frappe.get_doc", return_value=order_doc),
            patch(
                "catalog_extensions.order_fulfillment.automate_shipment_for_delivery_note",
                return_value={"shipment": "SHIP-TEST-0003"},
            ) as automate_shipment,
            patch("catalog_extensions.order_fulfillment.frappe.enqueue") as enqueue_job,
        ):
            order_fulfillment.sync_webshop_shipment_after_delivery_note_submit(delivery_note)

        automate_shipment.assert_called_once_with(order_doc, delivery_note)
        enqueue_job.assert_called_once()
        self.assertEqual(
            enqueue_job.call_args.kwargs["delivery_note_name"],
            delivery_note.name,
        )
        self.assertEqual(
            enqueue_job.call_args.kwargs["sales_order_name"],
            order_doc.name,
        )

    def test_delivery_note_submit_hook_skips_when_sales_order_is_missing(self):
        order_doc = DummyOrder(name="SO-TEST-0013", advance_paid=0, base_grand_total=100, order_type="Sales")
        delivery_note = DummyOrder(doctype="Delivery Note", name="DN-TEST-0004")

        with (
            patch(
                "catalog_extensions.order_fulfillment._get_sales_order_name_for_delivery_note",
                return_value=None,
            ),
            patch("catalog_extensions.order_fulfillment.frappe.db.exists", return_value=False),
            patch("catalog_extensions.order_fulfillment.frappe.get_doc", return_value=order_doc),
            patch("catalog_extensions.order_fulfillment.automate_shipment_for_delivery_note") as automate_shipment,
        ):
            order_fulfillment.sync_webshop_shipment_after_delivery_note_submit(delivery_note)

        automate_shipment.assert_not_called()

    def test_delivery_note_submit_hook_queues_retry_when_immediate_shipment_creation_fails(self):
        order_doc = DummyOrder(name="SO-TEST-0014", advance_paid=100, base_grand_total=100)
        delivery_note = DummyOrder(doctype="Delivery Note", name="DN-TEST-0005")

        with (
            patch(
                "catalog_extensions.order_fulfillment._get_sales_order_name_for_delivery_note",
                return_value=order_doc.name,
            ),
            patch("catalog_extensions.order_fulfillment.frappe.db.exists", return_value=True),
            patch("catalog_extensions.order_fulfillment.frappe.get_doc", return_value=order_doc),
            patch(
                "catalog_extensions.order_fulfillment.automate_shipment_for_delivery_note",
                side_effect=RuntimeError("shipment failed"),
            ),
            patch("catalog_extensions.order_fulfillment.frappe.log_error") as log_error,
            patch("catalog_extensions.order_fulfillment.frappe.enqueue") as enqueue_job,
        ):
            order_fulfillment.sync_webshop_shipment_after_delivery_note_submit(delivery_note)

        log_error.assert_called_once()
        enqueue_job.assert_called_once()
        self.assertEqual(len(order_doc.comments), 1)
        self.assertIn(order_fulfillment.DELIVERY_REPAIR_MARKER, order_doc.comments[0][1])

    def test_ensure_webshop_shipment_for_delivery_note_runs_shared_shipment_automation(self):
        order_doc = DummyOrder(name="SO-TEST-0016", advance_paid=100, base_grand_total=100)
        delivery_note = DummyOrder(doctype="Delivery Note", name="DN-TEST-0007")

        with (
            patch(
                "catalog_extensions.order_fulfillment.frappe.db.exists",
                side_effect=self.fake_exists({"Delivery Note", "Sales Order"}, comments_exist=False),
            ),
            patch(
                "catalog_extensions.order_fulfillment.frappe.get_doc",
                side_effect=[delivery_note, order_doc],
            ),
            patch("catalog_extensions.order_fulfillment.automate_shipment_for_delivery_note", return_value={"shipment": "SHIP-OK"}) as automate_shipment,
        ):
            result = order_fulfillment.ensure_webshop_shipment_for_delivery_note(delivery_note.name, order_doc.name)

        self.assertEqual(result["shipment"], "SHIP-OK")
        automate_shipment.assert_called_once_with(order_doc, delivery_note)

    def test_attempt_pickup_after_dispatch_adds_followup_when_remote_dispatch_not_ready(self):
        shipment_doc = DummyShipment(name="SHIP-TEST-0003", service_provider="Shiprocket", shiprocket_shipment_id=None)
        order_doc = DummyOrder(name="SO-TEST-0011")

        with (
            patch("catalog_extensions.order_fulfillment.frappe.get_doc", side_effect=[shipment_doc, order_doc]),
            patch("catalog_extensions.order_fulfillment.frappe.db.exists", return_value=False),
        ):
            order_fulfillment.attempt_pickup_after_dispatch(shipment_doc.name, order_doc.name)

        self.assertEqual(len(order_doc.comments), 1)
        self.assertIn(order_fulfillment.PICKUP_MARKER, order_doc.comments[0][1])

    def test_finalize_delivered_webshop_order_updates_delivery_note_order_and_invoice(self):
        shipment_doc = DummyShipment(
            name="SHIP-TEST-0004",
            status="Completed",
            tracking_status="Delivered",
            normalized_tracking_status="DELIVERED",
            awb_number="AWB-1",
            tracking_url="https://track.example/1",
            tracking_status_info="Delivered",
            shipment_delivery_note=[SimpleNamespace(delivery_note="DN-TEST-0005")],
        )
        delivery_note = DummyOrder(doctype="Delivery Note", name="DN-TEST-0005", status="To Deliver")
        sales_order = DummyOrder(name="SO-TEST-0014", advance_paid=100, base_grand_total=100, per_delivered=100)

        with (
            patch(
                "catalog_extensions.order_fulfillment.frappe.db.exists",
                side_effect=self.fake_exists({"Delivery Note", "Sales Order"}, comments_exist=False),
            ),
            patch(
                "catalog_extensions.order_fulfillment.frappe.get_doc",
                side_effect=[delivery_note, sales_order],
            ),
            patch(
                "catalog_extensions.order_fulfillment._get_sales_order_names_for_delivery_notes",
                return_value=[sales_order.name],
            ),
            patch("catalog_extensions.order_fulfillment._all_shipments_delivered_for_sales_order", return_value=True),
            patch(
                "catalog_extensions.order_fulfillment.order_billing.create_sales_invoice_for_fully_paid_webshop_order"
            ) as create_invoice,
        ):
            finalized = order_fulfillment.finalize_delivered_webshop_order_from_shipment(shipment_doc)

        self.assertTrue(finalized)
        self.assertEqual(delivery_note.get("status"), "Completed")
        self.assertEqual(sales_order.get("status"), "Completed")
        self.assertEqual(delivery_note.get("tracking_status"), "Delivered")
        create_invoice.assert_called_once_with(sales_order)

    def test_finalize_delivered_webshop_order_waits_until_all_shipments_are_delivered(self):
        shipment_doc = DummyShipment(
            name="SHIP-TEST-0005",
            status="Completed",
            tracking_status="Delivered",
            normalized_tracking_status="DELIVERED",
            shipment_delivery_note=[SimpleNamespace(delivery_note="DN-TEST-0006")],
        )
        delivery_note = DummyOrder(doctype="Delivery Note", name="DN-TEST-0006", status="To Deliver")
        sales_order = DummyOrder(name="SO-TEST-0015", advance_paid=100, base_grand_total=100, per_delivered=100)

        with (
            patch(
                "catalog_extensions.order_fulfillment.frappe.db.exists",
                side_effect=self.fake_exists({"Delivery Note", "Sales Order"}, comments_exist=False),
            ),
            patch(
                "catalog_extensions.order_fulfillment.frappe.get_doc",
                side_effect=[delivery_note, sales_order],
            ),
            patch(
                "catalog_extensions.order_fulfillment._get_sales_order_names_for_delivery_notes",
                return_value=[sales_order.name],
            ),
            patch("catalog_extensions.order_fulfillment._all_shipments_delivered_for_sales_order", return_value=False),
            patch(
                "catalog_extensions.order_fulfillment.order_billing.create_sales_invoice_for_fully_paid_webshop_order"
            ) as create_invoice,
        ):
            finalized = order_fulfillment.finalize_delivered_webshop_order_from_shipment(shipment_doc)

        self.assertFalse(finalized)
        self.assertEqual(delivery_note.get("status"), "Completed")
        self.assertNotEqual(sales_order.get("status"), "Completed")
        create_invoice.assert_not_called()

    def test_start_portal_refund_processing_after_return_receipt_is_idempotent(self):
        order_doc = DummyOrder()
        return_doc = DummyOrder(doctype="Sales Invoice", name="SINV-RET-0001")
        context = self.make_context(order_doc=order_doc, return_invoices=[{"name": return_doc.name}])
        signals = {
            "payment_received": True,
            "has_return_received": True,
            "refund_settled": False,
        }

        with (
            patch("catalog_extensions.api._has_portal_comment", side_effect=[False, True]),
            patch("catalog_extensions.api.run_as", return_value=nullcontext()),
            patch("catalog_extensions.api.frappe.db.exists", return_value=True),
            patch("catalog_extensions.api.frappe.get_doc", return_value=return_doc),
        ):
            started = api._start_portal_refund_processing(context, signals)
            started_again = api._start_portal_refund_processing(context, signals)

        self.assertTrue(started)
        self.assertFalse(started_again)
        self.assertEqual(len(order_doc.comments), 1)
        self.assertIn(api.PORTAL_REFUND_REQUEST_MARKER, order_doc.comments[0][1])
        self.assertEqual(len(return_doc.comments), 1)

    def test_get_order_delivery_tracking_starts_refund_processing_after_return_receipt(self):
        order_doc = DummyOrder()
        context = self.make_context(order_doc=order_doc, return_invoices=[{"name": "SINV-RET-0001"}])
        normalized = {
            "normalized_status_code": "refund_processing",
            "normalized_status_label": "Refund processing",
            "normalized_status_note": "Your refund is being processed after return receipt.",
            "status_signals": {"has_return_received": True},
        }

        with (
            patch("catalog_extensions.api._get_portal_order_doc", return_value=order_doc),
            patch("catalog_extensions.api._build_portal_order_tracking_context", side_effect=[context, context]),
            patch("catalog_extensions.api._start_portal_refund_processing", return_value=True) as start_refund,
            patch("catalog_extensions.api._resolve_normalized_status", return_value=normalized),
            patch("catalog_extensions.api._build_tracking_milestones", return_value=[]),
            patch("catalog_extensions.api._get_order_actions", return_value={}),
        ):
            result = api.get_order_delivery_tracking(order_doc.name, order_doc.doctype)

        start_refund.assert_called_once_with(context)
        self.assertEqual(result["normalized_status_code"], "refund_processing")
        self.assertTrue(result["return_receipt_confirmed"])

    def test_sync_refund_processing_hook_uses_return_delivery_note_sales_order(self):
        sales_order = DummyOrder(name="SO-TEST-0002")
        return_delivery_note = DummyOrder(doctype="Delivery Note", name="DN-RET-0001")
        return_delivery_note._values.update({"is_return": 1, "return_against": "DN-0001"})

        with (
            patch(
                "catalog_extensions.api._get_linked_sales_orders_for_delivery_note",
                return_value=[sales_order.name],
            ),
            patch("catalog_extensions.api.frappe.db.exists", return_value=True),
            patch("catalog_extensions.api.frappe.get_doc", return_value=sales_order),
            patch("catalog_extensions.api._build_portal_order_tracking_context", return_value={"order_doc": sales_order}),
            patch("catalog_extensions.api._start_portal_refund_processing") as start_refund,
        ):
            api.sync_portal_refund_processing_after_return_receipt(return_delivery_note)

        start_refund.assert_called_once_with({"order_doc": sales_order})
