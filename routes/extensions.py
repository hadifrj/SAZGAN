# -*- coding: utf-8 -*-
"""ثبت متمرکز افزونه‌ها و schemaهای جانبی."""
from __future__ import annotations
import os


def _build_helpers_dict(H):
    return {
        'get_db': H.get_db,
        'get_current_user': H.get_current_user,
        'write_audit': getattr(H, 'write_audit', lambda *a, **k: None),
        'create_backup': H.create_backup,
        'DELAY_THRESHOLD_DAYS': getattr(H, 'DELAY_THRESHOLD_DAYS', 3),
        'PROVINCES': __import__('core.constants', fromlist=['PROVINCES']).PROVINCES,
        'FINANCE_ROLE': __import__('core.constants', fromlist=['FINANCE_ROLE']).FINANCE_ROLE,
        'JALALI_MONTHS': __import__('core.constants', fromlist=['JALALI_MONTHS']).JALALI_MONTHS,
    }


def init_extension_schemas(H):
    """ایجاد/مهاجرت جداول افزونه‌ها."""
    ensure_improvements_schema = None
    ensure_features_schema = None
    ensure_control_wh_schema = None
    try:
        from routes.improvements import ensure_improvements_schema
    except Exception as e:
        print('[extensions] improvements schema import:', e)
    try:
        from routes.features import ensure_features_schema
    except Exception as e:
        print('[extensions] features schema import:', e)
    try:
        from core.control_warehouses import ensure_control_wh_schema
    except Exception as e:
        print('[extensions] control_wh schema import:', e)

    conn = H.get_db()
    try:
        if ensure_improvements_schema:
            try:
                ensure_improvements_schema(conn)
            except Exception as e:
                print('ensure_improvements_schema:', e)
        if ensure_features_schema:
            try:
                ensure_features_schema(conn)
            except Exception as e:
                print('ensure_features_schema:', e)
        if ensure_control_wh_schema:
            try:
                ensure_control_wh_schema(conn)
            except Exception as e:
                print('ensure_control_wh_schema:', e)
        conn.commit()
    except Exception as e:
        print('schema init:', e)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def register_extension_routes(app, H):
    """ثبت routeهای افزونه (به‌جز انبار کنترلی که در routes.warehouse است)."""
    Hd = _build_helpers_dict(H)

    try:
        from routes.improvements import register_improvements
        register_improvements(app, H.get_db, H.get_current_user, Hd)
    except Exception as e:
        print('[extensions] improvements routes:', e)

    try:
        from routes.features import register_feature_routes
        register_feature_routes(app, H.get_db, H.get_current_user)
    except Exception as e:
        print('[extensions] features routes:', e)

    try:
        # نکته: چون هم‌زمان app.py (فایل) و app/ (پوشه) در ریشه‌ی پروژه با یک نام
        # وجود دارند، import عادی «app.feature_extensions» هیچ‌وقت کار نمی‌کند
        # (پایتون app را به‌عنوان ماژول app.py می‌شناسد، نه پکیج) — بارگذاری مستقیم
        # از مسیر فایل با importlib این تداخل نام را دور می‌زند.
        import importlib.util
        _fe_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'feature_extensions.py')
        _fe_spec = importlib.util.spec_from_file_location('sazgan_app_feature_extensions', _fe_path)
        _fe_mod = importlib.util.module_from_spec(_fe_spec)
        _fe_spec.loader.exec_module(_fe_mod)
        _fe_mod.register_extensions(app, Hd)
    except Exception as e:
        print('[extensions] feature_extensions:', e)

    try:
        import importlib.util
        _ve_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'voucher_export.py')
        _ve_spec = importlib.util.spec_from_file_location('sazgan_app_voucher_export', _ve_path)
        _ve_mod = importlib.util.module_from_spec(_ve_spec)
        _ve_spec.loader.exec_module(_ve_mod)
        _ve_mod.register_voucher_export_routes(app, H.get_db, H.get_current_user)
    except Exception as e:
        # فایل ممکن است نباشد
        if 'No module named' not in str(e) and 'cannot import' not in str(e).lower():
            print('[extensions] voucher:', e)


def init_all_extensions(app, H):
    init_extension_schemas(H)
    register_extension_routes(app, H)
