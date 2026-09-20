# -*- coding: utf-8 -*-
"""هسته فاز ۲: پرونده مشتری، دستگاه و Timeline خدمات."""
from __future__ import annotations
from datetime import datetime

STATUS_FLOW = [
    ("ثبت شد", "درخواست مشتری ثبت شد"),
    ("پذیرش شد", "پذیرش و بررسی اولیه"),
    ("در حال بررسی", "در حال بررسی توسط کارشناس"),
    ("در انتظار قطعه", "در انتظار تامین قطعه"),
    ("در حال تعمیر", "عملیات تعمیر در حال انجام است"),
    ("کنترل کیفیت", "کنترل کیفیت و آزمون"),
    ("آماده تحویل", "دستگاه آماده تحویل است"),
    ("بسته شد", "پرونده بسته شد"),
]


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


def ensure_case_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            device_type TEXT NOT NULL,
            serial_number TEXT,
            model TEXT,
            purchase_date TEXT,
            warranty_until TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(customer_id, serial_number)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS case_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            event_type TEXT NOT NULL DEFAULT 'system',
            title TEXT NOT NULL,
            body TEXT,
            actor_type TEXT NOT NULL DEFAULT 'system',
            actor_name TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_case_timeline_request ON case_timeline(request_id, id)")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(requests)").fetchall()}
    wanted = {
        "customer_id": "INTEGER",
        "device_id": "INTEGER",
        "case_priority": "TEXT DEFAULT 'عادی'",
        "status_changed_at": "TEXT",
        "closed_at": "TEXT",
    }
    for name, typ in wanted.items():
        if name not in cols:
            try:
                conn.execute(f"ALTER TABLE requests ADD COLUMN {name} {typ}")
            except Exception:
                pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_customer_id_phase2 ON requests(customer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_devices_customer_phase2 ON customer_devices(customer_id)")
    conn.commit()


def upsert_device(conn, customer_id, device_type, serial_number=None, model=None):
    ensure_case_schema(conn)
    device_type = (device_type or "دستگاه ثبت نشده").strip()
    serial_number = (serial_number or "").strip()
    now = now_iso()
    if serial_number:
        row = conn.execute("SELECT id FROM customer_devices WHERE customer_id=? AND serial_number=?", (customer_id, serial_number)).fetchone()
        if row:
            conn.execute("UPDATE customer_devices SET device_type=?, model=COALESCE(NULLIF(?,''),model), updated_at=? WHERE id=?", (device_type, model or "", now, row["id"]))
            return row["id"]
    cur = conn.execute("INSERT INTO customer_devices(customer_id,device_type,serial_number,model,created_at,updated_at) VALUES(?,?,?,?,?,?)", (customer_id, device_type, serial_number or None, model or None, now, now))
    return cur.lastrowid


def add_timeline(conn, request_id, title, body=None, event_type="system", actor_type="system", actor_name=None):
    ensure_case_schema(conn)
    conn.execute("INSERT INTO case_timeline(request_id,event_type,title,body,actor_type,actor_name,created_at) VALUES(?,?,?,?,?,?,?)", (request_id, event_type, title, body, actor_type, actor_name, now_iso()))


def set_case_status(conn, request_id, new_status, actor_name=None, body=None):
    ensure_case_schema(conn)
    req = conn.execute(
        "SELECT request_category, service_type FROM requests WHERE id=?", (request_id,)
    ).fetchone()
    if req and (req["request_category"] or "") == "تعمیر" and (req["service_type"] or "") in ("کارخانه", "در محل"):
        # تعمیر داخلی/خارجی فقط از هسته‌ی Workflow عبور می‌کند؛ این helper عمومی
        # نباید به مسیر فرار برای تغییر مستقیم status تبدیل شود.
        raise ValueError("تغییر وضعیت تعمیر باید از core.workflow.transition_request انجام شود.")
    now = now_iso()
    closed_at = now if new_status == "بسته شد" else None
    conn.execute("UPDATE requests SET status=?, status_changed_at=?, closed_at=COALESCE(?,closed_at) WHERE id=?", (new_status, now, closed_at, request_id))
    add_timeline(conn, request_id, "تغییر وضعیت پرونده", body or f"وضعیت پرونده به «{new_status}» تغییر کرد.", "status", "staff", actor_name)


def case_timeline(conn, request_id):
    ensure_case_schema(conn)
    return conn.execute("SELECT * FROM case_timeline WHERE request_id=? ORDER BY id DESC", (request_id,)).fetchall()
