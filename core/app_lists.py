# -*- coding: utf-8 -*-
"""مدیریت لیست‌های کشویی نرم‌افزار (وضعیت‌ها، نقش‌ها و ...)

ذخیره در جدول app_list_items.
اگر برای یک کلید داده‌ای نباشد، از ثابت‌های constants.py استفاده می‌شود.
"""
from __future__ import annotations

from core.constants import (
    INTERNAL_REPAIR_STATUSES,
    EXTERNAL_REPAIR_STATUSES,
    INSTALLATION_REQUEST_STATUSES,
    VISIT_STATUSES,
    CLOSED_STATUSES,
    ROLES,
    LIFECYCLE_STAGES,
)

# تعریف لیست‌های قابل مدیریت
LIST_DEFINITIONS = {
    'internal_repair_statuses': {
        'label': 'وضعیت‌های تعمیر داخلی',
        'description': 'مراحل گردش کار تعمیرات کارخانه',
        'ordered': True,
        'critical': True,
        'defaults': list(INTERNAL_REPAIR_STATUSES),
    },
    'external_repair_statuses': {
        'label': 'وضعیت‌های تعمیر خارجی',
        'description': 'مراحل گردش کار تعمیرات در محل / نماینده',
        'ordered': True,
        'critical': True,
        'defaults': list(EXTERNAL_REPAIR_STATUSES),
    },
    'installation_statuses': {
        'label': 'وضعیت‌های نصب و آموزش',
        'description': 'مراحل درخواست نصب',
        'ordered': True,
        'critical': True,
        'defaults': list(INSTALLATION_REQUEST_STATUSES),
    },
    'visit_statuses': {
        'label': 'وضعیت‌های بازدید',
        'description': 'مراحل درخواست بررسی و بازدید',
        'ordered': True,
        'critical': True,
        'defaults': list(VISIT_STATUSES),
    },
    'closed_statuses': {
        'label': 'وضعیت‌های مختومه',
        'description': 'وضعیت‌هایی که پرونده را بسته در نظر می‌گیرند',
        'ordered': False,
        'critical': True,
        'defaults': sorted(CLOSED_STATUSES),
    },
    'roles': {
        'label': 'نقش‌های کاربری',
        'description': 'نقش‌های قابل انتخاب هنگام ساخت کاربر (حذف نقش‌های سیستمی توصیه نمی‌شود)',
        'ordered': True,
        'critical': True,
        'defaults': list(ROLES),
    },
    'lifecycle_stages': {
        'label': 'مراحل چرخه عمر',
        'description': 'مراحل مفهومی برای گزارش‌ها',
        'ordered': True,
        'critical': False,
        'defaults': list(LIFECYCLE_STAGES),
    },
    'rep_types': {
        'label': 'نوع نماینده',
        'description': 'حقیقی / حقوقی',
        'ordered': True,
        'critical': False,
        'defaults': ['حقیقی', 'حقوقی'],
    },
    'guarantee_statuses': {
        'label': 'وضعیت ضمانت نماینده',
        'description': 'دارد / ندارد',
        'ordered': True,
        'critical': False,
        'defaults': ['دارد', 'ندارد'],
    },
    'rep_status': {
        'label': 'وضعیت نماینده',
        'description': 'فعال / غیرفعال و مشابه',
        'ordered': True,
        'critical': False,
        'defaults': ['فعال', 'غیرفعال'],
    },
    'shipping_methods': {
        'label': 'روش‌های ارسال / باربری',
        'description': 'گزینه‌های روش ارسال در پرونده‌ها',
        'ordered': True,
        'critical': False,
        'defaults': ['باربری', 'پیک', 'پست', 'تحویل حضوری', 'سایر'],
    },
    'appearance_statuses': {
        'label': 'وضعیت ظاهری دستگاه',
        'description': 'گزینه‌های ظاهر دستگاه هنگام پذیرش',
        'ordered': True,
        'critical': False,
        'defaults': ['سالم', 'ضربه خورده', 'رنگ‌پریدگی', 'نقص ظاهری', 'سایر'],
    },
    'service_types': {
        'label': 'نوع خدمت',
        'description': 'کارخانه / در محل',
        'ordered': True,
        'critical': True,
        'defaults': ['کارخانه', 'در محل'],
    },
    'request_categories': {
        'label': 'دسته‌بندی درخواست',
        'description': 'تعمیر، نصب، بازدید و ...',
        'ordered': True,
        'critical': True,
        'defaults': ['تعمیر', 'نصب و آموزش', 'نصب Demo و امانی', 'بررسی و بازدید'],
    },
    'ready_texts_problem': {
        'label': 'متن آماده — شرح کار / اعلام خرابی',
        'description': 'متن‌های آماده برای فیلد شرح کار و اعلام خرابی (کد اختصاصی در ابتدای هر مورد)',
        'ordered': True,
        'critical': False,
        'defaults': [
            '[PRB-01] دستگاه روشن نمی‌شود',
            '[PRB-02] خطای سنسور',
            '[PRB-03] نشتی روغن / مایع',
            '[PRB-04] صدای غیرعادی هنگام کار',
            '[PRB-05] کاهش کیفیت تصویر / خروجی',
            '[PRB-06] درخواست سرویس دوره‌ای',
        ],
    },
    'ready_texts_accompanying': {
        'label': 'متن آماده — اقلام همراه دستگاه',
        'description': 'متن‌های آماده برای اقلام همراه هنگام پذیرش (کد اختصاصی در ابتدای هر مورد)',
        'ordered': True,
        'critical': False,
        'defaults': [
            '[ACC-01] کابل برق',
            '[ACC-02] کابل دیتا',
            '[ACC-03] پدال / فوت‌سویچ',
            '[ACC-04] دستیاب / ریموت',
            '[ACC-05] جعبه و بسته‌بندی اصلی',
            '[ACC-06] بدون متعلقات',
        ],
    },
    'ready_texts_appearance': {
        'label': 'متن آماده — وضعیت ظاهری',
        'description': 'متن‌های آماده وضعیت ظاهری دستگاه (کد اختصاصی در ابتدای هر مورد)',
        'ordered': True,
        'critical': False,
        'defaults': [
            '[APP-01] سالم — بدون نقص ظاهری',
            '[APP-02] ضربه روی بدنه',
            '[APP-03] خط و خش سطحی',
            '[APP-04] رنگ‌پریدگی',
            '[APP-05] شکستگی قطعه ظاهری',
            '[APP-06] آثار تعمیر قبلی',
        ],
    },
}


