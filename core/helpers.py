# -*- coding: utf-8 -*-
"""توابع مشترک هسته سامانه."""
from __future__ import annotations

import os
import re
import time
import secrets
import shutil
import threading
import sqlite3
import base64
import logging
from datetime import timedelta
from functools import wraps
from io import BytesIO

from flask import (
    Flask, request, session, redirect, render_template,
    jsonify, send_file, g, current_app, has_request_context,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jdatetime

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    from PIL import Image as _PILImage, ImageOps as _PILImageOps
except ImportError:
    _PILImage = None
    _PILImageOps = None

IMAGE_RESIZE_MAX_DIMENSION = 1600
IMAGE_RESIZE_JPEG_QUALITY = 82
_IMAGE_RESIZE_EXTENSIONS = {'png', 'jpg', 'jpeg'}


def save_uploaded_image(source, dest_path, max_dimension=IMAGE_RESIZE_MAX_DIMENSION,
                         quality=IMAGE_RESIZE_JPEG_QUALITY):
    """ذخیره تصویر آپلودی روی دیسک با کوچک‌سازی و فشرده‌سازی سمت سرور.

    source می‌تواند یک FileStorage (از request.files) یا bytes خام باشد.
    پسوند dest_path تعیین می‌کند خروجی jpg/jpeg یا png ذخیره شود؛ فرمت‌های
    غیرتصویری (pdf, docx, ...) بدون تغییر و خام ذخیره می‌شوند.
    در صورت نبود Pillow یا هر خطای غیرمنتظره، به ذخیره خام فایل برمی‌گردد
    تا آپلود کاربر هیچ‌وقت با شکست مواجه نشود.
    """
    if hasattr(source, 'read'):
        try:
            if hasattr(source, 'stream'):
                source.stream.seek(0)
        except Exception:
            pass
        raw = source.read()
    else:
        raw = source

    ext = dest_path.rsplit('.', 1)[-1].lower() if '.' in dest_path else ''

    if _PILImage is not None and ext in _IMAGE_RESIZE_EXTENSIONS:
        try:
            img = _PILImage.open(BytesIO(raw))
            img = _PILImageOps.exif_transpose(img)
            w, h = img.size
            if max(w, h) > max_dimension:
                scale = max_dimension / float(max(w, h))
                new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
                img = img.resize(new_size, _PILImage.LANCZOS)
            if ext in ('jpg', 'jpeg'):
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGBA')
                    bg = _PILImage.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1])
                    img = bg
                else:
                    img = img.convert('RGB')
                img.save(dest_path, 'JPEG', quality=quality, optimize=True)
            else:
                img.save(dest_path, 'PNG', optimize=True)
            return True
        except Exception:
            pass  # هر مشکلی پیش بیاد، به ذخیره خام زیر برمی‌گردیم

    with open(dest_path, 'wb') as fh:
        fh.write(raw)
    return True

from core.constants import *
try:
    from core.geo import get_geo_provinces
except Exception:
    get_geo_provinces = None  # noqa: F401,F403
try:
    from core.app_lists import roles_list
except Exception:
    roles_list = None  # noqa: F401,F403
from core.security import (
    load_or_create_secret as _load_or_create_secret,
    client_ip as _client_ip,
    login_is_locked as _login_is_locked,
    login_register_failure as _login_register_failure,
    login_clear_failures as _login_clear_failures,
    ensure_csrf_token as _ensure_csrf_token,
    validate_csrf as _validate_csrf,
    security_headers as _security_headers,
)
from core.jalali import (
    parse_jalali as _parse_jalali,
    add_jalali_months as _add_jalali_months,
    days_since as _days_since,
    now_jalali_str as _now_jalali_str,
    compute_warranty_status as _compute_warranty_status,
    enrich_warranty_row as _enrich_warranty_row,
)
from core.constants import (
    BASE_DIR, SECRET_FILE, BACKUP_DIR, UPLOAD_FOLDER, DB_NAME,
    MAX_LOGIN_ATTEMPTS, LOGIN_WINDOW_SEC, LOGIN_LOCKOUT_SEC,
    DELAY_THRESHOLD_DAYS, FINANCE_ROLE, PROVINCES,
    JALALI_MONTHS, JALALI_WEEKDAYS, ROLES, CLOSED_STATUSES, CLOSED_REQUEST_STATUSES, ADMIN_ROLES, FINANCE_ROLES,
)

# will be set from constants extraction




# backup → core.backup
from core.backup import create_backup, _backup_scheduler


def _security_before_request():
    from core.security import security_before_request as _sb
    return _sb(get_current_user=get_current_user)




def _security_headers(response):
    from core.security import security_headers as _sh
    return _sh(response)



def _is_finance_role(user):
    if not user:
        return False
    r = user.get('role') if isinstance(user, dict) else user['role']
    try:
        from core.constants import FINANCE_ROLES as _FR
        return r in _FR
    except Exception:
        return r == 'امور مالی'




def _is_finance(user):
    return _is_finance_role(user)




def _is_reception(user):
    if not user:
        return False
    r = user.get('role') if isinstance(user, dict) else user['role']
    try:
        from core.constants import ADMIN_ROLES as _AR
        return r in _AR or r == 'مسئول پذیرش'
    except Exception:
        return r in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم')






