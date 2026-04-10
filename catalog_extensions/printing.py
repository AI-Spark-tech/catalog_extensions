from urllib.parse import quote

import frappe

ORDER_RECEIPT_PRINT_FORMAT = "order receipt"


def ensure_order_receipt_print_format():
    values = {
        "doc_type": "Sales Order",
        "module": "Selling",
        "standard": "No",
        "custom_format": 1,
        "print_format_type": "Jinja",
        "raw_printing": 0,
        "disabled": 0,
        "margin_top": 12,
        "margin_bottom": 12,
        "margin_left": 12,
        "margin_right": 12,
        "page_number": "Hide",
        "html": "<div></div>",
    }

    if frappe.db.exists("Print Format", ORDER_RECEIPT_PRINT_FORMAT):
        doc = frappe.get_doc("Print Format", ORDER_RECEIPT_PRINT_FORMAT)
        changed = False
        for key, value in values.items():
            if doc.get(key) != value:
                doc.set(key, value)
                changed = True
        if changed:
            doc.save(ignore_permissions=True)
        return doc

    doc = frappe.get_doc(
        {
            "doctype": "Print Format",
            "name": ORDER_RECEIPT_PRINT_FORMAT,
            **values,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


@frappe.whitelist()
def get_portal_order_receipt_link(order_name: str, order_doctype: str | None = None):
    from catalog_extensions.api import _get_portal_order_doc

    original_doctype = (order_doctype or "").strip()
    original_name = (order_name or "").strip()
    target_doc = _get_portal_order_doc(original_name, original_doctype or None)

    if target_doc.doctype == "Sales Order":
        ensure_order_receipt_print_format()
        return {
            "href": (
                f"/printview?doctype=Sales%20Order&name={quote(target_doc.name)}"
                f"&format={quote(ORDER_RECEIPT_PRINT_FORMAT)}&landscape=1"
            ),
            "format": ORDER_RECEIPT_PRINT_FORMAT,
            "doctype": "Sales Order",
            "name": target_doc.name,
        }

    fallback_doctype = original_doctype or target_doc.doctype
    fallback_name = original_name or target_doc.name
    return {
        "href": (
            f"/printview?doctype={quote(fallback_doctype)}&name={quote(fallback_name)}&format=Standard"
        ),
        "format": "Standard",
        "doctype": fallback_doctype,
        "name": fallback_name,
    }


def get_print_format_template(jenv, print_format):
    if not print_format:
        return None

    if frappe.form_dict.get("doctype") != "Sales Order":
        return None

    if print_format.name != ORDER_RECEIPT_PRINT_FORMAT:
        return None

    return jenv.get_template("catalog_extensions/templates/print_formats/order_receipt.html")