def ensure_app_lists_schema(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS app_list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_key TEXT NOT NULL,
            value TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            is_system INTEGER NOT NULL DEFAULT 0,
            UNIQUE(list_key, value)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_app_list_key ON app_list_items(list_key, sort_order)')
    conn.commit()


def seed_defaults_if_empty(conn, list_key: str = None):
    """اگر لیستی خالی باشد، مقادیر پیش‌فرض constants را می‌کارد."""
    keys = [list_key] if list_key else list(LIST_DEFINITIONS.keys())
    for key in keys:
        defn = LIST_DEFINITIONS.get(key)
        if not defn:
            continue
        row = conn.execute(
            'SELECT COUNT(*) AS c FROM app_list_items WHERE list_key = ?', (key,)
        ).fetchone()
        if row and row['c'] > 0:
            continue
        for i, val in enumerate(defn['defaults']):
            try:
                conn.execute(
                    'INSERT OR IGNORE INTO app_list_items (list_key, value, sort_order, is_active, is_system) VALUES (?, ?, ?, 1, 1)',
                    (key, val, i),
                )
            except Exception:
                pass
    conn.commit()


def get_list(conn, list_key: str, active_only: bool = True):
    """برگرداندن لیست مقادیر. اگر خالی باشد از defaults."""
    defn = LIST_DEFINITIONS.get(list_key)
    try:
        sql = 'SELECT value FROM app_list_items WHERE list_key = ?'
        params = [list_key]
        if active_only:
            sql += ' AND is_active = 1'
        sql += ' ORDER BY sort_order, id'
        rows = conn.execute(sql, params).fetchall()
        if rows:
            return [r['value'] for r in rows]
    except Exception:
        pass
    if defn:
        return list(defn['defaults'])
    return []


def get_list_set(conn, list_key: str):
    return set(get_list(conn, list_key, active_only=True))


def get_list_items(conn, list_key: str):
    """همه آیتم‌ها با جزئیات برای صفحه مدیریت."""
    rows = conn.execute(
        '''SELECT id, value, sort_order, is_active, is_system
           FROM app_list_items WHERE list_key = ?
           ORDER BY sort_order, id''',
        (list_key,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_item(conn, list_key: str, value: str):
    value = (value or '').strip()
    if not value:
        return False, 'مقدار خالی است'
    if list_key not in LIST_DEFINITIONS:
        return False, 'کلید نامعتبر'
    # max sort
    row = conn.execute(
        'SELECT COALESCE(MAX(sort_order), -1) AS m FROM app_list_items WHERE list_key = ?',
        (list_key,),
    ).fetchone()
    nxt = (row['m'] if row else -1) + 1
    try:
        conn.execute(
            'INSERT INTO app_list_items (list_key, value, sort_order, is_active, is_system) VALUES (?, ?, ?, 1, 0)',
            (list_key, value, nxt),
        )
        conn.commit()
        return True, None
    except Exception as e:
        if 'UNIQUE' in str(e).upper():
            return False, 'این مقدار قبلاً وجود دارد'
        return False, str(e)


def update_item(conn, item_id: int, value: str = None, is_active: int = None):
    row = conn.execute('SELECT * FROM app_list_items WHERE id = ?', (item_id,)).fetchone()
    if not row:
        return False, 'یافت نشد'
    if value is not None:
        value = value.strip()
        if not value:
            return False, 'مقدار خالی است'
        try:
            conn.execute('UPDATE app_list_items SET value = ? WHERE id = ?', (value, item_id))
        except Exception as e:
            if 'UNIQUE' in str(e).upper():
                return False, 'این مقدار قبلاً وجود دارد'
            return False, str(e)
    if is_active is not None:
        conn.execute('UPDATE app_list_items SET is_active = ? WHERE id = ?', (1 if is_active else 0, item_id))
    conn.commit()
    return True, None


def delete_item(conn, item_id: int):
    row = conn.execute('SELECT * FROM app_list_items WHERE id = ?', (item_id,)).fetchone()
    if not row:
        return False, 'یافت نشد'
    # اجازه حذف حتی system — کاربر مسئول است؛ فقط هشدار در UI
    conn.execute('DELETE FROM app_list_items WHERE id = ?', (item_id,))
    conn.commit()
    return True, None


def reorder_items(conn, list_key: str, ordered_ids: list):
    for i, item_id in enumerate(ordered_ids):
        conn.execute(
            'UPDATE app_list_items SET sort_order = ? WHERE id = ? AND list_key = ?',
            (i, int(item_id), list_key),
        )
    conn.commit()
    return True, None


def reset_list_to_defaults(conn, list_key: str):
    defn = LIST_DEFINITIONS.get(list_key)
    if not defn:
        return False, 'کلید نامعتبر'
    conn.execute('DELETE FROM app_list_items WHERE list_key = ?', (list_key,))
    for i, val in enumerate(defn['defaults']):
        conn.execute(
            'INSERT INTO app_list_items (list_key, value, sort_order, is_active, is_system) VALUES (?, ?, ?, 1, 1)',
            (list_key, val, i),
        )
    conn.commit()
    return True, None


def seed_all(conn):
    ensure_app_lists_schema(conn)
    seed_defaults_if_empty(conn)


# --- سازگاری با کد قدیمی: توابعی که مثل constants عمل می‌کنند ---

def internal_repair_statuses(conn=None):
    if conn is None:
        return list(INTERNAL_REPAIR_STATUSES)
    return get_list(conn, 'internal_repair_statuses')


def external_repair_statuses(conn=None):
    if conn is None:
        return list(EXTERNAL_REPAIR_STATUSES)
    return get_list(conn, 'external_repair_statuses')


def installation_statuses(conn=None):
    if conn is None:
        return list(INSTALLATION_REQUEST_STATUSES)
    return get_list(conn, 'installation_statuses')


def visit_statuses(conn=None):
    if conn is None:
        return list(VISIT_STATUSES)
    return get_list(conn, 'visit_statuses')


def closed_statuses(conn=None):
    if conn is None:
        return set(CLOSED_STATUSES)
    return get_list_set(conn, 'closed_statuses')


def roles_list(conn=None):
    if conn is None:
        return list(ROLES)
    return get_list(conn, 'roles')
