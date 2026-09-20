# -*- coding: utf-8 -*-
"""ماتریس تأخیر سریال‌محور: ردیف = سریال، ستون = مرحله، سلول = روز."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import jdatetime

from core.constants import (
    DELAY_THRESHOLD_DAYS,
    INTERNAL_REPAIR_STATUSES,
    EXTERNAL_REPAIR_STATUSES,
    INSTALLATION_REQUEST_STATUSES,
    VISIT_STATUSES,
)
from core.jalali import days_since, parse_jalali


# سقف پیش‌فرض هر مرحله (روز) — قابل گسترش در تنظیمات
DEFAULT_STAGE_CAPS = {
    # تعمیر داخلی
    'در انتظار پذیرش دستگاه است': 2,
    'در انتظار تست اولیه است': 3,
    'در انتظار تأیید QC اولیه است': 2,
    'در انتظار گزارش فنی است': 5,
    'در انتظار ارسال پیش‌فاکتور است': 3,
    'در انتظار دریافت تاییدیه پیش‌فاکتور است': 7,
    # تعمیر خارجی
    'در انتظار بررسی پذیرش': 2,
    'در انتظار هماهنگی مأموریت است': 3,
    # نصب
    'درخواست ثبت شد': 2,
    'در انتظار هماهنگی نصب': 5,
    'در انتظار انجام نصب': 7,
    # عمومی
    '_default': DELAY_THRESHOLD_DAYS if DELAY_THRESHOLD_DAYS else 5,
}


def statuses_for_kind(kind: str, conn=None) -> List[str]:
    kind = (kind or 'internal').lower()
    key = 'internal_repair_statuses'
    if kind in ('external', 'تعمیر خارجی', 'onsite'):
        key = 'external_repair_statuses'
    elif kind in ('install', 'نصب', 'installation'):
        key = 'installation_statuses'
    elif kind in ('visit', 'بازدید', 'inspection'):
        key = 'visit_statuses'
    if conn is not None:
        try:
            from core.app_lists import get_list
            items = get_list(conn, key)
            if items:
                return items
        except Exception:
            pass
    fallback = {
        'internal_repair_statuses': INTERNAL_REPAIR_STATUSES,
        'external_repair_statuses': EXTERNAL_REPAIR_STATUSES,
        'installation_statuses': INSTALLATION_REQUEST_STATUSES,
        'visit_statuses': VISIT_STATUSES,
    }
    return list(fallback.get(key, INTERNAL_REPAIR_STATUSES))


def _sql_filter_kind(kind: str) -> Tuple[str, tuple]:
    kind = (kind or 'internal').lower()
    if kind in ('internal', 'تعمیر داخلی', 'factory'):
        return "request_category = 'تعمیر' AND service_type = 'کارخانه'", ()
    if kind in ('external', 'تعمیر خارجی', 'onsite'):
        return "request_category = 'تعمیر' AND service_type = 'در محل'", ()
    if kind in ('install', 'نصب', 'installation'):
        return "request_category = 'نصب و آموزش'", ()
    if kind in ('visit', 'بازدید', 'inspection'):
        return "request_category = 'بررسی و بازدید'", ()
    return "1=1", ()


def _jalali_diff_days(d1: Optional[str], d2: Optional[str]) -> Optional[int]:
    """تعداد روز بین دو تاریخ شمسی (d2 - d1)."""
    if not d1 or not d2:
        return None
    try:
        a = parse_jalali(d1)
        b = parse_jalali(d2)
        if a is None or b is None:
            return None
        return (b - a).days
    except Exception:
        return None


def build_delay_matrix(
    conn,
    kind: str = 'internal',
    serial_filter: str = '',
    province: str = '',
    limit: int = 200,
    only_delayed: bool = False,
) -> Dict[str, Any]:
    """ساخت ماتریس: rows[{serial, customer, reception_no, status, stages{name: days}, total, delayed_stages}]"""
    stages = statuses_for_kind(kind)
    where, params = _sql_filter_kind(kind)
    sql = f"""
        SELECT id, reception_no, serial_number, customer_name, status, province, city,
               reception_date, request_category, service_type, request_subtype,
               device_type, device_model, assigned_technician
        FROM requests
        WHERE {where}
          AND IFNULL(serial_number, '') != ''
    """
    args = list(params)
    if serial_filter:
        sql += " AND serial_number LIKE ?"
        args.append('%' + serial_filter.strip() + '%')
    if province:
        sql += " AND province = ?"
        args.append(province)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(int(limit))

    reqs = conn.execute(sql, args).fetchall()
    today = jdatetime.date.today()
    today_s = f"{today.year}/{today.month:02d}/{today.day:02d}"

    rows_out = []
    for r in reqs:
        rid = r['id']
        serial = r['serial_number'] or '—'
        # تاریخ‌های مرحله
        stage_rows = conn.execute(
            "SELECT stage_name, stage_date FROM request_stage_dates WHERE request_id = ? ORDER BY id",
            (rid,),
        ).fetchall()
        date_by_stage = {}
        for s in stage_rows:
            name = s['stage_name']
            if name and s['stage_date'] and name not in date_by_stage:
                date_by_stage[name] = s['stage_date']
        # نقطه شروع
        start0 = r['reception_date'] or date_by_stage.get(stages[0] if stages else '')

        stage_days = {}
        delayed_stages = []
        total = 0
        for i, st in enumerate(stages):
            d_in = date_by_stage.get(st)
            if not d_in:
                # اگر مرحله فعلی است از reception استفاده کن
                if (r['status'] or '') == st:
                    d_in = start0
                else:
                    stage_days[st] = None
                    continue
            # تاریخ خروج = تاریخ مرحله بعدی ثبت‌شده یا امروز اگر فعلی
            d_out = None
            for j in range(i + 1, len(stages)):
                if stages[j] in date_by_stage:
                    d_out = date_by_stage[stages[j]]
                    break
            if d_out is None:
                if (r['status'] or '') == st:
                    d_out = today_s
                else:
                    # مرحله گذشته بدون تاریخ بعدی — یک روز حداقل یا None
                    stage_days[st] = None
                    continue
            days = _jalali_diff_days(d_in, d_out)
            if days is None:
                days = days_since(d_in, today) if (r['status'] or '') == st else None
            stage_days[st] = days
            if days is not None and days >= 0:
                total += days
                cap = DEFAULT_STAGE_CAPS.get(st, DEFAULT_STAGE_CAPS['_default'])
                if days > cap:
                    delayed_stages.append(st)

        if only_delayed and not delayed_stages:
            continue

        delay_stage = delayed_stages[0] if delayed_stages else (r['status'] or '')
        rows_out.append({
            'id': rid,
            'serial': serial,
            'customer': r['customer_name'],
            'customer_name': r['customer_name'],
            'reception_no': r['reception_no'],
            'reception_date': r['reception_date'],
            'status': r['status'],
            'province': r['province'],
            'city': r['city'] if 'city' in r.keys() else None,
            'device_type': r['device_type'] if 'device_type' in r.keys() else None,
            'device_model': r['device_model'] if 'device_model' in r.keys() else None,
            'assigned_technician': r['assigned_technician'] if 'assigned_technician' in r.keys() else None,
            'request_category': r['request_category'],
            'service_type': r['service_type'],
            'delay_stage': delay_stage,
            'delay_reason': '—',
            'stage_days': stage_days,
            'total': total,
            'delayed_stages': delayed_stages,
            'is_delayed': bool(delayed_stages),
        })

    # میانگین هر ستون
    averages = {}
    for st in stages:
        vals = [row['stage_days'].get(st) for row in rows_out if row['stage_days'].get(st) is not None]
        averages[st] = round(sum(vals) / len(vals), 1) if vals else None

    return {
        'stages': stages,
        'rows': rows_out,
        'averages': averages,
        'caps': {st: DEFAULT_STAGE_CAPS.get(st, DEFAULT_STAGE_CAPS['_default']) for st in stages},
        'kind': kind,
    }
