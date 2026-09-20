# -*- coding: utf-8 -*-
"""سازگاری: منطق انبار کنترلی به core.control_warehouses منتقل شد."""
from core.control_warehouses import *  # noqa: F401,F403
from core.control_warehouses import (  # noqa: F401
    ensure_control_wh_schema,
    register_control_warehouse_routes,
    entry_internal,
    exit_internal_final_report,
    entry_external_province,
    transfer_external_to_rep,
    exit_external_from_report,
    exit_unused_from_rep,
    write_voucher_rows,
)
