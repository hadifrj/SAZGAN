# -*- coding: utf-8 -*-
"""مسیرهای چت پشتیبانی و تنظیمات بله."""
from __future__ import annotations

import os
import secrets
from datetime import datetime
from flask import request, redirect, render_template, jsonify, session, send_from_directory
from werkzeug.utils import secure_filename

from core.helpers import *  # noqa
from core.constants import *  # noqa
from core.support_chat import (
    ensure_support_schema,
    get_or_create_thread,
    post_message,
    list_messages,
    list_threads,
    close_thread,
    reopen_thread,
    mark_thread_read,
    mark_messages_delivered,
    get_thread_by_token,
    post_public_message,
    edit_message,
    get_bale_config,
    save_bale_config,
    send_bale_message,
    notify_users_bale,
    bale_api,
    list_reactions,
    toggle_reaction,
    _now
)

SUPPORT_UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'support'
)
os.makedirs(SUPPORT_UPLOAD_DIR, exist_ok=True)
ALLOWED_EXT = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf',
    'doc', 'docx', 'xls', 'xlsx', 'zip', 'txt',
}

# ---- حضور آنلاین کارکنان پشتیبانی (in-memory) ----
# هر بار که صفحه‌ی گفتگوی داخلی/فهرست پشتیبانی باز است، یک پینگ دوره‌ای
# زده می‌شود. اگر در بازه‌ی اخیر هیچ پینگی نرسیده باشد یعنی کسی از
# پشتیبانی آنلاین نیست (مستقل از روشن/خاموش بودن خود سرور).
import time as _time
_STAFF_PRESENCE = {}
STAFF_PRESENCE_WINDOW_SECONDS = 45


def _staff_is_online() -> bool:
    now = _time.time()
    for ts in list(_STAFF_PRESENCE.values()):
        if (now - ts) <= STAFF_PRESENCE_WINDOW_SECONDS:
            return True
    return False


def _is_staff(user) -> bool:
    """کارکنان پشتیبانی که باید همه گفتگوهای مشتری را ببینند."""
    if not user:
        return False
    try:
        role = (user['role'] if not isinstance(user, dict) else user.get('role')) or ''
    except Exception:
        role = getattr(user, 'role', '') or ''
    role = str(role).strip()
    staff_roles = {
        'مسئول پذیرش', 'مدیر سیستم', 'مدیر', 'مدیر فروش',
        'کارشناس پشتیبانی', 'پشتیبان', 'پذیرش',
    }
    try:
        from core.constants import ADMIN_ROLES
        staff_roles |= set(ADMIN_ROLES)
    except Exception:
        pass
    return role in staff_roles


def _sender_type_for(user) -> str:
    return 'support' if _is_staff(user) else 'user'

DEFAULT_CHAT_EMOJIS = ['👍','❤️','😂','😮','😢','😡','👏','🔥','🎉','😍','🙏','💯']

def _load_chat_emojis(conn):
    try:
        from core.db import get_setting
        raw = get_setting(conn, 'chat_emojis', '') or ''
        vals = [x for x in raw.split(',') if x.strip()]
        return vals[:80] or DEFAULT_CHAT_EMOJIS
    except Exception:
        return DEFAULT_CHAT_EMOJIS


def _load_quick_replies(conn, scope='internal'):
    ensure_support_schema(conn)
    rows = conn.execute('''SELECT q.id, q.title, q.body, q.category_id, IFNULL(c.name,'عمومی') AS category_name
                           FROM chat_quick_replies q LEFT JOIN chat_quick_reply_categories c ON c.id=q.category_id
                           WHERE q.is_active=1 AND IFNULL(q.scope,'internal')=? ORDER BY IFNULL(c.sort_order,0), q.sort_order, q.id''', (scope,)).fetchall()
    return [dict(r) for r in rows]


def _save_support_file(file_storage):
    if not file_storage or not getattr(file_storage, 'filename', None):
        return None, None
    original = file_storage.filename
    ext = original.rsplit('.', 1)[-1].lower() if '.' in original else ''
    if ext not in ALLOWED_EXT:
        return None, None
    safe = secure_filename(original) or f'file.{ext}'
    fname = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_{safe}"
    os.makedirs(SUPPORT_UPLOAD_DIR, exist_ok=True)
    path = os.path.join(SUPPORT_UPLOAD_DIR, fname)
    file_storage.save(path)
    return fname, original


