# -*- coding: utf-8 -*-
"""شماره پذیرش ترتیبی سازگان

دو صف جدا:
  P  → پرونده عملیاتی: تعمیر / نصب دستگاه / بازدید (گزارش)
  Q  → درخواست هماهنگی: درخواست نصب / درخواست بازدید

فرمت:  {P|Q}-{سال شمسی}-{شمارنده ۵ رقمی}
مثال:  P-1405-00042   Q-1405-00007
"""
from __future__ import annotations

from typing import Optional

try:
    import jdatetime
except ImportError:
    jdatetime = None


# ---------------------------------------------------------------------------
# تشخیص نوع سند → صف P یا Q
# ---------------------------------------------------------------------------

# subtypeهایی که در صف درخواست (Q) هستند
_Q_SUBTYPES = {
    'درخواست نصب',
    'درخواست بازدید',
}

# categoryهایی که اگر subtype خالی باشد و فقط درخواست باشند (رزرو)
_Q_CATEGORIES_WHEN_REQUEST = {
    # فعلاً فقط با subtype تشخیص می‌دهیم
}


def classify_series(
    request_category: Optional[str] = None,
    request_subtype: Optional[str] = None,
    service_type: Optional[str] = None,
) -> str:
    """برگرداندن 'P' یا 'Q' بر اساس نوع سند."""
    sub = (request_subtype or '').strip()
    if sub in _Q_SUBTYPES:
        return 'Q'
    # هر چیز دیگر (تعمیر، ثبت نصب، گزارش بازدید، اعلام خرابی، …) → P
    return 'P'


def _current_jalali_year() -> int:
    if jdatetime is not None:
        try:
            return int(jdatetime.date.today().year)
        except Exception:
            pass
    return 1405


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def ensure_reception_schema(conn) -> None:
    """جدول شمارنده + ستون reception_no روی requests."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reception_counters (
            series TEXT NOT NULL,
            year INTEGER NOT NULL,
            last_value INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (series, year)
        )
        """
    )
    cols = {row[1] for row in conn.execute('PRAGMA table_info(requests)').fetchall()}
    if 'reception_no' not in cols:
        try:
            conn.execute('ALTER TABLE requests ADD COLUMN reception_no TEXT')
        except Exception:
            pass
    # ایندکس یکتا (اگر داده تکراری نباشد)
    try:
        conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_requests_reception_no '
            'ON requests(reception_no) WHERE reception_no IS NOT NULL'
        )
    except Exception:
        pass
    # این تابع از داخل عملیات پذیرش نیز فراخوانی می‌شود؛ commit کردن اینجا
    # تراکنش Route را نیمه‌کاره می‌کند و در صورت خطای مرحله بعد rollback واقعی
    # را غیرممکن می‌سازد. commit به caller سپرده می‌شود.


# ---------------------------------------------------------------------------
# تولید شماره
# ---------------------------------------------------------------------------

def allocate_reception_no(conn, series: str, year: Optional[int] = None) -> str:
    """یک شماره جدید از صف series (P یا Q) برای سال داده‌شده برمی‌گرداند.

    از تراکنش و قفل ردیف برای جلوگیری از شماره تکراری در همزمانی استفاده می‌کند.
    """
    series = (series or 'P').upper()
    if series not in ('P', 'Q'):
        series = 'P'
    if year is None:
        year = _current_jalali_year()
    year = int(year)

    ensure_reception_schema(conn)

    # اطمینان از وجود ردیف شمارنده
    row = conn.execute(
        'SELECT last_value FROM reception_counters WHERE series = ? AND year = ?',
        (series, year),
    ).fetchone()
    if not row:
        conn.execute(
            'INSERT OR IGNORE INTO reception_counters (series, year, last_value) VALUES (?, ?, 0)',
            (series, year),
        )

    # افزایش اتمی
    conn.execute(
        'UPDATE reception_counters SET last_value = last_value + 1 '
        'WHERE series = ? AND year = ?',
        (series, year),
    )
    val = conn.execute(
        'SELECT last_value FROM reception_counters WHERE series = ? AND year = ?',
        (series, year),
    ).fetchone()[0]

    return f'{series}-{year}-{int(val):05d}'


