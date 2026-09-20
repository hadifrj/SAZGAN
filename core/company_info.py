# -*- coding: utf-8 -*-
"""اطلاعات شرکت فقط از تنظیمات — منبع واحد برای چاپ‌ها."""
from __future__ import annotations

from typing import Any, Dict


def get_company_info(conn) -> Dict[str, Any]:
    try:
        from core.db import get_setting
    except Exception:
        def get_setting(c, k, d=''):
            try:
                row = c.execute('SELECT value FROM app_settings WHERE key=?', (k,)).fetchone()
                return row[0] if row else d
            except Exception:
                return d
    return {
        'company_name': get_setting(conn, 'company_name', '') or '',
        'company_address': get_setting(conn, 'company_address', '') or '',
        'company_postal_code': get_setting(conn, 'company_postal_code', '') or '',
        'company_phone': get_setting(conn, 'company_phone', '') or '',
        'company_mobile': get_setting(conn, 'company_mobile', '') or '',
        'company_logo': get_setting(conn, 'company_logo', '') or '',
    }
