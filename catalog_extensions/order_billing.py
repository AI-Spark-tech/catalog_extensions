import frappe
from frappe.utils import flt
from catalog_extensions.simple_checkout import PAYMENT_MODE_COD, get_payment_mode_for_doc

DELIVERY_COMPLETE_MARKER = "[catalog_extensions_delivery_completed]"


def _has_existing_sales_invoice(sales_order_name: str) -> bool:
    return bool(
        frappe.db.sql(
            """
            SELECT si.name
            FROM `tabSales Invoice` si
            INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
            WHERE si.docstatus < 2
              AND sii.sales_order = %s
            LIMIT 1
            """,
            (sales_order_name,),
        )
    )


def _is_fully_paid_prepaid_order(doc) -> bool:
    order_total = flt(doc.get("base_rounded_total") or doc.get("base_grand_total") or 0)
    advance_paid = flt(doc.get("advance_paid") or 0)

    if order_total <= 0:
        return False

    return advance_paid >= (order_total - 0.01)


def _has_delivery_completion_marker(sales_order_name: str) -> bool:
    return bool(
        frappe.db.exists(
            "Comment",
            {
                "reference_doctype": "Sales Order",
                "reference_name": sales_order_name,
                "content": ["like", f"%{DELIVERY_COMPLETE_MARKER}%"],
            },
        )
    )


def create_sales_invoice_for_fully_paid_webshop_order(doc, method=None):
    if doc.doctype != "Sales Order":
        return

    if doc.docstatus != 1 or doc.get("order_type") != "Shopping Cart":
        return

    if (doc.get("status") or "") in ("Cancelled", "Closed"):
        return

    if (doc.get("status") or "") != "Completed" and not _has_delivery_completion_marker(doc.name):
        return

    if flt(doc.get("per_delivered")) < 100:
        return

    payment_mode = get_payment_mode_for_doc(doc)
    if payment_mode != PAYMENT_MODE_COD and not _is_fully_paid_prepaid_order(doc):
        return

    if _has_existing_sales_invoice(doc.name):
        return

    from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

    sales_invoice = make_sales_invoice(doc.name, ignore_permissions=True)
    sales_invoice.webshop_payment_mode = payment_mode
    sales_invoice.flags.ignore_permissions = True
    sales_invoice.insert(ignore_permissions=True)
    sales_invoice.submit()
