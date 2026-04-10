(function () {
	"use strict";

	const loadedAssets = new Set();

	function loadCss(href) {
		if (!href || loadedAssets.has(href) || document.querySelector(`link[href="${href}"]`)) {
			return;
		}

		const link = document.createElement("link");
		link.rel = "stylesheet";
		link.href = href;
		document.head.appendChild(link);
		loadedAssets.add(href);
	}

	function loadJs(src) {
		if (!src || loadedAssets.has(src) || document.querySelector(`script[src="${src}"]`)) {
			return;
		}

		const script = document.createElement("script");
		script.src = src;
		script.async = false;
		document.body.appendChild(script);
		loadedAssets.add(src);
	}

	function loadConfiguredZoomAssets() {
		if (typeof frappe === "undefined" || typeof frappe.call !== "function") {
			return;
		}

		frappe.call({
			method: "catalog_extensions.zoom_config.get_zoom_assets",
			callback: (response) => {
				const assets = response.message || {};
				loadCss(assets.css);
				loadJs(assets.js);
			},
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", loadConfiguredZoomAssets);
	} else {
		loadConfiguredZoomAssets();
	}
})();
