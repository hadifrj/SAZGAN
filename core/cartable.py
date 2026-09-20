# -*- coding: utf-8 -*-
"""کارتابل نقش‌محور: تکنسین، کنترل کیفیت، امور مالی."""
from __future__ import annotations

from core.constants import (
    CLOSED_STATUSES,
    DELAY_THRESHOLD_DAYS,
    FINANCE_INTERNAL_STATUSES,
    FINANCE_EXTERNAL_STATUSES,
    FINANCE_VISIT_STATUSES,
)
from core.jalali import days_since as _days_since
from core.request_utils import stage_date_for_status, enrich_delay


def get_finance_tasks(conn):
    """پرونده‌های در مراحل مالی."""
    statuses = list(
        set(FINANCE_INTERNAL_STATUSES)
        | set(FINANCE_EXTERNAL_STATUSES)
        | set(FINANCE_VISIT_STATUSES)
    )
    ph = ','.join(['?'] * len(statuses))
    rows = conn.execute(
        'SELECT * FROM requests WHERE status IN (' + ph + ") AND (is_deleted IS NULL OR is_deleted = 0) ORDER BY id DESC LIMIT 200",
        statuses,
    ).fetchall()
    return enrich_delay(conn, rows)


def get_qc_tasks(conn):
    """پرونده‌های تعمیر داخلی برای کارتابل کنترل کیفیت."""
    closed = ('پایان تعمیرات', 'تحویل شد', 'پایان')
    qc_focus = (
        'در انتظار تست اولیه است',
        'در انتظار تست نهایی و تحویل است',
        'در انتظار ارسال گزارش فنی است',
        'در انتظار گزارش نهایی است',
    )
    rows = conn.execute(
        """SELECT * FROM requests
           WHERE service_type = 'کارخانه' AND request_category = 'تعمیر'
             AND (is_deleted IS NULL OR is_deleted = 0)
           ORDER BY id DESC LIMIT 150"""
    ).fetchall()
    tasks = []
    for r in rows:
        status = r['status'] or ''
        is_closed = status in closed
        in_qc_stage = status in qc_focus or ('تست' in status)
        ref = stage_date_for_status(conn, r['id'], status) or r['reception_date']
        days = 0 if is_closed else (_days_since(ref) or 0)
        is_delayed = (not is_closed) and days >= DELAY_THRESHOLD_DAYS
        if is_closed:
            priority = 0
        elif in_qc_stage:
            priority = 3
        elif is_delayed:
            priority = 2
        else:
            priority = 1
        tasks.append({
            'id': r['id'],
            'kind': 'تعمیر داخلی — QC' + (' ★' if in_qc_stage and not is_closed else ''),
            'customer_name': r['customer_name'],
            'serial_number': r['serial_number'],
            'device_type': r['device_type'],
            'province': r['province'],
            'status': status,
            'reception_date': r['reception_date'],
            'problem_desc': r['problem_desc'] or r['hospital_request_desc'] or '',
            'detail_url': f"/service/internal-repair/view/{r['id']}",
            'is_closed': is_closed,
            'assigned_technician': r['assigned_technician'],
            'days_in_status': days,
            'is_delayed': is_delayed,
            'in_qc_stage': in_qc_stage and not is_closed,
            '_priority': priority,
        })
    tasks.sort(key=lambda t: (-t['_priority'], t['is_closed'], -(t['id'] or 0)))
    return tasks


