frappe.ready(function () {
  if (!window.doc_info || !window.doc_info.doctype_name || !window.doc_info.doctype) {
    return;
  }

  var printLinks = Array.from(document.querySelectorAll('.dropdown-menu a[href*="/printview?doctype="]'));
  if (!printLinks.length) {
    return;
  }

  frappe.call({
    method: "catalog_extensions.printing.get_portal_order_receipt_link",
    args: {
      order_name: window.doc_info.doctype_name,
      order_doctype: window.doc_info.doctype
    },
    callback: function (r) {
      var payload = r && r.message ? r.message : null;
      if (!payload || !payload.href) {
        return;
      }

      printLinks.forEach(function (link) {
        link.href = payload.href;
        link.setAttribute("target", "_blank");
        link.setAttribute("rel", "noopener noreferrer");
      });
    }
  });
});
