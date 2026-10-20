# Copyright (c) 2026, Evgheni Nemerenco and Contributors
# License: GNU General Public License v3. See license.txt

"""Custom fields and the Landed Cost Voucher property setter."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

DISTRIBUTE_OPTIONS = "Qty\nAmount\nDistribute Manually\nWeight\nVolume"

CUSTOM_FIELDS = {
	"Stock Settings": [
		{
			"fieldname": "inventory_tab",
			"fieldtype": "Tab Break",
			"label": "Inventory",
			"insert_after": "quality_tab",
		},
		{
			"fieldname": "inventory_measurement_section",
			"fieldtype": "Section Break",
			"label": "Weight and Volume",
			"insert_after": "inventory_tab",
		},
		{
			"fieldname": "weight_uom_category",
			"fieldtype": "Link",
			"label": "Weight UOM Category",
			"options": "UOM Category",
			"insert_after": "inventory_measurement_section",
			"description": "UOM Conversion Factor category used for item weight.",
		},
		{
			"fieldname": "volume_uom_category",
			"fieldtype": "Link",
			"label": "Volume UOM Category",
			"options": "UOM Category",
			"insert_after": "weight_uom_category",
			"description": "UOM Conversion Factor category used for item volume.",
		},
		{
			"fieldname": "inventory_measurement_column",
			"fieldtype": "Column Break",
			"insert_after": "volume_uom_category",
		},
		{
			"fieldname": "weight_base_uom",
			"fieldtype": "Link",
			"label": "Weight Base UOM",
			"options": "UOM",
			"insert_after": "inventory_measurement_column",
			"description": "Landed cost weight is stored in this unit.",
		},
		{
			"fieldname": "volume_base_uom",
			"fieldtype": "Link",
			"label": "Volume Base UOM",
			"options": "UOM",
			"insert_after": "weight_base_uom",
			"description": "Landed cost volume is stored in this unit.",
		},
	],
	"Item": [
		{
			"fieldname": "volume_per_unit",
			"fieldtype": "Float",
			"label": "Volume Per Unit",
			"insert_after": "weight_uom",
			"non_negative": 1,
			"depends_on": "is_stock_item",
		},
		{
			"fieldname": "volume_uom",
			"fieldtype": "Link",
			"label": "Volume UOM",
			"options": "UOM",
			"insert_after": "volume_per_unit",
			"depends_on": "eval:doc.is_stock_item",
			"ignore_user_permissions": 1,
		},
	],
	"Landed Cost Taxes and Charges": [
		{
			"fieldname": "distribution_method",
			"fieldtype": "Select",
			"label": "Distribution Method",
			"options": "Default\nAmount\nQty\nWeight\nVolume",
			"default": "Default",
			"in_list_view": 1,
			"insert_after": "description",
		},
	],
	"Landed Cost Item": [
		{
			"fieldname": "total_weight",
			"fieldtype": "Float",
			"label": "Total Weight",
			"insert_after": "amount",
			"in_list_view": 1,
			"non_negative": 1,
		},
		{
			"fieldname": "weight_uom",
			"fieldtype": "Data",
			"label": "Weight UOM",
			"insert_after": "total_weight",
			"read_only": 1,
			"in_list_view": 1,
		},
		{
			"fieldname": "total_volume",
			"fieldtype": "Float",
			"label": "Total Volume",
			"insert_after": "weight_uom",
			"in_list_view": 1,
			"non_negative": 1,
		},
		{
			"fieldname": "volume_uom",
			"fieldtype": "Data",
			"label": "Volume UOM",
			"insert_after": "total_volume",
			"read_only": 1,
			"in_list_view": 1,
		},
		{
			"fieldname": "fill_weight_and_volume",
			"fieldtype": "Button",
			"label": "Fill weight and volume from Item",
			"insert_after": "volume_uom",
		},
		{
			"fieldname": "weight_edited",
			"fieldtype": "Check",
			"label": "Weight Edited",
			"insert_after": "fill_weight_and_volume",
			"hidden": 1,
			"default": "0",
		},
		{
			"fieldname": "volume_edited",
			"fieldtype": "Check",
			"label": "Volume Edited",
			"insert_after": "weight_edited",
			"hidden": 1,
			"default": "0",
		},
	],
}


def ensure_customizations():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True, update=True)
	setter_name = "Landed Cost Voucher-distribute_charges_based_on-options"
	if frappe.db.exists("Property Setter", setter_name):
		frappe.db.set_value("Property Setter", setter_name, "value", DISTRIBUTE_OPTIONS)
		return
	make_property_setter(
		"Landed Cost Voucher",
		"distribute_charges_based_on",
		"options",
		DISTRIBUTE_OPTIONS,
		"Text",
		validate_fields_for_doctype=False,
	)


def set_default_stock_settings():
	"""Set Mass/Kg and Volume/Cubic Meter when those records already exist."""
	if not frappe.db.exists("DocType", "Stock Settings"):
		return
	settings = frappe.get_single("Stock Settings")
	changed = False

	if not settings.get("weight_uom_category") and frappe.db.exists("UOM Category", "Mass"):
		settings.weight_uom_category = "Mass"
		changed = True
	if not settings.get("volume_uom_category") and frappe.db.exists("UOM Category", "Volume"):
		settings.volume_uom_category = "Volume"
		changed = True

	if settings.get("weight_uom_category") and not settings.get("weight_base_uom"):
		if _uom_in_category("Kg", settings.weight_uom_category):
			settings.weight_base_uom = "Kg"
			changed = True
	if settings.get("volume_uom_category") and not settings.get("volume_base_uom"):
		if _uom_in_category("Cubic Meter", settings.volume_uom_category):
			settings.volume_base_uom = "Cubic Meter"
			changed = True

	if changed:
		settings.flags.ignore_permissions = True
		settings.flags.ignore_mandatory = True
		settings.save()


def _uom_in_category(uom, category):
	if not frappe.db.exists("UOM", uom):
		return False
	return bool(
		frappe.db.exists(
			"UOM Conversion Factor",
			{"category": category, "from_uom": uom},
		)
		or frappe.db.exists(
			"UOM Conversion Factor",
			{"category": category, "to_uom": uom},
		)
	)
