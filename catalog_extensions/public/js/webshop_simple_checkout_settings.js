frappe.ui.form.on("Webshop Simple Checkout Settings", {
	refresh(frm) {
		apply_checkout_settings_visibility(frm);
		apply_checkout_settings_copy(frm);
	},
	hide_payment_on_webshop(frm) {
		apply_checkout_settings_visibility(frm);
		apply_checkout_settings_copy(frm);
	},
});

function apply_checkout_settings_visibility(frm) {
	frm.toggle_display("enable_simple_checkout", false);
	var paymentDisabled = !!frm.doc.hide_payment_on_webshop;
	[
		"hide_shipping_on_webshop",
		"hide_payment_on_webshop",
		"default_shipping_address_type",
		"default_payment_term_template",
		"enable_cancel_order",
	].forEach((fieldname) => {
		frm.set_df_property(fieldname, "read_only", 0);
	});

	["enable_prepaid", "enable_cod", "default_payment_mode"].forEach((fieldname) => {
		frm.set_df_property(fieldname, "read_only", paymentDisabled ? 1 : 0);
	});
}

function apply_checkout_settings_copy(frm) {
	if (frm.page && typeof frm.page.set_title === "function") {
		frm.page.set_title(__("Webshop Checkout Settings"));
	}

	frm.set_df_property("hide_payment_on_webshop", "label", __("Disable Payment Section on Cart"));
	frm.set_df_property(
		"hide_payment_on_webshop",
		"description",
		__(
			"When enabled, checkout skips the payment workflow and ignores prepaid/COD customer choices on the cart."
		)
	);
	frm.set_df_property("hide_shipping_on_webshop", "label", __("Disable Shipping Section on Cart"));
	frm.set_df_property("enable_prepaid", "label", __("Enable Prepaid"));
	frm.set_df_property(
		"enable_prepaid",
		"description",
		__("This option is inactive while Disable Payment Section on Cart is enabled.")
	);
	frm.set_df_property("enable_cod", "label", __("Enable Cash on Delivery"));
	frm.set_df_property(
		"enable_cod",
		"description",
		__("This option is inactive while Disable Payment Section on Cart is enabled.")
	);
	frm.set_df_property("default_payment_mode", "label", __("Default Payment Mode"));
	frm.set_df_property(
		"default_payment_mode",
		"description",
		__("This applies only when the payment section is enabled and customers can choose a payment mode.")
	);
	frm.set_df_property("default_shipping_address_type", "label", __("Default Shipping Address Type"));
	frm.set_df_property("default_payment_term_template", "label", __("Default Payment Terms Template"));
	frm.set_df_property("enable_cancel_order", "label", __("Enable Cancel Order"));

	frm.set_intro(
		__(
			"Use these settings to control cart simplification, available checkout payment modes, and related customer actions on webshop order pages. Disabling the payment section also disables prepaid and COD selection on the cart."
		),
		"blue"
	);
}
