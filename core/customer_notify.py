# -*- coding: utf-8 -*-
"""اعلان پوش به مشتری بر اساس مرحلهٔ کلی سرویس.

نکته طراحی: پرونده‌های سازگان ده‌ها وضعیت داخلی دقیق دارند (برای گردش‌کار
تکنسین/QC/مالی). مشتری نباید با جزئیات داخلی اسپم شود؛ او فقط باید بداند
سرویسش در کدام یک از سه مرحلهٔ کلی است:

    پذیرش شد  →  در حال تعمیر/بررسی  →  آماده تحویل

این ماژول مستقل از منطق گردش‌کار داخلی است و فقط با ``request_id`` و
رشتهٔ وضعیت فعلی کار می‌کند، بنابراین افزودن آن به نقاط مختلف routes/service.py
هیچ رفتار موجودی را تغییر نمی‌دهد (فقط بعد از commit وضعیت فراخوانی می‌شود).
"""
from __future__ import annotations

import time
from typing import Optional

from core.constants import CLOSED_STATUSES

STAGE_RECEIVED = "received"
STAGE_REPAIR = "repair"
STAGE_READY = "ready"

_STAGE_TITLES = {
    STAGE_RECEIVED: ("پذیرش شد", "درخواست شما دریافت و ثبت شد."),
    STAGE_REPAIR: ("در حال بررسی/تعمیر", "کار روی درخواست شما آغاز شد."),
    STAGE_READY: ("آماده تحویل", "درخواست شما آماده تحویل/اتمام است."),
}


def ensure_customer_notify_schema(conn) -> None:
    """جدول کوچک برای جلوگیری از ارسال تکراری پوش برای یک مرحلهٔ تکراری."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_notify_state (
            request_id INTEGER PRIMARY KEY,
            last_stage TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()


def stage_for_status(status: Optional[str]) -> str:
    """نگاشت یک وضعیت دقیق داخلی به یکی از سه مرحلهٔ کلی مشتری."""
    if not status:
        return STAGE_RECEIVED
    if status in CLOSED_STATUSES:
        return STAGE_READY
    return STAGE_REPAIR


def _get_last_stage(conn, request_id: int) -> Optional[str]:
    row = conn.execute(
        "SELECT last_stage FROM customer_notify_state WHERE request_id=?",
        (request_id,),
    ).fetchone()
    if not row:
        return None
    try:
        return row["last_stage"]
    except Exception:
        return row[0]


def _set_last_stage(conn, request_id: int, stage: str) -> None:
    now = time.strftime("%Y-%m-%d %H:%M")
    try:
        conn.execute(
            """
            INSERT INTO customer_notify_state (request_id, last_stage, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
                last_stage = excluded.last_stage,
                updated_at = excluded.updated_at
            """,
            (request_id, stage, now),
        )
        conn.commit()
    except Exception:
        # سازگاری با نسخه‌های خیلی قدیمی sqlite بدون ON CONFLICT
        try:
            conn.execute(
                "DELETE FROM customer_notify_state WHERE request_id=?",
                (request_id,),
            )
            conn.execute(
                "INSERT INTO customer_notify_state (request_id, last_stage, updated_at) VALUES (?,?,?)",
                (request_id, stage, now),
            )
            conn.commit()
        except Exception:
            pass


def _send(conn, request_id: int, stage: str) -> None:
    try:
        row = conn.execute(
            "SELECT customer_phone, reception_no FROM requests WHERE id=?",
            (request_id,),
        ).fetchone()
        if not row:
            return
        try:
            phone = row["customer_phone"]
            reception_no = row["reception_no"]
        except Exception:
            phone, reception_no = row[0], row[1]
        if not phone:
            return

        title, body = _STAGE_TITLES.get(stage, ("به‌روزرسانی سرویس", ""))
        url = f"/c/status?code={reception_no}" if reception_no else "/c/status"

        from core.customer_push import send_customer_web_push

        send_customer_web_push(
            conn,
            phone,
            title=title,
            body=body,
            url=url,
            data={"request_id": request_id, "stage": stage, "reception_no": reception_no},
        )
    except Exception as e:
        print("[customer_notify] send error:", e)


def notify_request_received(conn, request_id: int) -> None:
    """هنگام ثبت پذیرش (بلافاصله بعد از تخصیص شماره پیگیری) فراخوانی شود."""
    if not request_id:
        return
    ensure_customer_notify_schema(conn)
    if _get_last_stage(conn, request_id):
        return
    _set_last_stage(conn, request_id, STAGE_RECEIVED)
    _send(conn, request_id, STAGE_RECEIVED)


def notify_status_change(conn, request_id: int, new_status: str) -> None:
    """هر جا وضعیت یک پرونده تغییر می‌کند فراخوانی شود.

    فقط وقتی مرحلهٔ کلی (نه وضعیت دقیق) عوض شود پوش ارسال می‌شود، تا مشتری
    برای هر یک از وضعیت‌های داخلی متعدد اسپم نشود.
    """
    if not request_id or not new_status:
        return
    ensure_customer_notify_schema(conn)
    stage = stage_for_status(new_status)
    last = _get_last_stage(conn, request_id)
    if stage == last:
        return
    _set_last_stage(conn, request_id, stage)
    _send(conn, request_id, stage)
