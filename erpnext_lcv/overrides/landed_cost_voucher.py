# Copyright (c) 2026, Evgheni Nemerenco and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.model.meta import get_field_precision
from frappe.utils import cint, flt

from erpnext.stock.doctype.landed_cost_voucher.landed_cost_voucher import LandedCostVoucher

from erpnext_lcv.landed_cost_advanced.allocate import (
	allocate_taxes,
	explicit_methods_on_manual,
)
from erpnext_lcv.landed_cost_advanced.measurements import (
	KINDS,
	allocation_errors,
	apply_calculated_measurements,
	category_records,
	get_measurement_settings,
	item_measurement_master,
)


class LandedCostVoucherAdvanced(LandedCostVoucher):
	@frappe.whitelist()
	def get_items_from_purchase_receipts(self):
		super().get_items_from_purchase_receipts()
		self._fill_item_measurements(force=True)
		self.set_applicable_charges_on_item()

	def validate(self):
		self.validate_manual_distribution_methods()
		self._fill_item_measurements(force=False)
		super().validate()

	def on_submit(self):
		self.assert_allocation_possible()
		super().on_submit()

	@frappe.whitelist()
	def set_applicable_charges_on_item(self):
		if self.distribute_charges_based_on == "Distribute Manually":
			return
		precision = self._applicable_charges_precision()
		charges = allocate_taxes(
			self.get("items") or [],
			self.get("taxes") or [],
			self.distribute_charges_based_on,
			precision,
		)
		for item, charge in zip(self.get("items") or [], charges, strict=False):
			item.applicable_charges = charge

	def validate_applicable_charges_for_item(self):
		self.validate_manual_distribution_methods()
		if self.distribute_charges_based_on == "Distribute Manually" and len(self.taxes or []) > 1:
			frappe.throw(
				_(
					"Please keep one Applicable Charges, when 'Distribute Charges Based On' is 'Distribute Manually'. For more charges, please create another Landed Cost Voucher."
				)
			)

		self.assert_allocation_possible()

		total_applicable_charges = sum(flt(d.applicable_charges) for d in self.get("items"))
		precision = self._applicable_charges_precision()
		diff = flt(flt(self.total_taxes_and_charges) - flt(total_applicable_charges), precision)
		if abs(diff) < (2.0 / (10**precision)):
			if self.get("items"):
				self.items[-1].applicable_charges += diff
		else:
			frappe.throw(
				_(
					"Total Applicable Charges in Purchase Receipt Items table must be same as Total Taxes and Charges"
				)
			)

	def validate_manual_distribution_methods(self):
		if self.distribute_charges_based_on != "Distribute Manually":
			return
		explicit = explicit_methods_on_manual(self.get("taxes") or [])
		if not explicit:
			return
		rows = ", ".join(str(tax.get("idx") or "") for tax in explicit)
		frappe.throw(
			_(
				"Expense row {0} has its own distribution method. Distribute Manually applies to the whole voucher, so set every expense line to Default or change the voucher method."
			).format(rows)
		)

	def assert_allocation_possible(self):
		errors = allocation_errors(
			self.get("items") or [],
			self.get("taxes") or [],
			self.distribute_charges_based_on,
		)
		if errors:
			frappe.throw("<br>".join(errors), title=_("Cannot allocate landed cost"))

	def _fill_item_measurements(self, force):
		settings = get_measurement_settings()
		records_by_kind = {
			kind["method"]: category_records(settings.get(kind["category_field"])) for kind in KINDS
		}
		masters = {}
		for item in self.get("items") or []:
			if force:
				item.weight_edited = 0
				item.volume_edited = 0
			elif cint(item.get("weight_edited")) and cint(item.get("volume_edited")):
				continue
			code = item.item_code
			if code not in masters:
				masters[code] = item_measurement_master(code)
			apply_calculated_measurements(
				item, masters[code], settings, records_by_kind, force=force
			)

	def _applicable_charges_precision(self):
		currency = None
		if self.company:
			currency = frappe.get_cached_value("Company", self.company, "default_currency")
		precision = get_field_precision(
			frappe.get_meta("Landed Cost Item").get_field("applicable_charges"),
			currency=currency,
		)
		return precision if precision is not None else 2
