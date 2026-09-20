# -*- coding: utf-8 -*-
"""دیتابیس SQLite: اتصال و init/مهاجرت."""
from __future__ import annotations

import logging

import os
import sqlite3
import secrets
import stat
from werkzeug.security import generate_password_hash

from core.constants import DB_NAME, BASE_DIR, UPLOAD_FOLDER, BACKUP_DIR

logger = logging.getLogger("sazgan")

class _RequestConnProxy:
    """پروکسی اتصال: close() داخل درخواست واقعی را نمی‌بندد
    تا کش per-request کار کند؛ بستن واقعی در teardown انجام می‌شود.
    """
    __slots__ = ('_conn',)

    def __init__(self, conn):
        object.__setattr__(self, '_conn', conn)

    def close(self):
        return None

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_conn'), name)

    def __setattr__(self, name, value):
        if name == '_conn':
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, '_conn'), name, value)


def _seed_demo_data(conn):
    """Seed deterministic sample data for the temporary visual/runtime preview build."""
    flag_key = 'demo_seed_v1'
    try:
        already = conn.execute(
            "SELECT value FROM app_settings WHERE key=?", (flag_key,)
        ).fetchone()
        if already:
            return

        customers = [
            ('فروشگاه نوین', '09122345678', '0012345679', 'تهران', 'کرج', 'بلوار اصلی'),
            ('مهندسی پارس', '09123456789', '0012345680', 'اصفهان', 'اصفهان', 'چهارباغ'),
            ('صنایع البرز', '09124567890', '0012345681', 'البرز', 'کرج', 'بلوار جمهوری'),
            ('تجهیزات سپهر', '09125678901', '0012345682', 'فارس', 'شیراز', 'معالی‌آباد'),
            ('شرکت داده‌گستر', '09126789012', '0012345683', 'خراسان رضوی', 'مشهد', 'سجاد'),
        ]
        for row in customers:
            conn.execute(
                """INSERT INTO customers
                (name, phone, national_id, province, city, address)
                VALUES (?, ?, ?, ?, ?, ?)""", row)

        devices = [
            ('موبایل', 'iPhone 13 Pro'),
            ('موبایل', 'Samsung S23'),
            ('لپ‌تاپ', 'MacBook Pro'),
            ('موبایل', 'Huawei P30'),
            ('تبلت', 'iPad Air'),
            ('لپ‌تاپ', 'Lenovo ThinkPad'),
        ]
        for row in devices:
            conn.execute("INSERT INTO devices (device_type, model) VALUES (?, ?)", row)

        demo_requests = [
            ('سعید محمدی', 'تهران، ونک', '09123456789', 'موبایل', 'SN-1403-0001',
             'خرابی شارژ و داغ شدن دستگاه', 'در محل', 'تهران', 'تکمیل شده', 'علی رضایی', '1407/07/20'),
            ('فاطمه احمدی', 'تهران، صادقیه', '09111111111', 'موبایل', 'SN-1403-0002',
             'تعویض صفحه نمایش', 'در محل', 'تهران', 'در انتظار بررسی', 'محمد رضایی', '1407/07/20'),
            ('محمد رضایی', 'اصفهان، چهارباغ', '09333333333', 'لپ‌تاپ', 'SN-1403-0003',
             'مشکل روشن نشدن دستگاه', 'کارخانه', 'اصفهان', 'در حال انجام', 'رضا کریمی', '1407/07/19'),
            ('علی محمدی', 'کرج، عظیمیه', '09144444444', 'موبایل', 'SN-1403-0004',
             'شکستگی قاب و ایراد دوربین', 'در محل', 'البرز', 'جدید', 'علی رضایی', '1407/07/18'),
            ('زهرا کریمی', 'شیراز، معالی‌آباد', '09222222222', 'تبلت', 'SN-1403-0005',
             'مشکل باتری', 'در محل', 'فارس', 'تکمیل شده', 'محمد رضایی', '1407/07/18'),
            ('حسین احمدی', 'مشهد، سجاد', '09999999999', 'لپ‌تاپ', 'SN-1403-0006',
             'تعویض فن و سرویس کامل', 'کارخانه', 'خراسان رضوی', 'در انتظار بررسی', 'رضا کریمی', '1407/07/17'),
            ('رضا بهرامی', 'تهران، ونک', '09155555555', 'لپ‌تاپ', 'SN-1403-0007',
             'ارتقای حافظه و نصب سیستم', 'در محل', 'تهران', 'در حال انجام', 'علی رضایی', '1407/07/17'),
            ('امیر نادری', 'کرج، مهرشهر', '09377777777', 'موبایل', 'SN-1403-0008',
             'ایراد میکروفون', 'در محل', 'البرز', 'جدید', 'محمد رضایی', '1407/07/16'),
        ]
        for row in demo_requests:
            conn.execute(
                """INSERT INTO requests
                (customer_name, customer_address, customer_phone, device_type,
                 serial_number, problem_desc, service_type, province, status,
                 assigned_technician, reception_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", row)

        contacts = [
            ('سعید محمدی', '09123456789', '', 'تهران', 1, 'مشتری فعال'),
            ('فاطمه احمدی', '09111111111', '', 'تهران', 2, 'مشتری فعال'),
            ('محمد رضایی', '09333333333', '', 'اصفهان', 3, 'مشتری سازمانی'),
            ('علی محمدی', '09144444444', '', 'کرج', 4, 'مشتری فعال'),
            ('زهرا کریمی', '09222222222', '', 'شیراز', 5, 'مشتری فعال'),
            ('حسین احمدی', '09999999999', '', 'مشهد', 6, 'نماینده'),
            ('رضا بهرامی', '09155555555', '', 'تهران', None, 'شرکت'),
            ('امیر نادری', '09377777777', '', 'کرج', None, 'مشتری'),
        ]
        for row in contacts:
            conn.execute(
                """INSERT INTO contacts
                (name, mobile, phone, city, customer_id, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""", row)

        warranties = [
            ('سعید محمدی', 'موبایل', 'iPhone 13 Pro', 'W-1403-0001', '1407/01/10', '1407/02/01'),
            ('فاطمه احمدی', 'موبایل', 'Samsung S23', 'W-1403-0002', '1407/02/15', '1407/03/01'),
            ('محمد رضایی', 'لپ‌تاپ', 'MacBook Pro', 'W-1403-0003', '1407/03/05', '1407/03/20'),
        ]
        for row in warranties:
            conn.execute(
                """INSERT OR IGNORE INTO warranty_cards
                (customer_name, device_type, model, serial_number, production_date, installation_date)
                VALUES (?, ?, ?, ?, ?, ?)""", row)

        parts = [
            ('P-1001', 'باتری iPhone 13 Pro', 'موبایل', 'iPhone 13 Pro'),
            ('P-1002', 'نمایشگر Samsung S23', 'موبایل', 'Samsung S23'),
            ('P-1003', 'فن MacBook Pro', 'لپ‌تاپ', 'MacBook Pro'),
            ('P-1004', 'باتری iPad Air', 'تبلت', 'iPad Air'),
        ]
        for row in parts:
            conn.execute(
                "INSERT INTO parts (warehouse_code, part_name, device_type, device_model) VALUES (?, ?, ?, ?)", row)

        for part_id in range(1, 5):
            conn.execute(
                """INSERT INTO warehouse_stock
                (part_id, location_type, province, quantity)
                VALUES (?, 'کارخانه', 'تهران', ?)""",
                (part_id, [12, 7, 9, 5][part_id-1])
            )

        # حساب‌های تست ثابت برای اجرای سریع سناریوهای گردش کار.
        # فقط در SAZGAN_DEMO_MODE اجرا می‌شوند و روی داده واقعی اثری ندارند.
        demo_users = [
            ('مسئول پذیرش تست', 'reception', 'مسئول پذیرش'),
            ('امور مالی تست', 'finance', 'امور مالی'),
            ('تکنسین کارخانه تست', 'tech_factory', 'تکنسین کارخانه'),
            ('تکنسین استانی تست', 'tech_prov', 'تکنسین استانی'),
            ('کنترل کیفیت تست', 'qc', 'کنترل کیفیت'),
            ('مدیر تست', 'manager', 'مدیر'),
        ]
        user_cols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
        for full_name, username, role in demo_users:
            exists = conn.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone()
            if exists:
                continue
            fields = ['full_name', 'username', 'password_hash', 'role', 'province']
            values = [full_name, username, generate_password_hash('Test@12345'), role, None]
            if 'must_change_password' in user_cols:
                fields.append('must_change_password'); values.append(0)
            if 'is_active' in user_cols:
                fields.append('is_active'); values.append(1)
            conn.execute(
                'INSERT INTO users (%s) VALUES (%s)' % (', '.join(fields), ', '.join(['?'] * len(fields))),
                values
            )

        # ورود مشتریان تست بدون نیاز به ساخت حساب جدید در هر بار آزمایش.
        portal_cols = {r[1] for r in conn.execute('PRAGMA table_info(customer_portal_accounts)').fetchall()}
        if portal_cols:
            for customer in conn.execute('SELECT id FROM customers').fetchall():
                exists = conn.execute('SELECT 1 FROM customer_portal_accounts WHERE customer_id=?', (customer['id'],)).fetchone()
                if not exists:
                    conn.execute(
                        'INSERT INTO customer_portal_accounts(customer_id,password_hash,must_change_password,is_active) VALUES(?,?,0,1)',
                        (customer['id'], generate_password_hash('Test@12345'))
                    )

        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?)",
            (flag_key, '2026-08-11')
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print('[sazgan] demo seed skipped:', e)


def _ensure_demo_test_accounts(conn):
    """Create/update deterministic test accounts. Never fail because optional demo tables are missing."""
    demo_users = [
        ('مدیر سیستم تست', 'test1', 'مدیر سیستم'),
        ('مسئول پذیرش تست', 'test2', 'مسئول پذیرش'),
        ('امور مالی تست', 'test3', 'امور مالی'),
        ('تکنسین کارخانه تست', 'test4', 'تکنسین کارخانه'),
        ('تکنسین استانی تست', 'test5', 'تکنسین استانی'),
        ('کنترل کیفیت تست', 'test6', 'کنترل کیفیت'),
        ('مدیر تست', 'test7', 'مدیر'),
    ]
    password_hash = generate_password_hash('123')
    cols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
    if not cols:
        raise RuntimeError('users table is not available')
    for full_name, username, role in demo_users:
        row = conn.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
        if row:
            updates = ['full_name=?', 'password_hash=?', 'role=?']
            values = [full_name, password_hash, role]
            if 'must_change_password' in cols:
                updates.append('must_change_password=?'); values.append(0)
            if 'is_active' in cols:
                updates.append('is_active=?'); values.append(1)
            values.append(row['id'])
            conn.execute('UPDATE users SET %s WHERE id=?' % ', '.join(updates), values)
        else:
            fields = ['full_name', 'username', 'password_hash', 'role']
            values = [full_name, username, password_hash, role]
            if 'province' in cols:
                fields.append('province'); values.append(None)
            if 'must_change_password' in cols:
                fields.append('must_change_password'); values.append(0)
            if 'is_active' in cols:
                fields.append('is_active'); values.append(1)
            conn.execute('INSERT INTO users (%s) VALUES (%s)' % (', '.join(fields), ', '.join(['?'] * len(fields))), values)
        print('[sazgan] test account ready:', username)
    conn.commit()
    print('[sazgan] TEST ACCOUNTS READY: test1..test7 / password: 123')
    print('[sazgan] test8/test9 require existing demo customers and are not blocking startup')

def _open_connection():
    """ساخت اتصال تازه با PRAGMAهای عملکردی."""
    db_path = os.path.join(BASE_DIR, DB_NAME)
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA journal_mode=WAL')
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=8000')
    conn.execute('PRAGMA temp_store=MEMORY')
    try:
        conn.execute('PRAGMA cache_size=-8000')  # ~8MB
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    try:
        conn.execute('PRAGMA mmap_size=268435456')  # 256MB mmap
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    try:
        conn.execute('PRAGMA read_uncommitted=1')
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    return conn


def get_db():
    """اتصال SQLite — داخل درخواست Flask از flask.g کش می‌شود تا
    چند بار باز/بسته نشود (علت اصلی کندی حرکت بین صفحات/تب‌ها).

    خارج از request context مثل قبل اتصال تازه برمی‌گرداند.
    """
    try:
        from flask import g, has_request_context, current_app
        if has_request_context():
            proxy = getattr(g, '_sazgan_db_proxy', None)
            if proxy is not None:
                try:
                    proxy.execute('SELECT 1')
                    return proxy
                except Exception:
                    real = getattr(g, '_sazgan_db', None)
                    if real is not None:
                        try:
                            real.close()
                        except Exception as e:
                            logger.exception("Silent exception in core/db.py")
                    g._sazgan_db = None
                    g._sazgan_db_proxy = None
            real = _open_connection()
            g._sazgan_db = real
            proxy = _RequestConnProxy(real)
            g._sazgan_db_proxy = proxy
            if not getattr(current_app, '_sazgan_db_teardown_registered', False):
                def _close_db(exc=None):
                    c = getattr(g, '_sazgan_db', None)
                    if c is not None:
                        try:
                            c.close()
                        except Exception as e:
                            logger.exception("Silent exception in core/db.py")
                    g._sazgan_db = None
                    g._sazgan_db_proxy = None
                try:
                    current_app.teardown_appcontext(_close_db)
                    current_app._sazgan_db_teardown_registered = True
                except Exception as e:
                    logger.exception("Silent exception in core/db.py")
            return proxy
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    return _open_connection()




def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            customer_address TEXT,
            customer_phone TEXT,
            device_type TEXT NOT NULL,
            serial_number TEXT,
            installation_date TEXT,
            problem_desc TEXT NOT NULL,
            service_type TEXT NOT NULL DEFAULT 'در محل',
            province TEXT NOT NULL DEFAULT 'تهران',
            status TEXT DEFAULT 'در انتظار بررسی',
            assigned_technician TEXT,
            reception_date TEXT,
            request_category TEXT NOT NULL DEFAULT 'تعمیر',
            invoice_number TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            province TEXT,
            representative_id INTEGER
        )
    ''')
    try:
        user_cols = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
        if 'photo_filename' not in user_cols:
            conn.execute('ALTER TABLE users ADD COLUMN photo_filename TEXT')
        if 'created_at' not in user_cols:
            conn.execute('ALTER TABLE users ADD COLUMN created_at TEXT')
        if 'must_change_password' not in user_cols:
            conn.execute('ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0')
        if 'is_active' not in user_cols:
            try:
                conn.execute('ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1')
            except Exception as e:
                logger.exception("Silent exception in core/db.py")
            try:
                conn.execute('UPDATE users SET is_active=1 WHERE is_active IS NULL')
            except Exception as e:
                logger.exception("Silent exception in core/db.py")
        for _bc in ('bank_card', 'bank_sheba', 'bank_owner'):
            if _bc not in user_cols:
                try:
                    conn.execute('ALTER TABLE users ADD COLUMN %s TEXT' % _bc)
                except Exception as e:
                    logger.exception("Silent exception in core/db.py")
        if 'city' not in user_cols:
            try:
                conn.execute('ALTER TABLE users ADD COLUMN city TEXT')
            except Exception as e:
                logger.exception("Silent exception in core/db.py")
        if 'display_prefs' not in user_cols:
            try:
                conn.execute('ALTER TABLE users ADD COLUMN display_prefs TEXT')
            except Exception as e:
                logger.exception("Silent exception in core/db.py")
        conn.commit()
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            national_id TEXT,
            economic_code TEXT,
            province TEXT,
            city TEXT,
            address TEXT,
            postal_code TEXT,
            equipment_manager_name TEXT,
            equipment_manager_mobile TEXT
        )
    ''')
    # مهاجرت ستون‌های طرف‌حساب برای دیتابیس‌های قدیمی
    try:
        cust_cols = {row[1] for row in conn.execute('PRAGMA table_info(customers)').fetchall()}
        for col, col_type in (
            ('phone', 'TEXT'),
            ('national_id', 'TEXT'),
            ('economic_code', 'TEXT'),
            ('province', 'TEXT'),
            ('city', 'TEXT'),
            ('address', 'TEXT'),
            ('postal_code', 'TEXT'),
            ('is_archived', 'INTEGER DEFAULT 0'),
            ('archive_date', 'TEXT'),
            ('equipment_manager_name', 'TEXT'),
            ('equipment_manager_mobile', 'TEXT'),
            ('person_type', "TEXT DEFAULT 'حقیقی'"),
            ('county', 'TEXT'),
        ):
            if col not in cust_cols:
                try:
                    conn.execute(f'ALTER TABLE customers ADD COLUMN {col} {col_type}')
                except Exception as e:
                    logger.exception("Silent exception in core/db.py")
        conn.commit()
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    # Customer portal credentials: stored separately from customer identity data.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS customer_portal_accounts (
            customer_id INTEGER PRIMARY KEY,
            password_hash TEXT NOT NULL,
            must_change_password INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_login TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS repair_quote_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            file_role TEXT NOT NULL CHECK(file_role IN ('original','signed')),
            stored_name TEXT NOT NULL,
            original_name TEXT NOT NULL,
            mime_type TEXT,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            uploaded_by TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'waiting_customer',
            FOREIGN KEY(request_id) REFERENCES requests(id)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_repair_quote_files_request ON repair_quote_files(request_id, file_role)')
    conn.commit()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS warranty_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            device_type TEXT,
            model TEXT,
            serial_number TEXT UNIQUE NOT NULL,
            production_date TEXT,
            installation_date TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_type TEXT NOT NULL,
            model TEXT NOT NULL
        )
    ''')
    try:
        _dev_cols = {row[1] for row in conn.execute('PRAGMA table_info(devices)').fetchall()}
        if 'photo_filename' not in _dev_cols:
            conn.execute('ALTER TABLE devices ADD COLUMN photo_filename TEXT')
            conn.commit()
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS representatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rep_type TEXT NOT NULL DEFAULT 'حقیقی',
            company_name TEXT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            father_name TEXT,
            national_id TEXT,
            phone TEXT,
            province TEXT,
            address TEXT,
            guarantee_status TEXT NOT NULL DEFAULT 'ندارد',
            status TEXT NOT NULL DEFAULT 'فعال',
            photo_filename TEXT
        )
    ''')
    conn.commit()
    # مهاجرت فیلدهای رابط نماینده حقوقی + سازگاری
    try:
        rep_cols = {row[1] for row in conn.execute('PRAGMA table_info(representatives)').fetchall()}
        for col, col_type in (
            ('contact_person_name', 'TEXT'),
            ('contact_person_first_name', 'TEXT'),
            ('contact_person_last_name', 'TEXT'),
            ('contact_person_phone', 'TEXT'),
            ('city', 'TEXT'),
            ('guarantee_amount', 'TEXT'),
            ('archive_date', 'TEXT'),
            ('archive_reason', 'TEXT'),
        ):
            if col not in rep_cols:
                try:
                    conn.execute(f'ALTER TABLE representatives ADD COLUMN {col} {col_type}')
                except Exception as e:
                    logger.exception("Silent exception in core/db.py")
        conn.commit()
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS wage_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_description TEXT NOT NULL,
            wage_amount INTEGER NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS wage_calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            representative_id INTEGER,
            representative_name TEXT NOT NULL,
            work_description TEXT NOT NULL,
            amount INTEGER NOT NULL,
            calc_date TEXT,
            notes TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_code TEXT,
            part_name TEXT NOT NULL,
            device_type TEXT,
            device_model TEXT
        )
    ''')
    # مهاجرت ستون‌های جدول قطعات برای دیتابیس‌های قدیمی (اسکیمای قبلی: id, warehouse_code, name, unit)
    try:
        parts_cols = {row[1] for row in conn.execute('PRAGMA table_info(parts)').fetchall()}
        if 'part_name' not in parts_cols:
            conn.execute('ALTER TABLE parts ADD COLUMN part_name TEXT')
            if 'name' in parts_cols:
                conn.execute('UPDATE parts SET part_name = name WHERE part_name IS NULL')
            conn.execute("UPDATE parts SET part_name = '' WHERE part_name IS NULL")
        if 'device_type' not in parts_cols:
            conn.execute('ALTER TABLE parts ADD COLUMN device_type TEXT')
        if 'device_model' not in parts_cols:
            conn.execute('ALTER TABLE parts ADD COLUMN device_model TEXT')
        conn.commit()
    except Exception as e:
        logger.exception("Silent exception in core/db.py (parts migration)")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS warehouse_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id INTEGER NOT NULL,
            location_type TEXT NOT NULL DEFAULT 'کارخانه',
            province TEXT,
            quantity INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (part_id) REFERENCES parts(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS request_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            part_id INTEGER,
            part_name TEXT,
            warehouse_code TEXT,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
            stage TEXT,
            notes TEXT,
            FOREIGN KEY (request_id) REFERENCES requests(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS request_stage_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            stage_name TEXT NOT NULL,
            stage_date TEXT,
            notes TEXT,
            UNIQUE(request_id, stage_name),
            FOREIGN KEY (request_id) REFERENCES requests(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS request_stage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            stage_name TEXT NOT NULL,
            stage_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES requests(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS visit_serials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            serial_number TEXT,
            visit_desc TEXT,
            FOREIGN KEY (request_id) REFERENCES requests(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS request_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT,
            label TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT
        )
    ''')
    
    try:
        _rp_cols = [r[1] for r in conn.execute('PRAGMA table_info(request_parts)').fetchall()]
        for col, col_type in (
            ('stock_applied', 'INTEGER DEFAULT 0'),
            ('stock_location', 'TEXT'),
            ('stock_province', 'TEXT'),
            ('serial_healthy', 'TEXT'),
            ('serial_faulty', 'TEXT'),
            ('serial_good', 'TEXT'),
            ('serial_defective', 'TEXT'),
            ('voucher_recorded', 'INTEGER DEFAULT 0'),
            ('source', 'TEXT'),
            ('phase', 'TEXT'),
            ('created_at', 'TEXT'),
            ('is_void', 'INTEGER DEFAULT 0'),
            ('stage', 'TEXT'),
            ('notes', 'TEXT'),
        ):
            if col not in _rp_cols:
                try:
                    conn.execute(f'ALTER TABLE request_parts ADD COLUMN {col} {col_type}')
                except Exception as e:
                    logger.exception("Silent exception in core/db.py")
        # مهاجرت یک‌باره: alias قدیمی → canonical
        try:
            conn.execute(
                """UPDATE request_parts
                   SET serial_good = COALESCE(NULLIF(serial_good, ''), serial_healthy)
                   WHERE (serial_good IS NULL OR serial_good = '')
                     AND serial_healthy IS NOT NULL AND serial_healthy != ''"""
            )
            conn.execute(
                """UPDATE request_parts
                   SET serial_defective = COALESCE(NULLIF(serial_defective, ''), serial_faulty)
                   WHERE (serial_defective IS NULL OR serial_defective = '')
                     AND serial_faulty IS NOT NULL AND serial_faulty != ''"""
            )
            # همگام‌سازی معکوس برای قالب‌های قدیمی
            conn.execute(
                """UPDATE request_parts
                   SET serial_healthy = COALESCE(NULLIF(serial_healthy, ''), serial_good)
                   WHERE (serial_healthy IS NULL OR serial_healthy = '')
                     AND serial_good IS NOT NULL AND serial_good != ''"""
            )
            conn.execute(
                """UPDATE request_parts
                   SET serial_faulty = COALESCE(NULLIF(serial_faulty, ''), serial_defective)
                   WHERE (serial_faulty IS NULL OR serial_faulty = '')
                     AND serial_defective IS NOT NULL AND serial_defective != ''"""
            )
        except Exception as e:
            logger.exception("Silent exception in core/db.py")
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    conn.commit()

    # ستون‌های اضافی requests (سازگار با دیتابیس قدیمی)
    extra_request_cols = {
        'customer_id': 'INTEGER',
        'city': 'TEXT',
        'county': 'TEXT',
        'equipment_manager_name': 'TEXT',
        'equipment_manager_mobile': 'TEXT',
        'contact_name': 'TEXT',
        'contact_phone': 'TEXT',
        'warranty_end_date': 'TEXT',
        'accompanying_items': 'TEXT',
        'appearance_status': 'TEXT',
        'hospital_request_desc': 'TEXT',
        'initial_qc_desc': 'TEXT',
        'technician_desc': 'TEXT',
        'final_qc_desc': 'TEXT',
        'actions_taken': 'TEXT',
        'tracking_number': 'TEXT',
        'shipping_method': 'TEXT',
        'carrier_name': 'TEXT',
        'carrier_delivery_date': 'TEXT',
        'invoice_number': 'TEXT',
        'invoice_date': 'TEXT',
        'device_model': 'TEXT',
        'is_paid_visit': 'INTEGER DEFAULT 0',
        'visit_device_type': 'TEXT',
        'visit_device_count': 'INTEGER',
        'install_unit': 'TEXT',
        'install_notes': 'TEXT',
        'request_subtype': 'TEXT',
        'report_filename': 'TEXT',
        'proforma_confirmed': 'INTEGER DEFAULT 0',
        'proforma_number': 'TEXT',
        'proforma_sent_date': 'TEXT',
        'company_id': 'INTEGER DEFAULT 1',
        'is_new_for_tech': 'INTEGER DEFAULT 1',
        'can_initial_test': 'INTEGER',
        'assigned_technician_id': 'INTEGER',
        'reception_no': 'TEXT',
        'source_request_id': 'INTEGER',
        'tracking_code': 'TEXT',
        'is_deleted': 'INTEGER DEFAULT 0',
        'deleted_at': 'TEXT',
        'deleted_by': 'TEXT',
        # این دو ستون را core/workflow.py's transition_request() لازم دارد و بدون
        # آن‌ها هر تغییر وضعیتی (در هر ۴ نوع درخواست) با خطای 500 کرش می‌کند —
        # باگ واقعی که با تست زنده (تایید پذیرش ساده) پیدا شد؛ فایل تست
        # (test_workflow_integrity.py) این دو را در یک اسکیمای دستی و جدا از
        # اسکیمای واقعی تعریف کرده بود، پس تست‌ها پاس می‌شدند ولی برنامه‌ی واقعی نه.
        'status_changed_at': 'TEXT',
        'closed_at': 'TEXT',
    }
    existing_cols = {row[1] for row in conn.execute('PRAGMA table_info(requests)').fetchall()}
    for col, col_type in extra_request_cols.items():
        if col not in existing_cols:
            try:
                conn.execute(f'ALTER TABLE requests ADD COLUMN {col} {col_type}')
            except Exception as e:
                logger.exception("Silent exception in core/db.py")
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_requests_tracking_code ON requests(tracking_code) WHERE tracking_code IS NOT NULL AND TRIM(tracking_code) <> ''")
    except Exception as e:
        logger.exception("Silent exception creating tracking_code index")
    conn.commit()

    # ستون شهریار روی کارت گارانتی
    wc_cols = {row[1] for row in conn.execute('PRAGMA table_info(warranty_cards)').fetchall()}
    if 'shahriar' not in wc_cols:
        try:
            conn.execute('ALTER TABLE warranty_cards ADD COLUMN shahriar TEXT')
        except Exception as e:
            logger.exception("Silent exception in core/db.py")
    if 'warranty_end_date' not in wc_cols:
        try:
            conn.execute('ALTER TABLE warranty_cards ADD COLUMN warranty_end_date TEXT')
        except Exception as e:
            logger.exception("Silent exception in core/db.py")
    if 'warranty_months' not in wc_cols:
        try:
            conn.execute('ALTER TABLE warranty_cards ADD COLUMN warranty_months INTEGER')
        except Exception as e:
            logger.exception("Silent exception in core/db.py")
    if 'warranty_status' not in wc_cols:
        try:
            conn.execute('ALTER TABLE warranty_cards ADD COLUMN warranty_status TEXT DEFAULT \'تولید شده\'')
        except Exception as e:
            logger.exception("Silent exception in core/db.py")
    conn.commit()


    conn.execute("CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, user_name TEXT, action TEXT, entity_type TEXT, entity_id INTEGER, details TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_name TEXT NOT NULL, request_id INTEGER, title TEXT, body TEXT, is_read INTEGER DEFAULT 0, created_at TEXT)")
    
    conn.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT,
        phone TEXT,
        city TEXT,
        customer_id INTEGER,
        notes TEXT,
        created_at TEXT,
        is_archived INTEGER DEFAULT 0
    )""")
    try:
        cols = {r[1] for r in conn.execute('PRAGMA table_info(contacts)').fetchall()}
        if 'city' not in cols:
            conn.execute('ALTER TABLE contacts ADD COLUMN city TEXT')
        for col, col_type in (
            ('company', 'TEXT'),
            ('email', 'TEXT'),
            ('website', 'TEXT'),
            ('address', 'TEXT'),
            ('status', 'TEXT'),
            ('group_name', 'TEXT'),
            ('avatar_filename', 'TEXT'),
        ):
            if col not in cols:
                conn.execute(f'ALTER TABLE contacts ADD COLUMN {col} {col_type}')
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    try:
        conn.execute('CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_contacts_mobile ON contacts(mobile)')
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("""CREATE TABLE IF NOT EXISTS calendar_holidays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        holiday_date TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        created_at TEXT
    )""")
    conn.execute("CREATE TABLE IF NOT EXISTS warehouse_movements (id INTEGER PRIMARY KEY AUTOINCREMENT, part_id INTEGER, location_type TEXT, province TEXT, delta INTEGER, quantity_after INTEGER, reason TEXT, request_id INTEGER, created_at TEXT, user_name TEXT)")
    conn.commit()

    # کاربر اولیه admin — رمز تصادفی امن یا مقدار صریح محیطی.
    import os as _os
    try:
        user_count = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
    except Exception:
        user_count = 0
    configured_admin_pw = (_os.environ.get('SAZGAN_ADMIN_PASSWORD') or '').strip()
    default_admin_pw = configured_admin_pw or secrets.token_urlsafe(18)
    if user_count == 0:
        cols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
        fields = ['full_name', 'username', 'password_hash', 'role', 'province']
        vals = ['مدیر سیستم', 'admin', generate_password_hash(default_admin_pw), 'مدیر سیستم', None]
        if 'must_change_password' in cols:
            fields.append('must_change_password')
            vals.append(1)
        if 'is_active' in cols:
            fields.append('is_active'); vals.append(1)
        placeholders = ','.join(['?'] * len(fields))
        conn.execute(
            'INSERT INTO users (%s) VALUES (%s)' % (', '.join(fields), placeholders),
            vals
        )
        conn.commit()
        if not configured_admin_pw:
            secret_path = os.path.join(BASE_DIR, '.initial_admin_password')
            try:
                with open(secret_path, 'w', encoding='utf-8') as fh:
                    fh.write(default_admin_pw + '\n')
                os.chmod(secret_path, stat.S_IRUSR | stat.S_IWUSR)
            except Exception as e:
                print('[sazgan] could not write initial admin credential file:', e)
            print('=' * 60)
            print('[sazgan] Initial admin account created')
            print('[sazgan] Username : admin')
            print('[sazgan] Password : %s' % default_admin_pw)
            print('[sazgan] Saved to : .initial_admin_password')
            print('[sazgan] (shown only once in this console)')
            print('=' * 60)
        else:
            print('[sazgan] initial admin account created from SAZGAN_ADMIN_PASSWORD')

    # هرگز رمز admin موجود را در startup بازنشانی نکن.
    # داده‌های نمونه فقط در حالت صریح Demo ساخته می‌شوند.
    if (_os.environ.get('SAZGAN_DEMO_MODE') or '').strip().lower() in ('1', 'true', 'yes'):
        _seed_demo_data(conn)
        _ensure_demo_test_accounts(conn)

    # یکسان‌سازی نقش قدیمی
    try:
        conn.execute("UPDATE users SET role='امور مالی' WHERE role='مالی'")
        conn.commit()
    except Exception as e:
        logger.exception("Silent exception in core/db.py")
    # ایندکس‌های پرکاربرد (سرعت جستجو/کارتابل/انبار)
    try:
        idx_statements = [
            "CREATE INDEX IF NOT EXISTS idx_req_status ON requests(status)",
            "CREATE INDEX IF NOT EXISTS idx_req_category ON requests(request_category)",
            "CREATE INDEX IF NOT EXISTS idx_req_service ON requests(service_type)",
            "CREATE INDEX IF NOT EXISTS idx_req_province ON requests(province)",
            "CREATE INDEX IF NOT EXISTS idx_req_serial ON requests(serial_number)",
            "CREATE INDEX IF NOT EXISTS idx_req_customer ON requests(customer_name)",
            "CREATE INDEX IF NOT EXISTS idx_req_tech ON requests(assigned_technician)",
            "CREATE INDEX IF NOT EXISTS idx_req_tech_id ON requests(assigned_technician_id)",
            "CREATE INDEX IF NOT EXISTS idx_req_reception_date ON requests(reception_date)",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_parts_whcode ON parts(warehouse_code)",
            "CREATE INDEX IF NOT EXISTS idx_wstock_part ON warehouse_stock(part_id)",
            "CREATE INDEX IF NOT EXISTS idx_wstock_loc ON warehouse_stock(location_type, province)",
            "CREATE INDEX IF NOT EXISTS idx_rparts_req ON request_parts(request_id)",
            "CREATE INDEX IF NOT EXISTS idx_settings_key ON app_settings(key)",
        ]
        for sql in idx_statements:
            try:
                conn.execute(sql)
            except Exception as e:
                logger.exception("Silent exception in core/db.py")
        conn.commit()
    except Exception as e:
        print('[sazgan] indexes:', e)

    # Database migration engine: run only after the legacy compatibility schema
    # has completed. Future releases are handled by versioned migrations.
    try:
        from core.migration_engine import migrate
        migrate(conn, dry_run=False, backup=True)
    except Exception as _migration_err:
        print("[sazgan] database migration failed:", _migration_err)
        raise

    # شماره پذیرش ترتیبی P/Q
    try:
        from core.reception_numbers import backfill_reception_numbers
        n = backfill_reception_numbers(conn)
        if n:
            print('[sazgan] backfill reception_no: %s rows' % n)
    except Exception as e:
        print('[sazgan] reception_numbers init:', e)

    conn.close()


# کش ساده در حافظه برای تنظیمات (TTL کوتاه)
_SETTINGS_CACHE = {}
_SETTINGS_CACHE_TTL = 30.0  # ثانیه


def _cache_get(key):
    import time
    item = _SETTINGS_CACHE.get(key)
    if not item:
        return None
    val, ts = item
    if time.time() - ts > _SETTINGS_CACHE_TTL:
        _SETTINGS_CACHE.pop(key, None)
        return None
    return val


def _cache_set(key, value):
    import time
    _SETTINGS_CACHE[key] = (value, time.time())


def _cache_invalidate(key=None):
    if key is None:
        _SETTINGS_CACHE.clear()
    else:
        _SETTINGS_CACHE.pop(key, None)


def get_setting(conn, key, default=''):
    cached = _cache_get(key)
    if cached is not None:
        return cached
    row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
    val = row['value'] if row and row['value'] is not None else default
    if row and row['value'] is not None:
        _cache_set(key, val)
    return val


def set_setting(conn, key, value):
    conn.execute(
        'INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
        (key, value)
    )
    _cache_set(key, value)
