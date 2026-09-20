# -*- coding: utf-8 -*-
"""چت پشتیبانی + اعلان بله.

جداول:
  support_threads  — یک گفتگو (معمولاً روی یک پرونده)
  support_messages — پیام‌ها
  bale_settings    — توکن ربات و وضعیت
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Optional, List, Any

try:
    import jdatetime
except ImportError:
    jdatetime = None


def _now() -> str:
    if jdatetime:
        d = jdatetime.datetime.now()
        return f"{d.year}/{d.month:02d}/{d.day:02d} {d.hour:02d}:{d.minute:02d}"
    from datetime import datetime
    return datetime.now().strftime('%Y/%m/%d %H:%M')


def ensure_support_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS support_threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            subject TEXT,
            opened_by_user_id INTEGER,
            opened_by_name TEXT,
            opened_by_role TEXT,
            contact_phone TEXT,
            status TEXT DEFAULT 'باز',
            priority TEXT DEFAULT 'عادی',
            last_message_at TEXT,
            created_at TEXT,
            closed_at TEXT,
            closed_by TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            sender_user_id INTEGER,
            sender_name TEXT NOT NULL,
            body TEXT NOT NULL,
            attachment_filename TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bale_link (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            chat_id TEXT NOT NULL,
            linked_at TEXT
        )
        """
    )
    cols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
    if 'bale_chat_id' not in cols:
        try:
            conn.execute('ALTER TABLE users ADD COLUMN bale_chat_id TEXT')
        except Exception:
            pass
    if 'mobile' not in cols:
        try:
            conn.execute('ALTER TABLE users ADD COLUMN mobile TEXT')
        except Exception:
            pass
    # ستون پیوست روی پیام‌های قدیمی
    msg_cols = {r[1] for r in conn.execute('PRAGMA table_info(support_messages)').fetchall()}
    if 'attachment_filename' not in msg_cols:
        try:
            conn.execute('ALTER TABLE support_messages ADD COLUMN attachment_filename TEXT')
        except Exception:
            pass
    if 'attachment_original' not in msg_cols:
        try:
            conn.execute('ALTER TABLE support_messages ADD COLUMN attachment_original TEXT')
        except Exception:
            pass
    if 'delivery_status' not in msg_cols:
        try:
            conn.execute("ALTER TABLE support_messages ADD COLUMN delivery_status TEXT DEFAULT 'sent'")
        except Exception:
            pass
    if 'is_edited' not in msg_cols:
        try:
            conn.execute("ALTER TABLE support_messages ADD COLUMN is_edited INTEGER DEFAULT 0")
        except Exception:
            pass
    if 'edited_at' not in msg_cols:
        try:
            conn.execute('ALTER TABLE support_messages ADD COLUMN edited_at TEXT')
        except Exception:
            pass
    if 'reply_to_id' not in msg_cols:
        try:
            conn.execute('ALTER TABLE support_messages ADD COLUMN reply_to_id INTEGER')
        except Exception:
            pass
    # ستون‌های یکپارچه‌سازی با اعلام خرابی عمومی
    th_cols = {r[1] for r in conn.execute('PRAGMA table_info(support_threads)').fetchall()}
    for col, decl in (
        ('announcement_id', 'INTEGER'),
        ('public_token', 'TEXT'),
        ('source', "TEXT DEFAULT 'internal'"),
        ('opened_by_role', 'TEXT'),
    ):
        if col not in th_cols:
            try:
                conn.execute(f'ALTER TABLE support_threads ADD COLUMN {col} {decl}')
            except Exception:
                pass
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_st_request ON support_threads(request_id)'
    )
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_st_token ON support_threads(public_token)'
    )
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_st_announce ON support_threads(announcement_id)'
    )
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_st_status ON support_threads(status)'
    )
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_sm_thread ON support_messages(thread_id)'
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS support_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            actor_key TEXT NOT NULL,
            emoji TEXT NOT NULL,
            created_at TEXT,
            UNIQUE(message_id, actor_key, emoji)
        )"""
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sr_message ON support_reactions(message_id)')
    # Chat V3 foundation: quick replies, tags, pins and internal notes.
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_quick_reply_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, sort_order INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_quick_replies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL, category_id INTEGER,
        is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0, scope TEXT NOT NULL DEFAULT 'internal', created_by INTEGER, updated_by INTEGER, created_at TEXT, updated_at TEXT
    )''')
    # Migration for existing databases; harmless for a new empty database.
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(chat_quick_replies)").fetchall()]
        if 'scope' not in cols:
            conn.execute("ALTER TABLE chat_quick_replies ADD COLUMN scope TEXT NOT NULL DEFAULT 'internal'")
    except Exception:
        pass
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, created_at TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_conversation_tags (
        conversation_id INTEGER NOT NULL, tag_id INTEGER NOT NULL, created_at TEXT,
        PRIMARY KEY(conversation_id, tag_id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_pinned_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
        pinned_by INTEGER, created_at TEXT, UNIQUE(conversation_id, message_id)
    )''')
    # Internal notes are messages with sender_type='internal' and never exposed to public chat.
    conn.execute('CREATE INDEX IF NOT EXISTS idx_qr_active ON chat_quick_replies(is_active, sort_order)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_ct_conversation ON chat_conversation_tags(conversation_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_cp_conversation ON chat_pinned_messages(conversation_id)')
    try:
        conn.commit()
    except Exception:
        pass


def get_bale_config(conn) -> dict:
    ensure_support_schema(conn)
    try:
        from core.db import get_setting
        raw = get_setting(conn, 'bale_config', '') or ''
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return {'token': '', 'enabled': False}


def save_bale_config(conn, conf: dict) -> None:
    from core.db import set_setting
    set_setting(conn, 'bale_config', json.dumps(conf, ensure_ascii=False))


def _normalize_token(token: str) -> str:
    return (token or '').strip()


def bale_api(token: str, method: str, payload: dict) -> dict:
    token = _normalize_token(token)
    if not token:
        return {'ok': False, 'error': 'no token'}
    url = f'https://tapi.bale.ai/bot{token}/{method}'
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url, data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode('utf-8') or '{}')
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def send_bale_message(conn, chat_id: str, text: str, button_url: Optional[str] = None, force: bool = False) -> dict:
    conf = get_bale_config(conn)
    if not force and not conf.get('enabled'):
        return {'ok': False, 'error': 'disabled'}
    token = conf.get('token') or ''
    payload = {'chat_id': chat_id, 'text': text}
    if button_url:
        payload['reply_markup'] = {
            'inline_keyboard': [[{'text': 'مشاهده', 'url': button_url}]]
        }
    return bale_api(token, 'sendMessage', payload)


def _notify_users_bale_sync(conn, user_ids, text: str, button_url: Optional[str] = None) -> int:
    conf = get_bale_config(conn)
    if not conf.get('enabled'):
        return 0
    n = 0
    for uid in user_ids or []:
        try:
            row = conn.execute('SELECT bale_chat_id FROM users WHERE id=?', (uid,)).fetchone()
            chat_id = row['bale_chat_id'] if row else None
            if chat_id:
                r = send_bale_message(conn, str(chat_id), text, button_url=button_url)
                if r.get('ok'):
                    n += 1
        except Exception:
            pass
    return n


def notify_users_bale(conn, user_ids, text: str, button_url: Optional[str] = None, background: bool = True) -> int:
    ids = list(user_ids or [])
    if not ids:
        return 0
    if not background:
        return _notify_users_bale_sync(conn, ids, text, button_url)
    try:
        import threading
        # snapshot needed data — use sync in thread with new connection ideally;
        # keep simple sync fallback if thread fails
        def _run():
            try:
                _notify_users_bale_sync(conn, ids, text, button_url)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()
        return 0
    except Exception as e:
        print('[bale] thread start:', e)
        return _notify_users_bale_sync(conn, ids, text, button_url)


def get_or_create_thread(conn, request_id, user, subject: str = '') -> int:
    ensure_support_schema(conn)
    if request_id:
        row = conn.execute(
            "SELECT id FROM support_threads WHERE request_id = ? AND status != 'بسته' ORDER BY id DESC LIMIT 1",
            (request_id,),
        ).fetchone()
        if row:
            return row['id']
    uid = user.get('id') if isinstance(user, dict) else user['id']
    name = user.get('full_name') if isinstance(user, dict) else user['full_name']
    role = user.get('role') if isinstance(user, dict) else user['role']
    now = _now()
    if not subject and request_id:
        subject = f'پشتیبانی پرونده #{request_id}'
    cur = conn.execute(
        """INSERT INTO support_threads
           (request_id, subject, opened_by_user_id, opened_by_name, opened_by_role,
            status, priority, last_message_at, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (request_id, subject or 'پشتیبانی', uid, name, role, 'باز', 'عادی', now, now),
    )
    conn.commit()
    return cur.lastrowid


