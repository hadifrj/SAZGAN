# -*- coding: utf-8 -*-
"""منطق موجودی انبار."""
from __future__ import annotations

def _get_get_stock_qty(conn, part_id, location_type='کارخانه', province=None):
    if not part_id:
        return 0
    if location_type == 'استانی' and province:
        row = conn.execute(
            "SELECT quantity FROM warehouse_stock WHERE part_id = ? AND location_type = 'استانی' AND province = ?",
            (part_id, province)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT quantity FROM warehouse_stock WHERE part_id = ? AND location_type = ?",
            (part_id, location_type)
        ).fetchone()
    return int(row['quantity']) if row else 0




def _adjust_stock(conn, part_id, delta, location_type='کارخانه', province=None):
    """تغییر موجودی با قفل اتمیک (جلوگیری از race condition).

    از BEGIN IMMEDIATE + UPDATE شرطی استفاده می‌کند تا دو درخواست همزمان
    نتوانند موجودی را منفی کنند.
    """
    if not part_id or delta == 0:
        return True, None
    try:
        delta = int(delta)
        part_id = int(part_id)
    except Exception:
        return False, 'شناسه/مقدار نامعتبر'

    # قفل سطح دیتابیس برای این تراکنش (SQLite)
    try:
        conn.execute('BEGIN IMMEDIATE')
    except Exception:
        # اگر از قبل داخل تراکنش باشیم، ادامه می‌دهیم
        pass

    is_province = (location_type == 'استانی' and province)

    if is_province:
        existing = conn.execute(
            "SELECT id, quantity FROM warehouse_stock WHERE part_id = ? AND location_type = 'استانی' AND province = ?",
            (part_id, province)
        ).fetchone()
    else:
        existing = conn.execute(
            "SELECT id, quantity FROM warehouse_stock WHERE part_id = ? AND location_type = ?",
            (part_id, location_type)
        ).fetchone()

    if existing:
        cur_q = int(existing['quantity'] or 0)
        if delta < 0:
            # به‌روزرسانی اتمیک فقط اگر موجودی کافی باشد
            cur = conn.execute(
                'UPDATE warehouse_stock SET quantity = quantity + ? WHERE id = ? AND quantity + ? >= 0',
                (delta, existing['id'], delta)
            )
            if cur.rowcount != 1:
                return False, f'موجودی کافی نیست (موجود: {cur_q})'
            new_q = cur_q + delta
            return True, new_q
        else:
            conn.execute(
                'UPDATE warehouse_stock SET quantity = quantity + ? WHERE id = ?',
                (delta, existing['id'])
            )
            return True, cur_q + delta

    # ردیف وجود ندارد
    if delta < 0:
        if is_province:
            return False, 'این قطعه در انبار استانی ثبت نشده است'
        return False, 'این قطعه در انبار کارخانه موجودی ندارد'

    if is_province:
        conn.execute(
            "INSERT INTO warehouse_stock (part_id, location_type, province, quantity) VALUES (?, 'استانی', ?, ?)",
            (part_id, province, delta)
        )
    else:
        conn.execute(
            "INSERT INTO warehouse_stock (part_id, location_type, quantity) VALUES (?, ?, ?)",
            (part_id, location_type, delta)
        )
    return True, delta







def _record_external_parts_to_province(conn, request_id, user_name=None):
    """ثبت ورود قطعات پرونده تعمیر خارجی به انبار استان مربوطه."""
    req = conn.execute('SELECT * FROM requests WHERE id = ?', (request_id,)).fetchone()
    if not req:
        return
    province = req['province'] if 'province' in req.keys() else None
    if not province:
        return
    rows = conn.execute(
        'SELECT * FROM request_parts WHERE request_id = ? AND (voucher_recorded IS NULL OR voucher_recorded = 0)',
        (request_id,)
    ).fetchall()
    for prow in rows:
        pid = prow['part_id']
        qty = int(prow['quantity'] or 1)
        if pid:
            _adjust_stock(conn, int(pid), +qty, 'استانی', province)
            after = _get_stock_qty(conn, int(pid), 'استانی', province)
            try:
                conn.execute(
                    'INSERT INTO warehouse_movements (part_id, location_type, province, delta, quantity_after, reason, request_id, created_at, user_name) VALUES (?,?,?,?,?,?,?,?,?)',
                    (int(pid), 'استانی', province, qty, after,
                     'ورود انبار استان — پذیرش #' + str(request_id), request_id, '', user_name)
                )
            except Exception:
                pass
        conn.execute(
            'UPDATE request_parts SET voucher_recorded = 1, stock_location = ?, stock_province = ? WHERE id = ?',
            ('استانی', province, prow['id'])
        )



