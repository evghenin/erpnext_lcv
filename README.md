# Landed Cost Advanced

Advanced landed cost allocation for [ERPNext](https://github.com/frappe/erpnext). Standard Landed Cost Vouchers spread every charge by one method for the whole document. This app keeps that voucher method and adds a distribution method on each expense line, plus weight-based and volume-based allocation.

Requires ERPNext. License: GPL-3.0.

## Features

### Per-expense distribution

`Distribute Charges Based On` on the Landed Cost Voucher gains two options, **Weight** and **Volume**, alongside the standard **Qty**, **Amount**, and **Distribute Manually**.

Each row in **Taxes and Charges** has its own **Distribution Method**:

| Method | How the charge is split |
| --- | --- |
| Default | Uses the method selected on the voucher |
| Amount | Share of each item's amount |
| Qty | Share of each item's quantity |
| Weight | Share of each item's total weight |
| Volume | Share of each item's total volume |

A freight line can be split by weight while a customs duty line on the same voucher is split by amount. Applicable charges are recalculated when the voucher method or a line method changes.

**Distribute Manually** still applies to the whole voucher. Expense lines must stay on **Default**. An explicit method on a line is rejected, because a manual split and an automatic one cannot be mixed. The standard ERPNext rule still applies: a manual voucher can have only one expense row.

### Weight and volume on items

Stock items already have **Weight Per Unit** and **Weight UOM**. The app adds **Volume Per Unit** and **Volume UOM**, shown for stock items.

A value and its UOM must be saved together. The UOM must belong to the category configured in Stock Settings (it must appear on a UOM Conversion Factor in that category). The Item form only offers UOMs from that category.

### Company measurement units

**Stock Settings → Inventory → Weight and Volume** stores:

- **Weight UOM Category** and **Weight Base UOM**
- **Volume UOM Category** and **Volume Base UOM**

Landed cost totals are stored in the base units. On install, empty settings are filled with **Mass / Kg** and **Volume / Litre** when those records already exist. Base UOM links only list units from the selected category.

### Filling landed cost rows

Purchase receipt items on a Landed Cost Voucher show **Total Weight**, **Weight UOM**, **Total Volume**, and **Volume UOM**. Totals are `quantity × per-unit measurement`, converted from the item UOM into the base UOM.

Conversion uses **UOM Conversion Factor** records for the configured category. Factors are read in both directions, and units that are not linked directly are converted through the category hub (for example Gram → Kg → Tonne).

- Pulling items from purchase receipts fills weight and volume and recalculates charges.
- Changing quantity recalculates a side that has not been edited by hand.
- Typing a total marks that side as edited. Later automatic fills leave it alone.
- **Fill weight and volume from Item** clears the edit flags and loads both sides from the item master again.

Item codes in the items table turn red when the current methods need a positive weight or volume and the row does not have one.

### Submit checks

Submit is blocked before stock and general ledger entries are updated when an automatic method cannot be applied:

- An item used by a weight or volume charge has no positive total, no per-unit value, no UOM, or no conversion into the base unit. The message names the item, the landed cost row, the expense row, the method, and the reason (including the missing UOM pair).
- Qty or amount charges have a zero total basis across all items.

A charge whose own basis is entirely zero is skipped during allocation (its share stays zero) until submit, which then refuses the voucher.

Rounding uses the currency precision of **Applicable Charges**. Each share is rounded, and the remainder is added to the last item that has a positive basis, so the allocated total matches the expense amount.

After a successful submit, ERPNext posts the voucher as usual: purchase receipt item costs, valuation rates, stock ledger entries, and general ledger entries are updated.

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app erpnext_lcv
```

Install creates the custom fields, extends the voucher distribution options, and sets the default weight and volume units when Mass, Kg, Volume, and Litre already exist.

Before allocating by weight or volume, confirm **Stock Settings** and make sure each stock item has a per-unit value and a UOM in the matching category.

## Contributing

This app uses [pre-commit](https://pre-commit.com/#installation) for formatting and linting:

```bash
cd apps/erpnext_lcv
pre-commit install
```

Hooks run ruff, eslint, prettier, and pyupgrade.

## License

GNU General Public License v3.0. See [license.txt](license.txt).
