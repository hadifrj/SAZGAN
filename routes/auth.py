# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from flask import (
    request, session, redirect, render_template, jsonify, send_file, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from io import BytesIO
import os, re, sqlite3, base64, time
import jdatetime
try:
    import openpyxl
except ImportError:
    openpyxl = None

from core.constants import *
from core import helpers as H

logger = logging.getLogger("sazgan")


from core.helpers import *  # noqa: F401,F403
from core.constants import *  # noqa: F401,F403

def register(app):
    """مسیرهای auth."""

    def _company_login_ctx():
        ctx = {
            'company_name': 'سازگان',
            'company_mobile': '',
            'company_phone': '',
            'company_address': '',
            'company_mobile_tel': '',
            'company_phone_tel': '',
        }
        try:
            conn = get_db()
            def gs(k, d=''):
                try:
                    return get_setting(conn, k, d) or d
                except Exception:
                    return d
            ctx['company_name'] = gs('company_name', 'سازگان')
            ctx['company_mobile'] = gs('company_mobile', '')
            ctx['company_phone'] = gs('company_phone', '')
            ctx['company_address'] = gs('company_address', '')
            import re as _re
            ctx['company_mobile_tel'] = _re.sub(r'[^0-9+]', '', ctx['company_mobile'] or '')
            ctx['company_phone_tel'] = _re.sub(r'[^0-9+]', '', ctx['company_phone'] or '')
            conn.close()
        except Exception:
            pass
        return ctx


    def _login_page(*args, **kwargs):
        """صفحه لاگین را هیچ‌وقت کش نکن — علت واقعی مشکل قدیمی Edge همین
        کش‌شدن فرم با توکن CSRF کهنه بود، نه خودِ بررسی CSRF."""
        resp = current_app.make_response(render_template(*args, **kwargs))
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        return resp

    # دسترسی به هلپرها
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        # فقط اگر کاربر واقعاً در دیتابیس باشد به خانه برو (جلوگیری از حلقه ریدایرکت)
        if 'user_id' in session:
            existing = get_current_user()
            if existing:
                return redirect('/')
            session.clear()

        ip = _client_ip()
        locked, remain = _login_is_locked(ip)
        if request.method == 'POST':
            if locked:
                return _login_page(
                    'login.html', **_company_login_ctx(),
                    error=f'به دلیل تلاش‌های ناموفق، ورود تا {remain // 60 + 1} دقیقه قفل است.',
                    csrf_token=_ensure_csrf_token()
                )
            # صفحه لاگین دیگر کش نمی‌شود (نگاه کنید به _login_page)، پس توکن
            # CSRF همیشه با نشست فعلی همگام است و بررسی آن دوباره فعال شد.
            if not _validate_csrf():
                return _login_page(
                    'login.html', **_company_login_ctx(),
                    error='نشست شما منقضی شده. لطفاً صفحه را تازه کنید و دوباره تلاش کنید.',
                    csrf_token=_ensure_csrf_token()
                )

            username = (request.form.get('username') or '').strip()
            password = request.form.get('password') or ''
            # حذف کاراکترهای مخفی RTL/ZW که گاهی Edge اضافه می‌کند
            username = ''.join(ch for ch in username if ch.isprintable()).strip()
            if not username:
                return _login_page('login.html', **_company_login_ctx(), error='نام کاربری را وارد کنید.', csrf_token=_ensure_csrf_token())
            if not password:
                return _login_page('login.html', **_company_login_ctx(), error='رمز عبور را وارد کنید.', csrf_token=_ensure_csrf_token())
            conn = get_db()
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            conn.close()
            ok = False
            if user:
                try:
                    ok = check_password_hash(user['password_hash'], password)
                except Exception:
                    ok = False
            if ok:
                # کاربر غیرفعال
                try:
                    keys = user.keys()
                    active = user['is_active'] if 'is_active' in keys else 1
                    if active is not None and int(active) == 0:
                        _login_register_failure(ip)
                        return _login_page('login.html', **_company_login_ctx(), error='این حساب کاربری غیرفعال است. با مدیر سیستم تماس بگیرید.', csrf_token=_ensure_csrf_token())
                except Exception:
                    pass
                if user['role'] == 'تکنسین استانی' and user['representative_id']:
                    conn = get_db()
                    rep = conn.execute('SELECT status FROM representatives WHERE id = ?', (user['representative_id'],)).fetchone()
                    conn.close()
                    if rep and rep['status'] != 'فعال':
                        _login_register_failure(ip)
                        return _login_page('login.html', **_company_login_ctx(), error='این نماینده غیرفعال شده و امکان ورود ندارد.', csrf_token=_ensure_csrf_token())
                _login_clear_failures(ip)
                session.clear()
                session['user_id'] = user['id']
                session.permanent = True
                session['_last_active'] = time.time()
                session.pop('force_password_change', None)
                dest = '/'
                _ensure_csrf_token()
                session.modified = True
                logger.info("login success username=%s ip=%s", username, ip)
                resp = redirect(dest)
                try:
                    app.session_interface.save_session(app, session, resp)
                except Exception:
                    pass
                return resp
            _login_register_failure(ip)
            logger.info("login failed username=%s ip=%s", username, ip)
            locked2, remain2 = _login_is_locked(ip)
            msg = 'نام کاربری یا رمز عبور نادرست است.'
            if locked2:
                msg += f' حساب موقتاً قفل شد ({remain2 // 60 + 1} دقیقه).'
            return _login_page('login.html', **_company_login_ctx(), error=msg, csrf_token=_ensure_csrf_token())
        try:
            ctx = _company_login_ctx()
            if locked:
                return _login_page(
                    'login.html', **ctx,
                    error=f'ورود موقتاً قفل است. {remain // 60 + 1} دقیقه دیگر تلاش کنید.',
                    csrf_token=_ensure_csrf_token()
                )
            return _login_page('login.html', **ctx, error=None, csrf_token=_ensure_csrf_token())
        except Exception as e:
            print('[login] render error:', e)
            try:
                return _login_page('login.html', company_name='سازگان', error=None, csrf_token='')
            except Exception as e2:
                print('[login] fatal:', e2)
                return ('ورود موقتاً در دسترس نیست. سرور را ری‌استارت کنید.', 500)





    @app.route('/logout')
    def logout():
        session.clear()
        return redirect('/login')



