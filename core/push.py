# -*- coding: utf-8 -*-
"""
Web Push notifications — سازگان
==============================
ارسال اعلان پس‌زمینه از طریق Web Push Protocol.
پشتیبانی از چند دستگاه برای هر کاربر و پاک‌سازی خودکار subscriptionهای منقضی.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Optional

from core.constants import BASE_DIR

# ---------------------------------------------------------------------------
# VAPID keys (تولید یک‌بار، ذخیره پایدار روی دیسک)
# ---------------------------------------------------------------------------
_VAPID_DIR = os.path.join(BASE_DIR, 'data')
_VAPID_PRIVATE = os.path.join(_VAPID_DIR, 'vapid_private.pem')
_VAPID_PUBLIC = os.path.join(_VAPID_DIR, 'vapid_public.pem')
_VAPID_CLAIMS_FILE = os.path.join(_VAPID_DIR, 'vapid_claims.json')

_vapid_lock = threading.Lock()
_vapid_cache: dict[str, Any] = {}
_vapid_warn_once = False


def _ensure_vapid_dir():
    os.makedirs(_VAPID_DIR, exist_ok=True)


def _generate_vapid_keys():
    """تولید جفت کلید VAPID با py_vapid یا cryptography."""
    _ensure_vapid_dir()
    try:
        from py_vapid import Vapid01
        v = Vapid01()
        v.generate_keys()
        with open(_VAPID_PRIVATE, 'wb') as f:
            f.write(v.private_pem())
        with open(_VAPID_PUBLIC, 'wb') as f:
            f.write(v.public_pem())
        # claims
        claims = {
            'sub': 'mailto:admin@sazgan.local',
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        with open(_VAPID_CLAIMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(claims, f)
        return True
    except Exception:
        pass

    # Fallback با cryptography (EC P-256)
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend

        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        with open(_VAPID_PRIVATE, 'wb') as f:
            f.write(priv_pem)
        with open(_VAPID_PUBLIC, 'wb') as f:
            f.write(pub_pem)
        claims = {
            'sub': 'mailto:admin@sazgan.local',
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        with open(_VAPID_CLAIMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(claims, f)
        return True
    except Exception as e:
        print('[push] VAPID key generation failed:', e)
        return False


def ensure_vapid_keys() -> bool:
    """اطمینان از وجود کلیدهای VAPID. در صورت نبود تولید می‌کند."""
    with _vapid_lock:
        if os.path.isfile(_VAPID_PRIVATE) and os.path.isfile(_VAPID_PUBLIC):
            return True
        return _generate_vapid_keys()


def get_vapid_public_key() -> Optional[str]:
    """کلید عمومی VAPID به صورت URL-safe base64 (برای frontend)."""
    if not ensure_vapid_keys():
        return None
    try:
        from py_vapid import Vapid01
        v = Vapid01.from_file(_VAPID_PRIVATE)
        # applicationServerKey format
        raw = v.public_key.public_bytes(
            encoding=__import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding']).Encoding.X962,
            format=__import__('cryptography.hazmat.primitives.serialization', fromlist=['PublicFormat']).PublicFormat.UncompressedPoint,
        )
        import base64
        return base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')
    except Exception:
        pass

    # Fallback: خواندن از PEM و تبدیل
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        import base64

        with open(_VAPID_PUBLIC, 'rb') as f:
            pub = serialization.load_pem_public_key(f.read(), backend=default_backend())
        raw = pub.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        return base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')
    except Exception as e:
        global _vapid_warn_once
        if not _vapid_warn_once:
            _vapid_warn_once = True
            msg = str(e)
            if 'cryptography' in msg:
                print('[push] Web Push inactive: install deps with Sazgan.bat option 2  (pip: cryptography pywebpush py-vapid)')
            else:
                print('[push] get_vapid_public_key failed:', e)
        return None




def _get_vapid_claims() -> dict:
    try:
        with open(_VAPID_CLAIMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'sub': 'mailto:admin@sazgan.local'}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
def ensure_push_schema(conn) -> None:
    """جدول subscriptionهای Web Push."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            user_agent TEXT,
            created_at TEXT,
            last_used_at TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_push_subs_user ON push_subscriptions(user_name)'
    )
    # فیلدهای اضافی برای notifications (url و data)
    try:
        cols = {r[1] for r in conn.execute('PRAGMA table_info(notifications)').fetchall()}
        if 'url' not in cols:
            conn.execute('ALTER TABLE notifications ADD COLUMN url TEXT')
        if 'data_json' not in cols:
            conn.execute('ALTER TABLE notifications ADD COLUMN data_json TEXT')
        if 'push_sent' not in cols:
            conn.execute('ALTER TABLE notifications ADD COLUMN push_sent INTEGER DEFAULT 0')
    except Exception:
        pass
    conn.commit()


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------
def save_subscription(conn, user_name: str, subscription: dict, user_agent: str = '') -> bool:
    """ذخیره یا به‌روزرسانی subscription."""
    try:
        endpoint = (subscription.get('endpoint') or '').strip()
        keys = subscription.get('keys') or {}
        p256dh = (keys.get('p256dh') or '').strip()
        auth = (keys.get('auth') or '').strip()
        if not endpoint or not p256dh or not auth:
            return False

        from core.helpers import _now_jalali_str
        import time as _t
        now = _now_jalali_str() + ' ' + _t.strftime('%H:%M')

        existing = conn.execute(
            'SELECT id FROM push_subscriptions WHERE endpoint=?', (endpoint,)
        ).fetchone()
        if existing:
            conn.execute(
                '''UPDATE push_subscriptions
                   SET user_name=?, p256dh=?, auth=?, user_agent=?, last_used_at=?, is_active=1
                   WHERE endpoint=?''',
                (user_name, p256dh, auth, user_agent[:300] if user_agent else '', now, endpoint)
            )
        else:
            conn.execute(
                '''INSERT INTO push_subscriptions
                   (user_name, endpoint, p256dh, auth, user_agent, created_at, last_used_at, is_active)
                   VALUES (?,?,?,?,?,?,?,1)''',
                (user_name, endpoint, p256dh, auth, user_agent[:300] if user_agent else '', now, now)
            )
        conn.commit()
        return True
    except Exception as e:
        print('[push] save_subscription error:', e)
        return False


