# -*- coding: utf-8 -*-
"""
نقطه ورود سامانه سازگان — معماری ماژولار
========================================
core/       ثابت‌ها و توابع مشترک
routes/     مسیرها بر اساس دامنه (auth, settings, service, ...)
"""
from __future__ import annotations

from core.logging_setup import setup_logging

logger = setup_logging()
logger.info("Sazgan application startup")

from routes.chat_backend_api import chat_api
from routes.data_safety_api import safety_api
from routes.excel_engine_api import excel_api
from routes.data_entry_api import data_entry_api
from routes.chat_notifications_api import notifications_api

# Windows console: UTF-8 for Persian logs
try:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
import secrets
from datetime import timedelta

from flask import Flask, request

from core.constants import BASE_DIR, SECRET_FILE, BACKUP_DIR

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)
# این Blueprintها جزو هسته برنامه‌اند؛ اگر ثبت آنها شکست بخورد،
# برنامه نباید بی‌صدا ناقص بالا بیاید. خطا باید در startup آشکار شود.
app.register_blueprint(notifications_api)
app.register_blueprint(data_entry_api)
app.register_blueprint(excel_api)
app.register_blueprint(safety_api)
app.register_blueprint(chat_api)


def _load_or_create_secret():
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

app.secret_key = _load_or_create_secret()

# محدودیت حجم درخواست‌ها — جلوگیری از حمله DoS با آپلود فایل‌های حجیم
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB
app.config['UPLOAD_MAX_SIZE'] = 50 * 1024 * 1024

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# در production با HTTPS: SAZGAN_SESSION_SECURE=1
_secure = os.environ.get('SAZGAN_SESSION_SECURE', '').strip().lower() in ('1', 'true', 'yes')
app.config['SESSION_COOKIE_SECURE'] = _secure
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_COOKIE_NAME'] = 'sazgan_session'
# False = کمتر نوشتن cookie در هر درخواست → ناوبری سریع‌تر
app.config['SESSION_REFRESH_EACH_REQUEST'] = False
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 604800  # ۷ روز؛ با ?v=version در URL کش‌باطل می‌شود
# جلوگیری از خواندن session با JS و کاهش ریسک fixation
app.config['SESSION_COOKIE_HTTPONLY'] = True
try:
    app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SAZGAN_SESSION_SAMESITE', 'Lax')
except Exception:
    pass

# پشت nginx (TLS termination) اجرا میشه؛ ProxyFix باعث میشه فلسک اسکیم/IP واقعی
# رو از هدرهای X-Forwarded-* بخونه، نه از خود کانکشن لوکال HTTP
# فعال‌سازی: SAZGAN_BEHIND_PROXY=1 (وقتی nginx-sazgan.conf رو استفاده می‌کنید)
if os.environ.get('SAZGAN_BEHIND_PROXY', '').strip().lower() in ('1', 'true', 'yes'):
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# مسیرگردان خطای «فایل خیلی بزرگ» متناظر با محدودیت MAX_CONTENT_LENGTH بالا
from werkzeug.exceptions import RequestEntityTooLarge

@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    from flask import jsonify
    return jsonify({'error': 'فایل خیلی بزرگ است (حداکثر 50 MB)', 'code': 413}), 413

# ---------------------------------------------------------------------------
# هسته: DB + هوک‌های امنیتی + context processor
# ---------------------------------------------------------------------------
from core import helpers as H

# اتصال init_db و هوک‌ها
@app.before_request
def _security_before_request():
    return H._security_before_request()

@app.after_request
def _security_headers(response):
    logger.info(
        "request method=%s path=%s status=%s",
        request.method if 'request' in globals() else 'UNKNOWN',
        request.path if 'request' in globals() else '-',
        response.status_code,
    )
    return H._security_headers(response)

@app.context_processor
def inject_header_date():
    return H.inject_header_date()

@app.context_processor
def inject_access():
    return H.inject_access()

@app.context_processor
def inject_help_tips():
    return H.inject_help_tips()

@app.context_processor
def inject_notifications_count():
    return H.inject_notifications_count()