def register(app):

    def _require_user():
        u = get_current_user()
        return u

    @app.route('/support/inbox')
    def support_inbox():
        user = _require_user()
        if not user:
            return redirect('/login')
        status = (request.args.get('status') or 'باز').strip()
        q = (request.args.get('q') or '').strip()
        if status not in ('باز', 'بسته', 'all'):
            status = 'باز'
        conn = get_db()
        ensure_support_schema(conn)
        staff = _is_staff(user)
        # کارکنان همیشه همه گفتگوها (از جمله عمومی) را می‌بینند
        threads = list_threads(conn, status=status, q=q, user=user, is_staff=staff)
        # شمارش‌ها
        open_n = conn.execute("SELECT COUNT(*) c FROM support_threads WHERE status='باز'").fetchone()['c']
        closed_n = conn.execute("SELECT COUNT(*) c FROM support_threads WHERE status='بسته'").fetchone()['c']
        conn.close()
        open_thread_id = request.args.get('open')
        try:
            open_thread_id = int(open_thread_id) if open_thread_id else None
        except (TypeError, ValueError):
            open_thread_id = None
        return render_template(
            'support_inbox.html',
            threads=threads,
            status_filter=status,
            q=q,
            open_count=open_n,
            closed_count=closed_n,
            is_staff=staff,
            current_user=user,
            active_page='support-inbox',
            open_thread_id=open_thread_id,
        )

    def _load_support_thread(thread_id, user):
        """داده‌های لازم برای رندر پنل گفتگو (هم صفحه کامل، هم embed) — GET only، بدون ارسال پیام."""
        conn = get_db()
        ensure_support_schema(conn)
        th = conn.execute('SELECT * FROM support_threads WHERE id=?', (thread_id,)).fetchone()
        if not th:
            conn.close()
            return None
        staff = _is_staff(user)
        if not staff:
            uid = user.get('id') if isinstance(user, dict) else user['id']
            if th['opened_by_user_id'] and int(th['opened_by_user_id']) != int(uid):
                conn.close()
                return None
        msgs = list_messages(conn, thread_id)
        mark_thread_read(conn, thread_id, for_staff=staff)
        detail_url = None
        serial_number = None
        if th['request_id']:
            try:
                req = conn.execute('SELECT serial_number FROM requests WHERE id=?', (th['request_id'],)).fetchone()
                serial_number = req['serial_number'] if req and 'serial_number' in req.keys() else None
                detail_url = f"/request/{th['request_id']}"
            except Exception:
                detail_url = f"/support/open/{th['request_id']}"
        chat_emojis = _load_chat_emojis(conn)
        quick_replies = _load_quick_replies(conn, 'internal')
        reaction_map = {m['id']: list_reactions(conn, m['id']) for m in msgs}
        conn.close()
        return {
            'thread': th, 'messages': msgs, 'detail_url': detail_url,
            'serial_number': serial_number, 'chat_emojis': chat_emojis, 'quick_replies': quick_replies,
            'reaction_map': reaction_map, 'is_staff': staff,
        }

    @app.route('/support/thread/<int:thread_id>/embed', methods=['GET', 'POST'])
    def support_thread_embed(thread_id):
        """نسخه‌ی بدون قالب اصلی (بدون سایدبار/تاپ‌بار) برای نمایش داخل iframe در نمای دوستونی."""
        user = _require_user()
        if not user:
            return redirect('/login')
        if request.method == 'POST':
            action = (request.form.get('action') or '').strip()
            conn = get_db()
            ensure_support_schema(conn)
            if action == 'close':
                close_thread(conn, thread_id, user)
                conn.close()
                # صفحه بسته + سیگنال به والد برای رفرش لیست
                return (
                    '<!DOCTYPE html><html><body style="background:#0e1621;color:#9aa7b5;'
                    'font-family:Tahoma,sans-serif;display:flex;align-items:center;'
                    'justify-content:center;height:100vh;margin:0">'
                    '<div style="text-align:center">'
                    '<p>گفتگو بسته و به بایگانی منتقل شد.</p>'
                    '<p style="font-size:12px;opacity:.7">لیست فعلی در دسترس نیست</p>'
                    '</div>'
                    '<script>try{parent.postMessage({type:"sazgan-thread-closed",id:'
                    + str(thread_id) + '},"*" )}catch(e){}'
                    'setTimeout(function(){location.href="/support/inbox?status=%D8%A8%D8%B3%D8%AA%D9%87"},600);'
                    '</script></body></html>'
                )
            elif action == 'reopen':
                reopen_thread(conn, thread_id)
            conn.close()
            return redirect(f'/support/thread/{thread_id}/embed')
        data = _load_support_thread(thread_id, user)
        if not data:
            return redirect('/support/inbox')
        return render_template(
            'support_thread_embed.html',
            current_user=user,
            active_page='support-inbox',
            is_embed=True,
            **data,
        )

    @app.route('/support/thread/<int:thread_id>', methods=['GET', 'POST'])
    def support_thread_view(thread_id):
        user = _require_user()
        if not user:
            return redirect('/login')
        conn = get_db()
        ensure_support_schema(conn)
        th = conn.execute('SELECT * FROM support_threads WHERE id=?', (thread_id,)).fetchone()
        if not th:
            conn.close()
            return redirect('/support/inbox')

        staff = _is_staff(user)
        # دسترسی: staff همه؛ کاربر عادی فقط گفتگوی خودش
        if not staff:
            uid = user.get('id') if isinstance(user, dict) else user['id']
            if th['opened_by_user_id'] and int(th['opened_by_user_id']) != int(uid):
                conn.close()
                return redirect('/support/inbox')

        if request.method == 'POST':
            action = (request.form.get('action') or 'send').strip()
            if action == 'close':
                close_thread(conn, thread_id, user)
                conn.close()
                return redirect('/support/inbox?status=%D8%A8%D8%B3%D8%AA%D9%87')  # بسته
            if action == 'reopen':
                reopen_thread(conn, thread_id)
                conn.close()
                return redirect(f'/support/thread/{thread_id}')

            body = (request.form.get('body') or '').strip()
            f = request.files.get('attachment')
            fname, original = _save_support_file(f)
            if body or fname:
                st = _sender_type_for(user)
                reply_to = request.form.get('reply_to_id') or request.form.get('reply_to')
                try:
                    reply_to = int(reply_to) if reply_to else None
                except Exception:
                    reply_to = None
                post_message(
                    conn, thread_id, user, body,
                    sender_type=st,
                    attachment_filename=fname,
                    attachment_original=original,
                    reply_to_id=reply_to,
                )
                try:
                    if st == 'user':
                        recs = conn.execute(
                            "SELECT id FROM users WHERE role IN ('مسئول پذیرش','مدیر سیستم','مدیر') AND IFNULL(is_active,1)=1"
                        ).fetchall()
                        notify_users_bale(
                            conn, [r['id'] for r in recs],
                            f"پیام جدید در چت #{thread_id}\n{(body or original or '')[:180]}",
                        )
                    else:
                        # اطلاع به بازکننده (کاربر داخلی، در صورت وجود)
                        oid = th['opened_by_user_id']
                        if oid:
                            notify_users_bale(
                                conn, [oid],
                                f"پاسخ پشتیبانی در چت #{thread_id}\n{(body or original or '')[:180]}",
                            )
                        # اطلاع پوش به موبایل مشتری (اگر از پرتال /c/ اعلان را فعال کرده باشد)
                        try:
                            phone = (th['contact_phone'] or '').strip()
                            if phone:
                                from core.customer_push import send_customer_web_push
                                send_customer_web_push(
                                    conn, phone,
                                    title='پاسخ پشتیبانی',
                                    body=(body or original or '')[:180],
                                    url=f"/support/chat/{th['public_token']}" if th['public_token'] else '/c/requests',
                                    data={'thread_id': thread_id},
                                )
                        except Exception:
                            pass
                except Exception:
                    pass
                # رفرش thread row after possible reopen by message
                th = conn.execute('SELECT * FROM support_threads WHERE id=?', (thread_id,)).fetchone()

        msgs = list_messages(conn, thread_id)
        mark_thread_read(conn, thread_id, for_staff=staff)

        detail_url = None
        serial_number = None
        if th['request_id']:
            try:
                req = conn.execute('SELECT serial_number FROM requests WHERE id=?', (th['request_id'],)).fetchone()
                serial_number = req['serial_number'] if req and 'serial_number' in req.keys() else None
                detail_url = f"/request/{th['request_id']}"
            except Exception:
                detail_url = f"/support/open/{th['request_id']}"

        chat_emojis = _load_chat_emojis(conn)
        quick_replies = _load_quick_replies(conn, 'internal')
        reaction_map = {m['id']: list_reactions(conn, m['id']) for m in msgs}
        conn.close()
        return render_template(
            'support_thread.html',
            thread=th,
            messages=msgs,
            detail_url=detail_url,
            chat_emojis=chat_emojis,
            quick_replies=quick_replies,
            reaction_map=reaction_map,
            is_staff=staff,
            current_user=user,
            active_page='support-inbox',
        )

    @app.route('/support/open/<int:request_id>', methods=['GET', 'POST'])
    def support_open_for_request(request_id):
        user = _require_user()
        if not user:
            return redirect('/login')
        conn = get_db()
        ensure_support_schema(conn)
        req = conn.execute(
            'SELECT id, reception_no, customer_name, status FROM requests WHERE id=?',
            (request_id,),
        ).fetchone()
        if not req:
            conn.close()
            return redirect('/')
        subject = f"پشتیبانی {req['reception_no'] or ('#'+str(request_id))} — {req['customer_name']}"
        tid = get_or_create_thread(conn, request_id, user, subject=subject)
        if request.method == 'POST':
            body = (request.form.get('body') or '').strip()
            f = request.files.get('attachment')
            fname, original = _save_support_file(f)
            if body or fname:
                post_message(
                    conn, tid, user, body,
                    sender_type=_sender_type_for(user),
                    attachment_filename=fname,
                    attachment_original=original,
                )
                try:
                    recs = conn.execute(
                        "SELECT id FROM users WHERE role IN ('مسئول پذیرش','مدیر سیستم','مدیر') AND IFNULL(is_active,1)=1"
                    ).fetchall()
                    notify_users_bale(
                        conn, [r['id'] for r in recs],
                        f"چت جدید روی {req['reception_no'] or request_id}\n{(body or original or '')[:180]}",
                    )
                except Exception:
                    pass
        conn.close()
        return redirect(f'/support/thread/{tid}')

    @app.route('/api/support/thread/<int:thread_id>/messages')
    def api_support_messages(thread_id):
        user = _require_user()
        if not user:
            return jsonify({'ok': False}), 401
        after = int(request.args.get('after') or 0)
        conn = get_db()
        ensure_support_schema(conn)
        staff = _is_staff(user)
        # دریافت = delivered
        try:
            mark_messages_delivered(conn, thread_id, viewer_is_staff=staff)
            mark_thread_read(conn, thread_id, for_staff=staff)
        except Exception:
            pass
        rows = list_messages(conn, thread_id, after_id=after)
        # وضعیت تیک‌های پیام‌های خودم (همه پیام‌های thread برای sync تیک)
        mine_type = 'support' if staff else 'user'
        status_rows = conn.execute(
            """SELECT id, delivery_status, is_read FROM support_messages
               WHERE thread_id=? AND sender_type=?""",
            (thread_id, mine_type),
        ).fetchall()
        # پیام‌های ویرایش‌شدهٔ کل گفتگو (هر دو طرف) برای sync زندهٔ برچسب «ویرایش شده» و متن
        edit_rows = conn.execute(
            """SELECT id, body, is_edited FROM support_messages
               WHERE thread_id=? AND IFNULL(is_edited,0)=1""",
            (thread_id,),
        ).fetchall()
        conn.close()
        out = []
        for m in rows:
            ds = m['delivery_status'] if 'delivery_status' in m.keys() else 'sent'
            out.append({
                'id': m['id'],
                'sender_type': m['sender_type'],
                'sender_name': m['sender_name'],
                'body': m['body'],
                'created_at': m['created_at'],
                'attachment_filename': m['attachment_filename'] if 'attachment_filename' in m.keys() else None,
                'attachment_original': m['attachment_original'] if 'attachment_original' in m.keys() else None,
                'delivery_status': ds or 'sent',
                'is_read': int(m['is_read'] or 0) if 'is_read' in m.keys() else 0,
                'is_edited': int(m['is_edited'] or 0) if 'is_edited' in m.keys() else 0,
                'edited_at': m['edited_at'] if 'edited_at' in m.keys() else None,
                'reply_to_id': m['reply_to_id'] if 'reply_to_id' in m.keys() else None,
                'reactions': list_reactions(conn, m['id']),
            })
        statuses = []
        for s in status_rows:
            statuses.append({
                'id': s['id'],
                'delivery_status': s['delivery_status'] or 'sent',
                'is_read': int(s['is_read'] or 0),
            })
        edits = [{'id': e['id'], 'body': e['body'], 'is_edited': int(e['is_edited'] or 0)} for e in edit_rows]
        return jsonify({'ok': True, 'messages': out, 'statuses': statuses, 'edits': edits})

    @app.route('/api/support/thread/<int:thread_id>/send', methods=['POST'])
    def api_support_send(thread_id):
        user = _require_user()
        if not user:
            return jsonify({'ok': False, 'error': 'auth'}), 401
        conn = get_db()
        ensure_support_schema(conn)
        th = conn.execute('SELECT * FROM support_threads WHERE id=?', (thread_id,)).fetchone()
        if not th:
            conn.close()
            return jsonify({'ok': False, 'error': 'not found'}), 404
        if th['status'] == 'بسته':
            conn.close()
            return jsonify({'ok': False, 'error': 'closed'}), 400
        body = (request.form.get('body') or '').strip()
        f = request.files.get('attachment')
        fname, original = _save_support_file(f)
        if not body and not fname:
            conn.close()
            return jsonify({'ok': False, 'error': 'empty'}), 400
        st = _sender_type_for(user)
        reply_to = request.form.get('reply_to_id') or request.form.get('reply_to')
        try:
            reply_to = int(reply_to) if reply_to else None
        except Exception:
            reply_to = None
        if reply_to is not None:
            ok_reply = conn.execute(
                'SELECT 1 FROM support_messages WHERE id=? AND thread_id=? LIMIT 1',
                (reply_to, thread_id),
            ).fetchone()
            if not ok_reply:
                conn.close()
                return jsonify({'ok': False, 'error': 'invalid reply target'}), 400
        try:
            mid = post_message(
                conn, thread_id, user, body,
                sender_type=st,
                attachment_filename=fname,
                attachment_original=original,
                reply_to_id=reply_to,
            )
            row = conn.execute('SELECT * FROM support_messages WHERE id=?', (mid,)).fetchone()
        except Exception as e:
            conn.close()
            return jsonify({'ok': False, 'error': str(e)}), 500
        conn.close()
        return jsonify({
            'ok': True,
            'message': {
                'id': row['id'],
                'sender_type': row['sender_type'],
                'sender_name': row['sender_name'],
                'body': row['body'],
                'created_at': row['created_at'],
                'attachment_filename': row['attachment_filename'] if 'attachment_filename' in row.keys() else None,
                'attachment_original': row['attachment_original'] if 'attachment_original' in row.keys() else None,
                'delivery_status': 'sent',
                'is_read': 0,
                'is_edited': 0,
                'edited_at': None,
                'reply_to_id': row['reply_to_id'] if 'reply_to_id' in row.keys() else None,
                'reactions': [],
            },
        })

    @app.route('/api/support/thread/<int:thread_id>/message/<int:message_id>/edit', methods=['POST'])
    def api_support_edit_message(thread_id, message_id):
        user = _require_user()
        if not user:
            return jsonify({'ok': False, 'error': 'auth'}), 401
        new_body = (request.form.get('body') or '').strip()
        if not new_body:
            return jsonify({'ok': False, 'error': 'empty'}), 400
        conn = get_db()
        ensure_support_schema(conn)
        th = conn.execute('SELECT * FROM support_threads WHERE id=?', (thread_id,)).fetchone()
        if not th:
            conn.close()
            return jsonify({'ok': False, 'error': 'not found'}), 404
        msg = conn.execute(
            'SELECT * FROM support_messages WHERE id=? AND thread_id=?',
            (message_id, thread_id),
        ).fetchone()
        if not msg:
            conn.close()
            return jsonify({'ok': False, 'error': 'not found'}), 404
        # فقط نویسنده‌ی خودِ پیام مجاز به ویرایش است
        uid = user.get('id') if isinstance(user, dict) else user['id']
        st = _sender_type_for(user)
        owns = (msg['sender_type'] == st and msg['sender_user_id'] is not None and int(msg['sender_user_id']) == int(uid))
        if not owns:
            conn.close()
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        edit_message(conn, message_id, new_body)
        row = conn.execute('SELECT * FROM support_messages WHERE id=?', (message_id,)).fetchone()
        conn.close()
        return jsonify({
            'ok': True,
            'message': {
                'id': row['id'],
                'body': row['body'],
                'is_edited': int(row['is_edited'] or 0) if 'is_edited' in row.keys() else 1,
                'edited_at': row['edited_at'] if 'edited_at' in row.keys() else None,
            },
        })

    @app.route('/api/support/thread/<int:thread_id>/message/<int:message_id>/reaction', methods=['POST'])
    def api_support_reaction(thread_id, message_id):
        user = _require_user()
        if not user:
            return jsonify({'ok': False, 'error': 'auth'}), 401
        emoji = (request.form.get('emoji') or '').strip()
        conn = get_db(); ensure_support_schema(conn)
        msg = conn.execute('SELECT id FROM support_messages WHERE id=? AND thread_id=?', (message_id, thread_id)).fetchone()
        if not msg:
            conn.close(); return jsonify({'ok': False, 'error': 'not found'}), 404
        uid = user.get('id') if isinstance(user, dict) else user['id']
        toggle_reaction(conn, message_id, 'user:'+str(uid), emoji)
        reactions = list_reactions(conn, message_id)
        conn.close()
        return jsonify({'ok': True, 'reactions': reactions})

    @app.route('/api/support/unread-count')
    def support_unread_count():
        user = _require_user()
        if not user:
            return jsonify({'count': 0})
        conn = get_db()
        ensure_support_schema(conn)
        staff = _is_staff(user)
        if staff:
            n = conn.execute(
                """SELECT COUNT(*) c FROM support_messages m
                   JOIN support_threads t ON t.id=m.thread_id
                   WHERE IFNULL(m.is_read,0)=0 AND m.sender_type='user' AND t.status!='بسته'"""
            ).fetchone()['c']
        else:
            uid = user.get('id') if isinstance(user, dict) else user['id']
            n = conn.execute(
                """SELECT COUNT(*) c FROM support_messages m
                   JOIN support_threads t ON t.id=m.thread_id
                   WHERE IFNULL(m.is_read,0)=0 AND m.sender_type!='user'
                     AND t.opened_by_user_id=?""",
                (uid,),
            ).fetchone()['c']
        conn.close()
        return jsonify({'count': int(n or 0)})

    @app.route('/static/uploads/support/<path:filename>')
    def support_upload_file(filename):
        # نام فایل‌ها تصادفی است؛ برای گفتگوی عمومی مشتری بدون لاگین هم قابل مشاهده‌اند
        return send_from_directory(SUPPORT_UPLOAD_DIR, filename)

    @app.route('/api/support/presence/ping', methods=['POST'])
    def support_presence_ping():
        # پینگ دوره‌ای از سمت کارکنان پشتیبانی (وقتی فهرست گفتگو یا یک
        # گفتگوی خاص باز است) تا وضعیت «آنلاین» برای مشتری قابل نمایش باشد.
        user = _require_user()
        if not user or not _is_staff(user):
            return jsonify({'ok': False}), 401
        uid = user.get('id') if isinstance(user, dict) else user['id']
        _STAFF_PRESENCE[str(uid)] = _time.time()
        return jsonify({'ok': True})

    @app.route('/api/support/presence/status')
    def support_presence_status():
        # این مسیر عمومی است (بدون لاگین) تا صفحه‌ی گفتگوی مشتری بتواند
        # وضعیت آنلاین/آفلاین پشتیبانی را بدون نیاز به ورود بررسی کند.
        return jsonify({'ok': True, 'online': _staff_is_online()})



    # ---- گفتگوی عمومی مشتری (بدون لاگین، با توکن) ----
    @app.route('/support/chat/<token>', methods=['GET', 'POST'])
    def public_customer_chat(token):
        conn = get_db()
        ensure_support_schema(conn)
        th = get_thread_by_token(conn, token)
        if not th:
            conn.close()
            return render_template('public_customer_chat.html', error='لینک گفتگو نامعتبر یا منقضی است.', thread=None, messages=[], token=token)
        if request.method == 'POST' and th['status'] != 'بسته':
            body = (request.form.get('body') or '').strip()
            f = request.files.get('attachment')
            fname, original = _save_support_file(f)
            if body or fname:
                post_public_message(
                    conn, th['id'],
                    sender_name=th['opened_by_name'] or 'مشتری',
                    body=body,
                    attachment_filename=fname,
                    attachment_original=original,
                    reply_to_id=(request.form.get('reply_to_id') or request.form.get('reply_to') or None),
                )
                try:
                    recs = conn.execute(
                        "SELECT id FROM users WHERE role IN ('مسئول پذیرش','مدیر سیستم','مدیر') AND IFNULL(is_active,1)=1"
                    ).fetchall()
                    notify_users_bale(
                        conn, [r['id'] for r in recs],
                        f"پیام مشتری در گفتگو #{th['id']}\n{(body or original or '')[:180]}",
                    )
                except Exception:
                    pass
                th = get_thread_by_token(conn, token)
        msgs = list_messages(conn, th['id'])
        chat_emojis = _load_chat_emojis(conn)
        quick_replies = _load_quick_replies(conn, 'customer')
        reaction_map = {m['id']: list_reactions(conn, m['id']) for m in msgs}
        conn.close()
        agent_name = None
        for m in reversed(msgs):
            if m['sender_type'] == 'support':
                agent_name = m['sender_name']
                break
        return render_template(
            'public_customer_chat.html',
            error=None,
            thread=th,
            messages=msgs,
            token=token,
            agent_name=agent_name,
            chat_emojis=chat_emojis,
            quick_replies=quick_replies,
            reaction_map=reaction_map,
            back_url='/c/chats' if session.get('customer_portal_customer_id') else '/support',
        )

    @app.route('/api/support/chat/<token>/recent')
    def api_public_chat_recent(token):
        """گفتگوهای اخیر همین مشتری؛ حداکثر 20 مورد و فقط بر اساس هویت همان گفتگو."""
        conn = get_db()
        ensure_support_schema(conn)
        th = get_thread_by_token(conn, token)
        if not th:
            conn.close()
            return jsonify({'ok': False, 'error': 'not found'}), 404
        phone = (th['contact_phone'] or '').strip()
        name = (th['opened_by_name'] or '').strip()
        if not phone:
            rows = [th]
        else:
            rows = conn.execute(
                """SELECT t.*,
                    (SELECT body FROM support_messages m WHERE m.thread_id=t.id ORDER BY m.id DESC LIMIT 1) AS last_body,
                    (SELECT COUNT(*) FROM support_messages m WHERE m.thread_id=t.id AND m.sender_type='support' AND IFNULL(m.is_read,0)=0) AS unread_count
                   FROM support_threads t
                  WHERE t.contact_phone=? AND IFNULL(t.opened_by_name,'')=?
                  ORDER BY IFNULL(t.last_message_at,t.created_at) DESC
                  LIMIT 20""",
                (phone, name),
            ).fetchall()
        out=[]
        for r in rows:
            out.append({
                'id': r['id'], 'token': r['public_token'], 'subject': r['subject'] or 'گفتگو با شرکت',
                'status': r['status'], 'last_body': r['last_body'] if 'last_body' in r.keys() else None,
                'last_message_at': r['last_message_at'] or r['created_at'],
                'unread_count': int(r['unread_count'] or 0) if 'unread_count' in r.keys() else 0,
            })
        conn.close()
        return jsonify({'ok': True, 'current_token': token, 'items': out})

    @app.route('/api/support/chat/<token>/messages')
    def api_public_chat_messages(token):
        after = int(request.args.get('after') or 0)
        conn = get_db()
        ensure_support_schema(conn)
        th = get_thread_by_token(conn, token)
        if not th:
            conn.close()
            return jsonify({'ok': False}), 404
        try:
            mark_messages_delivered(conn, th['id'], viewer_is_staff=False)
            mark_thread_read(conn, th['id'], for_staff=False)
        except Exception:
            pass
        rows = list_messages(conn, th['id'], after_id=after)
        status_rows = conn.execute(
            """SELECT id, delivery_status, is_read FROM support_messages
               WHERE thread_id=? AND sender_type='user'""",
            (th['id'],),
        ).fetchall()
        edit_rows = conn.execute(
            """SELECT id, body, is_edited FROM support_messages
               WHERE thread_id=? AND IFNULL(is_edited,0)=1""",
            (th['id'],),
        ).fetchall()
        conn.close()
        out = []
        for m in rows:
            ds = m['delivery_status'] if 'delivery_status' in m.keys() else 'sent'
            out.append({
                'id': m['id'],
                'sender_type': m['sender_type'],
                'sender_name': m['sender_name'],
                'body': m['body'],
                'created_at': m['created_at'],
                'attachment_filename': m['attachment_filename'] if 'attachment_filename' in m.keys() else None,
                'attachment_original': m['attachment_original'] if 'attachment_original' in m.keys() else None,
                'delivery_status': ds or 'sent',
                'is_read': int(m['is_read'] or 0) if 'is_read' in m.keys() else 0,
                'is_edited': int(m['is_edited'] or 0) if 'is_edited' in m.keys() else 0,
                'edited_at': m['edited_at'] if 'edited_at' in m.keys() else None,
                'reply_to_id': m['reply_to_id'] if 'reply_to_id' in m.keys() else None,
                'reactions': list_reactions(conn, m['id']),
            })
        statuses = [{
            'id': s['id'],
            'delivery_status': s['delivery_status'] or 'sent',
            'is_read': int(s['is_read'] or 0),
        } for s in status_rows]
        edits = [{'id': e['id'], 'body': e['body'], 'is_edited': int(e['is_edited'] or 0)} for e in edit_rows]
        return jsonify({'ok': True, 'messages': out, 'statuses': statuses, 'edits': edits})

    @app.route('/api/support/chat/<token>/send', methods=['POST'])
    def api_public_chat_send(token):
        conn = get_db()
        ensure_support_schema(conn)
        th = get_thread_by_token(conn, token)
        if not th:
            conn.close()
            return jsonify({'ok': False, 'error': 'not found'}), 404
        if th['status'] == 'بسته':
            conn.close()
            return jsonify({'ok': False, 'error': 'closed'}), 400
        body = (request.form.get('body') or '').strip()
        f = request.files.get('attachment')
        fname, original = _save_support_file(f)
        if not body and not fname:
            conn.close()
            return jsonify({'ok': False, 'error': 'empty'}), 400
        reply_to = request.form.get('reply_to_id') or request.form.get('reply_to')
        try:
            reply_to = int(reply_to) if reply_to else None
        except Exception:
            reply_to = None
        if reply_to is not None:
            ok_reply = conn.execute(
                'SELECT 1 FROM support_messages WHERE id=? AND thread_id=? LIMIT 1',
                (reply_to, th['id']),
            ).fetchone()
            if not ok_reply:
                conn.close()
                return jsonify({'ok': False, 'error': 'invalid reply target'}), 400
        mid = post_public_message(
            conn, th['id'],
            sender_name=th['opened_by_name'] or 'مشتری',
            body=body,
            attachment_filename=fname,
            attachment_original=original,
            reply_to_id=reply_to,
        )
        try:
            recs = conn.execute(
                "SELECT id FROM users WHERE role IN ('مسئول پذیرش','مدیر سیستم','مدیر') AND IFNULL(is_active,1)=1"
            ).fetchall()
            notify_users_bale(
                conn, [r['id'] for r in recs],
                f"پیام مشتری در گفتگو #{th['id']}\n{(body or original or '')[:180]}",
            )
        except Exception:
            pass
        row = conn.execute('SELECT * FROM support_messages WHERE id=?', (mid,)).fetchone()
        conn.close()
        return jsonify({
            'ok': True,
            'message': {
                'id': row['id'],
                'sender_type': row['sender_type'],
                'sender_name': row['sender_name'],
                'body': row['body'],
                'created_at': row['created_at'],
                'attachment_filename': row['attachment_filename'] if 'attachment_filename' in row.keys() else None,
                'attachment_original': row['attachment_original'] if 'attachment_original' in row.keys() else None,
                'delivery_status': 'sent',
                'is_read': 0,
                'is_edited': 0,
                'edited_at': None,
                # Keep the reply relation in the API response so the
                # customer chat can render the quote immediately after send.
                'reply_to_id': row['reply_to_id'] if 'reply_to_id' in row.keys() else None,
                'reactions': list_reactions(conn, row['id']),
            },
        })

    @app.route('/api/support/chat/<token>/message/<int:message_id>/reaction', methods=['POST'])
    def api_public_chat_reaction(token, message_id):
        emoji = (request.form.get('emoji') or '').strip()
        conn = get_db(); ensure_support_schema(conn)
        th = get_thread_by_token(conn, token)
        if not th:
            conn.close(); return jsonify({'ok': False, 'error': 'not found'}), 404
        msg = conn.execute('SELECT id FROM support_messages WHERE id=? AND thread_id=?', (message_id, th['id'])).fetchone()
        if not msg:
            conn.close(); return jsonify({'ok': False, 'error': 'not found'}), 404
        actor = 'public:'+token
        toggle_reaction(conn, message_id, actor, emoji)
        reactions = list_reactions(conn, message_id)
        conn.close()
        return jsonify({'ok': True, 'reactions': reactions})

    @app.route('/api/support/chat/<token>/message/<int:message_id>/edit', methods=['POST'])
    def api_public_chat_edit_message(token, message_id):
        new_body = (request.form.get('body') or '').strip()
        if not new_body:
            return jsonify({'ok': False, 'error': 'empty'}), 400
        conn = get_db()
        ensure_support_schema(conn)
        th = get_thread_by_token(conn, token)
        if not th:
            conn.close()
            return jsonify({'ok': False, 'error': 'not found'}), 404
        msg = conn.execute(
            "SELECT * FROM support_messages WHERE id=? AND thread_id=? AND sender_type='user'",
            (message_id, th['id']),
        ).fetchone()
        if not msg:
            conn.close()
            return jsonify({'ok': False, 'error': 'not found'}), 404
        edit_message(conn, message_id, new_body)
        row = conn.execute('SELECT * FROM support_messages WHERE id=?', (message_id,)).fetchone()
        conn.close()
        return jsonify({
            'ok': True,
            'message': {
                'id': row['id'],
                'body': row['body'],
                'is_edited': int(row['is_edited'] or 0) if 'is_edited' in row.keys() else 1,
                'edited_at': row['edited_at'] if 'edited_at' in row.keys() else None,
            },
        })

    @app.route('/api/support/quick-replies')
    def api_quick_replies():
        user = _require_user()
        if not user or not _is_staff(user): return jsonify({'ok': False}), 403
        scope=(request.args.get('scope') or 'internal').strip().lower();
        if scope not in ('internal','customer'): scope='internal'
        conn=get_db(); rows=_load_quick_replies(conn, scope); conn.close()
        return jsonify({'ok':True,'items':rows})

    @app.route('/settings/chat-quick-replies', methods=['GET','POST'])
    def settings_chat_quick_replies():
        user=_require_user()
        if not user or not _is_staff(user): return redirect('/')
        conn=get_db(); ensure_support_schema(conn); msg=None; err=None
        action=request.form.get('action','')
        try:
            if request.method=='POST':
                if action=='save':
                    title=(request.form.get('title') or '').strip(); body=(request.form.get('body') or '').strip(); scope=(request.form.get('scope') or 'internal').strip().lower()
                    if scope not in ('internal','customer'): scope='internal'
                    rid=request.form.get('id') or ''
                    if not title or not body: raise ValueError('عنوان و متن پیام الزامی است.')
                    now=_now()
                    uid=user.get('id') if isinstance(user,dict) else user['id']
                    if rid:
                        conn.execute('UPDATE chat_quick_replies SET title=?, body=?, scope=?, is_active=?, updated_by=?, updated_at=? WHERE id=?',(title,body,scope,1 if request.form.get('is_active')=='1' else 0,uid,now,int(rid)))
                    else:
                        conn.execute('INSERT INTO chat_quick_replies(title,body,scope,is_active,sort_order,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(title,body,scope,1 if request.form.get('is_active')=='1' else 0,0,uid,uid,now,now))
                    conn.commit(); msg='پیام آماده ذخیره شد.'
                elif action=='delete':
                    conn.execute('DELETE FROM chat_quick_replies WHERE id=?',(int(request.form.get('id')),)); conn.commit(); msg='حذف شد.'
        except Exception as e: err=str(e)
        rows=conn.execute('SELECT * FROM chat_quick_replies ORDER BY scope, sort_order,id').fetchall(); conn.close()
        return render_template('settings_chat_quick_replies.html', items=rows, msg=msg, err=err, current_user=user, active_page='settings')

    @app.route('/settings/chat-emojis', methods=['GET','POST'])
    def settings_chat_emojis():
        user = _require_user()
        if not user or not _is_staff(user):
            return redirect('/')
        conn = get_db(); ensure_support_schema(conn)
        if request.method == 'POST':
            raw = request.form.get('emojis') or ''
            # Keep Unicode emoji strings, remove duplicates, max 80.
            vals=[]; seen=set()
            for x in raw.replace('\n',',').split(','):
                x=x.strip()
                if x and x not in seen and len(x) <= 8:
                    vals.append(x); seen.add(x)
            if not vals: vals = DEFAULT_CHAT_EMOJIS
            from core.db import set_setting
            set_setting(conn, 'chat_emojis', ','.join(vals[:80]))
            msg='ایموجی‌های چت ذخیره شد.'
        else:
            msg=None
        emojis=_load_chat_emojis(conn)
        conn.close()
        return render_template('settings_chat_emojis.html', emojis=emojis, msg=msg, active_page='settings', current_user=user)

    # ---- تنظیمات بله ----
    @app.route('/settings/bale', methods=['GET', 'POST'])
    def settings_bale():
        user = _require_user()
        if not user or user['role'] not in ('مسئول پذیرش', 'مدیر سیستم', 'مدیر'):
            return redirect('/')
        conn = get_db()
        ensure_support_schema(conn)
        msg = err = None
        if request.method == 'POST':
            action = request.form.get('action') or 'save'
            if action == 'save':
                conf = {
                    'enabled': request.form.get('enabled') == '1',
                    'token': (request.form.get('token') or '').strip(),
                    'username': (request.form.get('username') or '').strip(),
                }
                save_bale_config(conn, conf)
                msg = 'ذخیره شد.'
            elif action == 'test':
                conf = get_bale_config(conn)
                chat_id = (request.form.get('test_chat_id') or '').strip()
                if not chat_id:
                    try:
                        row = conn.execute('SELECT bale_chat_id FROM users WHERE id=?', (user['id'],)).fetchone()
                        chat_id = (row['bale_chat_id'] if row else '') or ''
                    except Exception:
                        chat_id = ''
                if not (conf.get('token') or '').strip():
                    err = 'توکن ربات تنظیم نشده. اول ذخیره کنید.'
                elif not chat_id:
                    err = 'chat_id تست را وارد کنید (مثلاً 1931422408).'
                else:
                    # force=True: حتی اگر سوئیچ خاموش باشد تست بفرستد
                    r = send_bale_message(conn, chat_id, 'تست اعلان سازگان', force=True)
                    if r.get('ok'):
                        # ذخیره chat_id روی کاربر فعلی برای اعلان‌های بعدی
                        try:
                            conn.execute('UPDATE users SET bale_chat_id=? WHERE id=?', (str(chat_id).strip(), user['id']))
                            conn.commit()
                        except Exception:
                            pass
                        msg = 'پیام تست ارسال شد به chat_id=%s — بله را چک کنید.' % chat_id
                    else:
                        err = 'خطای بله: ' + str(r.get('description') or r.get('error') or r)
            elif action == 'link_me':
                code = secrets.token_hex(3).upper()
                session['bale_link_code'] = code
                session['bale_link_uid'] = user['id']
                try:
                    from core.db import get_setting, set_setting
                    import json
                    raw = get_setting(conn, 'bale_pending_link', '') or '{}'
                    pending = json.loads(raw) if raw else {}
                    pending[code] = user['id']
                    set_setting(conn, 'bale_pending_link', json.dumps(pending))
                    conn.commit()
                except Exception:
                    pass
                msg = f'در بله به ربات پیام بدهید: /start {code}'
        conf = get_bale_config(conn)
        my_chat = None
        try:
            row = conn.execute('SELECT bale_chat_id FROM users WHERE id=?', (user['id'],)).fetchone()
            my_chat = row['bale_chat_id'] if row else None
        except Exception:
            pass
        conn.close()
        return render_template(
            'settings_bale.html',
            conf=conf,
            msg=msg,
            err=err,
            my_chat=my_chat,
            link_code=session.get('bale_link_code'),
            current_user=user,
            active_page='settings-bale',
        )

    @app.route('/api/bale/webhook', methods=['POST'])
    def bale_webhook():
        """دریافت آپدیت از بله (اختیاری — برای اتصال حساب با /start CODE)."""
        try:
            data = request.get_json(force=True, silent=True) or {}
        except Exception:
            data = {}
        message = data.get('message') or {}
        text = (message.get('text') or '').strip()
        chat = message.get('chat') or {}
        chat_id = chat.get('id')
        if not chat_id or not text:
            return jsonify({'ok': True})
        conn = get_db()
        ensure_support_schema(conn)
        conf = get_bale_config(conn)
        token = conf.get('token') or ''
        if text.startswith('/start'):
            parts = text.split()
            code = parts[1].upper() if len(parts) > 1 else ''
            # جستجو در session ممکن نیست؛ کد را در app_settings موقت نگه می‌داریم
            # روش ساده: اگر کاربر از پنل کد گرفته، همان را در settings با user id ذخیره می‌کنیم
            try:
                from core.db import get_setting, set_setting
                raw = get_setting(conn, 'bale_pending_link', '') or '{}'
                import json
                pending = json.loads(raw) if raw else {}
                uid = pending.get(code)
                if uid:
                    conn.execute('UPDATE users SET bale_chat_id=? WHERE id=?', (str(chat_id), uid))
                    pending.pop(code, None)
                    set_setting(conn, 'bale_pending_link', json.dumps(pending))
                    conn.commit()
                    if token:
                        bale_api(token, 'sendMessage', {
                            'chat_id': chat_id,
                            'text': 'حساب سازگان شما متصل شد ✅',
                        })
            except Exception:
                pass
        conn.close()
        return jsonify({'ok': True})