def _apply_proforma_decision(conn, request_id, decision, user_name=None, note=''):
    """تصمیم پیش‌فاکتور از مسیر واحد Workflow انجام می‌شود."""
    from core.workflow import transition_request, WorkflowError
    decision = (decision or '').strip().lower()
    req = conn.execute('SELECT * FROM requests WHERE id = ?', (request_id,)).fetchone()
    if not req:
        return None
    stype = req['service_type'] if 'service_type' in req.keys() else ''
    cat = req['request_category'] if 'request_category' in req.keys() else ''
    if cat != 'تعمیر' or stype not in ('کارخانه', 'در محل'):
        return None
    if (req['status'] or '') != 'در انتظار دریافت تاییدیه پیش‌فاکتور است':
        return None

    if decision in ('1', 'approve', 'approved', 'yes', 'تایید', 'تأیید'):
        next_st = 'در انتظار ارسال حواله است' if stype == 'در محل' else 'در انتظار ارسال حواله تعمیر نهایی است'
        try:
            transition_request(conn, request_id, next_st, actor_name=user_name, note=note or 'تأیید پیش‌فاکتور')
        except WorkflowError:
            return None
        conn.execute('UPDATE requests SET proforma_confirmed = 1 WHERE id = ?', (request_id,))
        try:
            _set_stage_date(conn, request_id, next_st, None, note or 'تأیید پیش‌فاکتور')
            write_audit(conn, user_name, 'تأیید پیش‌فاکتور', 'request', request_id, note or '')
        except Exception:
            logging.getLogger('sazgan').exception('proforma approval audit failed for request %s', request_id)
        return 'approved'

    if decision in ('2', 'reject', 'rejected', 'no', 'رد'):
        reject_st = 'پیش‌فاکتور رد شد — درخواست لغو شد' if stype == 'در محل' else PROFORMA_REJECT_STATUS
        audit_msg = ('رد پیش‌فاکتور — لغو خودکار درخواست تعمیر خارجی' if stype == 'در محل'
                     else note or 'دستگاه به پذیرش برای ارسال به مشتری')
        try:
            transition_request(conn, request_id, reject_st, actor_name=user_name, note=note or audit_msg)
        except WorkflowError:
            return None
        conn.execute('UPDATE requests SET proforma_confirmed = 2 WHERE id = ?', (request_id,))
        try:
            _set_stage_date(conn, request_id, reject_st, None, note or audit_msg)
            write_audit(conn, user_name, 'رد پیش‌فاکتور', 'request', request_id, audit_msg)
        except Exception:
            logging.getLogger('sazgan').exception('proforma rejection audit failed for request %s', request_id)
        return 'rejected'
    return None



def _can_full_edit(user):
    return _is_reception(user)




def _finance_allowed_statuses_for(req):
    if isinstance(req, dict):
        cat = req.get('request_category') or ''
        stype = req.get('service_type') or ''
    else:
        cat = req['request_category'] if 'request_category' in req.keys() else ''
        stype = req['service_type'] if 'service_type' in req.keys() else ''
    if cat == 'تعمیر' and stype == 'کارخانه':
        return FINANCE_INTERNAL_STATUSES
    if cat == 'تعمیر' and stype == 'در محل':
        return FINANCE_EXTERNAL_STATUSES
    if cat == 'بررسی و بازدید':
        return FINANCE_VISIT_STATUSES
    return set(FINANCE_INTERNAL_STATUSES) | set(FINANCE_EXTERNAL_STATUSES) | set(FINANCE_VISIT_STATUSES)













# db → core.db
from core.db import get_db, init_db, get_setting, set_setting

# request utils → core.request_utils (re-export for compatibility)
from core.request_utils import search_rows as _search_rows
from core.request_utils import (
    request_detail_url as _request_detail_url,
    split_open_closed as _split_open_closed,
    stage_date_for_status as _stage_date_for_status,
    enrich_delay as _enrich_delay,
    filter_by_date_range as _filter_by_date_range,
    filter_rows as _filter_rows,
)

from core.cartable import (
    get_finance_tasks as _get_finance_tasks,
    get_qc_tasks as _get_qc_tasks,
    get_technician_tasks as _get_technician_tasks,
)



_FORM_LOOKUP_CACHE = {'ts': 0.0, 'data': None}
_FORM_LOOKUP_CACHE_TTL = 30.0

def _form_lookup_context(conn=None):
    """داده مشترک فرم‌های ثبت با کش کوتاه‌مدت و کش per-request.

    این داده‌ها در بسیاری از فرم‌های ثبت تکرار می‌شوند. قبل از این اصلاح،
    هر بازشدن فرم چند SELECT کامل روی customers/users/devices/parts اجرا می‌کرد.
    کش ۳۰ ثانیه‌ای فقط داده‌های lookup را نگه می‌دارد و پس از آن خودکار تازه می‌شود؛
    بنابراین رفتار کسب‌وکار و داده‌های فرم تغییر نمی‌کند.
    """
    from flask import g, has_request_context
    if has_request_context() and getattr(g, '_sazgan_form_lookup_context', None) is not None:
        return g._sazgan_form_lookup_context

    import time as _time
    now = _time.time()
    cached = _FORM_LOOKUP_CACHE.get('data')
    if cached is not None and (now - _FORM_LOOKUP_CACHE.get('ts', 0.0)) < _FORM_LOOKUP_CACHE_TTL:
        data = cached
        if has_request_context():
            g._sazgan_form_lookup_context = data
        return data

    close = False
    if conn is None:
        conn = get_db()
        close = True
    customers = conn.execute('SELECT id, name, province, city FROM customers ORDER BY name').fetchall()
    technicians_factory = conn.execute(
        "SELECT id, full_name, role, province FROM users WHERE role = 'تکنسین کارخانه' AND IFNULL(is_active,1)=1 ORDER BY full_name"
    ).fetchall()
    technicians_prov = conn.execute(
        "SELECT id, full_name, role, province FROM users WHERE role = 'تکنسین استانی' AND IFNULL(is_active,1)=1 ORDER BY full_name"
    ).fetchall()
    device_types = conn.execute('SELECT DISTINCT device_type FROM devices ORDER BY device_type').fetchall()
    parts_catalog = conn.execute('SELECT id, warehouse_code, part_name, device_type FROM parts ORDER BY part_name').fetchall()
    today = jdatetime.date.today()
    data = {
        'customers': customers,
        'technicians_factory': technicians_factory,
        'technicians_prov': technicians_prov,
        'device_types': device_types,
        'parts_catalog': parts_catalog,
        'provinces': PROVINCES,
        'jalali_months': JALALI_MONTHS,
        'today_year': today.year,
        'today_month': today.month,
        'today_day': today.day,
    }
    if close:
        conn.close()
    _FORM_LOOKUP_CACHE.update(ts=now, data=data)
    if has_request_context():
        g._sazgan_form_lookup_context = data
    return data




def _is_embed():
    try:
        return str(request.args.get('embed', '')).lower() in ('1', 'true', 'yes')
    except Exception:
        return False





