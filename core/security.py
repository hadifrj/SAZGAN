# -*- coding: utf-8 -*-
"""امنیت نشست، CSRF، قفل ورود، هوک درخواست."""
from __future__ import annotations

import os
import secrets
import threading
import time

from flask import request, session, redirect, current_app, jsonify

from core.constants import (
    SECRET_FILE, MAX_LOGIN_ATTEMPTS, LOGIN_WINDOW_SEC, LOGIN_LOCKOUT_SEC,
)

_LOGIN_FAILURES = {}
_LOGIN_LOCK = threading.Lock()


def load_or_create_secret():
    """کلید نشست تصادفی پایدار روی دیسک (نه مقدار ثابت در کد)."""
    env = os.environ.get('SAZGAN_SECRET_KEY', '').strip()
    if env:
        return env
    if os.path.isfile(SECRET_FILE):
        with open(SECRET_FILE, 'r', encoding='utf-8') as f:
            key = f.read().strip()
            if key:
                return key
    key = secrets.token_hex(32)
    try:
        with open(SECRET_FILE, 'w', encoding='utf-8') as f:
            f.write(key)
        try:
            os.chmod(SECRET_FILE, 0o600)
        except Exception:
            pass
    except Exception:
        pass
    return key


def client_ip():
    """فقط وقتی پشت پراکسی معتبر هستیم به X-Forwarded-For اعتماد کن."""
    import os
    behind = os.environ.get('SAZGAN_BEHIND_PROXY', '').strip().lower() in ('1', 'true', 'yes')
    if behind:
        xff = request.headers.get('X-Forwarded-For') or ''
        if xff:
            return xff.split(',')[0].strip()
    return (request.remote_addr or 'unknown').strip()


def login_is_locked(ip):
    now = time.time()
    with _LOGIN_LOCK:
        fails = [t for t in _LOGIN_FAILURES.get(ip, []) if now - t < LOGIN_WINDOW_SEC]
        _LOGIN_FAILURES[ip] = fails
        if len(fails) >= MAX_LOGIN_ATTEMPTS:
            oldest = min(fails)
            remain = int(LOGIN_LOCKOUT_SEC - (now - oldest))
            return True, max(remain, 1)
        return False, 0


def login_register_failure(ip):
    with _LOGIN_LOCK:
        _LOGIN_FAILURES.setdefault(ip, []).append(time.time())


def login_clear_failures(ip):
    with _LOGIN_LOCK:
        _LOGIN_FAILURES.pop(ip, None)


def ensure_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']


def validate_csrf():
    if request.method not in ('POST', 'PUT', 'DELETE', 'PATCH'):
        return True
    token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    expected = session.get('csrf_token')
    if not expected or not token or not secrets.compare_digest(str(token), str(expected)):
        return False
    return True


def security_before_request(get_current_user=None):
    if request.path.startswith('/static/'):
        return None

    # مسیرهای عمومیِ مشتری (بدون لاگین، احراز با توکن یک‌بارمصرف در URL):
    # فرم اعلام خرابی زیر /announce است؛ چت پشتیبانی مشتری هم زیر /support/chat
    # است و هم زیر /api/support/chat — اگر فقط پیشوند /announce معاف باشد،
    # مسیر API چت مشتری هرگز معاف نمی‌شود و در صورت وجود هر نشست فعال
    # (مثلاً کارشناسی که در همان مرورگر وارد شده) ارسال پیام مشتری با خطای
    # CSRF رد می‌شود — همان چیزی که فقط اولین پیام (ثبت‌شده در حین ارسال فرم
    # اعلام خرابی) دیده می‌شد و پیام‌های بعدی نه.
    _csrf_exempt = {'/login', '/announce', '/support', '/c/login'}
    _csrf_exempt_prefixes = ('/announce', '/support', '/api/announce', '/support/chat', '/api/support/chat', '/api/push/mark-read/')
    if (
        request.method == 'POST'
        and request.path not in _csrf_exempt
        and not request.path.startswith(_csrf_exempt_prefixes)
    ):
        if 'user_id' in session and not validate_csrf():
            return 'خطای امنیتی CSRF — صفحه را تازه کنید و دوباره تلاش کنید.', 400

    if 'user_id' in session:
        session.permanent = True
        now = time.time()
        last = session.get('_last_active', now)
        lifetime = current_app.config.get('PERMANENT_SESSION_LIFETIME')
        max_sec = lifetime.total_seconds() if lifetime is not None else 8 * 3600
        if now - last > max_sec:
            session.clear()
            if request.path not in ('/login', '/logout'):
                # وقتی نشست منقضی می‌شود، پاسخ باید بر اساس نوع درخواست فرق کند:
                # درخواست AJAX نباید صفحه لاگین HTML را دریافت کند (باعث خطای
                # parse در سمت کلاینت می‌شود)؛ باید JSON با کد ریدایرکت بگیرد.
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    # AJAX: JSON response
                    return jsonify({'error': 'جلسه انقضا شده است', 'code': 401, 'redirect': '/login'}), 401
                else:
                    # HTML: redirect
                    return redirect('/login')
            return None
        # فقط هر ۵ دقیقه _last_active را بنویس تا cookie هر درخواست عوض نشود
        if (now - last) > 300 or '_last_active' not in session:
            session['_last_active'] = now
        ensure_csrf_token()

        try:
            from core.access import enforce_path_access, is_public_path
            if not is_public_path(request.path):
                if get_current_user:
                    u = get_current_user()
                else:
                    from core.helpers import get_current_user as _gcu
                    u = _gcu()
                # Fail closed: an access-control failure must never grant access.
                if not u:
                    if request.is_json or request.path.startswith('/api/'):
                        return jsonify({'error': 'unauthorized', 'code': 401}), 401
                    return redirect('/login')
                if not enforce_path_access(u, request.path):
                    if request.is_json or request.path.startswith('/api/'):
                        return jsonify({'error': 'forbidden', 'code': 403}), 403
                    return redirect('/cartable')
        except Exception:
            current_app.logger.exception('access control check failed')
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'access_check_failed', 'code': 403}), 403
            return redirect('/cartable')
    return None


def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # HSTS: فقط وقتی درخواست واقعاً روی HTTPS اومده (یا nginx با X-Forwarded-Proto
    # اعلامش کرده — به لطف ProxyFix روی request.is_secure منعکس میشه).
    # روی HTTP ساده اضافه نمیشه چون فرستادنش روی HTTP معنی نداره و می‌تونه
    # کاربری که هنوز گواهی self-signed رو تأیید نکرده گیج کنه.
    try:
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=15768000; includeSubDomains'
    except Exception:
        pass
    # کش بلندمدت برای دارایی‌های استاتیک نسخه‌دار
    try:
        path = request.path or ''
        if path.startswith('/static/'):
            # ۷ روز + immutable — با ?v= در URL هنگام تغییر فایل باطل می‌شود
            response.headers['Cache-Control'] = 'public, max-age=604800, immutable'
            response.headers['Vary'] = 'Accept-Encoding'
    except Exception:
        pass
    return response


# سازگاری با نام‌های قدیمی helpers
_load_or_create_secret = load_or_create_secret
_client_ip = client_ip
_login_is_locked = login_is_locked
_login_register_failure = login_register_failure
_login_clear_failures = login_clear_failures
_ensure_csrf_token = ensure_csrf_token
_validate_csrf = validate_csrf
_security_before_request = security_before_request
_security_headers = security_headers
