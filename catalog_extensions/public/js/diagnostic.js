/**
 * DIAGNOSTIC SCRIPT - Grid View Checker
 * Add this temporarily to see what's wrong
 */

frappe.ready(() => {
	console.log('=== GRID VIEW DIAGNOSTIC ===');
	
	// Check if we're on a product listing page
	console.log('Current URL:', window.location.pathname);
	
	// Check for containers
	const gridArea = document.getElementById('products-grid-area');
	const listArea = document.getElementById('products-list-area');
	const productListing = document.getElementById('product-listing');
	
	console.log('Grid container exists:', !!gridArea);
	console.log('List container exists:', !!listArea);
	console.log('Product listing exists:', !!productListing);
	
	if (gridArea) {
		console.log('Grid container classes:', gridArea.className);
		console.log('Grid container hidden?', gridArea.classList.contains('hidden'));
		console.log('Grid container display style:', window.getComputedStyle(gridArea).display);
		
		// Check for products inside
		const gridProducts = gridArea.querySelectorAll('.item-card, .card');
		console.log('Products in grid:', gridProducts.length);
		
		// Check products-list inside grid-area
		const gridList = gridArea.querySelector('.products-list, .row');
		console.log('Grid .products-list exists:', !!gridList);
		if (gridList) {
			console.log('Grid .products-list children:', gridList.children.length);
		}
	}
	
	if (listArea) {
		console.log('List container classes:', listArea.className);
		console.log('List container hidden?', listArea.classList.contains('hidden'));
		console.log('List container display style:', window.getComputedStyle(listArea).display);
		
		// Check for products inside
		const listProducts = listArea.querySelectorAll('.item-card, .card');
		console.log('Products in list:', listProducts.length);
	}
	
	// Check for toggle buttons
	const gridBtn = document.querySelector('.btn-grid-view, #grid, button[data-view="grid"]');
	const listBtn = document.querySelector('.btn-list-view, #list, button[data-view="list"]');
	
	console.log('Grid button exists:', !!gridBtn);
	console.log('List button exists:', !!listBtn);
	
	if (gridBtn) {
		console.log('Grid button visible?', window.getComputedStyle(gridBtn).display !== 'none');
	}
	if (listBtn) {
		console.log('List button visible?', window.getComputedStyle(listBtn).display !== 'none');
	}
	
	// Check for any products anywhere
	const allProducts = document.querySelectorAll('.item-card');
	console.log('Total .item-card elements on page:', allProducts.length);
	
	// Check localStorage view preference
	const savedView = localStorage.getItem('product_view');
	console.log('Saved view preference:', savedView);
	
	console.log('=== END DIAGNOSTIC ===');
});
/**
 * DIAGNOSTIC SCRIPT - Grid View Checker
 * Add this temporarily to see what's wrong
 */

frappe.ready(() => {
	console.log('=== GRID VIEW DIAGNOSTIC ===');
	
	// Check if we're on a product listing page
	console.log('Current URL:', window.location.pathname);
	
	// Check for containers
	const gridArea = document.getElementById('products-grid-area');
	const listArea = document.getElementById('products-list-area');
	const productListing = document.getElementById('product-listing');
	
	console.log('Grid container exists:', !!gridArea);
	console.log('List container exists:', !!listArea);
	console.log('Product listing exists:', !!productListing);
	
	if (gridArea) {
		console.log('Grid container classes:', gridArea.className);
		console.log('Grid container hidden?', gridArea.classList.contains('hidden'));
		console.log('Grid container display style:', window.getComputedStyle(gridArea).display);
		
		// Check for products inside
		const gridProducts = gridArea.querySelectorAll('.item-card, .card');
		console.log('Products in grid:', gridProducts.length);
		
		// Check products-list inside grid-area
		const gridList = gridArea.querySelector('.products-list, .row');
		console.log('Grid .products-list exists:', !!gridList);
		if (gridList) {
			console.log('Grid .products-list children:', gridList.children.length);
		}
	}
	
	if (listArea) {
		console.log('List container classes:', listArea.className);
		console.log('List container hidden?', listArea.classList.contains('hidden'));
		console.log('List container display style:', window.getComputedStyle(listArea).display);
		
		// Check for products inside
		const listProducts = listArea.querySelectorAll('.item-card, .card');
		console.log('Products in list:', listProducts.length);
	}
	
	// Check for toggle buttons
	const gridBtn = document.querySelector('.btn-grid-view, #grid, button[data-view="grid"]');
	const listBtn = document.querySelector('.btn-list-view, #list, button[data-view="list"]');
	
	console.log('Grid button exists:', !!gridBtn);
	console.log('List button exists:', !!listBtn);
	
	if (gridBtn) {
		console.log('Grid button visible?', window.getComputedStyle(gridBtn).display !== 'none');
	}
	if (listBtn) {
		console.log('List button visible?', window.getComputedStyle(listBtn).display !== 'none');
	}
	
	// Check for any products anywhere
	const allProducts = document.querySelectorAll('.item-card');
	console.log('Total .item-card elements on page:', allProducts.length);
	
	// Check localStorage view preference
	const savedView = localStorage.getItem('product_view');
	console.log('Saved view preference:', savedView);
	
	console.log('=== END DIAGNOSTIC ===');
});
