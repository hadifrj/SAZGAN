# -*- coding: utf-8 -*-
from __future__ import annotations
from flask import (
    request, session, redirect, render_template, jsonify, send_file, current_app
)
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
try:
    from core.geo import get_geo_provinces
except Exception:
    get_geo_provinces = None
from core.access import is_system_admin
from core.customer_notify import notify_status_change
from core import helpers as H


from core.helpers import *  # noqa: F401,F403
from core.constants import *  # noqa: F401,F403
from core.company_info import get_company_info as _get_company_info
from core.jalali import add_jalali_months, enrich_warranty_row
from core.workflow import can_view_request, transition_request, WorkflowError, validate_positive_quantity

QUOTE_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'repair_quotes')
ALLOWED_QUOTE_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_QUOTE_BYTES = 10 * 1024 * 1024

def _quote_files(conn, req_id):
    return conn.execute("SELECT * FROM repair_quote_files WHERE request_id=? ORDER BY id DESC", (req_id,)).fetchall()

def _save_quote_upload(conn, req_id, uploaded, role, user_name):
    if not uploaded or not uploaded.filename:
        raise ValueError('فایلی انتخاب نشده است.')
    ext = os.path.splitext(secure_filename(uploaded.filename))[1].lower()
    if ext not in ALLOWED_QUOTE_EXTENSIONS:
        raise ValueError('فقط PDF، JPG، JPEG و PNG مجاز است.')
    uploaded.stream.seek(0, os.SEEK_END); size = uploaded.stream.tell(); uploaded.stream.seek(0)
    if size > MAX_QUOTE_BYTES:
        raise ValueError('حجم فایل نباید بیشتر از ۱۰ مگابایت باشد.')
    os.makedirs(QUOTE_UPLOAD_DIR, exist_ok=True)
    stored = f"{req_id}_{role}_{int(time.time()*1000)}{ext}"
    uploaded.save(os.path.join(QUOTE_UPLOAD_DIR, stored))
    conn.execute("DELETE FROM repair_quote_files WHERE request_id=? AND file_role=?", (req_id, role))
    conn.execute("INSERT INTO repair_quote_files(request_id,file_role,stored_name,original_name,mime_type,size_bytes,uploaded_by,status) VALUES(?,?,?,?,?,?,?,?)", (req_id, role, stored, secure_filename(uploaded.filename), uploaded.mimetype, size, user_name, 'waiting_customer' if role=='original' else 'waiting_finance'))

def _internal_repair_visible_panels(can_edit, is_qc, is_assigned_tech, is_finance, is_admin=False):
    """کدام تب‌های پرونده‌ی تعمیر داخلی برای این نقش نمایش داده شود.

    هر نقش فقط بخش کاری مربوط به خودش را می‌بیند، به‌علاوه‌ی خلاصه/وضعیت/تاریخچه/
    اطلاعات پذیرش که برای شناسایی پرونده لازم است. امور مالی مختص نقش مالی است —
    پذیرش/QC/تکنسین در آن نقشی ندارند و برعکس. مدیر سیستم همیشه دید کامل دارد.
    """
    if is_admin:
        return None
    panels = {'status', 'history', 'reception'}
    if can_edit:
        panels.add('reports')
        panels.add('parts')
        panels.add('voucher')
        panels.add('files')
        return panels
    if is_qc:
        panels.add('reports')
    if is_assigned_tech:
        panels.add('reports')
        panels.add('parts')
        panels.add('voucher')
    if is_finance:
        panels.add('finance')
    return panels


def _external_repair_visible_panels(can_edit, is_assigned_tech, is_finance, is_admin=False):
    """مشابه _internal_repair_visible_panels برای تعمیر بیرون‌شهری — این مسیر نقش QC جدا ندارد،
    فقط نماینده/تکنسین استانی (گزارش+قطعات) و امور مالی (پیش‌فاکتور/فاکتور). مدیر سیستم دید کامل دارد."""
    if is_admin:
        return None
    panels = {'status', 'history', 'reception'}
    if can_edit:
        panels.add('reports')
        panels.add('parts')
        panels.add('files')
        return panels
    if is_assigned_tech:
        panels.add('reports')
        panels.add('parts')
    if is_finance:
        panels.add('finance')
    return panels

