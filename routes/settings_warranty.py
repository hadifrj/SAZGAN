# -*- coding: utf-8 -*-
"""مسیرهای گارانتی: warranty(فعال‌سازی/ویرایش/حذف/ورودی)."""
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from flask import (
    request, session, redirect, render_template, jsonify, send_file, current_app
)

logger = logging.getLogger("sazgan")
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


from core.helpers import *  # noqa: F401,F403
from core.constants import *  # noqa: F401,F403



def register(app):
    @app.route('/settings/warranty', methods=['GET', 'POST'])
    def settings_warranty():
        """شناسنامه کالا — ثبت اولیه از تولید (گارانتی هنوز غیرفعال)."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        conn = get_db()
        error = None
        success = None
        if request.method == 'POST':
            customer_name = (request.form.get('customer_name') or '').strip() or None
            device_type = request.form.get('device_type', '').strip()
            model = request.form.get('model', '').strip()
            serial_number = request.form.get('serial_number', '').strip()
            shahriar = request.form.get('shahriar', '').strip() or None

            production_date = _jalali_from_form('prod') or None

            if not serial_number or not device_type:
                error = 'سریال و نوع دستگاه الزامی است.'
            else:
                existing = conn.execute(
                    'SELECT id FROM warranty_cards WHERE serial_number = ?', (serial_number,)
                ).fetchone()
                if existing:
                    error = 'این سریال قبلاً در شناسنامه کالا ثبت شده است.'
                else:
                    conn.execute(
                        "INSERT INTO warranty_cards "
                        "(customer_name, device_type, model, serial_number, production_date, "
                        "installation_date, shahriar, warranty_status, warranty_months, warranty_end_date) "
                        "VALUES (?, ?, ?, ?, ?, NULL, ?, 'تولید شده', NULL, NULL)",
                        (customer_name, device_type, model or None, serial_number, production_date, shahriar)
                    )
                    conn.commit()
                    success = f'شناسنامه کالا برای سریال {serial_number} ثبت شد (گارانتی هنوز فعال نیست).'

        q = (request.args.get('q') or request.args.get('serial') or '').strip()
        if q:
            like = f'%{q}%'
            rows = conn.execute(
                '''SELECT * FROM warranty_cards
                   WHERE serial_number LIKE ?
                      OR IFNULL(customer_name,'') LIKE ?
                      OR IFNULL(shahriar,'') LIKE ?
                      OR IFNULL(device_type,'') LIKE ?
                      OR IFNULL(model,'') LIKE ?
                   ORDER BY id DESC''',
                (like, like, like, like, like)
            ).fetchall()
        else:
            rows = conn.execute('SELECT * FROM warranty_cards ORDER BY id DESC').fetchall()
        cards_list = [_enrich_warranty_row(r) for r in rows]
        customers_list = conn.execute('SELECT * FROM customers WHERE IFNULL(is_archived,0)=0 ORDER BY name').fetchall()
        devices_list = conn.execute('SELECT * FROM devices ORDER BY device_type, model').fetchall()
        conn.close()

        today = jdatetime.date.today()
        return render_template(
            'settings_warranty.html', cards=cards_list, error=error, success=success,
            customers=customers_list, devices=devices_list,
            active_page='settings', current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day,
            import_error=None, imported_count=None, skipped_count=None,
            search_q=q,
        )





    @app.route('/settings/warranty/activate/<int:card_id>', methods=['GET', 'POST'])
    def activate_warranty(card_id):
        """فعال‌سازی گارانتی داخل شناسنامه کالا."""
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        conn = get_db()
        card = conn.execute('SELECT * FROM warranty_cards WHERE id = ?', (card_id,)).fetchone()
        if not card:
            conn.close()
            return redirect('/settings/warranty')

        error = None
        if request.method == 'POST':
            customer_name = (request.form.get('customer_name') or '').strip() or card['customer_name']
            try:
                months = int(request.form.get('warranty_months', '12'))
            except Exception:
                months = 12
            if months not in (6, 12, 18, 24):
                months = 12

            installation_date = _jalali_from_form('inst')
            if not installation_date:
                error = 'تاریخ نصب را کامل وارد کنید.'
            else:
                end_date = _add_jalali_months(installation_date, months)
                if not end_date:
                    error = 'تاریخ نصب نامعتبر است.'
                else:
                    status = _compute_warranty_status(installation_date, end_date)
                    conn.execute(
                        "UPDATE warranty_cards SET customer_name = ?, installation_date = ?, "
                        "warranty_months = ?, warranty_end_date = ?, warranty_status = ? WHERE id = ?",
                        (customer_name, installation_date, months, end_date, status, card_id)
                    )
                    conn.commit()
                    conn.close()
                    return redirect('/settings/warranty')

        customers_list = conn.execute('SELECT * FROM customers WHERE IFNULL(is_archived,0)=0 ORDER BY name').fetchall()
        card_d = _enrich_warranty_row(card)
        conn.close()
        today = jdatetime.date.today()
        return render_template(
            'activate_warranty.html',
            card=card_d,
            customers=customers_list,
            error=error,
            active_page='settings',
            current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day,
            warranty_month_options=(6, 12, 18, 24),
            embed=_is_embed(),
        )





    @app.route('/settings/warranty/edit/<int:card_id>', methods=['GET', 'POST'])
    def edit_warranty(card_id):
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        conn = get_db()
        card = conn.execute('SELECT * FROM warranty_cards WHERE id = ?', (card_id,)).fetchone()
        if not card:
            conn.close()
            return redirect('/settings/warranty')

        if request.method == 'POST':
            customer_name = (request.form.get('customer_name') or '').strip() or None
            device_type = request.form.get('device_type', '').strip()
            model = request.form.get('model', '').strip() or None
            serial_number = request.form.get('serial_number', '').strip()
            shahriar = request.form.get('shahriar', '').strip() or None

            production_date = _jalali_from_form('prod') or None

            months_raw = request.form.get('warranty_months') or ''
            installation_date = card['installation_date']
            warranty_months = card['warranty_months'] if 'warranty_months' in card.keys() else None
            warranty_end_date = card['warranty_end_date'] if 'warranty_end_date' in card.keys() else None

            inst_single = _jalali_from_form('inst')
            if inst_single:
                installation_date = inst_single
                try:
                    months = int(months_raw) if months_raw else (warranty_months or 12)
                except Exception:
                    months = 12
                if months not in (6, 12, 18, 24):
                    months = 12
                warranty_months = months
                warranty_end_date = _add_jalali_months(installation_date, months)

            status = _compute_warranty_status(installation_date, warranty_end_date)

            other = conn.execute(
                'SELECT id FROM warranty_cards WHERE serial_number = ? AND id != ?',
                (serial_number, card_id)
            ).fetchone()
            if other:
                customers_list = conn.execute('SELECT * FROM customers WHERE IFNULL(is_archived,0)=0 ORDER BY name').fetchall()
                devices_list = conn.execute('SELECT * FROM devices ORDER BY device_type, model').fetchall()
                conn.close()
                today = jdatetime.date.today()
                return render_template(
                    'edit_warranty.html', card=_enrich_warranty_row(card),
                    customers=customers_list, devices=devices_list,
                    error='سریال تکراری است.',
                    active_page='settings', current_user=current_user, embed=_is_embed(),
                    jalali_months=JALALI_MONTHS,
                    today_year=today.year, today_month=today.month, today_day=today.day,
                    warranty_month_options=(6, 12, 18, 24),
                )

            conn.execute(
                "UPDATE warranty_cards SET customer_name = ?, device_type = ?, model = ?, serial_number = ?, "
                "production_date = ?, installation_date = ?, shahriar = ?, warranty_months = ?, "
                "warranty_end_date = ?, warranty_status = ? WHERE id = ?",
                (customer_name, device_type, model, serial_number, production_date,
                 installation_date, shahriar, warranty_months, warranty_end_date, status, card_id)
            )
            conn.commit()
            conn.close()
            return redirect('/settings/warranty')

        customers_list = conn.execute('SELECT * FROM customers WHERE IFNULL(is_archived,0)=0 ORDER BY name').fetchall()
        devices_list = conn.execute('SELECT * FROM devices ORDER BY device_type, model').fetchall()
        card_d = _enrich_warranty_row(card)
        conn.close()

        today = jdatetime.date.today()
        return render_template(
            'edit_warranty.html', card=card_d, error=None,
            customers=customers_list, devices=devices_list,
            active_page='settings', current_user=current_user, embed=_is_embed(),
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day,
            warranty_month_options=(6, 12, 18, 24),
        )





    @app.route('/settings/warranty/delete/<int:card_id>', methods=['POST'])
    def delete_warranty(card_id):
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        conn = get_db()
        try:
            cols = {r[1] for r in conn.execute('PRAGMA table_info(warranty_cards)').fetchall()}
            if 'is_archived' not in cols:
                conn.execute('ALTER TABLE warranty_cards ADD COLUMN is_archived INTEGER DEFAULT 0')
            conn.execute('UPDATE warranty_cards SET is_archived=1 WHERE id=?', (card_id,))
        except Exception:
            conn.execute('DELETE FROM warranty_cards WHERE id = ?', (card_id,))
        conn.commit()
        conn.close()
        return redirect('/settings/warranty')





    @app.route('/settings/warranty/import', methods=['POST'])
    def import_warranty():
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        file = request.files.get('excel_file')
        import_error = None
        imported_count = 0
        skipped_count = 0

        if not file or file.filename == '':
            import_error = 'هیچ فایلی انتخاب نشده است.'
        elif not file.filename.lower().endswith(('.xlsx', '.xls')):
            import_error = 'فقط فایل اکسل (xlsx یا xls) مجاز است.'
        else:
            try:
                workbook = openpyxl.load_workbook(file, data_only=True)
                sheet = workbook.active
                conn = get_db()

                rows = list(sheet.iter_rows(values_only=True))
                data_rows = rows[1:] if rows else []

                for row in data_rows:
                    if not row:
                        continue
                    values = list(row) + [None] * 8
                    customer_name = values[0]
                    device_type = values[1]
                    model = values[2]
                    serial_number = values[3]
                    production_date = values[4]
                    shahriar = values[5] if len(values) > 5 else None

                    if not serial_number:
                        skipped_count += 1
                        continue

                    existing = conn.execute(
                        'SELECT id FROM warranty_cards WHERE serial_number = ?', (str(serial_number),)
                    ).fetchone()
                    if existing:
                        skipped_count += 1
                        continue

                    conn.execute(
                        "INSERT INTO warranty_cards "
                        "(customer_name, device_type, model, serial_number, production_date, "
                        "installation_date, shahriar, warranty_status) "
                        "VALUES (?, ?, ?, ?, ?, NULL, ?, 'تولید شده')",
                        (str(customer_name) if customer_name else None,
                         str(device_type) if device_type else None,
                         str(model) if model else None,
                         str(serial_number),
                         str(production_date) if production_date else None,
                         str(shahriar) if shahriar else None)
                    )
                    imported_count += 1

                conn.commit()
                conn.close()
            except Exception as e:
                import_error = f'خطا در پردازش فایل: {e}'

        conn = get_db()
        rows = conn.execute('SELECT * FROM warranty_cards ORDER BY id DESC').fetchall()
        cards_list = [_enrich_warranty_row(r) for r in rows]
        customers_list = conn.execute('SELECT * FROM customers WHERE IFNULL(is_archived,0)=0 ORDER BY name').fetchall()
        devices_list = conn.execute('SELECT * FROM devices ORDER BY device_type, model').fetchall()
        conn.close()

        today = jdatetime.date.today()
        return render_template(
            'settings_warranty.html', cards=cards_list,
            customers=customers_list, devices=devices_list,
            active_page='settings', current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day,
            error=None, success=None, import_error=import_error,
            imported_count=imported_count, skipped_count=skipped_count,
            search_q='',
        )




