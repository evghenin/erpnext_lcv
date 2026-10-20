# Copyright (c) 2026, Evgheni Nemerenco and Contributors
# License: GNU General Public License v3. See license.txt

"""UOM conversion through UOM Conversion Factor.

Standard factors are star-shaped: from_uom is the category hub (Kg, Litre)
and value is how many to_uom equal one from_uom (1 Kg = 1000 Gram).
"""

from frappe.utils import flt


def conversion_factor(from_uom, to_uom, records):
	"""Return multiplier so that quantity_in_to = quantity_in_from * factor.

	records are dicts with from_uom, to_uom and value for one category.
	Direct pairs are checked in both directions. Otherwise the path goes
	through a category hub (the from_uom of those records).
	"""
	if not from_uom or not to_uom:
		return None
	if from_uom == to_uom:
		return 1.0

	direct = _pair_factor(from_uom, to_uom, records)
	if direct is not None:
		return direct

	hubs = []
	for row in records:
		hub = row.get("from_uom")
		if hub and hub not in hubs:
			hubs.append(hub)

	for hub in hubs:
		if hub in (from_uom, to_uom):
			continue
		to_hub = _pair_factor(from_uom, hub, records)
		to_target = _pair_factor(hub, to_uom, records)
		if to_hub is not None and to_target is not None:
			return to_hub * to_target
	return None


def _pair_factor(from_uom, to_uom, records):
	for row in records:
		if row.get("from_uom") == from_uom and row.get("to_uom") == to_uom:
			value = flt(row.get("value"))
			if value:
				return value
	for row in records:
		if row.get("from_uom") == to_uom and row.get("to_uom") == from_uom:
			value = flt(row.get("value"))
			if value:
				return 1.0 / value
	return None


def convert_quantity(qty, from_uom, to_uom, records):
	factor = conversion_factor(from_uom, to_uom, records)
	if factor is None:
		return None
	return flt(qty) * factor


def uom_in_records(uom, records):
	for row in records:
		if row.get("from_uom") == uom or row.get("to_uom") == uom:
			return True
	return False
