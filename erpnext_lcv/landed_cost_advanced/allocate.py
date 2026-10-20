# Copyright (c) 2026, Evgheni Nemerenco and Contributors
# License: GNU General Public License v3. See license.txt

"""Per-expense allocation into applicable_charges."""

from frappe.utils import flt

BASIS_FIELD = {
	"Qty": "qty",
	"Amount": "amount",
	"Weight": "total_weight",
	"Volume": "total_volume",
}


def resolve_method(line_method, voucher_method):
	"""Blank and Default follow the voucher method."""
	method = (line_method or "").strip() or "Default"
	if method == "Default":
		return voucher_method
	return method


def split_amount(amount, bases, precision):
	"""Split amount by bases. Remainder goes to the last non-zero basis.

	Returns None when every basis is zero so the caller can block submit.
	"""
	amount = flt(amount, precision)
	cleaned = [flt(b) for b in bases]
	if sum(cleaned) <= 0:
		return None

	last = max(i for i, basis in enumerate(cleaned) if basis > 0)
	shares = []
	allocated = 0.0
	total_basis = sum(cleaned)
	for i, basis in enumerate(cleaned):
		if i == last:
			share = flt(amount - allocated, precision)
		elif basis <= 0:
			share = 0.0
		else:
			share = flt(basis / total_basis * amount, precision)
			allocated = flt(allocated + share, precision)
		shares.append(share)
	return shares


def allocate_taxes(items, taxes, voucher_method, precision):
	"""Return a new applicable_charges list, one value per item.

	items need qty, amount, total_weight, total_volume.
	taxes need base_amount and distribution_method.
	Distribute Manually is not allocated here.
	An expense with a zero basis is skipped (its share stays 0).
	"""
	charges = [0.0 for _ in items]
	if voucher_method == "Distribute Manually":
		return [flt(item.get("applicable_charges"), precision) for item in items]

	for tax in taxes:
		method = resolve_method(tax.get("distribution_method"), voucher_method)
		if method == "Distribute Manually":
			continue
		fieldname = BASIS_FIELD[method]
		bases = [item.get(fieldname) for item in items]
		shares = split_amount(tax.get("base_amount"), bases, precision)
		if not shares:
			continue
		for index, share in enumerate(shares):
			charges[index] = flt(charges[index] + share, precision)
	return charges


def explicit_methods_on_manual(taxes):
	"""Line methods that are not blank or Default."""
	found = []
	for tax in taxes:
		method = (tax.get("distribution_method") or "").strip() or "Default"
		if method != "Default":
			found.append(tax)
	return found
