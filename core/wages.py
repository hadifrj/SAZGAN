# -*- coding: utf-8 -*-
"""محاسبه دستمزد نماینده

قواعد:
- شهر نمایندگی از اطلاعات نماینده
- شهر مشتری از طرف‌حساب (اجباری)
- داخل شهر → نرخ محل نمایندگی + ایاب داخل شهر
- خارج شهر → نرخ خارج محل + (کیلومتر رفت‌وبرگشت × نرخ هر کیلومتر)
- چند دستگاه در یک تاریخ + یک مشتری → ایاب فقط یک‌بار
"""
from __future__ import annotations

from core.distance import calculate_distance, ensure_distance_schema

# کدهای استاندارد آیتم‌های دستمزد
RATE_CODES = {
    'install_first': 'نصب و آموزش دستگاه اول',
    'install_next': 'نصب دستگاه دوم به بعد',
    'install_central': 'نصب و آموزش دستگاه سانترال',
    'socket': 'سوکت زنی هر دستگاه',
    'train_section': 'آموزش هر بخش',
    'delivery': 'تحویل و دریافت',
    'pm_closed_lt3': 'سرویس PM بدون باز شدن / بازدید کمتر از سه دستگاه',
    'pm_closed_gt3': 'سرویس PM بدون باز شدن / بازدید گروهی بیشتر از سه دستگاه',
    'pm_open': 'سرویس PM با باز شدن دستگاه',
    'repair': 'سرویس و تعمیر هر دستگاه',
    'travel_local': 'ایاب و ذهاب داخل شهر',
    'travel_km': 'ایاب و ذهاب بین شهری (هر کیلومتر رفت و برگشت)',
}

DEFAULT_RATES = [
    # code, desc, amount, outside, per_km, category, sort, device_type, install_slot, is_central
    ('install_first', 'نصب و آموزش دستگاه اول', 6000000, None, 0, 'نصب', 1, None, 'first', 0),
    ('install_next', 'نصب دستگاه دوم به بعد', 3000000, None, 0, 'نصب', 2, None, 'next', 0),
    ('install_central', 'نصب و آموزش دستگاه سانترال', 5000000, None, 0, 'نصب', 3, None, 'central', 1),
    ('socket', 'سوکت زنی هر دستگاه', 1000000, None, 0, 'نصب', 4, None, 'any', 0),
    ('train_section', 'آموزش هر بخش', 3000000, None, 0, 'نصب', 5, None, 'any', 0),
    ('delivery', 'تحویل و دریافت', 2000000, None, 0, 'تحویل', 6, None, None, 0),
    ('pm_closed_lt3', 'سرویس PM بدون باز شدن دستگاه / بازدید کمتر از سه دستگاه', 3000000, None, 0, 'بازدید', 7, None, None, 0),
    ('pm_closed_gt3', 'سرویس PM بدون باز شدن دستگاه / بازدید گروهی بیشتر از سه دستگاه', 2000000, None, 0, 'بازدید', 8, None, None, 0),
    ('pm_open', 'سرویس PM با باز شدن دستگاه', 4000000, None, 0, 'بازدید', 9, None, None, 0),
    ('repair', 'سرویس و تعمیر هر دستگاه', 5500000, 6500000, 0, 'تعمیر', 10, None, None, 0),
    ('travel_local', 'ایاب و ذهاب داخل شهر', 2500000, None, 0, 'ایاب‌وذهاب', 11, None, None, 0),
    ('travel_km', 'ایاب و ذهاب بین شهری (هر کیلومتر رفت و برگشت)', 60000, None, 1, 'ایاب‌وذهاب', 12, None, None, 0),
]

