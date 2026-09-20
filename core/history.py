# -*- coding: utf-8 -*-
"""تاریخچه پرونده و برچسب زمانی ایجاد/ویرایش."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

try:
    import jdatetime
except ImportError:
    jdatetime = None


def now_stamp() -> str:
    """تاریخ و ساعت شمسی."""
    try:
        if jdatetime is not None:
            n = jdatetime.datetime.now()
            return n.strftime('%Y/%m/%d %H:%M:%S')
    except Exception:
        pass
    return time.strftime('%Y/%m/%d %H:%M:%S')


def ensure_history_schema(conn) -> None:
    """ستون‌های تاریخچه روی requests + ایندکس فاکتور یکتا."""
    cols = {r[1] for r in conn.execute('PRAGMA table_info(requests)').fetchall()}
    for col, typedef in (
        ('created_at', 'TEXT'),
        ('updated_at', 'TEXT'),
        ('created_by', 'TEXT'),
        ('updated_by', 'TEXT'),
    ):
        if col not in cols:
            try:
                conn.execute(f'ALTER TABLE requests ADD COLUMN {col} {typedef}')
            except Exception:
                pass
    try:
        conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_requests_invoice_unique '
            'ON requests(invoice_number) WHERE invoice_number IS NOT NULL AND invoice_number != \'\''
        )
    except Exception:
        pass
    conn.execute(
        """CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            user_name TEXT,
            action TEXT,
            entity_type TEXT,
            entity_id INTEGER,
            details TEXT
        )"""
    )
    try:
        conn.commit()
    except Exception:
        pass


def log_case_event(
    conn,
    user_name: Optional[str],
    request_id: Optional[int],
    action: str,
    details: str = '',
) -> None:
    """ثبت رویداد تاریخچه پرونده."""
    try:
        conn.execute(
            'INSERT INTO audit_log (created_at, user_name, action, entity_type, entity_id, details) '
            'VALUES (?,?,?,?,?,?)',
            (now_stamp(), user_name or '-', action, 'request', request_id, details or ''),
        )
    except Exception:
        pass


def stamp_create(conn, request_id: int, user_name: Optional[str]) -> None:
    try:
        conn.execute(
            'UPDATE requests SET created_at=COALESCE(created_at, ?), created_by=COALESCE(created_by, ?), '
            'updated_at=?, updated_by=? WHERE id=?',
            (now_stamp(), user_name or '-', now_stamp(), user_name or '-', request_id),
        )
    except Exception:
        pass
    log_case_event(conn, user_name, request_id, 'ایجاد پذیرش', '')


def stamp_update(conn, request_id: int, user_name: Optional[str], action: str = 'ویرایش اطلاعات', details: str = '') -> None:
    try:
        conn.execute(
            'UPDATE requests SET updated_at=?, updated_by=? WHERE id=?',
            (now_stamp(), user_name or '-', request_id),
        )
    except Exception:
        pass
    log_case_event(conn, user_name, request_id, action, details)


def get_case_history(conn, request_id: int, limit: int = 200) -> List[Dict[str, Any]]:
    """تاریخچه کامل یک پرونده بر اساس audit_log."""
    rows = conn.execute(
        """SELECT created_at, user_name, action, details
           FROM audit_log
           WHERE entity_type='request' AND entity_id=?
           ORDER BY id DESC LIMIT ?""",
        (request_id, limit),
    ).fetchall()
    out = []
    for r in rows:
        out.append({
            'created_at': r['created_at'],
            'user_name': r['user_name'],
            'action': r['action'],
            'details': r['details'] or '',
        })
    return out


def invoice_is_duplicate(conn, invoice_number: str, exclude_request_id: Optional[int] = None) -> bool:
    inv = (invoice_number or '').strip()
    if not inv:
        return False
    if exclude_request_id:
        row = conn.execute(
            'SELECT id FROM requests WHERE invoice_number=? AND id!=? LIMIT 1',
            (inv, exclude_request_id),
        ).fetchone()
    else:
        row = conn.execute(
            'SELECT id FROM requests WHERE invoice_number=? LIMIT 1',
            (inv,),
        ).fetchone()
    return bool(row)
