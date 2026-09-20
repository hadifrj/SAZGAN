# -*- coding: utf-8 -*-
"""تست دود: import هسته + ساخت جداول + مسیرهای حیاتی + ماژول‌های جدید."""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)


def main():
    errors = []
    # 1) imports
    try:
        from core import constants, access, jalali, security, stock, request_utils, cartable
        from core import helpers as H
        from core import control_warehouses as CW
        print('[ok] core imports (incl. request_utils, cartable, control_warehouses)')
    except Exception as e:
        print('[fail] core imports:', e)
        return 1

    # 2) jalali
    try:
        assert H._parse_jalali('1405/01/01') is not None
        assert H._now_jalali_str().startswith('14')
        from core.jalali import days_since, add_jalali_months
        assert days_since('1400/01/01') is not None
        assert add_jalali_months('1405/01/15', 1) is not None
        print('[ok] jalali')
    except Exception as e:
        errors.append(('jalali', e))
        print('[fail] jalali:', e)

    # 3) access
    try:
        from core.access import (
            DEFAULT_ROLE_ACCESS, module_for_path, enforce_path_access,
            user_has_access, ACCESS_MODULES,
        )
        assert module_for_path('/settings/calendar') == 'system'
        assert module_for_path('/login') is None
        u = {'role': 'امور مالی'}
        assert enforce_path_access(u, '/finance/cases') is True
        assert enforce_path_access(u, '/settings/system') is False
        assert user_has_access({'role': 'مدیر سیستم'}, 'system') is True
        assert len(ACCESS_MODULES) >= 8
        print('[ok] access')
    except Exception as e:
        errors.append(('access', e))
        print('[fail] access:', e)

    # 4) request_utils
    try:
        from core.request_utils import (
            request_detail_url, split_open_closed, filter_rows, enrich_delay,
        )
        fake = {
            'id': 1,
            'request_category': 'تعمیر',
            'service_type': 'کارخانه',
            'request_subtype': '',
            'status': 'پایان تعمیرات',
            'province': 'تهران',
            'is_delayed': False,
        }
        assert '/service/internal-repair/view/1' in request_detail_url(fake)
        open_r, closed_r = split_open_closed([fake])
        assert len(closed_r) == 1 and len(open_r) == 0
        assert len(filter_rows([fake], province='تهران')) == 1
        assert len(filter_rows([fake], province='اصفهان')) == 0
        # helpers re-export
        assert callable(H._request_detail_url)
        assert callable(H._enrich_delay)
        print('[ok] request_utils')
    except Exception as e:
        errors.append(('request_utils', e))
        print('[fail] request_utils:', e)

    # 4b) cartable
    try:
        from core.cartable import get_qc_tasks, get_technician_tasks, get_finance_tasks
        assert callable(H._get_qc_tasks) and callable(H._get_technician_tasks)
        print('[ok] cartable')
    except Exception as e:
        errors.append(('cartable', e))
        print('[fail] cartable:', e)

    # 5) control_warehouses (core + stub)
    try:
        from core.control_warehouses import ensure_control_wh_schema, register_control_warehouse_routes
        import control_warehouses as stub
        assert callable(stub.ensure_control_wh_schema)
        assert callable(CW.entry_internal)
        print('[ok] control_warehouses core + stub')
    except Exception as e:
        errors.append(('control_warehouses', e))
        print('[fail] control_warehouses:', e)

    # 6) security secret
    try:
        from core.security import load_or_create_secret
        k = load_or_create_secret()
        assert k and len(k) >= 16
        print('[ok] security secret')
    except Exception as e:
        errors.append(('security', e))
        print('[fail] security:', e)

    # 7) init_db (temp cwd so DB is isolated)
    try:
        tmp = tempfile.mkdtemp(prefix='sazgan_smoke_')
        prev = os.getcwd()
        os.chdir(tmp)
        try:
            H.init_db()
            conn = H.get_db()
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            # control warehouse tables
            try:
                from core.control_warehouses import ensure_control_wh_schema
                ensure_control_wh_schema(conn)
            except Exception:
                pass
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            conn.close()
            need = {
                'requests', 'users', 'app_settings', 'calendar_holidays',
                'control_stock_internal', 'control_stock_external', 'warehouse_vouchers',
            }
            missing = need - tables
            if missing:
                raise RuntimeError('missing tables: ' + str(missing))
            print('[ok] init_db tables (+ control warehouse)')
        finally:
            os.chdir(prev)
    except Exception as e:
        errors.append(('init_db', e))
        print('[fail] init_db:', e)

    # 8) templates critical files exist
    try:
        tpl = os.path.join(ROOT, 'templates')
        required = [
            'view_representative.html',
            'view_user.html',
            'login.html',
            'warehouse_internal.html',
            'warehouse_external.html',
        ]
        missing = [f for f in required if not os.path.isfile(os.path.join(tpl, f))]
        empty = [
            f for f in required
            if os.path.isfile(os.path.join(tpl, f)) and os.path.getsize(os.path.join(tpl, f)) == 0
        ]
        if missing or empty:
            raise RuntimeError(f'missing={missing} empty={empty}')
        print('[ok] critical templates present')
    except Exception as e:
        errors.append(('templates', e))
        print('[fail] templates:', e)

    # 9) Flask app routes
    try:
        from app import app
        client = app.test_client()
        r = client.get('/login')
        assert r.status_code == 200
        r2 = client.get('/health')
        print('[ok] flask login page', r.status_code, 'health', getattr(r2, 'status_code', None))
    except Exception as e:
        errors.append(('flask', e))
        print('[fail] flask:', e)

    # 10) compatibility stubs
    try:
        import features_compat  # noqa: F401
        import improvements_compat  # noqa: F401
        print('[ok] compatibility stubs')
    except Exception as e:
        errors.append(('stubs', e))
        print('[fail] stubs:', e)

    if errors:
        print('SMOKE FAIL', len(errors))
        for name, err in errors:
            print(' -', name, ':', err)
        return 1
    print('SMOKE PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