@app.after_request
def add_no_cache_headers(response):
    return H.add_no_cache_headers(response)

# ---------------------------------------------------------------------------
# ثبت مسیرهای دامنه‌ای
# ---------------------------------------------------------------------------
from routes import auth, api, main, settings_general, settings_access, settings_customers, settings_warranty, settings_devices_reps, settings_wages_parts, service_common, service_internal_repair, service_external_repair, service_installation, service_inspection, reports, warehouse, finance, support, data_hub, native_api, customer_portal, operations, system

auth.register(app)
api.register(app)
main.register(app)
settings_general.register(app)
settings_access.register(app)
settings_customers.register(app)
settings_warranty.register(app)
settings_devices_reps.register(app)
settings_wages_parts.register(app)
service_common.register(app)
service_internal_repair.register(app)
service_external_repair.register(app)
service_installation.register(app)
service_inspection.register(app)
reports.register(app)
warehouse.register(app)
finance.register(app)
support.register(app)
data_hub.register(app)
native_api.register(app)
customer_portal.register(app)
operations.register(app)
system.register(app)

# ---------------------------------------------------------------------------
# افزونه‌ها (ثبت متمرکز)
# ---------------------------------------------------------------------------
from routes.extensions import init_all_extensions

try:
    H.init_db()
    # Test mode: enforce deterministic accounts after all DB migrations are complete.
    if os.environ.get('SAZGAN_DEMO_MODE', '').strip().lower() in ('1', 'true', 'yes'):
        from core import db as _test_db
        _conn = _test_db.get_db()
        try:
            _test_db._ensure_demo_test_accounts(_conn)
            print('[sazgan] TEST MODE active - test1..test9 password: 123')
        except Exception:
            logger.exception('Demo test accounts setup failed')
        finally:
            try:
                _conn.close()
            except Exception:
                pass
except Exception:
    logger.exception('Database initialization failed')

try:
    from core.push import ensure_vapid_keys
    ensure_vapid_keys()
except Exception:
    logger.exception('VAPID initialization failed')

try:
    init_all_extensions(app, H)
except Exception:
    logger.exception('Extensions initialization failed')

# backup scheduler (daemon thread)
try:
    import threading
    threading.Thread(target=H._backup_scheduler, daemon=True).start()
except Exception:
    logger.exception('Backup scheduler initialization failed')

@app.context_processor
def inject_release_info():
    try:
        import json
        with open(os.path.join(BASE_DIR, "RELEASE.json"), encoding="utf-8") as f:
            r=json.load(f)
        return {"release_changes": r.get("last_changes", [])}
    except Exception:
        return {"release_changes": []}

if __name__ == '__main__':
    # 0.0.0.0 = قابل دسترسی از شبکه/موبایل با IP سرور
    host = (os.environ.get('SAZGAN_HOST') or '0.0.0.0').strip() or '0.0.0.0'
    port = int(os.environ.get('SAZGAN_PORT', '5000') or 5000)

    def _print_urls():
        print('=' * 50)
        print('[sazgan] listening on %s:%s' % (host, port))
        print('[sazgan] local  : http://127.0.0.1:%s' % port)
        try:
            import socket
            # IPهای واقعی کارت شبکه
            seen = set()
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = info[4][0]
                if ip and not ip.startswith('127.') and ip not in seen:
                    seen.add(ip)
                    print('[sazgan] network: http://%s:%s' % (ip, port))
            if not seen:
                # fallback
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    s.connect(('8.8.8.8', 80))
                    ip = s.getsockname()[0]
                    if ip and not ip.startswith('127.'):
                        print('[sazgan] network: http://%s:%s' % (ip, port))
                finally:
                    s.close()
        except Exception:
            pass
        print('[sazgan] mobile : use network URL above (same Wi-Fi / LAN)')
        print('=' * 50)

    _print_urls()
    try:
        from waitress import serve
        serve(
            app,
            host=host,
            port=port,
            threads=16,
            channel_timeout=60,
            connection_limit=200,
            cleanup_interval=30,
            asyncore_use_poll=True,
        )
    except ImportError:
        app.run(host=host, port=port, debug=False, use_reloader=False)
