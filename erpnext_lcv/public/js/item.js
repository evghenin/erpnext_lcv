// Copyright (c) 2026, Evgheni Nemerenco and Contributors
// License: GNU General Public License v3. See license.txt

function erpnext_lcv_category(fieldname) {
	const settings = frappe.boot.erpnext_lcv_stock_settings || {};
	return settings[fieldname] || "";
}

function erpnext_lcv_uom_query(category_field) {
	return {
		query: "erpnext_lcv.landed_cost_advanced.measurements.uom_query",
		filters: {
			category: erpnext_lcv_category(category_field),
		},
	};
}

frappe.ui.form.on("Item", {
	setup(frm) {
		frm.set_query("weight_uom", () => erpnext_lcv_uom_query("weight_uom_category"));
		frm.set_query("volume_uom", () => erpnext_lcv_uom_query("volume_uom_category"));
	},
});