def ensure_wage_schema(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS wage_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_description TEXT NOT NULL,
            wage_amount INTEGER NOT NULL
        )
    ''')
    cols = {r[1] for r in conn.execute('PRAGMA table_info(wage_rates)').fetchall()}
    for col, typ in (
        ('rate_code', 'TEXT'),
        ('amount_outside', 'INTEGER'),
        ('is_per_km', 'INTEGER DEFAULT 0'),
        ('category', 'TEXT'),
        ('sort_order', 'INTEGER DEFAULT 0'),
        ('is_active', 'INTEGER DEFAULT 1'),
        ('device_type', 'TEXT'),
        ('install_slot', 'TEXT'),
        ('is_central_device', 'INTEGER DEFAULT 0'),
    ):
        if col not in cols:
            try:
                conn.execute(f'ALTER TABLE wage_rates ADD COLUMN {col} {typ}')
            except Exception:
                pass

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
    wcols = {r[1] for r in conn.execute('PRAGMA table_info(wage_calculations)').fetchall()}
    for col, typ in (
        ('request_id', 'INTEGER'),
        ('customer_id', 'INTEGER'),
        ('customer_name', 'TEXT'),
        ('rate_code', 'TEXT'),
        ('is_local', 'INTEGER'),
        ('distance_km', 'REAL'),
        ('source', 'TEXT'),  # auto | manual
        ('device_count', 'INTEGER DEFAULT 1'),
        ('payment_status', "TEXT DEFAULT 'unpaid'"),  # unpaid | paid
        ('settlement_id', 'INTEGER'),
        ('paid_at', 'TEXT'),
    ):
        if col not in wcols:
            try:
                conn.execute(f'ALTER TABLE wage_calculations ADD COLUMN {col} {typ}')
            except Exception:
                pass

    conn.execute('''
        CREATE TABLE IF NOT EXISTS wage_settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            representative_id INTEGER NOT NULL,
            representative_name TEXT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            total_amount INTEGER NOT NULL DEFAULT 0,
            paid_amount INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            paid_at TEXT,
            paid_by TEXT,
            receipt_no TEXT,
            notes TEXT,
            bank_sheba TEXT,
            bank_card TEXT,
            bank_owner TEXT,
            created_at TEXT,
            UNIQUE(representative_id, year, month)
        )
    ''')

    # فیلدهای پرونده برای دستمزد
    try:
        rcols = {r[1] for r in conn.execute('PRAGMA table_info(requests)').fetchall()}
        for col, typ in (
            ('at_customer_site', 'INTEGER'),  # 1=در محل مشتری، 0=خیر
            ('visit_date', 'TEXT'),  # تاریخ مراجعه / تعمیر
            ('wage_calculated', 'INTEGER DEFAULT 0'),
        ):
            if col not in rcols:
                try:
                    conn.execute(f'ALTER TABLE requests ADD COLUMN {col} {typ}')
                except Exception:
                    pass
    except Exception:
        pass
    conn.commit()


def seed_default_wage_rates(conn, force=False):
    ensure_wage_schema(conn)
    count = conn.execute('SELECT COUNT(*) AS c FROM wage_rates').fetchone()['c']

    def _upsert(code, desc, amount, outside, per_km, cat, sort, device_type, install_slot, is_central):
        row = conn.execute(
            'SELECT id FROM wage_rates WHERE rate_code = ? OR work_description = ?',
            (code, desc),
        ).fetchone()
        if row:
            conn.execute(
                'UPDATE wage_rates SET rate_code=?, work_description=?, wage_amount=?, amount_outside=?, '
                'is_per_km=?, category=?, sort_order=?, is_active=1, device_type=?, install_slot=?, is_central_device=? WHERE id=?',
                (code, desc, amount, outside, per_km, cat, sort, device_type, install_slot, is_central, row['id']),
            )
        else:
            conn.execute(
                'INSERT INTO wage_rates (work_description, wage_amount, rate_code, amount_outside, is_per_km, '
                'category, sort_order, is_active, device_type, install_slot, is_central_device) VALUES (?,?,?,?,?,?,?,1,?,?,?)',
                (desc, amount, code, outside, per_km, cat, sort, device_type, install_slot, is_central),
            )

    if count > 0 and not force:
        for row in DEFAULT_RATES:
            _upsert(*row)
        conn.commit()
        return

    if force:
        conn.execute('DELETE FROM wage_rates')

    for row in DEFAULT_RATES:
        _upsert(*row)
    conn.commit()



def get_rate(conn, rate_code: str, device_type: str = None):
    """یافتن نرخ؛ اگر device_type داده شود اول نرخ مخصوص همان دستگاه."""
    if device_type:
        row = conn.execute(
            'SELECT * FROM wage_rates WHERE rate_code = ? AND device_type = ? AND COALESCE(is_active,1)=1',
            (rate_code, device_type),
        ).fetchone()
        if row:
            return dict(row)
    row = conn.execute(
        'SELECT * FROM wage_rates WHERE rate_code = ? AND (device_type IS NULL OR device_type = "") '
        'AND COALESCE(is_active,1)=1',
        (rate_code,),
    ).fetchone()
    if row:
        return dict(row)
    row = conn.execute(
        'SELECT * FROM wage_rates WHERE rate_code = ? AND COALESCE(is_active,1)=1',
        (rate_code,),
    ).fetchone()
    if row:
        return dict(row)
    for item in DEFAULT_RATES:
        code, desc, amount, outside, per_km, cat, sort = item[0], item[1], item[2], item[3], item[4], item[5], item[6]
        if code == rate_code:
            return {
                'rate_code': code,
                'work_description': desc,
                'wage_amount': amount,
                'amount_outside': outside,
                'is_per_km': per_km,
                'category': cat,
                'device_type': item[7] if len(item) > 7 else None,
                'install_slot': item[8] if len(item) > 8 else None,
            }
    return None


def get_install_rate(conn, device_type: str, is_first: bool, is_central: bool = False):
    """نرخ نصب بر اساس ترتیب دستگاه در همان روز/مشتری و نوع دستگاه."""
    if is_central:
        r = get_rate(conn, 'install_central', device_type)
        if r:
            return r
        return get_rate(conn, 'install_central')
    code = 'install_first' if is_first else 'install_next'
    r = get_rate(conn, code, device_type)
    if r:
        return r
    return get_rate(conn, code)


def count_installs_same_day(conn, representative_id, customer_key, calc_date) -> int:
    """تعداد نصب‌های ثبت‌شده همان روز برای همان مشتری (برای تشخیص اول/دوم)."""
    rows = conn.execute(
        "SELECT COALESCE(SUM(device_count), COUNT(*)) AS c FROM wage_calculations "
        "WHERE representative_id = ? AND calc_date = ? "
        "AND rate_code IN ('install_first', 'install_next', 'install_central') "
        "AND (customer_name = ? OR CAST(customer_id AS TEXT) = ?)",
        (representative_id, calc_date, customer_key, str(customer_key)),
    ).fetchone()
    return int(rows['c'] or 0) if rows else 0



def _norm_city(name: str) -> str:
    if not name:
        return ''
    s = str(name).strip().replace('ي', 'ی').replace('ك', 'ک')
    s = s.replace('آ', 'ا').replace('أ', 'ا')
    return s


def is_same_city(rep_city: str, customer_city: str) -> bool:
    a, b = _norm_city(rep_city), _norm_city(customer_city)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def get_rep_city(conn, representative_id: int) -> tuple:
    """(city, province, county, display_name)"""
    rep = conn.execute('SELECT * FROM representatives WHERE id = ?', (representative_id,)).fetchone()
    if not rep:
        return '', '', '', ''
    city = (rep['city'] if 'city' in rep.keys() else '') or ''
    province = (rep['province'] if 'province' in rep.keys() else '') or ''
    county = (rep['county'] if 'county' in rep.keys() else '') or ''
    if rep['rep_type'] == 'حقوقی' and rep['company_name']:
        name = rep['company_name']
    else:
        name = f"{rep['first_name'] or ''} {rep['last_name'] or ''}".strip()
    return city, province, county, name


def compute_travel(
    conn,
    rep_city: str,
    rep_province: str,
    customer_city: str,
    customer_province: str,
) -> dict:
    """
    خروجی:
      is_local, travel_amount, distance_km, description, rate_code
    """
    local = is_same_city(rep_city, customer_city)
    if local:
        rate = get_rate(conn, 'travel_local')
        amount = int(rate['wage_amount']) if rate else 2500000
        return {
            'is_local': True,
            'travel_amount': amount,
            'distance_km': 0,
            'description': rate['work_description'] if rate else 'ایاب و ذهاب داخل شهر',
            'rate_code': 'travel_local',
        }

    # بین شهری
    ensure_distance_schema(conn)
    dist = calculate_distance(
        conn,
        from_city=rep_city or rep_province,
        to_city=customer_city or customer_province,
        from_province=rep_province,
        to_province=customer_province,
    )
    rate = get_rate(conn, 'travel_km')
    per_km = int(rate['wage_amount']) if rate else 60000
    km = float(dist.get('round_trip_km') or 0) if dist.get('ok') else 0
    amount = int(round(km * per_km))
    desc = rate['work_description'] if rate else 'ایاب و ذهاب بین شهری'
    if km:
        desc = f"{desc} — {km} کیلومتر"
    return {
        'is_local': False,
        'travel_amount': amount,
        'distance_km': km,
        'description': desc,
        'rate_code': 'travel_km',
        'distance_error': dist.get('error'),
    }


def compute_repair_wage(
    conn,
    representative_id: int,
    customer_city: str,
    customer_province: str = '',
    device_count: int = 1,
    include_travel: bool = True,
) -> dict:
    """
    دستمزد سرویس/تعمیر + ایاب‌وذهاب.
    device_count: تعداد دستگاه (هر دستگاه نرخ تعمیر جدا؛ ایاب یک‌بار)
    """
    rep_city, rep_province, _, rep_name = get_rep_city(conn, representative_id)
    local = is_same_city(rep_city, customer_city)
    rate = get_rate(conn, 'repair')
    if not rate:
        return {'ok': False, 'error': 'نرخ تعمیر تعریف نشده'}

    unit = int(rate['wage_amount'] or 0)
    if not local and rate.get('amount_outside'):
        unit = int(rate['amount_outside'])

    service_total = unit * max(1, int(device_count or 1))
    items = [{
        'rate_code': 'repair',
        'description': rate['work_description'] + (' (خارج محل نمایندگی)' if not local else ' (محل نمایندگی)'),
        'amount': service_total,
        'qty': device_count,
    }]

    travel = None
    if include_travel:
        travel = compute_travel(conn, rep_city, rep_province, customer_city, customer_province)
        items.append({
            'rate_code': travel['rate_code'],
            'description': travel['description'],
            'amount': travel['travel_amount'],
            'qty': 1,
        })

    total = sum(i['amount'] for i in items)
    return {
        'ok': True,
        'is_local': local,
        'rep_name': rep_name,
        'rep_city': rep_city,
        'customer_city': customer_city,
        'service_amount': service_total,
        'travel_amount': travel['travel_amount'] if travel else 0,
        'distance_km': travel['distance_km'] if travel else 0,
        'total': total,
        'items': items,
    }


def save_wage_lines(conn, lines: list, representative_id, representative_name, calc_date,
                    request_id=None, customer_id=None, customer_name=None, source='auto', notes=''):
    """ذخیره چند خط دستمزد."""
    ids = []
    for line in lines:
        cur = conn.execute(
            '''INSERT INTO wage_calculations
               (representative_id, representative_name, work_description, amount, calc_date, notes,
                request_id, customer_id, customer_name, rate_code, is_local, distance_km, source, device_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                representative_id,
                representative_name,
                line.get('description') or line.get('work_description') or '',
                int(line.get('amount') or 0),
                calc_date,
                notes,
                request_id,
                customer_id,
                customer_name,
                line.get('rate_code'),
                line.get('is_local'),
                line.get('distance_km'),
                source,
                line.get('qty') or 1,
            ),
        )
        ids.append(cur.lastrowid)
    conn.commit()
    return ids


