# -*- coding: utf-8 -*-
"""لایه دسترسی نقش‌ها و دکوراتورهای مسیر."""
from __future__ import annotations

from functools import wraps
from flask import redirect, request, session, g, has_request_context

from core.constants import ADMIN_ROLES, FINANCE_ROLES, RECEPTION_ROLES

# ماژول‌های قابل کنترل در ماتریس دسترسی
ACCESS_MODULES = [
    ('cartable', 'کارتابل / وظایف'),
    ('dashboard', 'داشبورد'),
    ('search', 'جستجو'),
    ('notifications', 'اعلان‌ها'),
    ('customer_affairs', 'امور مشتریان'),
    ('warehouse', 'انبار'),
    ('finance', 'امور مالی'),
    ('reports', 'گزارش‌ها'),
    ('parties', 'طرف حساب‌ها'),
    ('system', 'تنظیمات سیستم'),
    ('products', 'مدیریت محصولات'),
    ('wages_settings', 'نرخ دستمزد'),
]

DEFAULT_ROLE_ACCESS = {
    'مسئول پذیرش': {
        'cartable': 1, 'dashboard': 1, 'search': 1, 'notifications': 1,
        'customer_affairs': 1, 'warehouse': 1, 'finance': 1, 'reports': 1,
        'parties': 1, 'system': 1, 'products': 1, 'wages_settings': 1,
    },
    'مدیر': {
        'cartable': 1, 'dashboard': 1, 'search': 1, 'notifications': 1,
        'customer_affairs': 1, 'warehouse': 1, 'finance': 1, 'reports': 1,
        'parties': 1, 'system': 1, 'products': 1, 'wages_settings': 1,
    },
    'مدیر سیستم': {
        'cartable': 1, 'dashboard': 1, 'search': 1, 'notifications': 1,
        'customer_affairs': 1, 'warehouse': 1, 'finance': 1, 'reports': 1,
        'parties': 1, 'system': 1, 'products': 1, 'wages_settings': 1,
    },
    'امور مالی': {
        'cartable': 1, 'dashboard': 1, 'search': 1, 'notifications': 1,
        'customer_affairs': 1, 'warehouse': 1, 'finance': 1, 'reports': 1,
        'parties': 0, 'system': 0, 'products': 0, 'wages_settings': 0,
    },
    'تکنسین کارخانه': {
        'cartable': 1, 'dashboard': 1, 'search': 1, 'notifications': 1,
        'customer_affairs': 0, 'warehouse': 1, 'finance': 0, 'reports': 0,
        'parties': 0, 'system': 0, 'products': 0, 'wages_settings': 0,
    },
    'تکنسین استانی': {
        'cartable': 1, 'dashboard': 1, 'search': 1, 'notifications': 1,
        'customer_affairs': 0, 'warehouse': 1, 'finance': 0, 'reports': 0,
        'parties': 0, 'system': 0, 'products': 0, 'wages_settings': 0,
    },
    'کنترل کیفیت': {
        'cartable': 1, 'dashboard': 1, 'search': 1, 'notifications': 1,
        'customer_affairs': 0, 'warehouse': 1, 'finance': 0, 'reports': 0,
        'parties': 0, 'system': 0, 'products': 0, 'wages_settings': 0,
    },
}

# نگاشت پیشوند مسیر → ماژول دسترسی (اولین تطبیق برنده است؛ مرتب از خاص به عام)
PATH_MODULE_RULES = [
    ('/settings/display', 'system'),
    ('/settings/calendar', 'system'),
    ('/settings/company', 'system'),
    ('/settings/changelog', 'system'),
    ('/settings/about', 'system'),
    ('/settings/backup', 'system'),
    ('/settings/activation', 'system'),
    ('/settings/messaging', 'system'),
    ('/settings/customer-comms', 'system'),
    ('/settings/customer-communication', 'system'),
    ('/settings/system', 'system'),
    ('/security/', 'system'),
    ('/announce/qr', 'system'),
    ('/announce/', 'customer_affairs'),
    ('/contacts', 'customer_affairs'),
    ('/settings/warranty', 'products'),
    ('/settings/devices', 'products'),
    ('/settings/parts', 'products'),
    ('/settings/products', 'products'),
    ('/settings/wages', 'wages_settings'),
    ('/settings/data-hub', 'system'),
    ('/settings/customers', 'parties'),
    ('/settings/representatives', 'parties'),
    ('/settings/parties', 'parties'),
    ('/settings/access', 'parties'),
    ('/settings/users', 'parties'),
    ('/settings', 'parties'),
    ('/customer-affairs', 'customer_affairs'),
    # این سه صفحه، صفحه‌ی «انجام وظیفه‌ی خودم» برای QC/تکنسین/امور مالی هم هست (از طریق
    # کارتابل به اینجا لینک می‌شن) — باید زیر ماژول cartable (که همه نقش‌ها دارن) باشه،
    # نه customer_affairs (که QC/تکنسین پیش‌فرض ندارن). این باگ واقعی 2026-08-25 حین تست
    # زنده‌ی QC/تکنسین پیدا شد: enforce_path_access این دو نقش رو قبل از رسیدن به خود
    # روت هم به /cartable ریدایرکت می‌کرد، یعنی هیچ‌وقت نمی‌تونستن گزارش QC/تکنسین ثبت کنن.
    ('/service/internal-repair/view/', 'cartable'),
    ('/service/external-repair/view/', 'cartable'),
    ('/service/inspection/view/', 'cartable'),
    ('/service/', 'customer_affairs'),
    ('/announce/list', 'customer_affairs'),
    ('/finance/', 'finance'),
    ('/reports/', 'reports'),
    ('/dashboard', 'dashboard'),
    ('/warehouse/', 'warehouse'),
    ('/search', 'search'),
    ('/notifications', 'notifications'),
    ('/cartable', 'cartable'),
    ('/change-password', 'cartable'),
]

