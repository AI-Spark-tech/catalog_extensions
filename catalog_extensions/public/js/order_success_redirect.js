frappe.ready(function() {
	if (!window.location.pathname || !window.location.pathname.startsWith("/cart")) {
		return;
	}

	var cartApi = window.shopping_cart || (window.webshop && window.webshop.webshop && window.webshop.webshop.shopping_cart);
	if (!cartApi || typeof cartApi.freeze !== "function" || typeof cartApi.unfreeze !== "function") {
		return;
	}

	var isSubmitting = false;

	function showCartError(response, button) {
		cartApi.unfreeze();
		isSubmitting = false;
		if (button) {
			button.disabled = false;
		}

		var msg = "";
		if (response && response._server_messages) {
			msg = JSON.parse(response._server_messages || []).join("<br>");
		}

		$("#cart-error")
			.empty()
			.html(msg || frappe._("Something went wrong!"))
			.toggle(true);
	}

	function placeOrderAndRedirect(button) {
		cartApi.freeze();

		return frappe.call({
			type: "POST",
			method: "webshop.webshop.shopping_cart.cart.place_order",
			btn: button,
			callback: function(r) {
				if (r.exc) {
					showCartError(r, button);
					return;
				}

				var payload = r.message || {};
				var redirectTo = "";

				if (typeof payload === "string") {
					redirectTo = "/order-success?order_id=" + encodeURIComponent(payload);
				} else if (payload.redirect_to) {
					redirectTo = payload.redirect_to;
				} else if (payload.order_id) {
					redirectTo = "/order-success?order_id=" + encodeURIComponent(payload.order_id);
				}

				if (!redirectTo) {
					showCartError(null, button);
					return;
				}

				$(button).hide();
				window.location.replace(redirectTo);
			},
			error: function() {
				showCartError(null, button);
			},
		});
	}

	document.addEventListener(
		"click",
		function(event) {
			var button = event.target && event.target.closest(".btn-place-order");
			if (!button) {
				return;
			}

			event.preventDefault();
			event.stopImmediatePropagation();

			if (isSubmitting) {
				return;
			}

			isSubmitting = true;
			button.disabled = true;
			placeOrderAndRedirect(button);
		},
		true
	);
});