def assign_reception_no(
    conn,
    request_id: int,
    request_category: Optional[str] = None,
    request_subtype: Optional[str] = None,
    service_type: Optional[str] = None,
    series: Optional[str] = None,
) -> Optional[str]:
    """به پرونده موجود (اگر reception_no خالی باشد) شماره تخصیص می‌دهد و برمی‌گرداند."""
    if not request_id:
        return None
    ensure_reception_schema(conn)

    existing = conn.execute(
        'SELECT reception_no, request_category, request_subtype, service_type '
        'FROM requests WHERE id = ?',
        (request_id,),
    ).fetchone()
    if not existing:
        return None

    # اگر از قبل دارد، همان را برگردان
    current = None
    try:
        current = existing['reception_no'] if 'reception_no' in existing.keys() else existing[0]
    except Exception:
        current = existing[0] if existing else None
    if current:
        return current

    if series is None:
        # از آرگومان یا از خود ردیف
        cat = request_category
        sub = request_subtype
        st = service_type
        try:
            if cat is None:
                cat = existing['request_category'] if 'request_category' in existing.keys() else None
            if sub is None:
                sub = existing['request_subtype'] if 'request_subtype' in existing.keys() else None
            if st is None:
                st = existing['service_type'] if 'service_type' in existing.keys() else None
        except Exception:
            pass
        series = classify_series(cat, sub, st)

    no = allocate_reception_no(conn, series)
    conn.execute(
        'UPDATE requests SET reception_no = ? WHERE id = ? AND (reception_no IS NULL OR reception_no = \'\')',
        (no, request_id),
    )
    return no


def _sync_counters_from_existing(conn) -> None:
    """شمارنده‌ها را با بزرگ‌ترین شماره موجود در requests هم‌تراز می‌کند."""
    ensure_reception_schema(conn)
    rows = conn.execute(
        """
        SELECT reception_no FROM requests
        WHERE reception_no IS NOT NULL AND TRIM(reception_no) <> ''
        """
    ).fetchall()
    for row in rows:
        try:
            no = row['reception_no'] if hasattr(row, 'keys') else row[0]
        except Exception:
            no = row[0] if row else None
        if not no:
            continue
        parts = str(no).strip().split('-')
        if len(parts) != 3:
            continue
        series, year_s, seq_s = parts[0].upper(), parts[1], parts[2]
        if series not in ('P', 'Q') or not year_s.isdigit() or not seq_s.isdigit():
            continue
        year, seq = int(year_s), int(seq_s)
        conn.execute(
            'INSERT OR IGNORE INTO reception_counters (series, year, last_value) VALUES (?, ?, 0)',
            (series, year),
        )
        conn.execute(
            """
            UPDATE reception_counters
            SET last_value = CASE WHEN last_value < ? THEN ? ELSE last_value END
            WHERE series = ? AND year = ?
            """,
            (seq, seq, series, year),
        )


def backfill_reception_numbers(conn) -> int:
    """برای پرونده‌های قدیمی بدون شماره، بر اساس id ترتیب زمانی شماره می‌سازد.

    شمارنده‌ها با بیشترین مقدار هم‌تراز می‌شوند تا شماره‌های بعدی تکراری نشوند.
    """
    ensure_reception_schema(conn)
    try:
        _sync_counters_from_existing(conn)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    rows = conn.execute(
        '''SELECT id, request_category, request_subtype, service_type, reception_date
           FROM requests
           WHERE reception_no IS NULL OR reception_no = ''
           ORDER BY id ASC'''
    ).fetchall()
    if not rows:
        return 0

    count = 0
    for r in rows:
        try:
            rid = r['id']
            cat = r['request_category'] if 'request_category' in r.keys() else None
            sub = r['request_subtype'] if 'request_subtype' in r.keys() else None
            st = r['service_type'] if 'service_type' in r.keys() else None
        except Exception:
            rid, cat, sub, st = r[0], r[1], r[2], r[3]

        # سال از تاریخ پذیرش اگر ممکن باشد
        year = _current_jalali_year()
        try:
            rd = r['reception_date'] if 'reception_date' in r.keys() else None
            if rd:
                parts = str(rd).replace('-', '/').split('/')
                if parts and parts[0].isdigit() and len(parts[0]) == 4:
                    year = int(parts[0])
        except Exception:
            pass

        series = classify_series(cat, sub, st)
        try:
            no = allocate_reception_no(conn, series, year=year)
            conn.execute(
                "UPDATE requests SET reception_no = ? WHERE id = ? "
                "AND (reception_no IS NULL OR reception_no = '')",
                (no, rid),
            )
            count += 1
        except Exception:
            # تداخل یکتا یا قفل — این ردیف را رد کن تا استارت متوقف نشود
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                _sync_counters_from_existing(conn)
                conn.commit()
            except Exception:
                pass

    try:
        conn.commit()
    except Exception:
        pass
    return count
