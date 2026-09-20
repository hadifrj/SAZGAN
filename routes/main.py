# -*- coding: utf-8 -*-
from __future__ import annotations
from flask import (
    request, session, redirect, render_template, jsonify, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from io import BytesIO
import os, base64, time
import jdatetime
try:
    import openpyxl
except ImportError:
    openpyxl = None

from core.constants import *


from core.helpers import *  # noqa: F401,F403
from core.constants import *  # noqa: F401,F403

def register(app):
    """مسیرهای main."""
    @app.route('/customer-affairs/surveys', methods=['GET'])
    def customer_affairs_surveys():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'customer_affairs')):
            return redirect('/')
        return render_template(
            'surveys_v46.html',
            active_page='customer_affairs',
            current_user=current_user,
        )

    # دسترسی به هلپرها

    def _cartable_template_for_role(current_user):
        """فقط تعیین می‌کنه کدوم تمپلیت مال کدوم نقشه — سبک و بدون کوئری سنگین؛
        این تشخیص باید همیشه با شاخه‌بندی نقش در /api/cartable/lazy هماهنگ بمونه."""
        role = current_user['role']
        if role == FINANCE_ROLE:
            return 'finance_cartable.html', {}
        if role in TECHNICIAN_ROLES or role == 'کنترل کیفیت':
            tpl = 'qc_cartable.html' if role == 'کنترل کیفیت' else 'tech_cartable.html'
            return tpl, {}
        return 'cartable.html', {}

    @app.route('/', methods=['GET', 'POST'])
    def home():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')

        # فاز ۲ بخش ۴ (lazy-load کارتابل سنگین): این روت دیگر کوئری سنگین رو خودش
        # اجرا نمی‌کنه — فقط بر اساس نقش تشخیص می‌ده کدوم تمپلیت باید رندر بشه و یک
        # اسکلت خالی برمی‌گردونه؛ خودِ تمپلیت با جاوااسکریپت از /api/cartable/lazy
        # داده‌ی واقعی رو می‌گیره و جایگزین می‌کنه. منطق تشخیص نقش/تمپلیت دقیقاً باید
        # با _cartable_lazy_dispatch (پایین همین فایل) هماهنگ بمونه.
        tpl, extra_ctx = _cartable_template_for_role(current_user)
        return render_template(
            tpl,
            lazy_cartable=True,
            active_page='home',
            current_user=current_user,
            delay_threshold=DELAY_THRESHOLD_DAYS,
            **extra_ctx
        )

    @app.route('/api/cartable/lazy', methods=['GET'])
    def api_cartable_lazy():
        current_user = get_current_user()
        if not current_user:
            return 'unauthorized', 401
        conn = get_db()

        if current_user['role'] == FINANCE_ROLE:
            tasks = _get_finance_tasks(conn)
            conn.close()
            return render_template(
                '_finance_cartable_body.html',
                tasks=tasks, open_count=len(tasks),
                active_page='home', current_user=current_user,
                delay_threshold=DELAY_THRESHOLD_DAYS,
            )

        if current_user['role'] in TECHNICIAN_ROLES or current_user['role'] == 'کنترل کیفیت':
            if current_user['role'] == 'کنترل کیفیت':
                tasks = _get_qc_tasks(conn)
            else:
                tasks = _get_technician_tasks(conn, current_user)
            conn.close()
            open_count = len([t for t in tasks if not t['is_closed']])
            closed_count = len([t for t in tasks if t['is_closed']])
            body_tpl = '_qc_cartable_body.html' if current_user['role'] == 'کنترل کیفیت' else '_tech_cartable_body.html'
            qc_open = len([t for t in tasks if t.get('in_qc_stage')]) if current_user['role'] == 'کنترل کیفیت' else 0
            return render_template(
                body_tpl,
                tasks=tasks, open_count=open_count, closed_count=closed_count,
                total_count=len(tasks), qc_open=qc_open,
                active_page='home', current_user=current_user,
                delay_threshold=DELAY_THRESHOLD_DAYS,
            )

        from routes.features import ensure_features_schema
        ensure_features_schema(conn)
        role = current_user['role']
        items = []
        if role in ('مسئول پذیرش', 'مدیر سیستم', 'مدیر'):
            try:
                cols = {r[1] for r in conn.execute('PRAGMA table_info(requests)').fetchall()}
            except Exception:
                cols = set()
            select_cols = 'id, customer_name, status, service_type, request_category, reception_date'
            if 'request_subtype' in cols:
                select_cols += ', request_subtype'
            rows = conn.execute(
                f"""
                SELECT {select_cols}
                FROM requests WHERE status IN (
                    'پذیرش','اعلام خرابی','تعمیر انجام‌شده — منتظر بررسی پذیرش',
                    'تحویل به پذیرش','رد پیش‌فاکتور — ارسال به مشتری',
                    'در انتظار پذیرش دستگاه است','پذیرش انجام شد',
                    'در انتظار پذیرش',
                    'در انتظار بررسی پذیرش'
                )
                OR (
                    request_category IN ('درخواست خدمات','اعلام خرابی','درخواست سرویس')
                    AND status IN ('در انتظار بررسی پذیرش','در انتظار پذیرش')
                )
                ORDER BY id DESC LIMIT 100
                """
            ).fetchall()
            items.extend([dict(r, bucket='پذیرش') for r in rows])
            anns = conn.execute(
                """
                SELECT id, hospital_name, contact_phone, status, created_at
                FROM service_announcements WHERE status LIKE 'جدید%' ORDER BY id DESC LIMIT 50
                """
            ).fetchall()
            items.extend([dict(r, bucket='اعلام درخواست خدمات', is_announce=1) for r in anns])
        if role in ('امور مالی', 'مدیر سیستم', 'مدیر'):
            rows = conn.execute(
                """
                SELECT id, customer_name, status, proforma_status, reception_date
                FROM requests WHERE status IN (
                    'منتظر تأیید پیش‌فاکتور','صدور پیش‌فاکتور','پایان تعمیر',
                    'در انتظار ارسال پیش‌فاکتور است','در انتظار دریافت تاییدیه پیش‌فاکتور است',
                    'در انتظار صدور فاکتور است','پایان تعمیرات'
                ) ORDER BY id DESC LIMIT 80
                """
            ).fetchall()
            items.extend([dict(r, bucket='مالی') for r in rows])
        conn.close()
        return render_template(
            '_cartable_body.html', items=items, active_page='home', current_user=current_user
        )

    @app.route('/quick-report-upload', methods=['GET', 'POST'])
    def quick_report_upload():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        allowed_roles = ['مسئول پذیرش', 'کنترل کیفیت', 'تکنسین کارخانه', 'تکنسین استانی', 'مدیر', 'مدیر سیستم']
        if current_user['role'] not in allowed_roles:
            return redirect('/')

        conn = get_db()
        result = None
        error = None

        if request.method == 'POST':
            reception_no = (request.form.get('reception_no') or '').strip()
            serial_number = (request.form.get('serial_number') or '').strip()
            img_data = request.form.get('cropped_image') or ''

            req = None
            if reception_no:
                req = conn.execute(
                    'SELECT id, reception_no, serial_number, customer_name FROM requests WHERE reception_no = ?',
                    (reception_no,)
                ).fetchone()

            if not reception_no:
                error = 'شماره پذیرش را وارد کنید.'
            elif not req:
                error = 'پذیرشی با این شماره پیدا نشد.'
            elif serial_number and req['serial_number'] and serial_number != req['serial_number']:
                error = 'سریال وارد شده با سریال ثبت‌شده برای این پذیرش مطابقت ندارد.'
            elif not img_data or ',' not in img_data:
                error = 'ابتدا با دوربین عکس بگیرید.'
            else:
                try:
                    header, b64data = img_data.split(',', 1)
                    raw = base64.b64decode(b64data)
                    os.makedirs(ATTACHMENTS_FOLDER, exist_ok=True)
                    filename = secure_filename(f"repreport_{req['id']}_{int(time.time())}.jpg")
                    save_uploaded_image(raw, os.path.join(ATTACHMENTS_FOLDER, filename))
                    today = jdatetime.date.today()
                    uploaded_at = f"{today.year}/{str(today.month).zfill(2)}/{str(today.day).zfill(2)}"
                    conn.execute(
                        'INSERT INTO request_attachments (request_id, filename, original_name, label, uploaded_by, uploaded_at) '
                        'VALUES (?, ?, ?, ?, ?, ?)',
                        (req['id'], filename, filename, 'گزارش نماینده (آپلود سریع)', current_user['full_name'], uploaded_at)
                    )
                    conn.commit()
                    result = dict(req)
                except Exception:
                    error = 'خطا در ذخیره‌سازی تصویر. دوباره تلاش کنید.'

        conn.close()
        return render_template(
            'quick_report_upload.html',
            current_user=current_user, active_page='quick-report-upload',
            result=result, error=error
        )

    @app.route('/attachments/upload/<int:req_id>', methods=['POST'])
    def attachment_upload(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        allowed_roles = ['مسئول پذیرش', 'کنترل کیفیت', 'تکنسین کارخانه', 'تکنسین استانی']
        if current_user['role'] not in allowed_roles:
            return redirect('/')

        conn = get_db()
        req = conn.execute('SELECT id FROM requests WHERE id = ?', (req_id,)).fetchone()
        if not req:
            conn.close()
            return redirect('/')

        f = request.files.get('attachment')
        label = (request.form.get('label') or '').strip() or 'پیوست'
        redirect_to = request.form.get('redirect_to') or request.referrer or '/'

        if f and f.filename:
            ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
            if ext in ALLOWED_ATTACHMENT_EXTENSIONS:
                import time
                safe = secure_filename(f.filename)
                filename = f"req{req_id}_{int(time.time())}_{safe}"
                path_save = os.path.join(ATTACHMENTS_FOLDER, filename)
                save_uploaded_image(f, path_save)
                today = jdatetime.date.today()
                uploaded_at = f"{today.year}/{str(today.month).zfill(2)}/{str(today.day).zfill(2)}"
                conn.execute(
                    'INSERT INTO request_attachments (request_id, filename, original_name, label, uploaded_by, uploaded_at) VALUES (?, ?, ?, ?, ?, ?)',
                    (req_id, filename, f.filename, label, current_user['full_name'], uploaded_at)
                )
                conn.commit()
        conn.close()
        return redirect(redirect_to)




    @app.route('/attachments/delete/<int:att_id>', methods=['POST'])
    def attachment_delete(att_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        att = conn.execute('SELECT * FROM request_attachments WHERE id = ?', (att_id,)).fetchone()
        redirect_to = request.form.get('redirect_to') or request.referrer or '/'
        if att:
            can = (
                current_user['role'] == 'مسئول پذیرش'
                or att['uploaded_by'] == current_user['full_name']
            )
            if can:
                fpath = os.path.join(ATTACHMENTS_FOLDER, att['filename'])
                if os.path.isfile(fpath):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
                conn.execute('DELETE FROM request_attachments WHERE id = ?', (att_id,))
                conn.commit()
        conn.close()
        return redirect(redirect_to)




    @app.route('/customer-affairs/new-request', methods=['GET'])
    def customer_affairs_new_request():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'customer_affairs')):
            return redirect('/')

        return render_template(
            'customer_affairs_new_request.html',
            service_categories=SERVICE_CATEGORIES,
            active_page='ca-new-request', current_user=current_user,
            embed=_is_embed()
        )

    @app.route('/customer-affairs/new-request/quick', methods=['GET', 'POST'])
    def customer_affairs_quick_new():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'customer_affairs')):
            return redirect('/')

        conn = get_db()

        if request.method == 'POST':
            slug = request.form['request_slug']
            cfg = SERVICE_CATEGORIES.get(slug)
            if not cfg:
                conn.close()
                return redirect('/customer-affairs/new-request/quick')

            customer_id = (request.form.get('customer_id') or '').strip()
            if not customer_id:
                conn.close()
                return redirect('/customer-affairs/new-request/quick?error=customer_required')
            try:
                crow = conn.execute('SELECT name, address, phone, province, city FROM customers WHERE id = ?', (int(customer_id),)).fetchone()
            except Exception:
                crow = None
            if not crow:
                conn.close()
                return redirect('/customer-affairs/new-request/quick?error=customer_required')
            customer_name = crow['name'] if hasattr(crow, 'keys') else crow[0]
            customer_address = (request.form.get('customer_address') or '').strip() or ((crow['address'] if hasattr(crow, 'keys') else (crow[1] or '')) or '')
            customer_phone = (request.form.get('customer_phone') or '').strip() or ((crow['phone'] if hasattr(crow, 'keys') else (crow[2] or '')) or '')
            device_type = request.form.get('device_type') or ''
            serial_number = request.form.get('serial_number') or ''
            installation_date = request.form.get('installation_date', '')
            problem_desc = request.form.get('problem_desc') or ''
            province = (request.form.get('province') or '').strip() or ((crow['province'] if hasattr(crow, 'keys') else (crow[3] or '')) or '')
            assigned_technician = request.form.get('assigned_technician') or None

            reception_date = _jalali_from_form('recep')
            if not reception_date:
                reception_date = request.form.get('recep_date') or ''

            conn.execute(
                '''INSERT INTO requests
                   (customer_name, customer_address, customer_phone, device_type, serial_number,
                    installation_date, problem_desc, service_type, province, assigned_technician,
                    reception_date, request_category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (customer_name, customer_address, customer_phone, device_type, serial_number,
                 installation_date, problem_desc, cfg['service_type'], province, assigned_technician,
                 reception_date, cfg['category'])
            )
            conn.commit()
            conn.close()
            return redirect('/customer-affairs/new-request')

        technicians = conn.execute(
            "SELECT id, full_name, role, province FROM users WHERE role IN ('تکنسین کارخانه', 'تکنسین استانی') AND IFNULL(is_active,1)=1 ORDER BY full_name"
        ).fetchall()
        try:
            customers = conn.execute(
                "SELECT id, name, province, city, address, phone FROM customers WHERE IFNULL(is_archived,0)=0 ORDER BY name"
            ).fetchall()
        except Exception:
            try:
                customers = conn.execute(
                    "SELECT id, name, province, city, address, phone FROM customers ORDER BY name"
                ).fetchall()
            except Exception:
                customers = []
        # متن‌های آماده شرح کار
        ready_texts_problem = []
        try:
            from core.app_lists import get_list_items
            ready_texts_problem = get_list_items(conn, 'problem') or get_list_items(conn, 'ready_texts_problem') or []
        except Exception:
            try:
                rows = conn.execute(
                    "SELECT value FROM app_lists WHERE list_key IN ('problem','ready_texts_problem','problem_desc') ORDER BY sort_order, id"
                ).fetchall()
                ready_texts_problem = [r[0] if not hasattr(r, 'keys') else r['value'] for r in rows]
            except Exception:
                ready_texts_problem = []
        conn.close()

        today = jdatetime.date.today()
        return render_template(
            'customer_affairs_quick_new.html',
            service_categories=SERVICE_CATEGORIES,
            provinces=PROVINCES, technicians=technicians,
            customers=customers,
            ready_texts_problem=ready_texts_problem,
            active_page='ca-new-request', current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day,
            embed=_is_embed()
        )




    @app.route('/customer-affairs/open-list')
    def customer_affairs_open_list():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'customer_affairs')):
            return redirect('/')

        conn = get_db()
        rows = conn.execute(
            """SELECT * FROM requests
               WHERE status NOT IN ('تحویل شد', 'پایان تعمیرات', 'پایان', 'بسته شد')
               ORDER BY id DESC"""
        ).fetchall()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        province = request.args.get('province', '').strip()
        status = request.args.get('status', '').strip()
        only_delayed = request.args.get('only_delayed') == '1'

        enriched = _enrich_delay(conn, rows)
        conn.close()
        enriched = _filter_by_date_range(enriched, date_from or None, date_to or None)
        enriched = _filter_rows(enriched, province=province or None, status=status or None, only_delayed=only_delayed)

        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        pg = paginate(enriched, page=parse_page(request.args), per_page=parse_per_page(request.args, 25))
        pg_ctx = pagination_context(pg, request.args)

        return render_template(
            'customer_affairs_list.html', requests=pg['items'],
            page_title='لیست درخواست‌های در جریان',
            active_page='ca-open-list', current_user=current_user,
            export_url='/customer-affairs/export?scope=open',
            date_from=date_from, date_to=date_to, province=province, status=status,
            only_delayed=only_delayed, provinces=PROVINCES, delay_threshold=DELAY_THRESHOLD_DAYS,
            show_status_filter=True,
            **pg_ctx,
        )




    @app.route('/customer-affairs/report')
    def customer_affairs_report():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'customer_affairs')):
            return redirect('/')

        conn = get_db()
        rows = conn.execute("SELECT * FROM requests ORDER BY id DESC").fetchall()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        province = request.args.get('province', '').strip()
        status = request.args.get('status', '').strip()
        only_delayed = request.args.get('only_delayed') == '1'

        enriched = _enrich_delay(conn, rows)
        conn.close()
        enriched = _filter_by_date_range(enriched, date_from or None, date_to or None)
        enriched = _filter_rows(enriched, province=province or None, status=status or None, only_delayed=only_delayed)

        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        pg = paginate(enriched, page=parse_page(request.args), per_page=parse_per_page(request.args, 25))
        pg_ctx = pagination_context(pg, request.args)

        return render_template(
            'customer_affairs_list.html', requests=pg['items'],
            page_title='گزارش عملکرد خدمات (بایگانی کامل)',
            active_page='ca-report', current_user=current_user,
            export_url='/customer-affairs/export?scope=all',
            date_from=date_from, date_to=date_to, province=province, status=status,
            only_delayed=only_delayed, provinces=PROVINCES, delay_threshold=DELAY_THRESHOLD_DAYS,
            show_status_filter=True,
            **pg_ctx,
        )




    @app.route('/customer-affairs/export')
    def customer_affairs_export():
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'customer_affairs')):
            return redirect('/')
        scope = request.args.get('scope', 'all')
        conn = get_db()
        if scope == 'open':
            rows = conn.execute(
                """SELECT * FROM requests
                   WHERE status NOT IN ('تحویل شد', 'پایان تعمیرات', 'پایان', 'بسته شد')
                   ORDER BY id"""
            ).fetchall()
            name = 'open_requests.xlsx'
        else:
            rows = conn.execute('SELECT * FROM requests ORDER BY id').fetchall()
            name = 'all_requests.xlsx'
        conn.close()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'درخواست‌ها'
        headers = [
            'کد', 'دسته', 'زیرنوع', 'نوع سرویس', 'تاریخ ثبت', 'نام مشتری', 'نوع دستگاه',
            'سریال', 'استان', 'شهر', 'شرح', 'تکنسین', 'وضعیت', 'شماره فاکتور', 'شماره پیگیری'
        ]
        ws.append(headers)
        for r in rows:
            ws.append([
                r['id'], r['request_category'], r['request_subtype'], r['service_type'],
                r['reception_date'], r['customer_name'], r['device_type'], r['serial_number'],
                r['province'], r['city'], r['problem_desc'], r['assigned_technician'],
                r['status'], r['invoice_number'], r['tracking_number'],
            ])
        for col in ws.columns:
            max_len = max((len(str(c.value)) if c.value else 0) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)
        out = BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(
            out,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=name
        )






    @app.route('/account', methods=['GET', 'POST'])
    def account_info():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        from_settings = (request.args.get('from') or request.form.get('from') or '') == 'settings'
        try:
            role = current_user['role'] if current_user and 'role' in current_user.keys() else ''
        except Exception:
            role = ''
        can_change_password = role in ('مدیر', 'مدیر سیستم', 'مسئول پذیرش')
        is_rep = role == 'تکنسین استانی'
        error = success = None
        bank_card = bank_sheba = bank_owner = ''

        def _bank_cols(conn):
            cols = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
            for c in ('bank_card', 'bank_sheba', 'bank_owner', 'photo_filename'):
                if c not in cols:
                    try:
                        conn.execute('ALTER TABLE users ADD COLUMN %s TEXT' % c)
                    except Exception:
                        pass
            try:
                conn.commit()
            except Exception:
                pass

        conn = get_db()
        try:
            _bank_cols(conn)
            row = conn.execute(
                'SELECT bank_card, bank_sheba, bank_owner FROM users WHERE id=?',
                (current_user['id'],),
            ).fetchone()
            if row:
                k = row.keys()
                bank_card = (row['bank_card'] if 'bank_card' in k else '') or ''
                bank_sheba = (row['bank_sheba'] if 'bank_sheba' in k else '') or ''
                bank_owner = (row['bank_owner'] if 'bank_owner' in k else '') or ''

            if request.method == 'POST':
                if not _validate_csrf():
                    error = 'خطای امنیتی CSRF'
                else:
                    section = (request.form.get('form_section') or '').strip()
                    # --- photo ---
                    if section == 'photo':
                        photo = request.files.get('photo')
                        cropped_b64 = (request.form.get('photo_cropped') or '').strip()
                        has_photo = bool((photo and getattr(photo, 'filename', None)) or cropped_b64.startswith('data:image'))
                        if not has_photo:
                            error = 'ابتدا عکس را انتخاب و برش را تأیید کنید.'
                        else:
                            try:
                                os.makedirs(USER_UPLOAD_FOLDER, exist_ok=True)
                                folder = USER_UPLOAD_FOLDER
                            except Exception:
                                folder = os.path.join(app.root_path, 'static', 'uploads', 'users')
                                os.makedirs(folder, exist_ok=True)
                            filename = 'user_%s.jpg' % current_user['id']
                            dest = os.path.join(folder, filename)
                            saved = False
                            if cropped_b64.startswith('data:image'):
                                import base64
                                raw = base64.b64decode(cropped_b64.split(',', 1)[1])
                                save_uploaded_image(raw, dest)
                                saved = True
                            elif photo and photo.filename:
                                save_uploaded_image(photo, dest)
                                saved = True
                            if saved:
                                conn.execute('UPDATE users SET photo_filename=? WHERE id=?', (filename, current_user['id']))
                                conn.commit()
                                success = 'عکس پروفایل ذخیره شد.'
                                current_user = get_current_user()
                            else:
                                error = 'ذخیره عکس ناموفق بود.'

                    # --- password ---
                    elif section == 'password':
                        if not can_change_password:
                            error = 'تغییر رمز فقط توسط مدیر / مسئول پذیرش انجام می‌شود.'
                        else:
                            cur = (request.form.get('current_password') or '').strip()
                            new1 = (request.form.get('new_password') or '').strip()
                            new2 = (request.form.get('new_password2') or '').strip()
                            if not cur or not check_password_hash(current_user['password_hash'], cur):
                                error = 'رمز فعلی اشتباه است.'
                            elif len(new1) < 8:
                                error = 'رمز جدید باید حداقل ۸ کاراکتر باشد.'
                            elif new1 != new2:
                                error = 'تکرار رمز جدید مطابقت ندارد.'
                            else:
                                cols = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
                                if 'must_change_password' in cols:
                                    conn.execute(
                                        'UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?',
                                        (generate_password_hash(new1), current_user['id']),
                                    )
                                else:
                                    conn.execute(
                                        'UPDATE users SET password_hash=? WHERE id=?',
                                        (generate_password_hash(new1), current_user['id']),
                                    )
                                conn.commit()
                                session.pop('force_password_change', None)
                                success = 'رمز عبور به‌روز شد.'

                    # --- finance (rep only) ---
                    elif section == 'finance':
                        if not is_rep:
                            error = 'اطلاعات مالی فقط برای نماینده است.'
                        else:
                            import re as _re
                            card = _re.sub(r'\D', '', (request.form.get('bank_card') or ''))
                            sheba = (request.form.get('bank_sheba') or '').strip().upper().replace(' ', '')
                            owner = (request.form.get('bank_owner') or '').strip()
                            if card and len(card) != 16:
                                error = 'شماره کارت باید ۱۶ رقم باشد.'
                            elif sheba and not (sheba.startswith('IR') and len(sheba) == 26 and sheba[2:].isdigit()):
                                error = 'شبا باید با IR و ۲۴ رقم بعد از آن باشد.'
                            else:
                                conn.execute(
                                    'UPDATE users SET bank_card=?, bank_sheba=?, bank_owner=? WHERE id=?',
                                    (card or None, sheba or None, owner or None, current_user['id']),
                                )
                                conn.commit()
                                bank_card, bank_sheba, bank_owner = card, sheba, owner
                                success = 'اطلاعات مالی ذخیره شد.'
        except Exception:
            if not error:
                error = 'خطا در ذخیره.'
        finally:
            try:
                conn.close()
            except Exception:
                pass

        joined_jalali = None
        try:
            _created = current_user['created_at'] if 'created_at' in current_user.keys() else None
            if _created:
                from core.jalali import from_utc_iso
                joined_jalali = from_utc_iso(_created)
        except Exception:
            joined_jalali = None

        return render_template(
            'account.html',
            current_user=current_user,
            from_settings=from_settings,
            can_change_password=can_change_password,
            bank_card=bank_card,
            bank_sheba=bank_sheba,
            bank_owner=bank_owner,
            joined_jalali=joined_jalali,
            error=error,
            success=success,
            csrf_token=_ensure_csrf_token(),
            active_page='account',
        )

    @app.route('/account/profile', methods=['GET', 'POST'])
    @app.route('/account/password', methods=['GET', 'POST'])
    @app.route('/account/finance', methods=['GET', 'POST'])
    def account_legacy_redirect():
        # POST به /account با form_section؛ GET نمایش قالب مربوط
        path = (request.path or '').rstrip('/')
        if request.method == 'POST':
            return redirect('/account')  # forms now post to /account directly
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if path.endswith('/password'):
            return render_template('account_password.html', current_user=current_user, active_page='account', csrf_token=session.get('csrf_token',''))
        if path.endswith('/finance'):
            return render_template('account_finance.html', current_user=current_user, active_page='account', csrf_token=session.get('csrf_token',''))
        return render_template('account_profile.html', current_user=current_user, active_page='account', csrf_token=session.get('csrf_token',''))

    @app.route('/change-password', methods=['GET', 'POST'])
    def change_password():
        return redirect('/account')


    @app.route('/security/backup', methods=['POST'])
    def security_backup():
        current_user = get_current_user()
        if not current_user or current_user['role'] not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم'):
            return redirect('/')
        if not _validate_csrf():
            return 'CSRF', 400
        dest = create_backup('manual')
        return redirect('/settings?backup=' + os.path.basename(dest))





    @app.route('/security/backups/save', methods=['POST'])
    def security_backups_save():
        """ذخیره مسیر بکاپ و در صورت نیاز اجرای بکاپ — یکپارچه."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        try:
            from core.access import is_system_admin as _isa
            role = current_user['role'] if 'role' in current_user.keys() else ''
            if role not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم') and not _isa(current_user):
                return redirect('/')
        except Exception:
            return redirect('/')
        try:
            if not _validate_csrf():
                return redirect('/security/backups')
        except Exception:
            pass
        path = (request.form.get('backup_network_path') or '').strip()
        action = (request.form.get('action') or 'save').strip()
        try:
            max_keep = int(request.form.get('backup_max_keep') or 20)
        except Exception:
            max_keep = 20
        max_keep = max(3, min(100, max_keep))
        try:
            max_days = int(request.form.get('backup_max_days') or 30)
        except Exception:
            max_days = 30
        max_days = max(7, min(365, max_days))
        auto_en = (request.form.get('backup_auto_enabled') or '1').strip()
        if auto_en not in ('0', '1'):
            auto_en = '1'
        conn = get_db()
        try:
            set_setting(conn, 'backup_network_path', path)
            set_setting(conn, 'backup_max_keep', str(max_keep))
            set_setting(conn, 'backup_max_days', str(max_days))
            set_setting(conn, 'backup_auto_enabled', auto_en)
            try:
                write_audit(conn, current_user['full_name'], 'تنظیمات پشتیبان‌گیری', 'settings', None, (path or '')[:80])
            except Exception:
                pass
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        if action == 'backup':
            try:
                dest = create_backup('manual')
                return redirect('/security/backups?backup=1&path_saved=1')
            except Exception:
                return redirect('/security/backups?path_saved=1')
        return redirect('/security/backups?path_saved=1')

    @app.route('/security/backups')
    def security_backups_list():
        current_user = get_current_user()
        if not current_user or current_user['role'] not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم'):
            return redirect('/')
        items = []
        if os.path.isdir(BACKUP_DIR):
            seen = set()
            for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
                path = os.path.join(BACKUP_DIR, name)
                if not name.startswith('backup_'):
                    continue
                if name.endswith('.zip'):
                    try:
                        size = os.path.getsize(path)
                    except Exception:
                        size = 0
                    base = name[:-4]
                    items.append({
                        'name': base, 'zip_name': name, 'size_kb': size // 1024,
                        'has_zip': True, 'has_folder': os.path.isdir(os.path.join(BACKUP_DIR, base)),
                        'mtime': time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(path))),
                    })
                    seen.add(base)
                elif os.path.isdir(path) and name not in seen:
                    size = 0
                    for root, dirs, files in os.walk(path):
                        for f in files:
                            try:
                                size += os.path.getsize(os.path.join(root, f))
                            except Exception:
                                pass
                    items.append({
                        'name': name, 'zip_name': name + '.zip' if os.path.isfile(path + '.zip') else '',
                        'size_kb': size // 1024, 'has_zip': os.path.isfile(path + '.zip'),
                        'has_folder': True,
                        'mtime': time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(path))),
                    })
                    seen.add(name)
        backup_network_path = ''
        backup_max_keep = 20
        backup_max_days = 30
        backup_auto_enabled = True
        try:
            conn = get_db()
            backup_network_path = get_setting(conn, 'backup_network_path', '') or ''
            try:
                backup_max_keep = int(get_setting(conn, 'backup_max_keep', '20') or 20)
            except Exception:
                backup_max_keep = 20
            try:
                backup_max_days = int(get_setting(conn, 'backup_max_days', '30') or 30)
            except Exception:
                backup_max_days = 30
            auto = (get_setting(conn, 'backup_auto_enabled', '1') or '1').strip()
            backup_auto_enabled = auto not in ('0', 'false', 'False', 'no')
            conn.close()
        except Exception:
            pass
        return render_template(
            'security_backups.html',
            backup_network_path=backup_network_path,
            backup_max_keep=backup_max_keep,
            backup_max_days=backup_max_days,
            backup_auto_enabled=backup_auto_enabled,
            items=items,
            csrf_token=_ensure_csrf_token(),
            current_user=current_user,
            active_page='settings',
            path_saved=bool(request.args.get('path_saved')),
        )



    # ---------- بهبودهای عملیاتی / گزارش / جستجو / اعلان ----------


    @app.route('/security/backup/download/<path:name>')
    def security_backup_download(name):
        current_user = get_current_user()
        if not current_user or current_user['role'] not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم'):
            return redirect('/')
        name = os.path.basename(name)
        if not name.startswith('backup_'):
            return 'نامعتبر', 400
        zip_path = os.path.join(BACKUP_DIR, name if name.endswith('.zip') else name + '.zip')
        if not os.path.isfile(zip_path):
            return 'فایل zip یافت نشد', 404
        return send_file(zip_path, as_attachment=True, download_name=os.path.basename(zip_path))




    @app.route('/security/backup/restore', methods=['POST'])
    def security_backup_restore():
        """بازیابی دیتابیس از یک بکاپ (فقط پوشه یا zip). قبل از بازیابی یک بکاپ pre-restore گرفته می‌شود."""
        current_user = get_current_user()
        if not current_user or current_user['role'] not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم'):
            return redirect('/')
        if not _validate_csrf():
            return 'CSRF', 400
        name = os.path.basename((request.form.get('name') or '').strip())
        if not name.startswith('backup_'):
            return 'نامعتبر', 400
        db_path = os.path.join(BASE_DIR, DB_NAME)
        # safety backup
        try:
            create_backup('pre-restore')
        except Exception:
            pass
        src_db = None
        folder = os.path.join(BACKUP_DIR, name.replace('.zip', ''))
        zip_path = os.path.join(BACKUP_DIR, name if name.endswith('.zip') else name + '.zip')
        import tempfile, zipfile as zf
        tmp = None
        try:
            if os.path.isdir(folder) and os.path.isfile(os.path.join(folder, DB_NAME)):
                src_db = os.path.join(folder, DB_NAME)
            elif os.path.isfile(zip_path):
                tmp = tempfile.mkdtemp(prefix='sazgan_restore_')
                with zf.ZipFile(zip_path, 'r') as z:
                    z.extractall(tmp)
                cand = os.path.join(tmp, DB_NAME)
                if os.path.isfile(cand):
                    src_db = cand
            if not src_db:
                return 'دیتابیس در بکاپ نیست', 400
            # replace db
            for suf in ('', '-wal', '-shm'):
                p = db_path + suf
                if os.path.isfile(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
            shutil.copy2(src_db, db_path)
            return redirect('/security/backups?restored=1')
        except Exception as e:
            return 'خطا در بازیابی: %s' % e, 500
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)




    @app.route('/search')
    def global_search():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        from core.constants import TECHNICIAN_ROLES

        q = (request.args.get('q') or '').strip()
        all_types = ['requests', 'devices', 'customers', 'technicians', 'parts']
        selected_types = [t for t in request.args.getlist('type') if t in all_types]
        if not selected_types:
            selected_types = all_types[:]

        time_range = (request.args.get('time_range') or '').strip()
        status_filter = (request.args.get('status') or '').strip()
        category_filter = (request.args.get('category') or '').strip()

        conn = get_db()

        # شمارش کلی هر دسته (برای کارت‌های بالای صفحه — مستقل از عبارت جستجو)
        counts = {
            'requests': conn.execute('SELECT COUNT(*) c FROM requests').fetchone()['c'],
            'devices': conn.execute('SELECT COUNT(*) c FROM warranty_cards').fetchone()['c'],
            'customers': conn.execute('SELECT COUNT(*) c FROM customers').fetchone()['c'],
            # Placeholder count is derived only from the fixed TECHNICIAN_ROLES tuple; role values remain bound parameters.
            'technicians': conn.execute(
                'SELECT COUNT(*) c FROM users WHERE role IN (%s)' % ','.join('?' * len(TECHNICIAN_ROLES)),
                tuple(TECHNICIAN_ROLES)
            ).fetchone()['c'],
            'parts': conn.execute('SELECT COUNT(*) c FROM parts').fetchone()['c'],
        }

        results = []
        if q:
            like = f'%{q}%'

            if 'requests' in selected_types:
                where = ["(customer_name LIKE ? OR serial_number LIKE ? OR CAST(id AS TEXT)=? " \
                         "OR IFNULL(reception_no,'') LIKE ? OR IFNULL(invoice_number,'') LIKE ? " \
                         "OR IFNULL(tracking_number,'') LIKE ? OR problem_desc LIKE ?)"]
                params = [like, like, q, like, like, like, like]
                if status_filter:
                    where.append('status=?'); params.append(status_filter)
                if category_filter:
                    where.append('request_category=?'); params.append(category_filter)
                rows = conn.execute(
                    f'''SELECT id, reception_no, customer_name, serial_number, device_type, status,
                               request_category, service_type, province, reception_date
                        FROM requests WHERE {" AND ".join(where)}
                        ORDER BY id DESC LIMIT 200''',
                    params
                ).fetchall()
                if time_range:
                    days = {'1m': 30, '3m': 90, '6m': 180, '1y': 365}.get(time_range)
                    if days:
                        from core.jalali import to_utc_iso as _to_iso
                        cutoff = (jdatetime.date.today().togregorian() - __import__('datetime').timedelta(days=days)).isoformat()
                        def _keep(r):
                            iso = _to_iso(r['reception_date']) if r['reception_date'] else None
                            return bool(iso and iso >= cutoff)
                        rows = [r for r in rows if _keep(r)]
                rows = rows[:100]
                for r in rows:
                    results.append({
                        'type': 'requests', 'type_label': 'درخواست',
                        'title': f"درخواست تعمیر {r['device_type'] or ''}".strip(),
                        'subtitle': r['reception_no'] or ('#' + str(r['id'])),
                        'meta': [
                            ('مشتری', r['customer_name'] or '—'),
                            ('ثبت شده در', r['reception_date'] or '—'),
                        ],
                        'status': r['status'],
                        'url': _request_detail_url(r),
                    })

            if 'devices' in selected_types:
                rows = conn.execute(
                    '''SELECT id, customer_name, device_type, model, serial_number
                       FROM warranty_cards
                       WHERE serial_number LIKE ? OR customer_name LIKE ? OR model LIKE ? OR device_type LIKE ?
                       ORDER BY id DESC LIMIT 100''',
                    (like, like, like, like)
                ).fetchall()
                for r in rows:
                    results.append({
                        'type': 'devices', 'type_label': 'دستگاه',
                        'title': f"{r['device_type'] or ''} {r['model'] or ''}".strip(),
                        'subtitle': r['serial_number'] or '—',
                        'meta': [('مشتری', r['customer_name'] or '—')],
                        'status': None,
                        'url': f"/settings/warranty/edit/{r['id']}",
                    })

            if 'customers' in selected_types:
                rows = conn.execute(
                    '''SELECT id, name, phone, province, city
                       FROM customers
                       WHERE name LIKE ? OR phone LIKE ? OR IFNULL(national_id,'') LIKE ?
                       ORDER BY id DESC LIMIT 100''',
                    (like, like, like)
                ).fetchall()
                for r in rows:
                    results.append({
                        'type': 'customers', 'type_label': 'مشتری',
                        'title': r['name'],
                        'subtitle': f"کد: {r['id']}",
                        'meta': [
                            ('تلفن', r['phone'] or '—'),
                            ('استان', r['province'] or '—'),
                        ],
                        'status': None,
                        'url': f"/settings/customers/edit/{r['id']}",
                    })

            if 'technicians' in selected_types:
                rows = conn.execute(
                    '''SELECT id, full_name, username, role, province
                       FROM users WHERE role IN (%s)
                       AND (full_name LIKE ? OR username LIKE ?)
                       ORDER BY id DESC LIMIT 100''' % ','.join('?' * len(TECHNICIAN_ROLES)),
                    tuple(TECHNICIAN_ROLES) + (like, like)
                ).fetchall()
                for r in rows:
                    results.append({
                        'type': 'technicians', 'type_label': 'تعمیرکار',
                        'title': r['full_name'],
                        'subtitle': r['username'],
                        'meta': [
                            ('نقش', r['role'] or '—'),
                            ('استان', r['province'] or '—'),
                        ],
                        'status': None,
                        'url': None,
                    })

            if 'parts' in selected_types:
                rows = conn.execute(
                    '''SELECT id, warehouse_code, part_name, device_type, device_model
                       FROM parts
                       WHERE part_name LIKE ? OR IFNULL(warehouse_code,'') LIKE ?
                       ORDER BY id DESC LIMIT 100''',
                    (like, like)
                ).fetchall()
                for r in rows:
                    results.append({
                        'type': 'parts', 'type_label': 'قطعه',
                        'title': r['part_name'],
                        'subtitle': r['warehouse_code'] or '—',
                        'meta': [('دستگاه', f"{r['device_type'] or ''} {r['device_model'] or ''}".strip() or '—')],
                        'status': None,
                        'url': '/settings/parts',
                    })

        # ایندکس پوشه پرونده دستگاه
        try:
            if q:
                from core.device_folders import ensure_device_folder_schema, search_serial as df_search
                ensure_device_folder_schema(conn)
                for fr in df_search(conn, q, limit=10):
                    results.append({
                        'type': 'device_folder',
                        'type_label': 'پوشه دستگاه',
                        'title': fr.get('serial_raw') or fr.get('serial') or q,
                        'subtitle': fr.get('sh_folder') or '',
                        'meta': [('مسیر', fr.get('resolved_path') or fr.get('full_path') or '')],
                        'status': None,
                        'url': None,
                        'folder_path': fr.get('resolved_path') or fr.get('full_path') or '',
                    })
        except Exception as _df_err:
            print('[search] device_folder:', _df_err)

        conn.close()

        pg = paginate(results, page=parse_page(request.args), per_page=parse_per_page(request.args, 5))
        pg_ctx = pagination_context(pg, request.args)

        return render_template(
            'search.html',
            q=q, results=pg['items'], total_results=len(results),
            counts=counts, selected_types=selected_types, all_types=all_types,
            time_range=time_range, status_filter=status_filter, category_filter=category_filter,
            current_user=current_user, active_page='search',
            **pg_ctx,
        )

    @app.route('/search/global')
    def search_global_redirect():
        return redirect('/search?' + request.query_string.decode('utf-8'))





    @app.route('/notifications')
    def notifications_list():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        conn = get_db()
        rows = conn.execute(
            'SELECT * FROM notifications WHERE user_name=? ORDER BY id DESC LIMIT 500',
            (current_user['full_name'],)
        ).fetchall()
        conn.close()
        pg = paginate(rows, page=parse_page(request.args), per_page=parse_per_page(request.args, 25))
        pg_ctx = pagination_context(pg, request.args)
        return render_template(
            'notifications.html',
            rows=pg['items'],
            current_user=current_user,
            active_page='notifications',
            **pg_ctx,
        )




    @app.route('/notifications/read/<int:nid>', methods=['POST'])
    def notification_read(nid):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        row = conn.execute(
            'SELECT request_id, url, title, body FROM notifications WHERE id=? AND user_name=?',
            (nid, current_user['full_name'])
        ).fetchone()
        if not row:
            conn.close()
            return redirect('/notifications')

        conn.execute(
            'UPDATE notifications SET is_read=1 WHERE id=? AND user_name=?',
            (nid, current_user['full_name'])
        )

        # خواندن اعلان فقط اعلان را خوانده‌شده می‌کند؛ وضعیت درخواست تغییر نمی‌کند.
        conn.commit()
        conn.close()
        if row:
            try:
                dest = row['url'] if 'url' in row.keys() else None
            except Exception:
                dest = None
            if dest:
                return redirect(dest)
            if row['request_id']:
                return redirect('/?highlight=%s' % row['request_id'])
        return redirect('/notifications')




    @app.route('/notifications/read-all', methods=['POST'])
    def notifications_read_all():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        conn.execute('UPDATE notifications SET is_read=1 WHERE user_name=?', (current_user['full_name'],))
        conn.commit()
        conn.close()
        return redirect('/notifications')



    @app.route('/health')
    def health():
        try:
            conn = get_db()
            conn.execute('SELECT 1').fetchone()
            conn.close()
            return jsonify({'status': 'ok', 'time': time.strftime('%Y-%m-%d %H:%M:%S')})
        except Exception as e:
            return jsonify({'status': 'error', 'detail': str(e)}), 500




    @app.route('/sw.js')
    def service_worker():
        """Service Worker در ریشه برای scope کامل PWA."""
        from flask import Response
        path = os.path.join(app.root_path, 'static', 'sw.js')
        if os.path.isfile(path):
            resp = send_file(path, mimetype='application/javascript')
        else:
            # fallback inline SW so install does not 500
            body = (
                "self.addEventListener('install',e=>e.waitUntil(self.skipWaiting()));"
                "self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));"
            )
            resp = Response(body, mimetype='application/javascript')
        resp.headers['Service-Worker-Allowed'] = '/'
        resp.headers['Cache-Control'] = 'no-cache'
        return resp




    @app.route('/offline')
    def offline_page():
        return render_template('offline.html')




    @app.route('/manifest.webmanifest')
    def web_manifest_alias():
        return send_file(
            os.path.join(app.root_path, 'static', 'manifest.webmanifest'),
            mimetype='application/manifest+json'
        )

    @app.route('/contacts')
    def contacts_list():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        # مهاجرت ستون‌های مخاطبین
        try:
            cols = {r[1] for r in conn.execute('PRAGMA table_info(contacts)').fetchall()}
            # Fixed schema whitelist; identifiers are not sourced from request data.
            for col, col_type in (
                ('city', 'TEXT'), ('company', 'TEXT'), ('email', 'TEXT'),
                ('website', 'TEXT'), ('address', 'TEXT'), ('status', 'TEXT'),
                ('group_name', 'TEXT'), ('avatar_filename', 'TEXT'),
            ):
                if col not in cols:
                    conn.execute(f'ALTER TABLE contacts ADD COLUMN {col} {col_type}')
            conn.commit()
        except Exception:
            pass

        DEFAULT_STATUS = 'مشتری'
        DEFAULT_GROUP = 'مشتریان'
        rows = []
        try:
            for r in conn.execute(
                """SELECT id, name, mobile, phone, city, company, email, website,
                          address, status, group_name, notes, created_at, 'manual' AS src
                   FROM contacts WHERE COALESCE(is_archived,0)=0
                   ORDER BY name"""
            ).fetchall():
                d = dict(r)
                d['key'] = 'manual-%s' % d['id']
                d['status'] = d.get('status') or DEFAULT_STATUS
                d['group_name'] = d.get('group_name') or DEFAULT_GROUP
                d['source_label'] = 'دستی'
                rows.append(d)
        except Exception:
            pass
        try:
            for r in conn.execute(
                """SELECT id, name,
                          equipment_manager_mobile AS mobile,
                          phone,
                          city,
                          address,
                          equipment_manager_name AS notes
                   FROM customers
                   WHERE COALESCE(is_archived,0)=0
                     AND (
                       (phone IS NOT NULL AND TRIM(phone) != '')
                       OR (equipment_manager_mobile IS NOT NULL AND TRIM(equipment_manager_mobile) != '')
                     )
                   ORDER BY name"""
            ).fetchall():
                d = dict(r)
                d['key'] = 'customer-%s' % d['id']
                d['company'] = d.get('name')
                d['email'] = None
                d['website'] = None
                d['status'] = DEFAULT_STATUS
                d['group_name'] = DEFAULT_GROUP
                d['created_at'] = None
                d['source_label'] = 'طرف‌حساب'
                rows.append(d)
        except Exception:
            pass
        rows.sort(key=lambda x: (x.get('name') or ''))
        conn.close()

        # فیلترها
        q = (request.args.get('q') or '').strip().lower()
        status_f = (request.args.get('status') or '').strip()
        group_f = (request.args.get('group') or '').strip()

        status_options = sorted({r.get('status') for r in rows if r.get('status')})
        group_options = sorted({r.get('group_name') for r in rows if r.get('group_name')})

        def matches(r):
            if status_f and r.get('status') != status_f:
                return False
            if group_f and r.get('group_name') != group_f:
                return False
            if q:
                hay = ' '.join(str(r.get(k) or '') for k in
                                ('name', 'company', 'mobile', 'phone', 'email', 'city', 'notes')).lower()
                if q not in hay:
                    return False
            return True

        filtered = [r for r in rows if matches(r)]

        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        page = parse_page(request.args)
        per_page = parse_per_page(request.args, default=8)
        page_result = paginate(filtered, page=page, per_page=per_page)
        pg_ctx = pagination_context(page_result, request.args, per_page_choices=(8, 25, 50, 100))

        ctx = dict(
            contacts=page_result['items'],
            current_user=current_user,
            active_page='contacts',
            status_options=status_options,
            group_options=group_options,
            filter_q=request.args.get('q') or '',
            filter_status=status_f,
            filter_group=group_f,
        )
        ctx.update(pg_ctx)
        return render_template('contacts.html', **ctx)

    @app.route('/contacts/add', methods=['POST'])
    def contacts_add():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        name = (request.form.get('name') or '').strip()
        mobile = (request.form.get('mobile') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        city = (request.form.get('city') or '').strip()
        company = (request.form.get('company') or '').strip()
        email = (request.form.get('email') or '').strip()
        website = (request.form.get('website') or '').strip()
        address = (request.form.get('address') or '').strip()
        status = (request.form.get('status') or '').strip()
        group_name = (request.form.get('group_name') or '').strip()
        notes = (request.form.get('notes') or '').strip()
        if not name:
            return redirect('/contacts')
        conn = get_db()
        try:
            cols = {r[1] for r in conn.execute('PRAGMA table_info(contacts)').fetchall()}
            for col, col_type in (
                ('city', 'TEXT'), ('company', 'TEXT'), ('email', 'TEXT'),
                ('website', 'TEXT'), ('address', 'TEXT'), ('status', 'TEXT'),
                ('group_name', 'TEXT'), ('avatar_filename', 'TEXT'),
            ):
                if col not in cols:
                    conn.execute(f'ALTER TABLE contacts ADD COLUMN {col} {col_type}')
            import jdatetime
            now = jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')
            conn.execute(
                '''INSERT INTO contacts
                   (name, mobile, phone, city, company, email, website, address, status, group_name, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (name, mobile or None, phone or None, city or None, company or None,
                 email or None, website or None, address or None, status or None,
                 group_name or None, notes or None, now)
            )
            conn.commit()
        except Exception:
            pass
        conn.close()
        return redirect('/contacts')




