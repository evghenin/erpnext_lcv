// Copyright (c) 2026, Evgheni Nemerenco and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Stock Settings", {
	setup(frm) {
		frm.set_query("weight_base_uom", () => ({
			query: "erpnext_lcv.landed_cost_advanced.measurements.uom_query",
			filters: { category: frm.doc.weight_uom_category },
		}));
		frm.set_query("volume_base_uom", () => ({
			query: "erpnext_lcv.landed_cost_advanced.measurements.uom_query",
			filters: { category: frm.doc.volume_uom_category },
		}));
	},
});
