frappe.ui.form.on("Webshop Simple Checkout Settings", {
	refresh(frm) {
		toggle_simple_checkout_fields(frm);
	},

	enable_simple_checkout(frm) {
		toggle_simple_checkout_fields(frm);
	},
});

function toggle_simple_checkout_fields(frm) {
	const enabled = !!frm.doc.enable_simple_checkout;
	const dependentFields = [
		"hide_shipping_on_webshop",
		"hide_payment_on_webshop",
		"default_shipping_address_type",
		"default_payment_term_template",
	];

	dependentFields.forEach((fieldname) => {
		frm.set_df_property(fieldname, "read_only", enabled ? 0 : 1);
	});
}