def resolve_technician(conn, form_value, expected_role=None, province=None):
    """از مقدار فرم (نام یا id) → تکنسین/نماینده‌ی فعال معتبر."""
    val = (form_value or '').strip()
    if not val:
        return None, None
    params = []
    where = ['IFNULL(is_active,1)=1']
    if expected_role:
        if isinstance(expected_role, (tuple, list, set)):
            where.append('role IN (%s)' % ','.join('?' for _ in expected_role))
            params.extend(list(expected_role))
        else:
            where.append('role=?'); params.append(expected_role)
    if province:
        where.append('(province=? OR province IS NULL OR TRIM(province)=\'\')')
        params.append(province)
    if val.isdigit():
        where.insert(0, 'id=?')
        params.insert(0, int(val))
    else:
        where.insert(0, 'full_name=?')
        params.insert(0, val)
    row = conn.execute(
        'SELECT id, full_name FROM users WHERE ' + ' AND '.join(where) + ' ORDER BY id LIMIT 1',
        tuple(params),
    ).fetchone()
    if not row:
        raise ValueError('تکنسین/نماینده انتخاب‌شده معتبر، فعال یا متناسب با نوع پرونده نیست.')
    return row['id'], row['full_name']


def sync_request_technician(conn, request_id, form_value, expected_role=None, province=None):
    """تنظیم هم‌زمان assigned_technician و assigned_technician_id."""
    tid, tname = resolve_technician(conn, form_value, expected_role=expected_role, province=province)
    try:
        cols = {r[1] for r in conn.execute('PRAGMA table_info(requests)').fetchall()}
    except Exception:
        cols = set()
    if 'assigned_technician_id' in cols:
        conn.execute(
            'UPDATE requests SET assigned_technician = ?, assigned_technician_id = ? WHERE id = ?',
            (tname, tid, request_id)
        )
    else:
        conn.execute(
            'UPDATE requests SET assigned_technician = ? WHERE id = ?',
            (tname, request_id)
        )
    return tid, tname


def part_serials_from_form(form=None):
    """خواندن سریال قطعه از فرم با پشتیبانی نام‌های قدیمی و canonical."""
    from flask import request as _req
    f = form if form is not None else _req.form
    good = (f.get('serial_good') or f.get('serial_healthy') or '').strip()
    defective = (f.get('serial_defective') or f.get('serial_faulty') or '').strip()
    return good, defective


def coalesce_part_serials(row):
    """از ردیف request_parts سریال canonical برگردان."""
    if row is None:
        return '', ''
    keys = row.keys() if hasattr(row, 'keys') else []
    def g(a, b):
        va = (row[a] if a in keys else None) or ''
        vb = (row[b] if b in keys else None) or ''
        return (va or vb or '').strip()
    return g('serial_good', 'serial_healthy'), g('serial_defective', 'serial_faulty')


def get_current_user():
    """کاربر جاری — یک‌بار در هر درخواست در flask.g کش می‌شود."""
    try:
        from flask import g, has_request_context
        if has_request_context() and hasattr(g, '_sazgan_user'):
            return g._sazgan_user
    except Exception:
        pass

    user = None
    if 'user_id' not in session:
        # ⚠️ DEV ONLY — بای‌پس لاگین برای تست سریع ⚠️
        # با ست‌کردن متغیر محیطی SAZGAN_DEV_NO_LOGIN=1 ورود خودکار به‌عنوان
        # اولین کاربر فعال دیتابیس انجام می‌شود (بدون نیاز به رمز عبور).
        # قبل از نسخه نهایی/انتشار حتماً این بلاک را حذف کن یا متغیر را
        # از محیط پاک کن تا رمز عبور دوباره الزامی شود.
        if os.environ.get('SAZGAN_DEV_NO_LOGIN', '').strip().lower() in ('1', 'true', 'yes') and \
           os.environ.get('SAZGAN_BEHIND_PROXY', '').strip().lower() not in ('1', 'true', 'yes'):
            # دفاع لایه‌دوم (defense-in-depth، 2026-08-25): حتی اگر SAZGAN_DEV_NO_LOGIN
            # به‌اشتباه در سرور واقعی ست بشه، وقتی SAZGAN_BEHIND_PROXY=1 (یعنی نصب
            # پشت nginx/دیپلوی واقعی طبق nginx-sazgan.conf) باشه، بای‌پس همیشه غیرفعاله.
            try:
                conn = get_db()
                dev_user = conn.execute(
                    "SELECT * FROM users WHERE is_active = 1 OR is_active IS NULL ORDER BY id LIMIT 1"
                ).fetchone()
                if dev_user:
                    session['user_id'] = dev_user['id']
                    session.permanent = True
                    user = dev_user
            except Exception:
                user = None
        else:
            user = None
    else:
        try:
            conn = get_db()
            user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
            # close عمداً فراخوانی نمی‌شود؛ اتصال per-request کش است
        except Exception:
            user = None
        if not user:
            # نشست خراب/کاربر حذف‌شده — پاک کردن تا حلقه ریدایرکت نشود.
            # (این فقط باید وقتی اجرا شود که user_id واقعاً در session بوده و نامعتبر
            # درآمده — نه برای بازدیدکننده‌ی کاملاً ناشناس، وگرنه توکن CSRF صفحه‌ی
            # لاگین که هم‌زمان در همین درخواست ساخته می‌شود از بین می‌رود.
            # این باگ واقعی در 2026-08-25 حین اصلاح current_user.get() پیدا و برطرف شد.)
            try:
                session.clear()
            except Exception:
                pass
            user = None

    # تبدیل sqlite3.Row به dict: چون در ده‌ها نقطه از کد current_user.get('...')
    # صدا زده می‌شود (که sqlite3.Row پشتیبانی نمی‌کند و AttributeError می‌داد) —
    # این تبدیل باعث می‌شود هم current_user['field'] و هم current_user.get('field')
    # هر دو درست کار کنند. (باگ واقعی که در تست گردش‌کار تعمیر داخلی 2026-08-25 پیدا شد.)
    if user is not None and not isinstance(user, dict):
        try:
            user = dict(user)
        except Exception:
            pass

    try:
        from flask import g, has_request_context
        if has_request_context():
            g._sazgan_user = user
    except Exception:
        pass
    return user






