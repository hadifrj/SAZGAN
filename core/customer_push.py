# -*- coding: utf-8 -*-
"""Web Push برای مشتریان — جدا از subscriptionهای کارمندان (core/push.py).

از همان کلید VAPID برنامه استفاده می‌کند (یک کلید برای کل دامنه کافی است)؛
فقط جدول subscription و کلید دریافت‌کننده (شماره موبایل به‌جای نام‌کاربری
کارمند) جدا نگه داشته می‌شود تا داده مشتری و کارمند مخلوط نشود.
"""
from __future__ import annotations

import os
import time
from typing import Optional

from core.push import (
    ensure_vapid_keys,
    get_vapid_public_key,  # noqa: F401  (برای import مستقیم توسط routes)
    _send_one,
    _get_vapid_claims,
    _VAPID_PRIVATE,
)


def ensure_customer_push_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_phone TEXT NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            user_agent TEXT,
            created_at TEXT,
            last_used_at TEXT,
            is_active INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_customer_push_subs_phone "
        "ON customer_push_subscriptions(customer_phone)"
    )
    conn.commit()


def save_customer_subscription(conn, phone: str, subscription: dict, user_agent: str = "") -> bool:
    try:
        endpoint = (subscription.get("endpoint") or "").strip()
        keys = subscription.get("keys") or {}
        p256dh = (keys.get("p256dh") or "").strip()
        auth = (keys.get("auth") or "").strip()
        phone = (phone or "").strip()
        if not endpoint or not p256dh or not auth or not phone:
            return False

        now = time.strftime("%Y-%m-%d %H:%M")

        existing = conn.execute(
            "SELECT id FROM customer_push_subscriptions WHERE endpoint=?", (endpoint,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE customer_push_subscriptions
                   SET customer_phone=?, p256dh=?, auth=?, user_agent=?, last_used_at=?, is_active=1
                   WHERE endpoint=?""",
                (phone, p256dh, auth, user_agent[:300] if user_agent else "", now, endpoint),
            )
        else:
            conn.execute(
                """INSERT INTO customer_push_subscriptions
                   (customer_phone, endpoint, p256dh, auth, user_agent, created_at, last_used_at, is_active)
                   VALUES (?,?,?,?,?,?,?,1)""",
                (phone, endpoint, p256dh, auth, user_agent[:300] if user_agent else "", now, now),
            )
        conn.commit()
        return True
    except Exception as e:
        print("[customer_push] save_subscription error:", e)
        return False


def remove_customer_subscription(conn, endpoint: str) -> bool:
    try:
        conn.execute("DELETE FROM customer_push_subscriptions WHERE endpoint=?", (endpoint,))
        conn.commit()
        return True
    except Exception:
        return False


def get_customer_subscriptions(conn, phone: str) -> list:
    try:
        rows = conn.execute(
            """SELECT id, endpoint, p256dh, auth FROM customer_push_subscriptions
               WHERE customer_phone=? AND is_active=1""",
            (phone,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _deactivate(conn, endpoint: str) -> None:
    try:
        conn.execute(
            "UPDATE customer_push_subscriptions SET is_active=0 WHERE endpoint=?",
            (endpoint,),
        )
        conn.commit()
    except Exception:
        pass


def send_customer_web_push(
    conn,
    phone: str,
    title: str,
    body: str = "",
    url: str = "/c/status",
    icon: str = "/static/icons/icon-192.png",
    badge: str = "/static/icons/icon-96.png",
    data: Optional[dict] = None,
) -> int:
    """ارسال Web Push به همهٔ دستگاه‌های ثبت‌شدهٔ یک مشتری. تعداد ارسال موفق را برمی‌گرداند."""
    subs = get_customer_subscriptions(conn, phone)
    if not subs:
        return 0

    if not ensure_vapid_keys() or not os.path.isfile(_VAPID_PRIVATE):
        print("[customer_push] no VAPID private key")
        return 0

    claims = dict(_get_vapid_claims())
    claims.setdefault("sub", "mailto:admin@sazgan.local")

    payload = {
        "title": title or "سازگان",
        "body": body or "",
        "icon": icon,
        "badge": badge,
        "tag": "sazgan-customer",
        "url": url or "/c/status",
        "data": data or {},
        "timestamp": int(time.time() * 1000),
        "dir": "rtl",
        "lang": "fa",
    }

    sent = 0
    for sub in subs:
        ok, err = _send_one(sub, payload, _VAPID_PRIVATE, claims)
        if ok:
            sent += 1
        elif err == "expired":
            _deactivate(conn, sub["endpoint"])
        else:
            print(f"[customer_push] send failed for {sub['endpoint'][:50]}...: {err}")

    try:
        conn.commit()
    except Exception:
        pass
    return sent
