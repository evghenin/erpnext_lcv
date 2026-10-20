# Copyright (c) 2026, Evgheni Nemerenco and Contributors
# License: GNU General Public License v3. See license.txt

import frappe


def boot_session(bootinfo):
	settings = frappe.get_cached_doc("Stock Settings")
	bootinfo.erpnext_lcv_stock_settings = {
		"weight_uom_category": settings.get("weight_uom_category"),
		"volume_uom_category": settings.get("volume_uom_category"),
		"weight_base_uom": settings.get("weight_base_uom"),
		"volume_base_uom": settings.get("volume_base_uom"),
	}