def get_technician_tasks(conn, user):
    """جمع‌آوری وظایف برای کارتابل تکنسین (اولویت با assigned_technician_id)."""
    name = user['full_name'] if not isinstance(user, dict) else user.get('full_name')
    role = user['role'] if not isinstance(user, dict) else user.get('role')
    province = user['province'] if not isinstance(user, dict) else user.get('province')
    uid = user['id'] if not isinstance(user, dict) else user.get('id')
    closed_statuses = tuple(CLOSED_STATUSES)
    # تشخیص وجود ستون id
    try:
        cols = {r[1] for r in conn.execute('PRAGMA table_info(requests)').fetchall()}
        has_tech_id = 'assigned_technician_id' in cols
    except Exception:
        has_tech_id = False

    if not has_tech_id or not uid:
        return []

    if role == 'تکنسین کارخانه':
        rows = conn.execute(
            """SELECT * FROM requests
               WHERE service_type = 'کارخانه' AND request_category = 'تعمیر'
                 AND (is_deleted IS NULL OR is_deleted = 0)
                 AND status IN (
                    'در انتظار دریافت قطعه تعمیر اولیه است','در انتظار تعمیر اولیه است',
                    'در انتظار ارسال گزارش فنی است','در انتظار دریافت قطعه تعمیر نهایی است',
                    'در انتظار گزارش نهایی است','در انتظار ارسال حواله تعمیر نهایی است'
                 )
                 AND assigned_technician_id = ?
               ORDER BY id DESC LIMIT 100""",
            (uid,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM requests
               WHERE (
                    (request_category = 'تعمیر' AND service_type = 'در محل')
                 OR request_category = 'نصب و آموزش'
                 OR request_category = 'بررسی و بازدید'
               )
               AND (is_deleted IS NULL OR is_deleted = 0)
               AND assigned_technician_id = ?
               AND (request_category <> 'تعمیر' OR province = ? OR province IS NULL OR province = '')
               ORDER BY id DESC LIMIT 150""",
            (uid, province),
        ).fetchall()

    tasks = []
    for r in rows:
        keys = r.keys() if hasattr(r, 'keys') else []
        assigned = r['assigned_technician']
        assigned_id = r['assigned_technician_id'] if has_tech_id and 'assigned_technician_id' in keys else None
        # اگر به فرد دیگری با id تخصیص شده، رد کن
        if assigned_id and uid and int(assigned_id) != int(uid):
            continue
        if (not assigned_id) and assigned and assigned != name:
            continue

        is_closed = (r['status'] or '') in closed_statuses
        cat = r['request_category'] or ''
        subtype = r['request_subtype'] or ''
        service_type = r['service_type'] or ''

        if cat == 'تعمیر' and service_type == 'کارخانه':
            kind = 'تعمیر داخلی'
            detail_url = f"/service/internal-repair/view/{r['id']}"
        elif cat == 'تعمیر' and service_type == 'در محل':
            kind = 'تعمیر خارجی'
            detail_url = f"/service/external-repair/view/{r['id']}"
        elif cat == 'نصب و آموزش' and subtype == 'درخواست نصب':
            kind = 'درخواست نصب'
            detail_url = f"/service/installation/request-view/{r['id']}"
        elif cat == 'نصب و آموزش' and subtype == 'ثبت نصب':
            kind = 'ثبت نصب'
            detail_url = f"/service/installation/register-view/{r['id']}"
        elif cat == 'بررسی و بازدید':
            paid = r['is_paid_visit'] if 'is_paid_visit' in r.keys() else 0
            kind = 'بازدید (غیررایگان)' if paid else 'بازدید (رایگان)'
            detail_url = f"/service/inspection/view/{r['id']}"
        else:
            kind = cat or 'سایر'
            detail_url = '/'

        ref = stage_date_for_status(conn, r['id'], r['status']) or r['reception_date']
        days = 0 if is_closed else (_days_since(ref) or 0)
        is_delayed = (not is_closed) and days >= DELAY_THRESHOLD_DAYS

        tasks.append({
            'id': r['id'],
            'kind': kind,
            'customer_name': r['customer_name'],
            'serial_number': r['serial_number'],
            'device_type': r['device_type'],
            'province': r['province'],
            'status': r['status'],
            'reception_date': r['reception_date'],
            'problem_desc': r['problem_desc'] or '',
            'detail_url': detail_url,
            'is_closed': is_closed,
            'assigned_technician': assigned,
            'days_in_status': days,
            'is_delayed': is_delayed,
        })

    tasks.sort(key=lambda t: (t['is_closed'], -(t['id'] or 0)))
    return tasks


# نام‌های مستعار با پیشوند _
_get_finance_tasks = get_finance_tasks
_get_qc_tasks = get_qc_tasks
_get_technician_tasks = get_technician_tasks
