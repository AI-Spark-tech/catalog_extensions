frappe.ready(function () {
	try {
		if (!window.frappe) return;
		if (!frappe.boot) frappe.boot = {};
		if (frappe.boot.assets_json && typeof frappe.boot.assets_json === "object") return;

		fetch("/assets/assets.json", { credentials: "same-origin" })
			.then(function (r) {
				if (!r.ok) throw new Error("Failed to fetch assets.json");
				return r.json();
			})
			.then(function (assets) {
				if (!frappe.boot) frappe.boot = {};
				frappe.boot.assets_json = assets;
			})
			.catch(function () {
				// no-op
			});
	} catch (e) {
		// no-op
	}
});
