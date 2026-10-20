# Copyright (c) 2026, Evgheni Nemerenco and Contributors
# License: GNU General Public License v3. See license.txt

from erpnext_lcv.landed_cost_advanced.custom_fields import ensure_customizations, set_default_stock_settings


def after_install():
	ensure_customizations()
	set_default_stock_settings()
