/**
 * Cart Page Fixes - Ensure proper mobile display
 * This script ensures the cart displays correctly on mobile devices
 */

frappe.ready(function () {
	// Only run on cart page
	if (!window.location.pathname || !window.location.pathname.startsWith("/cart")) {
		return;
	}

	// Wait for DOM to be fully loaded
	setTimeout(function() {
		fixCartDisplay();
		fixCartAddressDisplay();
	}, 500);

	// Also fix on any dynamic updates
	$(document).on('cart-updated', function() {
		setTimeout(function() {
			fixCartDisplay();
			fixCartAddressDisplay();
		}, 300);
	});
});

function fixCartDisplay() {
	// On mobile, ensure proper layout
	if (window.innerWidth < 768) {
		const cartTable = document.querySelector('.cart-items table, .cart-table');
		
		if (cartTable) {
			// Ensure proper classes are applied
			cartTable.classList.add('cart-table');
			
			// Remove any inline styles that might interfere
			const rows = cartTable.querySelectorAll('tbody tr');
			rows.forEach(function(row) {
				// Ensure each cart item displays as a card on mobile
				row.style.display = 'block';
				row.style.width = '100%';
			});
		}

		// Ensure container doesn't cause horizontal scroll
		const containers = document.querySelectorAll('.cart-container, .page-content-wrapper, .container');
		containers.forEach(function(container) {
			container.style.overflowX = 'hidden';
			container.style.maxWidth = '100vw';
		});
	}
}

function fixCartAddressDisplay() {
	// Ensure address sections are visible
	const addressSelectors = [
		'[data-section="shipping-address"]',
		'[data-section="billing-address"]',
		'.shipping-address',
		'.billing-address',
		'.cart-payment-addresses'
	];

	addressSelectors.forEach(function(selector) {
		const elements = document.querySelectorAll(selector);
		elements.forEach(function(el) {
			if (el) {
				el.style.display = 'block';
				el.style.visibility = 'visible';
				el.style.opacity = '1';
			}
		});
	});

	// If no addresses are showing, log for debugging
	const shippingSection = document.querySelector('[data-section="shipping-address"]');
	const billingSection = document.querySelector('[data-section="billing-address"]');
	
	if (!shippingSection && !billingSection) {
		console.log('Cart: No address sections found - may need manual address entry');
	}
}

// Re-run fixes on window resize (debounced)
let resizeTimer;
window.addEventListener('resize', function() {
	clearTimeout(resizeTimer);
	resizeTimer = setTimeout(function() {
		if (window.location.pathname && window.location.pathname.startsWith("/cart")) {
			fixCartDisplay();
		}
	}, 250);
});