def load_app_version():
    """خواندن نسخه برنامه. خروجی: dict با version, version_label, release_jalali, build_info.

    ✅ اصلاح‌شده: این تابع دیگر خودش فایل VERSION را نمی‌خواند و آن را
    تفسیر نمی‌کند. تنها مرجع نسخه، core/version.py است (Single Source of
    Truth) و همه‌ی بخش‌های برنامه — این تابع، /api/version، Native Client،
    Installer، Release Builder — باید از همان‌جا بگیرند تا هیچ‌وقت دو
    قسمت از برنامه نسخه‌ی متفاوتی نشان ندهند."""
    from core.version import get_version
    return get_version()


def load_changelog_entries(limit=50):
    """پارس ساده CHANGELOG.md برای نمایش داخل نرم‌افزار."""
    entries = []
    try:
        from core.constants import BASE_DIR
        path = os.path.join(BASE_DIR, 'CHANGELOG.md')
        if not os.path.isfile(path):
            return entries
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        current = None
        for raw in content.splitlines():
            line = raw.rstrip()
            if line.startswith('## ['):
                if current:
                    entries.append(current)
                # ## [v2.4.1] — 1405/05/12
                title = line[3:].strip()
                current = {'title': title, 'sections': [], '_section': None}
            elif current is None:
                continue
            elif line.startswith('### '):
                sec = line[4:].strip()
                current['_section'] = sec
                current['sections'].append({'name': sec, 'items': []})
            elif line.startswith('- ') and current['sections']:
                current['sections'][-1]['items'].append(line[2:].strip())
        if current:
            entries.append(current)
        for e in entries:
            e.pop('_section', None)
        if limit and len(entries) > limit:
            entries = entries[:limit]
    except Exception:
        pass
    return entries


# کش سبک تعطیلات و متن‌های آماده (کم‌تغییر) — کاهش I/O و DB هر درخواست.
# توجه: کش نسخه دیگر اینجا نیست؛ core/version.py خودش کش دارد (Single Source of Truth).
_HOLIDAYS_CACHE = {'ts': 0, 'data': None}
_READY_TEXTS_CACHE = {'ts': 0, 'data': None}
_CACHE_TTL_SEC = 60


def _load_ready_texts():
    """یک‌بار در بازه‌ی کش، لیست‌های آماده را از DB می‌خواند (نه در هر request).

    ✅ اصلاح‌شده: قبلاً این کوئری‌ها (get_db + get_list + seed_defaults_if_empty
    برای هر یک از سه لیست) در هر درخواست، برای هر صفحه، اجرا می‌شدند — فقط برای
    نمایش اطلاعات ثابت هدر صفحه. حالا مثل holidays با TTL کش می‌شوند."""
    out = {
        'ready_texts_problem': [],
        'ready_texts_accompanying': [],
        'ready_texts_appearance': [],
    }
    try:
        from core.db import get_db
        from core.app_lists import get_list, seed_defaults_if_empty
        conn = get_db()
        try:
            for key in ('ready_texts_problem', 'ready_texts_accompanying', 'ready_texts_appearance'):
                try:
                    seed_defaults_if_empty(conn, key)
                except Exception:
                    pass
                out[key] = get_list(conn, key, active_only=True) or []
        finally:
            conn.close()
    except Exception:
        pass
    return out


def inject_header_date():
    try:
        today = jdatetime.date.today()
        weekday_name = JALALI_WEEKDAYS[today.weekday()]
        header_date = f"{weekday_name} {today.day} {JALALI_MONTHS[today.month - 1]} {today.year}"
    except Exception:
        from datetime import date as _date
        header_date = _date.today().isoformat()
    tok = ''
    try:
        tok = _ensure_csrf_token()
    except Exception:
        pass
    embed = False
    try:
        embed = str(request.args.get('embed', '')).lower() in ('1', 'true', 'yes')
    except Exception:
        pass

    import time as _time
    now = _time.time()

    # ✅ نسخه از core/version.py گرفته می‌شود (کش داخلی دارد، هیچ I/O اضافه‌ای اینجا نیست)
    ver = load_app_version()

    holidays = _HOLIDAYS_CACHE.get('data')
    if holidays is None or (now - _HOLIDAYS_CACHE.get('ts', 0)) > _CACHE_TTL_SEC:
        try:
            holidays = holidays_map_for_js()
        except Exception:
            holidays = {}
        _HOLIDAYS_CACHE['data'] = holidays
        _HOLIDAYS_CACHE['ts'] = now

    # ✅ متن‌های آماده از app_lists — دیگر در هر request به DB وصل نمی‌شویم؛
    # فقط وقتی کش منقضی شده باشد (حداکثر هر ۶۰ ثانیه یک بار).
    ready = _READY_TEXTS_CACHE.get('data')
    if ready is None or (now - _READY_TEXTS_CACHE.get('ts', 0)) > _CACHE_TTL_SEC:
        ready = _load_ready_texts()
        _READY_TEXTS_CACHE['data'] = ready
        _READY_TEXTS_CACHE['ts'] = now

    return {
        'header_date': header_date,
        'csrf_token': tok,
        'embed': embed,
        'app_version': ver.get('version', ''),
        'app_version_label': ver.get('version_label', 'v0.0.0'),
        'app_version_label_full': ver.get('version_label_full', 'v0.0.0'),  # ✅ شامل تاریخ
        'app_release_jalali': ver.get('release_jalali', ''),
        'app_build_info': ver.get('build_info', ''),  # ✅ اطلاعات build
        'sazgan_holidays': holidays or {},
        'ready_texts_problem': ready.get('ready_texts_problem', []),
        'ready_texts_accompanying': ready.get('ready_texts_accompanying', []),
        'ready_texts_appearance': ready.get('ready_texts_appearance', []),
    }