def post_message(
    conn,
    thread_id,
    user,
    body: str,
    sender_type: str = 'user',
    attachment_filename: Optional[str] = None,
    attachment_original: Optional[str] = None,
    reply_to_id: Optional[int] = None,
) -> int:
    ensure_support_schema(conn)
    uid = user.get('id') if isinstance(user, dict) else (user['id'] if user else None)
    name = (user.get('full_name') if isinstance(user, dict) else user['full_name']) if user else 'سیستم'
    now = _now()
    text = (body or '').strip()
    if not text and attachment_filename:
        text = '📎 فایل پیوست'
    rid = int(reply_to_id) if reply_to_id else None
    cur = conn.execute(
        """INSERT INTO support_messages
           (thread_id, sender_type, sender_user_id, sender_name, body,
            attachment_filename, attachment_original, is_read, delivery_status, created_at, reply_to_id)
           VALUES (?,?,?,?,?,?,?,0,'sent',?,?)""",
        (thread_id, sender_type, uid, name, text or '—',
         attachment_filename, attachment_original, now, rid),
    )
    conn.execute(
        "UPDATE support_threads SET last_message_at=? WHERE id=?",
        (now, thread_id),
    )
    # فقط پیام مشتری گفتگوی بسته‌شده را دوباره باز می‌کند
    if sender_type == 'user':
        conn.execute(
            "UPDATE support_threads SET status='باز', closed_at=NULL, closed_by=NULL WHERE id=? AND status='بسته'",
            (thread_id,),
        )
    conn.commit()
    return cur.lastrowid


