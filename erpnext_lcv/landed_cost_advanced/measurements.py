# Copyright (c) 2026, Evgheni Nemerenco and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext_lcv.landed_cost_advanced.allocate import BASIS_FIELD, resolve_method
from erpnext_lcv.landed_cost_advanced.uom import convert_quantity, uom_in_records

KINDS = (
	{
		"method": "Weight",
		"total_field": "total_weight",
		"edited_field": "weight_edited",
		"row_uom_field": "weight_uom",
		"per_unit_field": "weight_per_unit",
		"item_uom_field": "weight_uom",
		"category_field": "weight_uom_category",
		"base_field": "weight_base_uom",
		"label": "weight",
	},
	{
		"method": "Volume",
		"total_field": "total_volume",
		"edited_field": "volume_edited",
		"row_uom_field": "volume_uom",
		"per_unit_field": "volume_per_unit",
		"item_uom_field": "volume_uom",
		"category_field": "volume_uom_category",
		"base_field": "volume_base_uom",
		"label": "volume",
	},
)


def get_measurement_settings():
	settings = frappe.get_cached_doc("Stock Settings")
	return {
		"weight_uom_category": settings.get("weight_uom_category"),
		"volume_uom_category": settings.get("volume_uom_category"),
		"weight_base_uom": settings.get("weight_base_uom"),
		"volume_base_uom": settings.get("volume_base_uom"),
	}


def category_records(category):
	if not category:
		return []
	return frappe.get_all(
		"UOM Conversion Factor",
		filters={"category": category},
		fields=["from_uom", "to_uom", "value"],
	)


def item_measurement_master(item_code):
	if not item_code:
		return {}
	return (
		frappe.db.get_value(
			"Item",
			item_code,
			["weight_per_unit", "weight_uom", "volume_per_unit", "volume_uom"],
			as_dict=True,
		)
		or {}
	)


def apply_calculated_measurements(row, master, settings, records_by_kind, force=False):
	"""Fill total weight and volume from the item when the row was not edited."""
	for kind in KINDS:
		if not force and cint(row.get(kind["edited_field"])):
			continue
		value, base_uom, _reason = _calculate(row, master, settings, records_by_kind, kind)
		row.set(kind["total_field"], value)
		row.set(kind["row_uom_field"], base_uom or None)
		if force:
			row.set(kind["edited_field"], 0)


def _calculate(row, master, settings, records_by_kind, kind):
	category = settings.get(kind["category_field"])
	base_uom = settings.get(kind["base_field"])
	if not category or not base_uom:
		return None, None, "missing settings"
	per_unit = master.get(kind["per_unit_field"])
	item_uom = master.get(kind["item_uom_field"])
	if not item_uom and not per_unit:
		return None, base_uom, "missing value"
	if not item_uom:
		return None, base_uom, "missing UOM"
	if per_unit in (None, ""):
		return None, base_uom, "missing value"
	records = records_by_kind.get(kind["method"]) or []
	converted = convert_quantity(_stock_qty(row) * flt(per_unit), item_uom, base_uom, records)
	if converted is None:
		return None, base_uom, "no conversion"
	if converted <= 0:
		return converted, base_uom, "zero"
	return converted, base_uom, None


def _stock_qty(row):
	"""Qty in the item stock UOM. Item weight and volume are per stock UOM."""
	qty = flt(row.get("qty"))
	factor = row.get("conversion_factor")
	if factor in (None, ""):
		factor = _receipt_conversion_factor(row)
	factor = flt(factor)
	if factor <= 0:
		factor = 1
	return qty * factor


def _receipt_conversion_factor(row):
	name = row.get("purchase_receipt_item")
	parenttype = row.get("receipt_document_type")
	if not name or not parenttype:
		return 1
	child = f"{parenttype} Item"
	if not frappe.get_meta(child).has_field("conversion_factor"):
		return 1
	return frappe.db.get_value(child, name, "conversion_factor")


def measurement_problem(row, master, settings, records_by_kind, kind):
	"""Why this row cannot supply a positive measurement, or None."""
	if cint(row.get(kind["edited_field"])):
		total = row.get(kind["total_field"])
		if total in (None, ""):
			return "missing value"
		if flt(total) <= 0:
			return "zero"
		return None
	_value, _uom, reason = _calculate(row, master, settings, records_by_kind, kind)
	if reason == "no conversion":
		item_uom = master.get(kind["item_uom_field"]) or _("not set")
		base_uom = settings.get(kind["base_field"]) or _("not set")
		return _("no conversion from {0} to {1}").format(item_uom, base_uom)
	return reason