def travel_already_paid(conn, representative_id, customer_key, calc_date) -> bool:
    """آیا برای این نماینده + مشتری + تاریخ قبلاً ایاب ثبت شده؟"""
    rows = conn.execute(
        '''SELECT id FROM wage_calculations
           WHERE representative_id = ? AND calc_date = ?
             AND rate_code IN ('travel_local', 'travel_km')
             AND (customer_name = ? OR customer_id = ?)''',
        (representative_id, calc_date, customer_key, customer_key if str(customer_key).isdigit() else -1),
    ).fetchall()
    return bool(rows)


def auto_wage_for_request(conn, req_id: int, force: bool = False) -> dict:
    """
    استخراج خودکار دستمزد هنگام تکمیل پرونده پذیرش.
    - تعمیر: نرخ repair + ایاب (یک‌بار در روز/مشتری)
    - نصب: install_first / install_next بر اساس تعداد
    - بازدید: pm_closed_lt3 به‌صورت پیش‌فرض
    """
    ensure_wage_schema(conn)
    req = conn.execute('SELECT * FROM requests WHERE id = ?', (req_id,)).fetchone()
    if not req:
        return {'ok': False, 'error': 'پرونده یافت نشد'}

    # جلوگیری از تکرار
    if not force:
        already = conn.execute(
            "SELECT COUNT(*) AS c FROM wage_calculations WHERE request_id = ? AND COALESCE(source, '') = ?",
            (req_id, 'auto'),
        ).fetchone()
        if already and already['c'] > 0:
            return {'ok': False, 'error': 'قبلاً برای این پرونده دستمزد خودکار ثبت شده', 'skipped': True}
        if 'wage_calculated' in req.keys() and req['wage_calculated']:
            return {'ok': False, 'error': 'پرچم wage_calculated فعال است', 'skipped': True}

    # نماینده از تکنسین مسئول
    rep_id = None
    tech_id = req['assigned_technician_id'] if 'assigned_technician_id' in req.keys() else None
    tech_name = (req['assigned_technician'] if 'assigned_technician' in req.keys() else '') or ''
    if tech_id:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (tech_id,)).fetchone()
        if user and 'representative_id' in user.keys() and user['representative_id']:
            rep_id = user['representative_id']
    if not rep_id and tech_name:
        # جستجو بر اساس نام
        user = conn.execute(
            'SELECT * FROM users WHERE full_name = ? OR username = ?',
            (tech_name, tech_name),
        ).fetchone()
        if user and 'representative_id' in user.keys() and user['representative_id']:
            rep_id = user['representative_id']

    if not rep_id:
        return {'ok': False, 'error': 'نماینده به پرونده وصل نیست'}

    rep_city, rep_province, _, rep_name = get_rep_city(conn, rep_id)
    customer_city = (req['city'] if 'city' in req.keys() else '') or ''
    customer_province = (req['province'] if 'province' in req.keys() else '') or ''
    customer_name = (req['customer_name'] if 'customer_name' in req.keys() else '') or ''
    customer_id = req['customer_id'] if 'customer_id' in req.keys() else None

    # تاریخ مراجعه
    calc_date = ''
    if 'visit_date' in req.keys() and req['visit_date']:
        calc_date = req['visit_date']
    elif 'reception_date' in req.keys() and req['reception_date']:
        calc_date = req['reception_date']
    else:
        try:
            import jdatetime
            t = jdatetime.date.today()
            calc_date = f'{t.year}/{str(t.month).zfill(2)}/{str(t.day).zfill(2)}'
        except Exception:
            calc_date = ''

    category = (req['request_category'] if 'request_category' in req.keys() else '') or ''
    service_type = (req['service_type'] if 'service_type' in req.keys() else '') or ''

    lines = []
    is_local = is_same_city(rep_city, customer_city)

    device_type = (req['device_type'] if 'device_type' in req.keys() else '') or ''
    # سانترال: از device_type یا فلگ آینده
    is_central = 'سانترال' in device_type or 'central' in device_type.lower()

    # آیتم اصلی بر اساس نوع پرونده
    if 'نصب' in category:
        cust_key = customer_name or str(customer_id or '')
        prior = count_installs_same_day(conn, rep_id, cust_key, calc_date)
        is_first = prior == 0 and not is_central
        rate = get_install_rate(conn, device_type, is_first=is_first, is_central=is_central)
        if rate:
            code = rate.get('rate_code') or ('install_central' if is_central else ('install_first' if is_first else 'install_next'))
            desc = rate['work_description']
            if device_type:
                desc = f"{desc} — {device_type}"
            lines.append({
                'rate_code': code,
                'description': desc,
                'amount': int(rate['wage_amount']),
                'qty': 1,
                'is_local': is_local,
            })
    elif 'بازدید' in category or 'بررسی' in category:
        rate = get_rate(conn, 'pm_closed_lt3')
        if rate:
            lines.append({
                'rate_code': 'pm_closed_lt3',
                'description': rate['work_description'],
                'amount': int(rate['wage_amount']),
                'qty': 1,
                'is_local': is_local,
            })
    else:
        # تعمیر پیش‌فرض
        rate = get_rate(conn, 'repair')
        if rate:
            unit = int(rate['wage_amount'] or 0)
            if not is_local and rate.get('amount_outside'):
                unit = int(rate['amount_outside'])
            desc = rate['work_description']
            desc += ' (محل نمایندگی)' if is_local else ' (خارج محل نمایندگی)'
            lines.append({
                'rate_code': 'repair',
                'description': desc,
                'amount': unit,
                'qty': 1,
                'is_local': is_local,
            })

    # ایاب‌وذهاب — فقط یک‌بار برای روز + مشتری
    cust_key = customer_name or str(customer_id or '')
    if not travel_already_paid(conn, rep_id, cust_key, calc_date):
        travel = compute_travel(conn, rep_city, rep_province, customer_city, customer_province)
        lines.append({
            'rate_code': travel['rate_code'],
            'description': travel['description'],
            'amount': travel['travel_amount'],
            'qty': 1,
            'is_local': travel['is_local'],
            'distance_km': travel.get('distance_km'),
        })

    if not lines:
        return {'ok': False, 'error': 'آیتمی برای محاسبه پیدا نشد'}

    ids = save_wage_lines(
        conn, lines, rep_id, rep_name, calc_date,
        request_id=req_id, customer_id=customer_id, customer_name=customer_name,
        source='auto', notes=f'استخراج خودکار از پرونده #{req_id}',
    )
    try:
        conn.execute('UPDATE requests SET wage_calculated = 1 WHERE id = ?', (req_id,))
        conn.commit()
    except Exception:
        pass

    total = sum(l['amount'] for l in lines)
    return {'ok': True, 'ids': ids, 'total': total, 'lines': lines, 'rep_name': rep_name}