def edit_message(conn, message_id, new_body: str) -> bool:
    """ویرایش متن یک پیام از پیش ارسال‌شده. پیوست (در صورت وجود) دست‌نخورده می‌ماند."""
    ensure_support_schema(conn)
    text = (new_body or '').strip()
    if not text:
        return False
    now = _now()
    conn.execute(
        "UPDATE support_messages SET body=?, is_edited=1, edited_at=? WHERE id=?",
        (text, now, message_id),
    )
    conn.commit()
    return True


def list_messages(conn, thread_id, after_id: int = 0):
    ensure_support_schema(conn)
    if after_id:
        return conn.execute(
            'SELECT * FROM support_messages WHERE thread_id = ? AND id > ? ORDER BY id ASC',
            (thread_id, after_id),
        ).fetchall()
    return conn.execute(
        'SELECT * FROM support_messages WHERE thread_id = ? ORDER BY id ASC',
        (thread_id,),
    ).fetchall()


def close_thread(conn, thread_id, user) -> bool:
    ensure_support_schema(conn)
    name = ''
    if user:
        name = user.get('full_name') if isinstance(user, dict) else user['full_name']
    now = _now()
    conn.execute(
        "UPDATE support_threads SET status='بسته', closed_at=?, closed_by=? WHERE id=?",
        (now, name or '—', thread_id),
    )
    conn.commit()
    return True


def reopen_thread(conn, thread_id) -> bool:
    ensure_support_schema(conn)
    conn.execute(
        "UPDATE support_threads SET status='باز', closed_at=NULL, closed_by=NULL WHERE id=?",
        (thread_id,),
    )
    conn.commit()
    return True


