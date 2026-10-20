// Copyright (c) 2026, Evgheni Nemerenco and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("erpnext.stock");

function lcv_resolved_method(frm, tax) {
	let method = (tax.distribution_method || "Default").trim() || "Default";
	if (method === "Default") {
		method = frm.doc.distribute_charges_based_on;
	}
	return method;
}

function lcv_set_indicator(frm) {
	frm.set_indicator_formatter("item_code", function (doc) {
		const taxes = frm.doc.taxes || [];
		const needs_weight = taxes.some((tax) => lcv_resolved_method(frm, tax) === "Weight");
		const needs_volume = taxes.some((tax) => lcv_resolved_method(frm, tax) === "Volume");
		if (!needs_weight && !needs_volume) {
			return "green";
		}
		if (needs_weight && !(flt(doc.total_weight) > 0)) {
			return "red";
		}
		if (needs_volume && !(flt(doc.total_volume) > 0)) {
			return "red";
		}
		return "green";
	});
}

function lcv_help_html() {
	return `<br><br>
		<table class="table table-bordered" style="background-color: var(--scrollbar-track-color);">
			<tr><td>
				<h4>
					<i class="fa fa-hand-right"></i>
					${__("Notes")}:
				</h4>
				<ul>
					<li>
						${__("Charges will be distributed proportionately based on item qty, amount, weight, or volume, as per your selection")}
					</li>
					<li>
						${__("Each expense line has its own distribution method. Default uses the method selected on the voucher.")}
					</li>
					<li>
						${__("Remove item if charges is not applicable to that item")}
					</li>
					<li>
						${__("Charges are updated in Purchase Receipt against each item")}
					</li>
					<li>
						${__("Item valuation rate is recalculated considering landed cost voucher amount")}
					</li>
					<li>
						${__("Stock Ledger Entries and GL Entries are reposted for the selected Purchase Receipts")}
					</li>
				</ul>
			</td></tr>
		</table>`;
}

function lcv_refresh_indicator(frm) {
	lcv_set_indicator(frm);
	frm.refresh_field("items");
}

const lcv_refresh = erpnext.stock.LandedCostVoucher.prototype.refresh;
erpnext.stock.LandedCostVoucher.prototype.refresh = function () {
	lcv_refresh.apply(this, arguments);
	set_field_options("landed_cost_help", lcv_help_html());
	lcv_set_indicator(this.frm);
};

erpnext.stock.LandedCostVoucher.prototype.set_applicable_charges_for_item = function () {
	const frm = this.frm;
	if (!frm.doc.taxes || !frm.doc.taxes.length) {
		return;
	}
	if (frm.doc.distribute_charges_based_on === "Distribute Manually") {
		lcv_refresh_indicator(frm);
		return;
	}
	return frm.call({
		doc: frm.doc,
		method: "set_applicable_charges_on_item",
		callback() {
			lcv_refresh_indicator(frm);
		},
	});
};

frappe.ui.form.on("Landed Cost Voucher", {
	setup(frm) {
		lcv_set_indicator(frm);
	},
	refresh(frm) {
		lcv_set_indicator(frm);
	},
});

frappe.ui.form.on("Landed Cost Taxes and Charges", {
	distribution_method(frm) {
		frm.trigger("set_applicable_charges_for_item");
		lcv_refresh_indicator(frm);
	},
});

function lcv_apply_measurement(frm, cdt, cdn, force) {
	const row = locals[cdt][cdn];
	if (force) {
		row.weight_edited = 0;
		row.volume_edited = 0;
	}
	frappe.call({
		method: "erpnext_lcv.landed_cost_advanced.measurements.recalculate_item_row",
		args: {
			item_code: row.item_code,
			qty: row.qty,
			weight_edited: row.weight_edited ? 1 : 0,
			volume_edited: row.volume_edited ? 1 : 0,
		},
		callback(r) {
			if (!r.message) {
				return;
			}
			frappe.flags.lcv_filling_measurement = true;
			if (!row.weight_edited) {
				row.total_weight = r.message.total_weight;
				row.weight_uom = r.message.weight_uom;
			}
			if (!row.volume_edited) {
				row.total_volume = r.message.total_volume;
				row.volume_uom = r.message.volume_uom;
			}
			frappe.flags.lcv_filling_measurement = false;
			frm.refresh_field("items");
			frm.trigger("set_applicable_charges_for_item");
			lcv_refresh_indicator(frm);
		},
	});
}

frappe.ui.form.on("Landed Cost Item", {
	qty(frm, cdt, cdn) {
		lcv_apply_measurement(frm, cdt, cdn, false);
	},
	total_weight(frm, cdt, cdn) {
		if (frappe.flags.lcv_filling_measurement) {
			return;
		}
		locals[cdt][cdn].weight_edited = 1;
		frm.trigger("set_applicable_charges_for_item");
		lcv_refresh_indicator(frm);
	},
	total_volume(frm, cdt, cdn) {
		if (frappe.flags.lcv_filling_measurement) {
			return;
		}
		locals[cdt][cdn].volume_edited = 1;
		frm.trigger("set_applicable_charges_for_item");
		lcv_refresh_indicator(frm);
	},
	fill_weight_and_volume(frm, cdt, cdn) {
		lcv_apply_measurement(frm, cdt, cdn, true);
	},
});