def add_no_cache_headers(response):
    """کنترل کش سه‌دسته‌ای (فاز ۲، مطابق sazgan-frontend-handoff.md بخش ۳):
    - /static/  → دست نمی‌زنیم (از قبل long-term cache دارد)
    - /api/ و مسیرهای حساس (لاگین، مالی، تغییر رمز، دسترسی‌ها) → no-store کامل، بدون تغییر
    - بقیه‌ی صفحات HTML → کش کوتاهِ خصوصی به‌جای no-store کامل، تا back/forward
      مرورگر و navigation بین صفحات سریع‌تر شود بدون این‌که داده‌ی بی‌اعتبار نشون داده بشه
      (max-age=0 + must-revalidate یعنی مرورگر همیشه با سرور چک می‌کنه، ولی از cache
      محلی به‌عنوان نامزد استفاده می‌کنه — نه این‌که کورکورانه نگهش داره)
    """
    path = request.path
    if path.startswith('/static/'):
        return response
    # مسیرهای حساس که باید همیشه no-store واقعی بگیرن، حتی اگر با /api/ شروع نشن —
    # این لیست مستقیم از routes/auth.py، routes/finance.py، و مسیرهای رمز/دسترسی
    # استخراج شده (نه حدسی)، طبق دستور صریح سند فاز ۲.
    sensitive_prefixes = (
        '/login', '/logout', '/finance', '/my-wages',
        '/account/password', '/change-password', '/c/change-password',
        '/settings/access',
    )
    if path.startswith('/api/') or path.startswith(sensitive_prefixes):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    else:
        response.headers['Cache-Control'] = 'private, max-age=0, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
    return response








def _jalali_from_form(prefix='recep'):
    single = (request.form.get(f'{prefix}_date') or request.form.get('reception_date') or '').strip()
    if single:
        single = single.replace('-', '/')
        parts = single.split('/')
        if len(parts) >= 3:
            try:
                return f"{int(parts[0])}/{str(int(parts[1])).zfill(2)}/{str(int(parts[2])).zfill(2)}"
            except Exception:
                return single
        return single
    y = request.form.get(f'{prefix}_year', '')
    mo = request.form.get(f'{prefix}_month', '')
    d = request.form.get(f'{prefix}_day', '')
    if y and mo and d:
        return f"{y}/{str(mo).zfill(2)}/{str(d).zfill(2)}"
    return ''


def _set_stage_date(conn, request_id, stage_name, stage_date=None, notes=None):
    """ثبت تاریخ/رویداد مرحله به‌صورت سیستمی.

    request_stage_dates آخرین تاریخ هر Status را برای گزارش‌های سریع نگه می‌دارد؛
    request_stage_events تاریخچهٔ تمام ورودهای تکراری به یک Status را بدون overwrite نگه می‌دارد.
    تاریخ مرحله در گردش‌کار هرگز از ورودی کاربر گرفته نمی‌شود.
    """
    if not stage_date:
        try:
            stage_date = _now_jalali_str()
        except Exception:
            d = jdatetime.date.today()
            stage_date = f'{d.year}/{d.month:02d}/{d.day:02d}'
    existing = conn.execute(
        'SELECT id FROM request_stage_dates WHERE request_id = ? AND stage_name = ?',
        (request_id, stage_name)
    ).fetchone()
    if existing:
        conn.execute(
            'UPDATE request_stage_dates SET stage_date = ?, notes = ? WHERE id = ?',
            (stage_date, notes, existing['id'])
        )
    else:
        conn.execute(
            'INSERT INTO request_stage_dates (request_id, stage_name, stage_date, notes) VALUES (?, ?, ?, ?)',
            (request_id, stage_name, stage_date, notes)
        )
    # تاریخچهٔ تکرارپذیر Status؛ هر ورود به یک Status یک event مستقل است.
    try:
        conn.execute(
            'INSERT INTO request_stage_events (request_id, stage_name, stage_date, notes, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
            (request_id, stage_name, stage_date, notes, )
        )
    except Exception:
        pass
    try:
        uname = None
        try:
            from flask import session as _s
            if _s.get('user_id'):
                u = conn.execute('SELECT full_name FROM users WHERE id=?', (_s['user_id'],)).fetchone()
                uname = u['full_name'] if u else None
        except Exception:
            pass
        write_audit(conn, uname, f'مرحله: {stage_name}', 'request', request_id, notes or stage_date)
        # notify assigned tech
        req = conn.execute('SELECT assigned_technician, status FROM requests WHERE id=?', (request_id,)).fetchone()
        if req and req['assigned_technician']:
            notify_user(conn, req['assigned_technician'], request_id, f'به‌روزرسانی پرونده #{request_id}', stage_name)
            conn.execute('UPDATE requests SET is_new_for_tech=1 WHERE id=?', (request_id,))
    except Exception:
        pass