def list_threads(conn, status: str = 'باز', q: str = '', user=None, is_staff: bool = False):
    """لیست گفتگوها با فیلتر وضعیت و جستجو."""
    ensure_support_schema(conn)
    where = ['1=1']
    params: List[Any] = []
    if status and status != 'all':
        where.append('t.status = ?')
        params.append(status)
    if q:
        like = f'%{q.strip()}%'
        where.append(
            '(IFNULL(t.subject,"") LIKE ? OR IFNULL(t.opened_by_name,"") LIKE ?'
            ' OR IFNULL(t.contact_phone,"") LIKE ? OR IFNULL(t.public_token,"") LIKE ?'
            ' OR CAST(t.id AS TEXT)=? OR CAST(IFNULL(t.request_id,0) AS TEXT)=?)'
        )
        params.extend([like, like, like, like, q.strip(), q.strip()])
    if user and not is_staff:
        # کاربر عادی: فقط گفتگوهای خودش (نه گفتگوهای عمومی مشتری)
        try:
            uid = user['id'] if not isinstance(user, dict) else user.get('id')
        except Exception:
            uid = None
        if uid is not None:
            where.append('t.opened_by_user_id = ?')
            params.append(uid)
        else:
            where.append('0=1')
    sql = f'''
        SELECT t.*,
          (SELECT COUNT(*) FROM support_messages m
             WHERE m.thread_id = t.id AND IFNULL(m.is_read,0)=0
               AND m.sender_type != 'user') AS unread_support,
          (SELECT COUNT(*) FROM support_messages m
             WHERE m.thread_id = t.id AND IFNULL(m.is_read,0)=0
               AND m.sender_type = 'user') AS unread_user,
          (SELECT body FROM support_messages m WHERE m.thread_id=t.id ORDER BY m.id DESC LIMIT 1) AS last_body
        FROM support_threads t
        WHERE {' AND '.join(where)}
        ORDER BY
          CASE WHEN t.status='باز' THEN 0 ELSE 1 END,
          IFNULL(t.last_message_at, t.created_at) DESC
        LIMIT 200
    '''
    return conn.execute(sql, params).fetchall()


def mark_thread_read(conn, thread_id, for_staff: bool = False) -> None:
    """علامت‌گذاری پیام‌ها به‌عنوان خوانده‌شده (دو تیک آبی)."""
    ensure_support_schema(conn)
    if for_staff:
        conn.execute(
            """UPDATE support_messages SET is_read=1, delivery_status='read'
               WHERE thread_id=? AND sender_type='user'""",
            (thread_id,),
        )
    else:
        conn.execute(
            """UPDATE support_messages SET is_read=1, delivery_status='read'
               WHERE thread_id=? AND sender_type!='user'""",
            (thread_id,),
        )
    conn.commit()


def mark_messages_delivered(conn, thread_id, viewer_is_staff: bool = False) -> None:
    """وقتی طرف مقابل پیام‌ها را از API می‌گیرد → delivered (دو تیک خاکستری)."""
    ensure_support_schema(conn)
    if viewer_is_staff:
        # staff viewing → customer messages delivered
        conn.execute(
            """UPDATE support_messages SET delivery_status='delivered'
               WHERE thread_id=? AND sender_type='user'
                 AND IFNULL(delivery_status,'sent')='sent'""",
            (thread_id,),
        )
    else:
        conn.execute(
            """UPDATE support_messages SET delivery_status='delivered'
               WHERE thread_id=? AND sender_type!='user'
                 AND IFNULL(delivery_status,'sent')='sent'""",
            (thread_id,),
        )
    conn.commit()