def remove_subscription(conn, endpoint: str = None, user_name: str = None, sub_id: int = None) -> bool:
    """حذف subscription (بر اساس endpoint یا id)."""
    try:
        if sub_id:
            conn.execute('DELETE FROM push_subscriptions WHERE id=?', (sub_id,))
        elif endpoint:
            conn.execute('DELETE FROM push_subscriptions WHERE endpoint=?', (endpoint,))
        elif user_name:
            conn.execute('DELETE FROM push_subscriptions WHERE user_name=?', (user_name,))
        else:
            return False
        conn.commit()
        return True
    except Exception:
        return False


def get_user_subscriptions(conn, user_name: str) -> list:
    """لیست subscriptionهای فعال یک کاربر."""
    try:
        rows = conn.execute(
            '''SELECT id, endpoint, p256dh, auth, user_agent, created_at, last_used_at
               FROM push_subscriptions
               WHERE user_name=? AND is_active=1''',
            (user_name,)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _deactivate_subscription(conn, endpoint: str):
    try:
        conn.execute(
            'UPDATE push_subscriptions SET is_active=0 WHERE endpoint=?',
            (endpoint,)
        )
        conn.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------
def _send_one(subscription_info: dict, payload: dict, vapid_private_key, claims: dict) -> tuple[bool, str]:
    """ارسال به یک endpoint. برمی‌گرداند (موفقیت، پیام خطا)."""
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        return False, 'pywebpush not installed'

    try:
        sub_info = {
            'endpoint': subscription_info['endpoint'],
            'keys': {
                'p256dh': subscription_info['p256dh'],
                'auth': subscription_info['auth'],
            },
        }
        # vapid_private_key: file path (str) or PEM string
        webpush(
            subscription_info=sub_info,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=vapid_private_key,
            vapid_claims=claims,
            ttl=86400,  # 24h
            timeout=12,
        )
        return True, ''
    except Exception as e:
        err = str(e)
        # 404 / 410 = subscription منقضی یا لغو شده
        if '404' in err or '410' in err or 'Gone' in err or 'Not Found' in err:
            return False, 'expired'
        status = getattr(getattr(e, 'response', None), 'status_code', None)
        if status in (404, 410):
            return False, 'expired'
        return False, err[:200]


def send_web_push(
    conn,
    user_name: str,
    title: str,
    body: str = '',
    url: str = '/',
    tag: str = None,
    notification_id: int = None,
    icon: str = '/static/icons/icon-192.png',
    badge: str = '/static/icons/icon-96.png',
    data: dict = None,
) -> int:
    """
    ارسال Web Push به همه دستگاه‌های فعال کاربر.
    تعداد ارسال موفق را برمی‌گرداند.
    """
    subs = get_user_subscriptions(conn, user_name)
    if not subs:
        return 0

    if not ensure_vapid_keys() or not os.path.isfile(_VAPID_PRIVATE):
        print('[push] no VAPID private key')
        return 0

    claims = dict(_get_vapid_claims())
    # pywebpush expects 'sub' claim
    if 'sub' not in claims:
        claims['sub'] = 'mailto:admin@sazgan.local'

    payload = {
        'title': title or 'سازگان',
        'body': body or '',
        'icon': icon,
        'badge': badge,
        'tag': tag or (f'sazgan-{notification_id}' if notification_id else 'sazgan'),
        'url': url or '/',
        'notification_id': notification_id,
        'data': data or {},
        'timestamp': int(time.time() * 1000),
        'dir': 'rtl',
        'lang': 'fa',
    }

    sent = 0
    for sub in subs:
        ok, err = _send_one(sub, payload, _VAPID_PRIVATE, claims)
        if ok:
            sent += 1
            try:
                from core.helpers import _now_jalali_str
                import time as _t
                now = _now_jalali_str() + ' ' + _t.strftime('%H:%M')
                conn.execute(
                    'UPDATE push_subscriptions SET last_used_at=? WHERE id=?',
                    (now, sub['id'])
                )
            except Exception:
                pass
        elif err == 'expired':
            _deactivate_subscription(conn, sub['endpoint'])
        else:
            print(f'[push] send failed for {sub["endpoint"][:50]}...: {err}')

    try:
        conn.commit()
    except Exception:
        pass
    return sent


def notify_and_push(
    conn,
    user_name: str,
    request_id: int = None,
    title: str = '',
    body: str = '',
    url: str = None,
    data: dict = None,
) -> Optional[int]:
    """
    ایجاد رکورد اعلان در دیتابیس + ارسال Web Push.
    شناسه اعلان را برمی‌گرداند.
    """
    if not user_name:
        return None

    from core.helpers import _now_jalali_str
    import time as _t
    now = _now_jalali_str() + ' ' + _t.strftime('%H:%M')

    # تعیین URL پیش‌فرض
    if not url:
        if request_id:
            url = f'/?highlight={request_id}'
        else:
            url = '/notifications'

    data_json = json.dumps(data or {}, ensure_ascii=False) if data else None

    try:
        cur = conn.execute(
            '''INSERT INTO notifications
               (user_name, request_id, title, body, is_read, created_at, url, data_json, push_sent)
               VALUES (?,?,?,?,0,?,?,?,0)''',
            (user_name, request_id, title, body or '', now, url, data_json)
        )
        nid = cur.lastrowid
        conn.commit()
    except Exception:
        # fallback بدون ستون‌های جدید
        try:
            cur = conn.execute(
                '''INSERT INTO notifications
                   (user_name, request_id, title, body, is_read, created_at)
                   VALUES (?,?,?,?,0,?)''',
                (user_name, request_id, title, body or '', now)
            )
            nid = cur.lastrowid
            conn.commit()
        except Exception as e:
            print('[push] insert notification failed:', e)
            return None

    # ارسال Web Push در پس‌زمینه (non-blocking)
    def _bg_send():
        try:
            from core.db import get_db as _get_db
            c = _get_db()
            n = send_web_push(
                c,
                user_name=user_name,
                title=title,
                body=body or '',
                url=url,
                notification_id=nid,
                data=data,
            )
            if n > 0:
                try:
                    c.execute('UPDATE notifications SET push_sent=1 WHERE id=?', (nid,))
                    c.commit()
                except Exception:
                    pass
            c.close()
        except Exception as e:
            print('[push] background send error:', e)

    try:
        t = threading.Thread(target=_bg_send, daemon=True)
        t.start()
    except Exception:
        # fallback همزمان
        try:
            send_web_push(conn, user_name, title, body or '', url, notification_id=nid, data=data)
            try:
                conn.execute('UPDATE notifications SET push_sent=1 WHERE id=?', (nid,))
                conn.commit()
            except Exception:
                pass
        except Exception:
            pass

    return nid


def get_unread_count(conn, user_name: str) -> int:
    try:
        row = conn.execute(
            'SELECT COUNT(*) AS c FROM notifications WHERE user_name=? AND is_read=0',
            (user_name,)
        ).fetchone()
        return int(row['c']) if row else 0
    except Exception:
        return 0


def cleanup_expired_subscriptions(conn, days: int = 90) -> int:
    """حذف subscriptionهایی که مدت طولانی استفاده نشده‌اند."""
    try:
        # ساده‌سازی: حذف غیرفعال‌ها
        cur = conn.execute('DELETE FROM push_subscriptions WHERE is_active=0')
        conn.commit()
        return cur.rowcount or 0
    except Exception:
        return 0