def internal_repair_new():
    """ثبت پذیرش تعمیر داخلی با فیلدهای کامل."""
    current_user = get_current_user()
    conn = get_db()

    if request.method == 'POST':
        customer_id = request.form.get('customer_id') or None
        customer_name = request.form['customer_name'].strip()
        province = request.form.get('province', '')
        county = request.form.get('county', '')
        city = request.form.get('city') or request.form.get('city_manual') or ''
        customer_address = request.form.get('customer_address', '')
        customer_phone = request.form.get('customer_phone', '')
        equipment_manager_name = request.form.get('equipment_manager_name', '')
        equipment_manager_mobile = request.form.get('equipment_manager_mobile', '')
        contact_name = request.form.get('contact_name', '')
        contact_phone = request.form.get('contact_phone', '')
        device_type = request.form.get('device_type', '') or '—'
        serial_number = request.form.get('serial_number', '')
        installation_date = request.form.get('installation_date', '')
        warranty_end_date = request.form.get('warranty_end_date', '')
        accompanying_items = request.form.get('accompanying_items', '')
        appearance_status = request.form.get('appearance_status', '')
        assigned_technician = request.form.get('assigned_technician') or None
        hospital_request_desc = request.form.get('hospital_request_desc', '')
        problem_desc = hospital_request_desc or request.form.get('problem_desc', '') or 'تعمیر داخلی'
        can_initial_test = 1 if request.form.get('can_initial_test') == '1' else 0
        reception_date = _jalali_from_form('recep')
        # پرونده همیشه از «پذیرش دستگاه انجام شد» شروع می‌شود؛ can_initial_test فقط پرچمی برای
        # QC است (بعداً تصمیم می‌گیرد تست بگیرد یا مستقیم به تعمیر اولیه ارجاع دهد)، نه وضعیت شروع.
        initial_status = INTERNAL_REPAIR_STATUSES[0]

        cur = conn.execute(
            '''INSERT INTO requests
               (customer_name, customer_address, customer_phone, device_type, serial_number,
                installation_date, problem_desc, service_type, province, county, assigned_technician,
                reception_date, request_category, status,
                customer_id, city, equipment_manager_name, equipment_manager_mobile,
                contact_name, contact_phone, warranty_end_date, accompanying_items,
                appearance_status, hospital_request_desc, can_initial_test)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (customer_name, customer_address, customer_phone, device_type, serial_number,
             installation_date, problem_desc, 'کارخانه', province, county, assigned_technician,
             reception_date, 'تعمیر', initial_status,
             customer_id, city, equipment_manager_name, equipment_manager_mobile,
             contact_name, contact_phone, warranty_end_date, accompanying_items,
             appearance_status, hospital_request_desc, can_initial_test)
        )
        new_id = cur.lastrowid
        try:
            from core.reception_numbers import assign_reception_no
            assign_reception_no(conn, new_id)
            try:
                from core.history import stamp_create
                stamp_create(conn, new_id, None)
            except Exception:
                pass
        except Exception:
            pass
        if assigned_technician:
            try:
                sync_request_technician(conn, new_id, assigned_technician, expected_role='تکنسین کارخانه')
            except Exception:
                conn.rollback(); conn.close()
                return redirect(f'/service/internal-repair/new?err=technician_invalid')
        _set_stage_date(conn, new_id, initial_status, None, 'ثبت پذیرش — تاریخ مرحله خودکار توسط سیستم')
        conn.commit()
        conn.close()
        return redirect(f'/service/internal-repair/view/{new_id}')

    customers = conn.execute('SELECT id, name, province, city FROM customers ORDER BY name').fetchall()
    technicians = conn.execute(
        "SELECT id, full_name, role, province FROM users WHERE role = 'تکنسین کارخانه' AND IFNULL(is_active,1)=1 ORDER BY full_name"
    ).fetchall()
    device_types = conn.execute('SELECT DISTINCT device_type FROM devices ORDER BY device_type').fetchall()
    conn.close()
    today = jdatetime.date.today()
    return render_template(
        'internal_repair_new.html',
        back=request.args.get('back'),
        customers=customers, technicians=technicians, device_types=device_types,
        provinces=(get_geo_provinces(conn) if get_geo_provinces else PROVINCES), statuses=(__import__('core.app_lists', fromlist=['get_list']).get_list(conn, 'internal_repair_statuses') or INTERNAL_REPAIR_STATUSES),
        active_page='service-internal-repair-new',
        current_user=current_user,
        jalali_months=JALALI_MONTHS,
        today_year=today.year, today_month=today.month, today_day=today.day,
        embed=_is_embed(),
    )




def external_repair_new():
    """ثبت درخواست تعمیر خارجی."""
    current_user = get_current_user()
    conn = get_db()

    if request.method == 'POST':
        customer_id = request.form.get('customer_id') or None
        customer_name = request.form['customer_name'].strip()
        province = request.form.get('province', '')
        county = request.form.get('county', '')
        city = request.form.get('city') or request.form.get('city_manual') or ''
        customer_address = request.form.get('customer_address', '')
        customer_phone = request.form.get('customer_phone', '')
        equipment_manager_name = request.form.get('equipment_manager_name', '')
        equipment_manager_mobile = request.form.get('equipment_manager_mobile', '')
        contact_name = request.form.get('contact_name', '')
        contact_phone = request.form.get('contact_phone', '')
        device_type = request.form.get('device_type', '') or '—'
        serial_number = request.form.get('serial_number', '')
        installation_date = request.form.get('installation_date', '')
        warranty_end_date = request.form.get('warranty_end_date', '')
        assigned_technician = request.form.get('assigned_technician') or None
        hospital_request_desc = request.form.get('hospital_request_desc', '')
        problem_desc = hospital_request_desc or 'تعمیر خارجی'
        reception_date = _jalali_from_form('recep')

        cur = conn.execute(
            '''INSERT INTO requests
               (customer_name, customer_address, customer_phone, device_type, serial_number,
                installation_date, problem_desc, service_type, province, county, assigned_technician,
                reception_date, request_category, status,
                customer_id, city, equipment_manager_name, equipment_manager_mobile,
                contact_name, contact_phone, warranty_end_date, hospital_request_desc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (customer_name, customer_address, customer_phone, device_type, serial_number,
             installation_date, problem_desc, 'در محل', province, county, assigned_technician,
             reception_date, 'تعمیر', EXTERNAL_REPAIR_STATUSES[0],
             customer_id, city, equipment_manager_name, equipment_manager_mobile,
             contact_name, contact_phone, warranty_end_date, hospital_request_desc)
        )
        new_id = cur.lastrowid
        try:
            from core.reception_numbers import assign_reception_no
            assign_reception_no(conn, new_id)
            try:
                from core.history import stamp_create
                stamp_create(conn, new_id, None)
            except Exception:
                pass
        except Exception:
            pass
        if assigned_technician:
            try:
                sync_request_technician(conn, new_id, assigned_technician, expected_role='تکنسین استانی', province=province)
            except Exception:
                conn.rollback(); conn.close()
                return redirect('/service/external-repair/new?err=technician_invalid')
        if reception_date:
            _set_stage_date(conn, new_id, EXTERNAL_REPAIR_STATUSES[0], reception_date, 'ثبت اولیه درخواست تعمیر خارجی')

        # قطعات احتمالی انتخاب‌شده در فرم
        part_ids = request.form.getlist('probable_part_ids')
        for pid in part_ids:
            p = conn.execute('SELECT * FROM parts WHERE id = ?', (pid,)).fetchone()
            if p:
                conn.execute(
                    '''INSERT INTO request_parts
                       (request_id, part_id, part_name, warehouse_code, quantity, stage, notes)
                       VALUES (?, ?, ?, ?, 1, ?, ?)''',
                    (new_id, p['id'], p['part_name'], p['warehouse_code'], 'قطعات احتمالی', 'ثبت در پذیرش')
                )

        conn.commit()
        conn.close()
        return redirect(f'/service/external-repair/view/{new_id}')

    customers = conn.execute('SELECT id, name, province, city FROM customers ORDER BY name').fetchall()
    technicians = conn.execute(
        "SELECT id, full_name, role, province FROM users WHERE role = 'تکنسین استانی' AND IFNULL(is_active,1)=1 ORDER BY full_name"
    ).fetchall()
    device_types = conn.execute('SELECT DISTINCT device_type FROM devices ORDER BY device_type').fetchall()
    parts_catalog = conn.execute('SELECT * FROM parts ORDER BY part_name').fetchall()
    conn.close()
    today = jdatetime.date.today()
    return render_template(
        'external_repair_new.html',
        back=request.args.get('back'),
        customers=customers, technicians=technicians, device_types=device_types,
        parts_catalog=parts_catalog, provinces=(get_geo_provinces(conn) if get_geo_provinces else PROVINCES), statuses=(__import__('core.app_lists', fromlist=['get_list']).get_list(conn, 'external_repair_statuses') or EXTERNAL_REPAIR_STATUSES),
        active_page='service-external-repair-new',
        current_user=current_user,
        jalali_months=JALALI_MONTHS,
        today_year=today.year, today_month=today.month, today_day=today.day
    , embed=_is_embed()
    )




def _load_attachments(conn, req_id):
    return conn.execute(
        'SELECT * FROM request_attachments WHERE request_id = ? ORDER BY id DESC', (req_id,)
    ).fetchall()





from core import stock as _stock_mod
_get_get_stock_qty = _stock_mod._get_get_stock_qty
_adjust_stock = _stock_mod._adjust_stock
_record_external_parts_to_province = _stock_mod._record_external_parts_to_province
_apply_request_parts_stock = _stock_mod._apply_request_parts_stock
_record_voucher_parts = _stock_mod._record_voucher_parts
_issue_part_from_stock = _stock_mod._issue_part_from_stock
_restore_part_to_stock = _stock_mod._restore_part_to_stock


def write_audit(conn, user_name, action, entity_type=None, entity_id=None, details=None):
    try:
        try:
            from core.history import now_stamp
            ts = now_stamp()
        except Exception:
            ts = _now_jalali_str() + ' ' + time.strftime('%H:%M')
        conn.execute(
            'INSERT INTO audit_log (created_at, user_name, action, entity_type, entity_id, details) VALUES (?,?,?,?,?,?)',
            (ts, user_name or '-', action, entity_type, entity_id, details)
        )
        if entity_type == 'request' and entity_id:
            try:
                from core.history import stamp_update
                # فقط updated_at بدون لاگ دوباره
                conn.execute(
                    'UPDATE requests SET updated_at=?, updated_by=? WHERE id=?',
                    (ts, user_name or '-', entity_id),
                )
            except Exception:
                logging.getLogger('sazgan').exception(
                    'write_audit: failed to stamp updated_at for %s #%s', entity_type, entity_id
                )
    except Exception:
        # عملیات اصلی کاربر نباید به‌خاطر شکست ثبت audit متوقف شود، اما این
        # شکست دیگر بی‌صدا نیست — بدون این لاگ هیچ اثری از خطای درج در
        # audit_log باقی نمی‌ماند و امکان تشخیص مشکل (مثلاً قفل بودن دیتابیس
        # یا ناسازگاری schema) از بین می‌رود.
        logging.getLogger('sazgan').exception(
            'write_audit: failed to record action=%s entity_type=%s entity_id=%s user=%s',
            action, entity_type, entity_id, user_name
        )




def notify_user(conn, user_name, request_id, title, body='', url=None, data=None):
    """ثبت اعلان در دیتابیس و ارسال Web Push به دستگاه‌های کاربر."""
    if not user_name:
        return
    try:
        from core.push import notify_and_push
        return notify_and_push(
            conn,
            user_name=user_name,
            request_id=request_id,
            title=title,
            body=body or '',
            url=url,
            data=data,
        )
    except Exception:
        # fallback بدون push
        try:
            conn.execute(
                'INSERT INTO notifications (user_name, request_id, title, body, is_read, created_at) VALUES (?,?,?,?,0,?)',
                (user_name, request_id, title, body, _now_jalali_str() + ' ' + time.strftime('%H:%M'))
            )
        except Exception:
            pass
        return None







# لایه دسترسی متمرکز
from core.access import (  # noqa: E402
    ACCESS_MODULES, DEFAULT_ROLE_ACCESS, PATH_MODULE_RULES,
    get_role_access_map as _access_get_role_map,
    user_has_access as _access_user_has,
    module_for_path, is_public_path, enforce_path_access,
    require_login, require_access, require_roles,
)

def get_role_access_map(conn=None):
    return _access_get_role_map(conn, get_db=get_db, get_setting=get_setting)

def user_has_access(user, module, conn=None):
    return _access_user_has(user, module, conn=conn, get_db=get_db, get_setting=get_setting)




def list_calendar_holidays(conn=None):
    """لیست تعطیلات دستی (غیر از جمعه)."""
    close = False
    if conn is None:
        conn = get_db()
        close = True
    try:
        rows = conn.execute(
            'SELECT id, holiday_date, title FROM calendar_holidays ORDER BY holiday_date'
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        if close:
            try:
                conn.close()
            except Exception:
                pass


def holidays_map_for_js(conn=None):
    """dict تاریخ→عنوان برای datepicker."""
    out = {}
    for h in list_calendar_holidays(conn):
        d = (h.get('holiday_date') or '').strip().replace('-', '/')
        parts = d.split('/')
        if len(parts) == 3:
            try:
                d = f"{int(parts[0])}/{int(parts[1]):02d}/{int(parts[2]):02d}"
            except Exception:
                pass
        if d:
            out[d] = h.get('title') or 'تعطیل'
    return out


def add_calendar_holiday(conn, holiday_date, title):
    d = (holiday_date or '').strip().replace('-', '/')
    title = (title or '').strip() or 'تعطیل رسمی'
    parts = d.split('/')
    if len(parts) != 3:
        return False, 'تاریخ نامعتبر'
    try:
        d = f"{int(parts[0])}/{int(parts[1]):02d}/{int(parts[2]):02d}"
    except Exception:
        return False, 'تاریخ نامعتبر'
    try:
        conn.execute(
            'INSERT INTO calendar_holidays (holiday_date, title, created_at) VALUES (?,?,?)',
            (d, title, _now_jalali_str())
        )
        return True, d
    except Exception as e:
        return False, 'این تاریخ قبلاً ثبت شده یا خطا رخ داد'


def delete_calendar_holiday(conn, holiday_id):
    try:
        conn.execute('DELETE FROM calendar_holidays WHERE id=?', (int(holiday_id),))
        return True
    except Exception:
        return False


def inject_access():
    """دسترسی ماژول‌ها برای قالب‌ها.
    مدیر سیستم / نام کاربری admin = دسترسی کامل به همه منوها (از جمله وظایف من).
    """
    def can_access(module):
        try:
            u = get_current_user()
            return user_has_access(u, module)
        except Exception:
            return False

    def is_sys_admin():
        try:
            from core.access import is_system_admin
            return is_system_admin(get_current_user())
        except Exception:
            return False

    return dict(can_access=can_access, is_sys_admin=is_sys_admin)


def inject_help_tips():
    """متن راهنماهای قابل‌ویرایش (آیکون i) برای قالب‌ها — با کش per-request."""
    def get_help_tip_text(key, default=''):
        try:
            from flask import g, has_request_context
            from core.help_tips import get_help_tip as _get_help_tip
            if has_request_context():
                cache = getattr(g, '_sazgan_help_tips', None)
                if cache is None:
                    cache = {}
                    g._sazgan_help_tips = cache
                if key in cache:
                    return cache[key]
                conn = get_db()
                try:
                    val = _get_help_tip(conn, key, default)
                finally:
                    conn.close()
                cache[key] = val
                return val
            conn = get_db()
            try:
                return _get_help_tip(conn, key, default)
            finally:
                conn.close()
        except Exception:
            return default
    return dict(get_help_tip_text=get_help_tip_text)

_COMPANY_CACHE = {'ts': 0, 'name': None, 'logo': None}


def inject_notifications_count():
    """اعلان‌های خوانده‌نشده + نام شرکت — با کش per-request و کش کوتاه شرکت."""
    n = 0
    try:
        from flask import g, has_request_context
        if has_request_context() and hasattr(g, '_sazgan_unread'):
            n = g._sazgan_unread
        else:
            u = get_current_user()
            if u:
                conn = get_db()
                row = conn.execute(
                    'SELECT COUNT(*) AS c FROM notifications WHERE user_name=? AND is_read=0',
                    (u['full_name'],)
                ).fetchone()
                n = row['c'] if row else 0
            if has_request_context():
                g._sazgan_unread = n
    except Exception:
        pass

    import time as _time
    now = _time.time()
    company = _COMPANY_CACHE.get('name')
    logo = _COMPANY_CACHE.get('logo')
    if not company or (now - _COMPANY_CACHE.get('ts', 0)) > 120:
        company = 'سازگان'
        logo = ''
        try:
            conn = get_db()
            company = get_setting(conn, 'company_name', 'سازگان گستر') or 'سازگان'
            logo = get_setting(conn, 'company_logo', '') or ''
        except Exception:
            pass
        _COMPANY_CACHE['name'] = company
        _COMPANY_CACHE['logo'] = logo
        _COMPANY_CACHE['ts'] = now
    # تعداد وظایف فعال کارتابل برای Badge هدر. شمارش بر اساس نقش انجام می‌شود
    # و از اعلان‌ها مستقل است؛ کارتابل نمایانگر کار واقعیِ نیازمند اقدام است.
    cartable_open_count = 0
    try:
        from flask import g, has_request_context
        if has_request_context() and hasattr(g, '_sazgan_cartable_open'):
            cartable_open_count = g._sazgan_cartable_open
        else:
            u = get_current_user()
            if u:
                conn = get_db()
                role = u.get('role') if hasattr(u, 'get') else u['role']
                if role in ('تکنسین کارخانه', 'تکنسین شهرستان'):
                    tasks = _get_technician_tasks(conn, u)
                    cartable_open_count = sum(1 for task in tasks if not task.get('is_closed'))
                elif role == 'کنترل کیفیت':
                    tasks = _get_qc_tasks(conn)
                    cartable_open_count = sum(1 for task in tasks if not task.get('is_closed'))
                elif role == 'امور مالی':
                    tasks = _get_finance_tasks(conn)
                    cartable_open_count = sum(1 for task in tasks if not task.get('is_closed', False))
                elif role in ('مسئول پذیرش', 'مدیر سیستم', 'مدیر'):
                    row = conn.execute(
                        """SELECT COUNT(*) AS c FROM requests
                           WHERE status IN ('پذیرش','اعلام خرابی','تعمیر انجام‌شده — منتظر بررسی پذیرش',
                               'تحویل به پذیرش','رد پیش‌فاکتور — ارسال به مشتری',
                               'در انتظار پذیرش دستگاه است','پذیرش انجام شد','در انتظار پذیرش',
                               'در انتظار بررسی پذیرش')
                           OR (request_category IN ('درخواست خدمات','اعلام خرابی','درخواست سرویس')
                               AND status IN ('در انتظار بررسی پذیرش','در انتظار پذیرش'))
                        """
                    ).fetchone()
                    cartable_open_count = row['c'] if row else 0
                conn.close()
            if has_request_context():
                g._sazgan_cartable_open = cartable_open_count
    except Exception:
        cartable_open_count = 0

    return dict(
        unread_notifications=n,
        cartable_open_count=cartable_open_count,
        company_name=company,
        company_logo=logo,
    )










# اجازه import * حتی برای توابع خصوصی (_xxx)
__all__ = [n for n in list(globals().keys()) if not n.startswith('__')]


def search_rows(rows, q):
    from core.request_utils import search_rows as _sr
    return _sr(rows, q)