# مسیرهای عمومی (بدون نیاز به ماژول)
PUBLIC_PREFIXES = (
    '/static/', '/login', '/logout', '/health',
    '/api/lookup_warranty', '/api/warranty-check', '/offline', '/support',
    '/manifest', '/sw.js', '/favicon',
)


def get_role_access_map(conn=None, get_db=None, get_setting=None):
    """نقشه دسترسی نقش‌ها از تنظیمات یا پیش‌فرض."""
    import json
    close = False
    try:
        if conn is None and get_db:
            conn = get_db()
            close = True
        if conn is not None and get_setting:
            raw = get_setting(conn, 'role_access_map', '') or ''
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict) and data:
                    out = {}
                    for role, defaults in DEFAULT_ROLE_ACCESS.items():
                        merged = dict(defaults)
                        if role in data and isinstance(data[role], dict):
                            for k, v in data[role].items():
                                merged[k] = 1 if v else 0
                        out[role] = merged
                    for role, perms in data.items():
                        if role not in out and isinstance(perms, dict):
                            out[role] = {m: (1 if perms.get(m) else 0) for m, _ in ACCESS_MODULES}
                    return out
    except Exception:
        pass
    finally:
        if close and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return {r: dict(p) for r, p in DEFAULT_ROLE_ACCESS.items()}



def is_system_admin(user) -> bool:
    """admin همان مدیر سیستم است — همه‌کاره سامانه (دسترسی کامل)."""
    if not user:
        return False
    try:
        if isinstance(user, dict):
            role = (user.get('role') or '')
            uname = (user.get('username') or '')
        else:
            role = user['role'] if 'role' in user.keys() else ''
            uname = user['username'] if 'username' in user.keys() else ''
    except Exception:
        return False
    if (uname or '').strip().lower() == 'admin':
        return True
    if (role or '').strip() == 'مدیر سیستم':
        return True
    return False


def user_has_access(user, module, conn=None, get_db=None, get_setting=None):
    if not user:
        return False
    if is_system_admin(user):
        return True
    role = user['role'] if not isinstance(user, dict) else user.get('role')
    if not role:
        return False
    if role == 'مدیر سیستم':
        return True
    # The sidebar can call can_access() many times while rendering one page.
    # Cache the role-access map per request so each menu item does not hit
    # app_settings/SQLite again. This preserves live permissions between requests.
    amap = None
    if has_request_context():
        amap = getattr(g, '_sazgan_role_access_map', None)
    if amap is None:
        try:
            from core import helpers as H
            amap = get_role_access_map(conn, get_db=H.get_db, get_setting=H.get_setting)
        except Exception:
            amap = {r: dict(p) for r, p in DEFAULT_ROLE_ACCESS.items()}
        if has_request_context():
            g._sazgan_role_access_map = amap
    perms = amap.get(role) or DEFAULT_ROLE_ACCESS.get(role) or {}
    return bool(perms.get(module, 0))


def module_for_path(path: str):
    if not path:
        return None
    for prefix in PUBLIC_PREFIXES:
        if path == prefix.rstrip('/') or path.startswith(prefix):
            return None
    for prefix, mod in PATH_MODULE_RULES:
        if path == prefix or path.startswith(prefix):
            return mod
    return None


def is_public_path(path: str) -> bool:
    if not path:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path == prefix.rstrip('/') or path.startswith(prefix):
            return True
    return False


def require_login(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        from core.helpers import get_current_user
        if not get_current_user():
            return redirect('/login')
        return view(*args, **kwargs)
    return wrapped


def require_access(module):
    def deco(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            from core.helpers import get_current_user
            u = get_current_user()
            if not u:
                return redirect('/login')
            if not user_has_access(u, module):
                return redirect('/')
            return view(*args, **kwargs)
        return wrapped
    return deco


def require_roles(*roles):
    def deco(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            from core.helpers import get_current_user
            u = get_current_user()
            if not u:
                return redirect('/login')
            if is_system_admin(u):
                return view(*args, **kwargs)
            r = u['role'] if not isinstance(u, dict) else u.get('role')
            if r not in roles and r != 'مدیر سیستم':
                return redirect('/')
            return view(*args, **kwargs)
        return wrapped
    return deco


def enforce_path_access(user, path: str):
    """اگر مسیر نیاز به ماژول داشته باشد و کاربر نداشته باشد، False."""
    if is_public_path(path):
        return True
    if not user:
        return False
    mod = module_for_path(path)
    if mod is None:
        return True  # مسیر بدون قانون خاص
    return user_has_access(user, mod)
