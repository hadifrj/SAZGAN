# -*- coding: utf-8 -*-
"""مسیرهای عمومی تنظیمات: changelog/about/hub/system/geo/app-lists/help-tips/distance/calendar/products/parties/display/اصلی/company."""
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from flask import (
    request, session, redirect, render_template, jsonify, send_file, current_app
)

logger = logging.getLogger("sazgan")
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from io import BytesIO
import os, re, sqlite3, base64, time
import jdatetime
try:
    import openpyxl
except ImportError:
    openpyxl = None

from core.constants import *
from core import helpers as H


from core.helpers import *  # noqa: F401,F403
from core.constants import *  # noqa: F401,F403

from routes.settings_shared import _ensure_user_active_col


def register(app):
    @app.route('/settings/changelog')
    def settings_changelog():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        entries = load_changelog_entries()
        return render_template(
            'settings_changelog.html',
            active_page='settings-changelog',
            current_user=current_user,
            entries=entries,
        )


    @app.route('/settings/about')
    def settings_about():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'system')):
            return redirect('/')
        entries = []
        try:
            entries = load_changelog_entries()
        except Exception:
            entries = []
        return render_template(
            'settings_about.html',
            active_page='settings-about',
            current_user=current_user,
            entries=entries,
        )


    @app.route('/settings/hub')
    def settings_hub():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user)
                or user_has_access(current_user, 'parties')
                or user_has_access(current_user, 'system')
                or user_has_access(current_user, 'products')
                or user_has_access(current_user, 'wages_settings')):
            return redirect('/')
        import os as _os
        from core.constants import BASE_DIR, DB_NAME
        return render_template(
            'settings_hub.html',
            active_page='settings-hub',
            current_user=current_user,
            active_db_path=_os.path.join(BASE_DIR, DB_NAME),
            active_host=request.host,
        )


    @app.route('/settings/system')
    def settings_system():
        # اکنون بخشی از صفحه‌ی یکپارچه‌ی تنظیمات است.
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        return redirect('/settings/hub')



    @app.route('/settings/geo', methods=['GET'])
    def settings_geo():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'system')):
            return redirect('/')
        from core.geo import geo_stats, ensure_geo_schema
        conn = get_db()
        ensure_geo_schema(conn)
        stats = geo_stats(conn)
        try:
            from core.geo import get_geo_provinces
            provinces = get_geo_provinces(conn)
        except Exception:
            provinces = PROVINCES
        conn.close()
        dist_stats = {'with_coords': 0, 'total_cities': 0}
        road_factor = 1.3
        distance_method = 'haversine'
        osrm_url = 'https://router.project-osrm.org'
        try:
            from core.distance import (
                ensure_distance_schema, coords_stats, get_road_factor,
                get_distance_method, get_osrm_base_url,
            )
            dconn = get_db()
            ensure_distance_schema(dconn)
            dist_stats = coords_stats(dconn)
            road_factor = get_road_factor(dconn)
            distance_method = get_distance_method(dconn)
            osrm_url = get_osrm_base_url(dconn)
            dconn.close()
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        return render_template(
            'settings_geo.html',
            active_page='settings-geo',
            current_user=current_user,
            stats=stats,
            msg=request.args.get('msg'),
            error=request.args.get('error'),
            provinces=provinces,
            dist_stats=dist_stats,
            road_factor=road_factor,
            distance_method=distance_method,
            osrm_url=osrm_url,
        )




    @app.route('/settings/app-lists', methods=['GET', 'POST'])
    def settings_app_lists():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'system')):
            return redirect('/')

        from core.app_lists import (
            LIST_DEFINITIONS, ensure_app_lists_schema, seed_defaults_if_empty,
            get_list_items, add_item, update_item, delete_item, reset_list_to_defaults,
        )
        conn = get_db()
        ensure_app_lists_schema(conn)
        seed_defaults_if_empty(conn)

        msg = error = None
        active_key = (request.values.get('key') or request.form.get('list_key') or 'internal_repair_statuses').strip()
        if active_key not in LIST_DEFINITIONS:
            active_key = 'internal_repair_statuses'

        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            list_key = (request.form.get('list_key') or active_key).strip()
            active_key = list_key if list_key in LIST_DEFINITIONS else active_key
            try:
                if action == 'add':
                    ok, err = add_item(conn, list_key, request.form.get('value'))
                    if ok:
                        msg = 'گزینه اضافه شد'
                        write_audit(conn, current_user['full_name'], 'افزودن گزینه لیست', 'app_list', None, list_key)
                        conn.commit()
                    else:
                        error = err
                elif action == 'edit':
                    item_id = int(request.form.get('item_id') or 0)
                    ok, err = update_item(conn, item_id, value=request.form.get('value'))
                    if ok:
                        msg = 'ذخیره شد'
                    else:
                        error = err
                elif action == 'toggle':
                    item_id = int(request.form.get('item_id') or 0)
                    row = conn.execute('SELECT is_active FROM app_list_items WHERE id = ?', (item_id,)).fetchone()
                    if row:
                        ok, err = update_item(conn, item_id, is_active=0 if row['is_active'] else 1)
                        msg = 'وضعیت تغییر کرد' if ok else None
                        error = err
                elif action == 'delete':
                    item_id = int(request.form.get('item_id') or 0)
                    ok, err = delete_item(conn, item_id)
                    if ok:
                        msg = 'حذف شد'
                        write_audit(conn, current_user['full_name'], 'حذف گزینه لیست', 'app_list', item_id, list_key)
                        conn.commit()
                    else:
                        error = err
                elif action == 'reset':
                    ok, err = reset_list_to_defaults(conn, list_key)
                    if ok:
                        msg = 'به پیش‌فرض کارخانه بازنشانی شد'
                        write_audit(conn, current_user['full_name'], 'بازنشانی لیست', 'app_list', None, list_key)
                        conn.commit()
                    else:
                        error = err
            except Exception as e:
                error = str(e)

        items = get_list_items(conn, active_key)
        defn = LIST_DEFINITIONS.get(active_key)
        conn.close()
        return render_template(
            'settings_app_lists.html',
            active_page='settings-app-lists',
            current_user=current_user,
            definitions=LIST_DEFINITIONS,
            active_key=active_key,
            defn=defn,
            items=items,
            msg=msg,
            error=error,
        )




    @app.route('/settings/help-tips', methods=['GET', 'POST'])
    def settings_help_tips():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'system')):
            return redirect('/')

        from core.help_tips import list_help_tips, set_help_tip, HELP_TIP_CATALOG

        conn = get_db()
        msg = error = None

        if request.method == 'POST':
            if not _validate_csrf():
                error = 'خطای امنیتی CSRF'
            else:
                saved = 0
                for key in HELP_TIP_CATALOG.keys():
                    field = 'tip_' + key
                    if field in request.form:
                        set_help_tip(conn, key, request.form.get(field, ''))
                        saved += 1
                conn.commit()
                msg = 'راهنماها ذخیره شد.'

        tips = list_help_tips(conn)
        conn.close()
        return render_template(
            'settings_help_tips.html', tips=tips,
            current_user=current_user, active_page='settings',
            msg=msg, error=error,
        )


    @app.route('/settings/distance', methods=['POST'])
    def settings_distance():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'system')):
            return redirect('/')
        from core.distance import (
            ensure_distance_schema, coords_stats, seed_coordinates_from_json,
            get_road_factor, DEFAULT_ROAD_FACTOR,
        )
        from core.geo import get_geo_provinces
        import json, os
        from core.constants import BASE_DIR

        conn = get_db()
        ensure_distance_schema(conn)
        msg = error = None

        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            if action == 'seed_coords':
                coords_path = os.path.join(BASE_DIR, 'data', 'iran_city_coords.json')
                if not os.path.isfile(coords_path):
                    error = 'فایل مختصات پیدا نشد: data/iran_city_coords.json'
                else:
                    try:
                        with open(coords_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        updated, skipped, err = seed_coordinates_from_json(conn, data)
                        if err:
                            error = err
                        else:
                            msg = f'مختصات به‌روز شد: {updated} شهر — رد شده/بدون تطبیق: {skipped}'
                            try:
                                write_audit(conn, current_user['full_name'], 'بارگذاری مختصات شهرها', 'geo', None, msg)
                                conn.commit()
                            except Exception as e:
                                logger.exception("Silent exception in routes/settings.py")
                    except Exception as e:
                        error = str(e)
            elif action == 'set_factor':
                try:
                    f = float(request.form.get('road_factor') or DEFAULT_ROAD_FACTOR)
                    if not (1.0 <= f <= 2.5):
                        error = 'ضریب باید بین ۱ و ۲٫۵ باشد'
                    else:
                        set_setting(conn, 'distance_road_factor', str(f))
                        conn.commit()
                        msg = f'ضریب جاده روی {f} تنظیم شد'
                except Exception as e:
                    error = str(e)
            elif action == 'set_method':
                method = (request.form.get('distance_method') or 'haversine').strip().lower()
                if method in ('1', 'haversine'):
                    method = 'haversine'
                elif method in ('2', 'osrm'):
                    method = 'osrm'
                else:
                    error = 'روش نامعتبر است'
                    method = None
                if method:
                    set_setting(conn, 'distance_method', method)
                    osrm_url = (request.form.get('osrm_url') or '').strip()
                    if osrm_url:
                        set_setting(conn, 'distance_osrm_url', osrm_url.rstrip('/'))
                    conn.commit()
                    label = 'تقریبی (هوایی × ضریب)' if method == 'haversine' else 'مسیر جاده‌ای OSRM'
                    msg = f'روش محاسبه مسافت: {label}'

        conn.close()
        from urllib.parse import quote
        q = []
        if msg: q.append('msg=' + quote(msg))
        if error: q.append('error=' + quote(error))
        return redirect('/settings/geo' + (('?' + '&'.join(q)) if q else ''))



    @app.route('/settings/calendar', methods=['GET', 'POST'])
    def settings_calendar():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'system')):
            return redirect('/')
        conn = get_db()
        msg = error = None
        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            if action == 'add':
                ok, info = add_calendar_holiday(conn, request.form.get('holiday_date'), request.form.get('title'))
                if ok:
                    write_audit(conn, current_user['full_name'], 'افزودن تعطیلی تقویم', 'calendar', None, info)
                    conn.commit()
                    msg = 'تعطیلی ثبت شد.'
                else:
                    error = info
            elif action == 'delete':
                hid = request.form.get('holiday_id')
                if delete_calendar_holiday(conn, hid):
                    write_audit(conn, current_user['full_name'], 'حذف تعطیلی تقویم', 'calendar', hid, None)
                    conn.commit()
                    msg = 'تعطیلی حذف شد.'
                else:
                    error = 'حذف ناموفق بود.'
        holidays = list_calendar_holidays(conn)
        conn.close()
        return render_template(
            'settings_calendar.html',
            active_page='settings-calendar',
            current_user=current_user,
            holidays=holidays,
            msg=msg,
            error=error,
        )



    @app.route('/settings/products')
    def settings_products():
        # اکنون بخشی از صفحه‌ی یکپارچه‌ی تنظیمات است.
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        return redirect('/settings/hub')


    @app.route('/settings/parties')
    def settings_parties():
        # اکنون بخشی از صفحه‌ی یکپارچه‌ی تنظیمات است.
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        return redirect('/settings/hub')


    @app.route('/settings/display')
    def settings_display():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        return render_template(
            'settings_display.html',
            active_page='settings-display',
            current_user=current_user,
        )








    @app.route('/settings', methods=['GET', 'POST'])
    def settings():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        error = None
        if request.method == 'POST':
            role = request.form['role']
            username = request.form['username']
            password = request.form['password']

            conn = get_db()
            existing = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()

            if existing:
                error = 'این نام کاربری قبلاً استفاده شده است.'
            elif role == 'تکنسین استانی':
                representative_id = request.form.get('representative_id')
                rep = conn.execute('SELECT * FROM representatives WHERE id = ?', (representative_id,)).fetchone() if representative_id else None
                if not rep:
                    error = 'لطفاً یک نماینده را انتخاب کنید.'
                else:
                    if rep['rep_type'] == 'حقوقی' and rep['company_name']:
                        full_name = rep['company_name']
                    else:
                        full_name = f"{rep['first_name']} {rep['last_name']}"
                    _created_at = jdatetime.date.today().togregorian().isoformat()
                    conn.execute(
                        'INSERT INTO users (full_name, username, password_hash, role, province, representative_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (full_name, username, generate_password_hash(password), role, rep['province'], rep['id'], _created_at)
                    )
                    conn.commit()
            else:
                full_name = request.form['full_name']
                _created_at = jdatetime.date.today().togregorian().isoformat()
                conn.execute(
                    'INSERT INTO users (full_name, username, password_hash, role, province, representative_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (full_name, username, generate_password_hash(password), role, None, None, _created_at)
                )
                conn.commit()

            if error:
                try:
                    _ensure_user_active_col(conn)
                except Exception as e:
                    logger.exception("Silent exception in routes/settings.py")
                users_list = conn.execute('SELECT * FROM users WHERE IFNULL(is_active,1)=1 ORDER BY id DESC').fetchall()
                reps_list = conn.execute("SELECT * FROM representatives WHERE status = 'فعال' ORDER BY first_name").fetchall()
                try:
                    _roles = roles_list(conn) if roles_list else ROLES
                except Exception:
                    _roles = ROLES
                try:
                    _provinces = get_geo_provinces(conn) if get_geo_provinces else PROVINCES
                except Exception:
                    _provinces = PROVINCES
                conn.close()
                return render_template(
                    'settings.html', users=users_list, roles=_roles, provinces=_provinces,
                    representatives=reps_list,
                    active_page='settings', current_user=current_user, error=error
                )
            conn.close()
            return redirect('/settings')

        conn = get_db()
        try:
            _ensure_user_active_col(conn)
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        users_list = conn.execute('SELECT * FROM users WHERE IFNULL(is_active,1)=1 ORDER BY id DESC').fetchall()
        reps_list = conn.execute("SELECT * FROM representatives WHERE status = 'فعال' ORDER BY first_name").fetchall()
        try:
            _roles = roles_list(conn) if roles_list else ROLES
        except Exception:
            _roles = ROLES
        try:
            _provinces = get_geo_provinces(conn) if get_geo_provinces else PROVINCES
        except Exception:
            _provinces = PROVINCES
        conn.close()

        return render_template(
            'settings.html', users=users_list, roles=_roles, provinces=_provinces,
            representatives=reps_list,
            active_page='settings', current_user=current_user, error=None
        )





    @app.route('/settings/company', methods=['GET', 'POST'])
    def settings_company():
        current_user = get_current_user()
        from core.access import is_system_admin as _isa
        if not current_user or (current_user['role'] not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم') and not _isa(current_user)):
            return redirect('/')
        conn = get_db()
        if request.method == 'POST':
            set_setting(conn, 'company_name', request.form.get('company_name', ''))
            set_setting(conn, 'company_mobile', request.form.get('company_mobile', ''))
            set_setting(conn, 'company_phone', request.form.get('company_phone', ''))
            set_setting(conn, 'company_address', request.form.get('company_address', ''))
            set_setting(conn, 'company_postal_code', request.form.get('company_postal_code', ''))
            if request.form.get('remove_company_logo') == '1':
                set_setting(conn, 'company_logo', '')
            logo = request.files.get('company_logo_file')
            if logo and logo.filename:
                ext = logo.filename.rsplit('.', 1)[-1].lower() if '.' in logo.filename else ''
                if ext in ALLOWED_PHOTO_EXTENSIONS:
                    os.makedirs(COMPANY_UPLOAD_FOLDER, exist_ok=True)
                    filename = secure_filename(f'company_logo_{int(time.time())}.{ext}')
                    save_uploaded_image(logo, os.path.join(COMPANY_UPLOAD_FOLDER, filename))
                    set_setting(conn, 'company_logo', filename)
            write_audit(conn, current_user['full_name'], 'به‌روزرسانی تنظیمات شرکت', 'settings', None, None)
            conn.commit()
            conn.close()
            try:
                from core.helpers import _COMPANY_CACHE
                _COMPANY_CACHE['ts'] = 0
            except Exception as e:
                logger.exception("Silent exception in routes/settings.py")
            return redirect('/settings/company')
        data = {
            'company_name': get_setting(conn, 'company_name', 'سازگان گستر'),
            'company_mobile': get_setting(conn, 'company_mobile', ''),
            'company_phone': get_setting(conn, 'company_phone', ''),
            'company_address': get_setting(conn, 'company_address', ''),
            'company_postal_code': get_setting(conn, 'company_postal_code', ''),
            'company_logo': get_setting(conn, 'company_logo', ''),
        }
        conn.close()
        return render_template('settings_company.html', data=data, current_user=current_user, active_page='settings')



