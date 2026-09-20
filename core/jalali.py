# -*- coding: utf-8 -*-
"""ابزار تاریخ شمسی."""
from __future__ import annotations

import jdatetime


def parse_jalali(s):
    """تبدیل رشته YYYY/MM/DD شمسی به jdatetime.date یا None."""
    if not s:
        return None
    s = str(s).strip().replace('-', '/')
    parts = s.split('/')
    if len(parts) != 3:
        return None
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        return jdatetime.date(y, m, d)
    except Exception:
        return None


def add_jalali_months(jalali_str, months):
    """افزودن ماه به تاریخ شمسی؛ خروجی رشته YYYY/MM/DD یا None."""
    dt = parse_jalali(jalali_str)
    if not dt or months is None:
        return None
    try:
        months = int(months)
    except Exception:
        return None
    y, m, d = dt.year, dt.month, dt.day
    m += months
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    for day in range(d, 0, -1):
        try:
            nd = jdatetime.date(y, m, day)
            return f"{nd.year}/{nd.month:02d}/{nd.day:02d}"
        except Exception:
            continue
    return None


def days_since(jalali_str, today=None):
    """تعداد روز گذشته از تاریخ شمسی تا امروز."""
    dt = parse_jalali(jalali_str)
    if not dt:
        return None
    if today is None:
        today = jdatetime.date.today()
    try:
        return (today - dt).days
    except Exception:
        return None


def now_jalali_str():
    d = jdatetime.date.today()
    return f"{d.year}/{str(d.month).zfill(2)}/{str(d.day).zfill(2)}"


def compute_warranty_status(installation_date, warranty_end_date, explicit=None):
    if explicit == 'ابطال':
        return 'ابطال'
    if not installation_date:
        return 'تولید شده'
    end = parse_jalali(warranty_end_date) if warranty_end_date else None
    today = jdatetime.date.today()
    if end and today > end:
        return 'منقضی'
    return 'فعال'


def enrich_warranty_row(row):
    d = dict(row)
    status = compute_warranty_status(
        d.get('installation_date'),
        d.get('warranty_end_date'),
        d.get('warranty_status') if d.get('warranty_status') == 'ابطال' else None,
    )
    d['warranty_status'] = status
    return d


# نام‌های سازگار با helpers قدیمی
_parse_jalali = parse_jalali
_add_jalali_months = add_jalali_months
_days_since = days_since
_now_jalali_str = now_jalali_str
_compute_warranty_status = compute_warranty_status
_enrich_warranty_row = enrich_warranty_row


# ---- لایه دوگانه تاریخ (جلالی در UI، ISO/UTC برای محاسبات آینده) ----
def to_utc_iso(jalali_str):
    """رشته شمسی YYYY/MM/DD → ISO-8601 تاریخ میلادی یا None."""
    dt = parse_jalali(jalali_str)
    if not dt:
        return None
    try:
        g = dt.togregorian()
        return f"{g.year:04d}-{g.month:02d}-{g.day:02d}"
    except Exception:
        return None


def from_utc_iso(iso_str):
    """ISO YYYY-MM-DD میلادی → رشته شمسی YYYY/MM/DD یا None."""
    if not iso_str:
        return None
    s = str(iso_str).strip()[:10]
    parts = s.replace('/', '-').split('-')
    if len(parts) != 3:
        return None
    try:
        from datetime import date as _date
        g = _date(int(parts[0]), int(parts[1]), int(parts[2]))
        j = jdatetime.date.fromgregorian(date=g)
        return f"{j.year}/{j.month:02d}/{j.day:02d}"
    except Exception:
        return None