def create_public_thread(conn, *, subject, contact_name, contact_phone, announcement_id=None, request_id=None, first_message='', serial_number=None):
    """ایجاد گفتگوی مشتری از فرم عمومی اعلام خرابی؛ برمی‌گرداند (thread_id, public_token).

    اگر serial_number داده شود، به‌عنوان یک پیام جداگانه (قبل از پیام اصلی)
    ثبت می‌شود — نه بهم‌چسبیده با متن پیام کاربر."""
    import secrets
    import time as _time
    ensure_support_schema(conn)
    token = secrets.token_urlsafe(16)
    now = _now()
    cur = conn.execute(
        """INSERT INTO support_threads
           (request_id, announcement_id, subject, opened_by_user_id, opened_by_name, opened_by_role,
            contact_phone, status, priority, last_message_at, created_at, public_token, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            request_id,
            announcement_id,
            subject or 'پیگیری اعلام خرابی',
            None,
            contact_name or 'مشتری',
            'مشتری',
            contact_phone or '',
            'باز',
            'عادی',
            now,
            now,
            token,
            'public_announce',
        ),
    )
    tid = cur.lastrowid
    serial_number = (serial_number or '').strip()
    if serial_number:
        conn.execute(
            """INSERT INTO support_messages
               (thread_id, sender_type, sender_user_id, sender_name, body, is_read, delivery_status, created_at)
               VALUES (?,?,?,?,?,0,'sent',?)""",
            (tid, 'user', None, contact_name or 'مشتری', f'سریال دستگاه: {serial_number}', now),
        )
    if first_message and first_message.strip():
        conn.execute(
            """INSERT INTO support_messages
               (thread_id, sender_type, sender_user_id, sender_name, body, is_read, delivery_status, created_at)
               VALUES (?,?,?,?,?,0,'sent',?)""",
            (tid, 'user', None, contact_name or 'مشتری', first_message.strip(), now),
        )
    conn.commit()
    return tid, token


def get_thread_by_token(conn, token: str):
    ensure_support_schema(conn)
    if not token:
        return None
    return conn.execute(
        'SELECT * FROM support_threads WHERE public_token=?',
        (token,),
    ).fetchone()


def post_public_message(conn, thread_id, sender_name: str, body: str, attachment_filename=None, attachment_original=None, reply_to_id=None) -> int:
    ensure_support_schema(conn)
    now = _now()
    text_body = (body or '').strip()
    if not text_body and attachment_filename:
        text_body = '📎 فایل پیوست'
    rid = None
    try:
        rid = int(reply_to_id) if reply_to_id else None
    except Exception:
        rid = None
    cur = conn.execute(
        """INSERT INTO support_messages
           (thread_id, sender_type, sender_user_id, sender_name, body,
            attachment_filename, attachment_original, is_read, delivery_status, created_at, reply_to_id)
           VALUES (?,?,?,?,?,?,?,0,'sent',?,?)""",
        (thread_id, 'user', None, sender_name or 'مشتری', text_body or '—',
         attachment_filename, attachment_original, now, rid),
    )
    conn.execute(
        "UPDATE support_threads SET last_message_at=?, status='باز', closed_at=NULL, closed_by=NULL WHERE id=?",
        (now, thread_id),
    )
    conn.commit()
    return cur.lastrowid


def list_reactions(conn, message_id):
    rows = conn.execute(
        'SELECT emoji, COUNT(*) AS count FROM support_reactions WHERE message_id=? GROUP BY emoji ORDER BY count DESC, emoji',
        (message_id,)
    ).fetchall()
    return [{'emoji': r['emoji'], 'count': int(r['count'] or 0)} for r in rows]

def toggle_reaction(conn, message_id, actor_key, emoji):
    ensure_support_schema(conn)
    emoji = (emoji or '').strip()
    if not emoji or len(emoji) > 8:
        return False
    row = conn.execute('SELECT id FROM support_reactions WHERE message_id=? AND actor_key=? AND emoji=?', (message_id, actor_key, emoji)).fetchone()
    if row:
        conn.execute('DELETE FROM support_reactions WHERE id=?', (row['id'],))
        conn.commit()
        return False
    conn.execute('INSERT INTO support_reactions(message_id,actor_key,emoji,created_at) VALUES(?,?,?,?)', (message_id, actor_key, emoji, _now()))
    conn.commit()
    return True