def try_auto_wage_on_status(conn, req_id: int, new_status: str):
    """اگر وضعیت مختومه شد، دستمزد خودکار بساز."""
    closed = {
        'پایان تعمیرات', 'پایان', 'بسته شد', 'تحویل شد',
        'نصب انجام شد', 'بازدید انجام شد',
        'تحویل به مشتری', 'اتمام کار', 'بایگانی',
        'گزارش نهایی ثبت شد', 'تست نهایی و تحویل',
    }
    try:
        from core.app_lists import closed_statuses
        extra = closed_statuses(conn) or set()
        if isinstance(extra, (list, tuple, set)):
            closed = set(closed) | set(extra)
    except Exception:
        pass
    st = (new_status or '').strip()
    if st not in closed and not any(x in st for x in ('پایان', 'تحویل', 'بسته', 'انجام شد', 'نهایی')):
        return None
    try:
        return auto_wage_for_request(conn, req_id, force=False)
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def get_rep_bank_info(conn, representative_id):
    """اطلاعات بانکی از کاربر متصل به نماینده."""
    if not representative_id:
        return {'bank_card': '', 'bank_sheba': '', 'bank_owner': '', 'mobile': ''}
    user = conn.execute(
        'SELECT bank_card, bank_sheba, bank_owner, mobile, full_name FROM users WHERE representative_id = ? LIMIT 1',
        (int(representative_id),),
    ).fetchone()
    if not user:
        return {'bank_card': '', 'bank_sheba': '', 'bank_owner': '', 'mobile': ''}
    return {
        'bank_card': (user['bank_card'] or '') if 'bank_card' in user.keys() else '',
        'bank_sheba': (user['bank_sheba'] or '') if 'bank_sheba' in user.keys() else '',
        'bank_owner': (user['bank_owner'] or '') if 'bank_owner' in user.keys() else '',
        'mobile': (user['mobile'] or '') if 'mobile' in user.keys() else '',
    }


