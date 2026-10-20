# Copyright (c) 2026, Evgheni Nemerenco and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext_lcv.landed_cost_advanced.allocate import allocate_taxes, resolve_method
from erpnext_lcv.landed_cost_advanced.measurements import (
	allocation_errors,
	validate_item_measurement_fields,
)
from erpnext_lcv.landed_cost_advanced.uom import conversion_factor
from erpnext_lcv.overrides.landed_cost_voucher import LandedCostVoucherAdvanced


MASS_RECORDS = [
	{"from_uom": "Kg", "to_uom": "Gram", "value": 1000},
	{"from_uom": "Kg", "to_uom": "Tonne", "value": 0.001},
]


def _items():
	return [
		{"item_code": "A", "idx": 1, "qty": 1, "amount": 10, "total_weight": 1, "total_volume": 5},
		{"item_code": "B", "idx": 2, "qty": 1, "amount": 30, "total_weight": 3, "total_volume": 5},
	]


class TestLandedCostAllocation(FrappeTestCase):
	def test_mixed_methods_in_one_voucher(self):
		taxes = [
			{"idx": 1, "base_amount": 40, "distribution_method": "Amount"},
			{"idx": 2, "base_amount": 8, "distribution_method": "Weight"},
		]
		charges = allocate_taxes(_items(), taxes, "Qty", 2)
		self.assertEqual(charges, [12.0, 36.0])

	def test_default_follows_voucher_method(self):
		taxes = [{"idx": 1, "base_amount": 40, "distribution_method": "Default"}]
		self.assertEqual(resolve_method("", "Amount"), "Amount")
		self.assertEqual(resolve_method(None, "Weight"), "Weight")
		by_amount = allocate_taxes(_items(), taxes, "Amount", 2)
		by_weight = allocate_taxes(_items(), taxes, "Weight", 2)
		self.assertEqual(by_amount, [10.0, 30.0])
		self.assertEqual(by_weight, [10.0, 30.0])
		explicit = [{"idx": 1, "base_amount": 40, "distribution_method": "Qty"}]
		self.assertEqual(allocate_taxes(_items(), explicit, "Amount", 2), [20.0, 20.0])

	def test_rounding_remainder_stays_within_precision(self):
		items = [
			{"qty": 1, "amount": 1, "total_weight": 1, "total_volume": 1},
			{"qty": 1, "amount": 1, "total_weight": 1, "total_volume": 1},
			{"qty": 1, "amount": 1, "total_weight": 1, "total_volume": 1},
		]
		taxes = [{"base_amount": 1, "distribution_method": "Qty"}]
		shares = allocate_taxes(items, taxes, "Qty", 2)
		self.assertEqual(shares, [0.33, 0.33, 0.34])
		self.assertEqual(round(sum(shares), 2), 1.0)

	def test_submit_names_item_and_does_not_update_stock(self):
		doc = frappe.new_doc("Landed Cost Voucher")
		doc.company = frappe.db.get_value("Company", {}, "name")
		doc.distribute_charges_based_on = "Amount"
		doc.append(
			"items",
			{
				"item_code": "MISSING-WEIGHT",
				"qty": 2,
				"amount": 10,
				"total_weight": 0,
				"weight_edited": 1,
			},
		)
		doc.items[0].idx = 1
		doc.items[0].__dict__["weight_edited"] = 1
		doc.items[0].__dict__["total_weight"] = 0
		doc.append(
			"taxes",
			{
				"expense_account": "Freight",
				"description": "Freight",
				"amount": 5,
				"base_amount": 5,
				"distribution_method": "Weight",
			},
		)
		doc.taxes[0].idx = 3
		doc.taxes[0].__dict__["distribution_method"] = "Weight"
		calls = []
		doc.update_landed_cost = lambda *args, **kwargs: calls.append("update_landed_cost")

		with self.assertRaises(frappe.ValidationError) as caught:
			doc.on_submit()

		message = str(caught.exception)
		self.assertIn("MISSING-WEIGHT", message)
		self.assertIn("zero", message)
		self.assertIn("3", message)
		self.assertEqual(calls, [])

	def test_uom_outside_category_is_rejected(self):
		if not frappe.get_meta("Stock Settings").has_field("weight_uom_category"):
			self.skipTest("Stock Settings fields are applied by bench migrate")
		if not frappe.db.exists("UOM Category", "Mass"):
			self.skipTest("Mass category is not installed")
		base = "Kg" if frappe.db.exists("UOM", "Kg") else None
		if not base:
			self.skipTest("Kg is not installed")

		settings = frappe.get_single("Stock Settings")
		previous = (
			settings.get("weight_uom_category"),
			settings.get("weight_base_uom"),
			settings.get("volume_uom_category"),
			settings.get("volume_base_uom"),
		)
		settings.weight_uom_category = "Mass"
		settings.weight_base_uom = base
		settings.flags.ignore_permissions = True
		settings.flags.ignore_mandatory = True
		settings.save()
		frappe.clear_document_cache("Stock Settings", "Stock Settings")

		try:
			item = frappe._dict(
				doctype="Item",
				item_code="LCV-UOM-TEST",
				name="LCV-UOM-TEST",
				weight_per_unit=1,
				weight_uom="Nos",
				volume_per_unit=0,
				volume_uom=None,
			)
			with self.assertRaises(frappe.ValidationError) as caught:
				validate_item_measurement_fields(item)
			message = str(caught.exception)
			self.assertIn("Weight UOM", message)
			self.assertIn("Nos", message)
			self.assertIn("Mass", message)
		finally:
			settings.weight_uom_category = previous[0]
			settings.weight_base_uom = previous[1]
			settings.volume_uom_category = previous[2]
			settings.volume_base_uom = previous[3]
			settings.save()

	def test_conversion_uses_category_hub(self):
		self.assertEqual(conversion_factor("Gram", "Tonne", MASS_RECORDS), 0.001 / 1000)
		self.assertEqual(conversion_factor("Gram", "Kg", MASS_RECORDS), 0.001)
		self.assertIsNone(conversion_factor("Gram", "Litre", MASS_RECORDS))

	def test_allocation_error_lists_missing_conversion(self):
		items = [
			{
				"item_code": "BOX",
				"idx": 4,
				"qty": 2,
				"amount": 10,
				"weight_edited": 0,
				"total_weight": None,
			}
		]
		taxes = [{"idx": 2, "base_amount": 5, "distribution_method": "Weight"}]
		settings = {
			"weight_uom_category": "Mass",
			"weight_base_uom": "Kg",
			"volume_uom_category": "Volume",
			"volume_base_uom": "Litre",
		}
		masters = {"BOX": {"weight_per_unit": 1, "weight_uom": "Stone", "volume_per_unit": None, "volume_uom": None}}
		errors = allocation_errors(
			items,
			taxes,
			"Amount",
			settings=settings,
			masters=masters,
			records_by_kind={"Weight": MASS_RECORDS, "Volume": []},
		)
		self.assertEqual(len(errors), 1)
		self.assertIn("BOX", errors[0])
		self.assertIn("Stone", errors[0])
		self.assertIn("Kg", errors[0])
