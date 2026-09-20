# -*- coding: utf-8 -*-
"""ابزارهای خالص پرونده: فیلتر، تأخیر، لینک جزئیات."""
from __future__ import annotations

import jdatetime

from core.constants import (
    CLOSED_STATUSES,
    CLOSED_REQUEST_STATUSES,
    DELAY_THRESHOLD_DAYS,
)
from core.jalali import days_since as _days_since


def request_detail_url(r):
    """لینک پرونده بر اساس نوع درخواست."""
    if isinstance(r, dict):
        cat = r.get('request_category') or ''
        st = r.get('service_type') or ''
        sub = r.get('request_subtype') or ''
        rid = r.get('id')
    else:
        cat = r['request_category'] if 'request_category' in r.keys() else ''
        st = r['service_type'] if 'service_type' in r.keys() else ''
        sub = r['request_subtype'] if 'request_subtype' in r.keys() else ''
        rid = r['id']
    if cat == 'تعمیر' and st == 'کارخانه':
        return f'/service/internal-repair/view/{rid}'
    if cat == 'تعمیر' and st == 'در محل':
        return f'/service/external-repair/view/{rid}'
    if cat == 'نصب و آموزش' and sub == 'درخواست نصب':
        return f'/service/installation/request-view/{rid}'
    if cat == 'نصب و آموزش' and sub == 'ثبت نصب':
        return f'/service/installation/register-view/{rid}'
    if cat == 'بررسی و بازدید':
        return f'/service/inspection/view/{rid}'
    return f'/service/internal-repair/view/{rid}'


def split_open_closed(rows):
    """جداسازی پرونده‌های باز و بایگانی‌شده."""
    open_rows, closed_rows = [], []
    for r in rows:
        st = (r.get('status') if isinstance(r, dict) else r['status']) or ''
        if st in CLOSED_REQUEST_STATUSES:
            closed_rows.append(r)
        else:
            open_rows.append(r)
    return open_rows, closed_rows


def stage_date_for_status(conn, request_id, status):
    """تاریخ ثبت وضعیت فعلی از request_stage_dates."""
    if not status:
        return None
    row = conn.execute(
        'SELECT stage_date FROM request_stage_dates WHERE request_id = ? AND stage_name = ? ORDER BY id DESC LIMIT 1',
        (request_id, status)
    ).fetchone()
    if row and row['stage_date']:
        return row['stage_date']
    return None


def enrich_delay(conn, rows, threshold=None):
    """افزودن days_in_status و is_delayed به هر ردیف."""
    if threshold is None:
        threshold = DELAY_THRESHOLD_DAYS
    today = jdatetime.date.today()
    closed = set(CLOSED_STATUSES) if CLOSED_STATUSES else {
        'پایان تعمیرات', 'پایان', 'تحویل شد', 'بسته شد', 'نصب انجام شد', 'بازدید انجام شد'
    }
    result = []
    for r in rows:
        d = dict(r)
        status = d.get('status') or ''
        if status in closed:
            d['days_in_status'] = 0
            d['is_delayed'] = False
            d['delay_ref_date'] = None
        else:
            ref = stage_date_for_status(conn, d['id'], status) or d.get('reception_date')
            days = _days_since(ref, today)
            d['days_in_status'] = days if days is not None else 0
            d['is_delayed'] = (days is not None and days >= threshold)
            d['delay_ref_date'] = ref
        d['detail_url'] = request_detail_url(r)
        result.append(d)
    return result


def filter_by_date_range(rows, date_from=None, date_to=None, date_field='reception_date'):
    """فیلتر لیست بر اساس بازه تاریخ شمسی."""
    if not date_from and not date_to:
        return rows
    out = []
    for r in rows:
        val = r.get(date_field) if isinstance(r, dict) else (
            r[date_field] if date_field in r.keys() else None
        )
        if not val:
            continue
        val_n = str(val).strip().replace('-', '/')
        parts = val_n.split('/')
        if len(parts) == 3:
            try:
                val_n = f"{int(parts[0])}/{int(parts[1]):02d}/{int(parts[2]):02d}"
            except Exception:
                pass
        if date_from:
            df = date_from.replace('-', '/')
            fp = df.split('/')
            if len(fp) == 3:
                try:
                    df = f"{int(fp[0])}/{int(fp[1]):02d}/{int(fp[2]):02d}"
                except Exception:
                    pass
            if val_n < df:
                continue
        if date_to:
            dt = date_to.replace('-', '/')
            tp = dt.split('/')
            if len(tp) == 3:
                try:
                    dt = f"{int(tp[0])}/{int(tp[1]):02d}/{int(tp[2]):02d}"
                except Exception:
                    pass
            if val_n > dt:
                continue
        out.append(r)
    return out


def _g(r, key, default=None):
    if isinstance(r, dict):
        return r.get(key, default)
    try:
        return r[key] if key in r.keys() else default
    except Exception:
        return default


def filter_rows(rows, province=None, status=None, only_delayed=False,
                city=None, technician=None, device_type=None, device_model=None):
    """فیلتر استاندارد لیست‌ها و گزارش‌ها."""
    out = list(rows)
    if province:
        out = [r for r in out if (_g(r, 'province') or '') == province]
    if city:
        out = [r for r in out if city in (_g(r, 'city') or '')]
    if status:
        out = [r for r in out if (_g(r, 'status') or '') == status]
    if technician:
        tech = technician.strip()
        out = [r for r in out if tech in (_g(r, 'assigned_technician') or '')]
    if device_type:
        out = [r for r in out if device_type in (_g(r, 'device_type') or '')]
    if device_model:
        out = [r for r in out if device_model in ((_g(r, 'device_model') or '') + (_g(r, 'model') or ''))]
    if only_delayed:
        out = [r for r in out if (_g(r, 'is_delayed') if isinstance(r, dict) else False)]
    return out


def search_rows(rows, q):
    """جستجوی متنی روی شماره پذیرش، مشتری، سریال، فاکتور، تکنسین/نماینده."""
    if not q or not str(q).strip():
        return list(rows)
    needle = str(q).strip().lower()
    fields = (
        'reception_no', 'id', 'customer_name', 'serial_number',
        'invoice_number', 'assigned_technician', 'device_type', 'device_model',
        'province', 'city', 'tracking_number', 'carrier_name',
    )
    out = []
    for r in rows:
        blob = []
        for f in fields:
            v = _g(r, f)
            if v is not None:
                blob.append(str(v))
        if needle in ' '.join(blob).lower():
            out.append(r)
    return out


# نام‌های مستعار با پیشوند _ برای سازگاری با callers قدیمی
_request_detail_url = request_detail_url
_split_open_closed = split_open_closed
_stage_date_for_status = stage_date_for_status
_enrich_delay = enrich_delay
_filter_by_date_range = filter_by_date_range
_filter_rows = filter_rows

_search_rows = search_rows
_filter_rows = filter_rows