def parse_calc_ym(calc_date):
    if not calc_date:
        return None, None
    s = str(calc_date).replace('-', '/').strip()
    parts = s.split('/')
    try:
        if len(parts) >= 2:
            return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return None, None


def month_name_fa(month: int) -> str:
    names = {
        1: 'فروردین', 2: 'اردیبهشت', 3: 'خرداد', 4: 'تیر',
        5: 'مرداد', 6: 'شهریور', 7: 'مهر', 8: 'آبان',
        9: 'آذر', 10: 'دی', 11: 'بهمن', 12: 'اسفند',
    }
    return names.get(int(month or 0), str(month))


def summarize_rep_wages(conn, representative_id, year, month):
    """جمع ماه/سال و وضعیت پرداخت برای یک نماینده."""
    ensure_wage_schema(conn)
    rows = conn.execute(
        'SELECT * FROM wage_calculations WHERE representative_id = ? ORDER BY id DESC',
        (int(representative_id),),
    ).fetchall()
    month_total = year_total = unpaid_month = paid_month = 0
    month_rows = []
    for r in rows:
        y, m = parse_calc_ym(r['calc_date'] if 'calc_date' in r.keys() else None)
        amt = int(r['amount'] or 0)
        status = (r['payment_status'] if 'payment_status' in r.keys() else None) or 'unpaid'
        if y == year:
            year_total += amt
            if m == month:
                month_total += amt
                month_rows.append(r)
                if status == 'paid':
                    paid_month += amt
                else:
                    unpaid_month += amt
    settlement = conn.execute(
        'SELECT * FROM wage_settlements WHERE representative_id = ? AND year = ? AND month = ?',
        (int(representative_id), int(year), int(month)),
    ).fetchone()
    if settlement:
        settle_status = settlement['status']
    elif unpaid_month <= 0 and month_total > 0:
        settle_status = 'paid'
    elif month_total == 0:
        settle_status = 'empty'
    else:
        settle_status = 'pending'
    return {
        'month_total': month_total,
        'year_total': year_total,
        'unpaid_month': unpaid_month,
        'paid_month': paid_month,
        'month_rows': month_rows,
        'settlement': settlement,
        'settle_status': settle_status,
    }