def _apply_request_parts_stock(conn, request_id, user_name=None, reason='خروج با گزارش نهایی'):
    """خروج از انبار: قطعات واردشده با حواله اولیه/نهایی با گزارش نهایی خارج می‌شوند (موجودی به صفر)."""
    rows = conn.execute(
        'SELECT * FROM request_parts WHERE request_id = ? AND voucher_recorded = 1 AND (stock_applied IS NULL OR stock_applied = 0)',
        (request_id,)
    ).fetchall()
    errors = []
    for prow in rows:
        pid = prow['part_id']
        qty = int(prow['quantity'] or 1)
        if not pid:
            conn.execute('UPDATE request_parts SET stock_applied = 1 WHERE id = ?', (prow['id'],))
            continue
        ok, info = _adjust_stock(conn, int(pid), -qty, 'کارخانه', None)
        if not ok:
            cur = _get_stock_qty(conn, int(pid), 'کارخانه', None)
            if cur and cur > 0:
                _adjust_stock(conn, int(pid), -int(cur), 'کارخانه', None)
            else:
                errors.append(str(info))
        conn.execute(
            'UPDATE request_parts SET stock_applied = 1, stock_location = ? WHERE id = ?',
            ('کارخانه', prow['id'])
        )
        try:
            after = _get_stock_qty(conn, int(pid), 'کارخانه', None)
            conn.execute(
                'INSERT INTO warehouse_movements (part_id, location_type, province, delta, quantity_after, reason, request_id, created_at, user_name) VALUES (?,?,?,?,?,?,?,?,?)',
                (int(pid), 'کارخانه', None, -qty, after, reason + ' — پذیرش #' + str(request_id), request_id, '', user_name)
            )
        except Exception:
            pass
    return errors




def _record_voucher_parts(conn, request_id, stage_label, user_name=None):
    """ورود به انبار کارخانه با حواله تعمیر اولیه یا نهایی."""
    rows = conn.execute('SELECT * FROM request_parts WHERE request_id = ?', (request_id,)).fetchall()
    label = stage_label or ''
    for prow in rows:
        keys = prow.keys()
        stage = (prow['stage'] or '') if 'stage' in keys else ''
        # فقط قطعات هم‌نوع با حواله
        if 'اولیه' in label and stage and ('نهایی' in stage) and ('اولیه' not in stage):
            continue
        if ('نهایی' in label) and ('اولیه' not in label) and stage and ('اولیه' in stage) and ('نهایی' not in stage):
            continue
        if 'voucher_recorded' in keys and prow['voucher_recorded']:
            continue
        pid = prow['part_id']
        qty = int(prow['quantity'] or 1)
        after = None
        if pid:
            ok, info = _adjust_stock(conn, int(pid), +qty, 'کارخانه', None)
            after = _get_stock_qty(conn, int(pid), 'کارخانه', None)
        conn.execute(
            'UPDATE request_parts SET voucher_recorded = 1, stock_location = ? WHERE id = ?',
            ('کارخانه', prow['id'])
        )
        try:
            conn.execute(
                'INSERT INTO warehouse_movements (part_id, location_type, province, delta, quantity_after, reason, request_id, created_at, user_name) VALUES (?,?,?,?,?,?,?,?,?)',
                (pid, 'کارخانه', None, qty if pid else 0, after,
                 'ورود با حواله پذیرش #' + str(request_id) + ' — ' + str(stage_label),
                 request_id, '', user_name)
            )
        except Exception:
            pass




def _issue_part_from_stock(conn, part_id, quantity, service_type, province=None):
    """صدور قطعه از انبار مناسب. برای تعمیر داخلی از کارخانه، برای خارجی از استانی سپس کارخانه."""
    qty = int(quantity or 1)
    if not part_id:
        return True, 'بدون کاتالوگ قطعه — موجودی تغییر نکرد', None, None
    if service_type == 'کارخانه':
        ok, info = _adjust_stock(conn, part_id, -qty, 'کارخانه')
        return ok, info, 'کارخانه', None
    # در محل: اول انبار استانی
    if province:
        ok, info = _adjust_stock(conn, part_id, -qty, 'استانی', province)
        if ok:
            return True, info, 'استانی', province
    ok, info = _adjust_stock(conn, part_id, -qty, 'کارخانه')
    if ok:
        return True, info, 'کارخانه', None
    return False, info, None, None




def _restore_part_to_stock(conn, part_row):
    """حذف ردیف: خنثی‌کردن ورود حواله یا برگشت پس از خروج."""
    if not part_row:
        return
    keys = part_row.keys() if hasattr(part_row, 'keys') else []
    part_id = part_row['part_id'] if 'part_id' in keys else None
    if not part_id:
        return
    qty = int(part_row['quantity'] or 1)
    loc = part_row['stock_location'] if 'stock_location' in keys and part_row['stock_location'] else 'کارخانه'
    prov = part_row['stock_province'] if 'stock_province' in keys else None
    voucher = part_row['voucher_recorded'] if 'voucher_recorded' in keys else 0
    exited = part_row['stock_applied'] if 'stock_applied' in keys else 0
    if exited:
        _adjust_stock(conn, part_id, qty, loc, prov)
    elif voucher:
        _adjust_stock(conn, part_id, -qty, loc, prov)

def _get_stock_qty(conn, part_id, location_type='کارخانه', province=None):
    """نام استاندارد؛ همان _get_get_stock_qty."""
    return _get_get_stock_qty(conn, part_id, location_type, province)