def allocation_errors(items, taxes, voucher_method, settings=None, masters=None, records_by_kind=None):
	"""Problems that must block submit. Each entry is a translated string."""
	settings = settings if settings is not None else get_measurement_settings()
	if records_by_kind is None:
		records_by_kind = {
			kind["method"]: category_records(settings.get(kind["category_field"])) for kind in KINDS
		}
	masters = masters or {}
	errors = []

	for tax in taxes or []:
		method = resolve_method(tax.get("distribution_method"), voucher_method)
		if method == "Distribute Manually":
			continue
		kind = next((row for row in KINDS if row["method"] == method), None)
		if kind:
			for item in items or []:
				master = masters.get(item.get("item_code"))
				if master is None:
					master = item_measurement_master(item.get("item_code"))
				reason = measurement_problem(item, master, settings, records_by_kind, kind)
				if not reason:
					continue
				errors.append(_problem_line(item, tax, method, reason))
			continue

		fieldname = BASIS_FIELD.get(method)
		if not fieldname:
			continue
		bases = [flt(item.get(fieldname)) for item in items or []]
		if sum(bases) <= 0:
			errors.append(
				_(
					"Expense row {0} ({1}): total {2} for all items is zero. Remove the expense or change its distribution method."
				).format(tax.get("idx") or "", method, fieldname)
			)
	return errors


def _problem_line(item, tax, method, reason):
	return _(
		"Item {0}, landed cost row {1}, expense row {2}, method {3}: {4}."
	).format(
		item.get("item_code") or "",
		item.get("idx") or "",
		tax.get("idx") or "",
		method,
		reason,
	)


def validate_item_measurement_fields(item, method=None):
	"""Item.validate hook: value and UOM together, UOM inside the configured category."""
	settings = get_measurement_settings()
	_validate_pair(
		item,
		value=item.get("weight_per_unit"),
		uom=item.get("weight_uom"),
		value_label=_("Weight Per Unit"),
		uom_label=_("Weight UOM"),
		category=settings.get("weight_uom_category"),
		base_uom=settings.get("weight_base_uom"),
		category_label=_("Weight UOM Category"),
		base_label=_("Weight Base UOM"),
	)
	_validate_pair(
		item,
		value=item.get("volume_per_unit"),
		uom=item.get("volume_uom"),
		value_label=_("Volume Per Unit"),
		uom_label=_("Volume UOM"),
		category=settings.get("volume_uom_category"),
		base_uom=settings.get("volume_base_uom"),
		category_label=_("Volume UOM Category"),
		base_label=_("Volume Base UOM"),
	)


def _validate_pair(item, value, uom, value_label, uom_label, category, base_uom, category_label, base_label):
	has_value = value not in (None, "", 0)
	has_uom = bool(uom)
	if not has_value and not has_uom:
		return
	if has_value != has_uom:
		frappe.throw(
			_("{0} and {1} are required together on Item {2}.").format(
				value_label, uom_label, item.get("item_code") or item.get("name") or ""
			)
		)
	if not category or not base_uom:
		frappe.throw(
			_(
				"Set {0} and {1} in Stock Settings before saving an item with {2}."
			).format(category_label, base_label, value_label)
		)
	records = category_records(category)
	if not uom_in_records(uom, records):
		frappe.throw(
			_(
				"{0} {1} is not in a UOM Conversion Factor for category {2}. Create a conversion factor in that category."
			).format(uom_label, uom, category)
		)


@frappe.whitelist()
def uom_query(doctype, txt, searchfield, start, page_len, filters):
	category = (filters or {}).get("category")
	if not category:
		return []
	return frappe.db.sql(
		"""
		select distinct uom
		from (
			select from_uom as uom
			from `tabUOM Conversion Factor`
			where category = %(category)s
			union
			select to_uom as uom
			from `tabUOM Conversion Factor`
			where category = %(category)s
		) units
		where uom like %(txt)s
		order by uom
		limit %(page_len)s offset %(start)s
		""",
		{
			"category": category,
			"txt": f"%{txt}%",
			"start": cint(start),
			"page_len": cint(page_len) or 20,
		},
	)


@frappe.whitelist()
def recalculate_item_row(
	item_code,
	qty,
	weight_edited=0,
	volume_edited=0,
	conversion_factor=None,
	purchase_receipt_item=None,
	receipt_document_type=None,
):
	"""Values for one landed cost row. Edited sides are left for the client."""
	settings = get_measurement_settings()
	master = item_measurement_master(item_code)
	records_by_kind = {
		kind["method"]: category_records(settings.get(kind["category_field"])) for kind in KINDS
	}
	row = frappe._dict(
		qty=qty,
		weight_edited=cint(weight_edited),
		volume_edited=cint(volume_edited),
		conversion_factor=conversion_factor,
		purchase_receipt_item=purchase_receipt_item,
		receipt_document_type=receipt_document_type,
	)
	result = {}
	for kind in KINDS:
		if cint(row.get(kind["edited_field"])):
			result[kind["total_field"]] = None
			result[kind["row_uom_field"]] = settings.get(kind["base_field"])
			continue
		value, base_uom, _reason = _calculate(row, master, settings, records_by_kind, kind)
		result[kind["total_field"]] = value
		result[kind["row_uom_field"]] = base_uom
	return result
