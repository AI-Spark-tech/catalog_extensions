frappe.ready(function () {
	// Only run on the cart page
	if (!window.location.pathname || !window.location.pathname.startsWith("/cart")) {
		return;
	}

	var checkoutFlags = null;

	function removeMatchingElements(selectors) {
		selectors.forEach(function (selector) {
			var elements = document.querySelectorAll(selector);
			elements.forEach(function (element) {
				element.remove();
			});
		});
	}

	function renderPaymentModeSelector(flags) {
		var placeOrderContainer = document.querySelector(".cart-payment-addresses .place-order");
		if (!placeOrderContainer) {
			return;
		}

		var existing = document.getElementById("ce-payment-mode-selector");
		if (existing) {
			existing.remove();
		}

		if (!flags.show_payment_mode_selector) {
			return;
		}

		var wrapper = document.createElement("div");
		wrapper.id = "ce-payment-mode-selector";
		wrapper.className = "mb-3";
		wrapper.innerHTML = [
			'<label class="form-label font-md" for="ce-payment-mode-input">Payment Method</label>',
			'<select class="form-control" id="ce-payment-mode-input">',
			flags.enable_prepaid ? '<option value="PREPAID">Pay Now</option>' : "",
			flags.enable_cod ? '<option value="COD">Cash on Delivery</option>' : "",
			"</select>",
			'<div class="text-muted mt-2" id="ce-payment-mode-note"></div>',
		].join("");

		placeOrderContainer.parentNode.insertBefore(wrapper, placeOrderContainer);

		var select = document.getElementById("ce-payment-mode-input");
		var note = document.getElementById("ce-payment-mode-note");
		select.value = flags.selected_payment_mode || flags.default_payment_mode || "PREPAID";
		updatePaymentModeNote(select.value, note);

		select.addEventListener("change", function () {
			var nextMode = select.value;
			frappe.call({
				method: "catalog_extensions.simple_checkout.set_checkout_payment_mode",
				args: { payment_mode: nextMode },
				callback: function (response) {
					var message = response && response.message ? response.message : {};
					checkoutFlags.selected_payment_mode = message.selected_payment_mode || nextMode;
					select.value = checkoutFlags.selected_payment_mode;
					updatePaymentModeNote(checkoutFlags.selected_payment_mode, note);
				},
			});
		});
	}

	function updatePaymentModeNote(selectedMode, noteEl) {
		if (!noteEl) {
			return;
		}

		if (checkoutFlags && checkoutFlags.hide_payment_on_webshop) {
			noteEl.textContent = "Your order will be confirmed now using the default checkout settings.";
			return;
		}

		if (selectedMode === "COD") {
			noteEl.textContent = "Your order will be confirmed now and payment will be collected on delivery.";
			return;
		}

		noteEl.textContent = "You can place the order now and complete payment from the order page.";
	}

	function overridePlaceOrder(flags) {
		var cartNamespace = window.webshop && window.webshop.webshop && window.webshop.webshop.shopping_cart;
		if (!cartNamespace) {
			return;
		}

		cartNamespace.place_order = function (btn) {
			cartNamespace.freeze();

			var selectedMode = null;
			var selector = document.getElementById("ce-payment-mode-input");
			if (flags && flags.hide_payment_on_webshop) {
				selectedMode = null;
			} else if (selector) {
				selectedMode = selector.value || selectedMode;
			} else if (flags && flags.selected_payment_mode) {
				selectedMode = flags.selected_payment_mode;
			}

			return frappe.call({
				type: "POST",
				method: "webshop.webshop.shopping_cart.cart.place_order",
				btn: btn,
				args: {
					payment_mode: selectedMode,
				},
				callback: function (r) {
					if (r.exc) {
						cartNamespace.unfreeze();
						var msg = "";
						if (r._server_messages) {
							msg = JSON.parse(r._server_messages || []).join("<br>");
						}

					$("#cart-error")
							.empty()
							.html(msg || frappe._("Something went wrong!"))
							.toggle(true);
					} else {
						$(btn).hide();
						var payload = r.message || {};
						if (typeof payload === "string") {
							window.location.href = "/orders/" + encodeURIComponent(payload);
							return;
						}

						var redirectTo = payload.redirect_to || payload.order_redirect || "";
						if (!redirectTo && payload.order_id) {
							redirectTo = "/orders/" + encodeURIComponent(payload.order_id);
						}
						window.location.href = redirectTo || "/orders";
					}
				}
			});
		};
	}

	frappe.call({
		method: "catalog_extensions.simple_checkout.get_simple_checkout_flags",
		freeze: false,
		callback: function (r) {
			if (!r || !r.message) return;

			var flags = r.message;
			checkoutFlags = flags;
			window.checkoutFlags = flags;
			renderPaymentModeSelector(flags);
			overridePlaceOrder(flags);

			// Hide payment-related UI on the cart sidebar
			if (flags.hide_payment_on_webshop) {
				// Hide only the payment summary and coupon section.
				// Keep the Place Order button visible so checkout can complete.
				removeMatchingElements([
					".cart-payment-addresses .payment-summary",
					".cart-payment-addresses [data-section='payment-summary']",
				]);

				// Coupon section (if present)
				var couponButton = document.querySelector(".cart-payment-addresses .bt-coupon");
				if (couponButton && couponButton.parentElement) {
					// Remove the row containing coupon controls
					couponButton.parentElement.remove();
				}
			}

			// Hide shipping/billing address selection UI
			if (flags.hide_shipping_on_webshop) {
				removeMatchingElements([
					'[data-section="shipping-address"]',
					'[data-section="billing-address"]',
					".cart-payment-addresses .shipping-address",
					".cart-payment-addresses .billing-address",
				]);

				// Remove the "Billing Address is same as Shipping Address" checkbox row if present
				var sameBillingInput = document.getElementById("input_same_billing");
				if (sameBillingInput && sameBillingInput.closest('.checkbox')) {
					sameBillingInput.closest('.checkbox').remove();
				}
			}
		},
	});
});
