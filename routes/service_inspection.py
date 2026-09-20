# -*- coding: utf-8 -*-
"""مسیرهای بازدید: /service/inspection/*."""
# -*- coding: utf-8 -*-
from __future__ import annotations
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
try:
    from core.geo import get_geo_provinces
except Exception:
    get_geo_provinces = None
from core.access import is_system_admin
from core.customer_notify import notify_status_change
from core import helpers as H


from core.helpers import *  # noqa: F401,F403
from core.constants import *  # noqa: F401,F403
from core.company_info import get_company_info as _get_company_info
from core.jalali import add_jalali_months, enrich_warranty_row
from core.workflow import can_view_request, transition_request, WorkflowError, validate_positive_quantity
from routes.service_shared import _quote_files, _save_quote_upload, _internal_repair_visible_panels, _external_repair_visible_panels


def register(app):
    @app.route('/service/inspection/request-new', methods=['GET', 'POST'])
    def inspection_request_new():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')

        conn = get_db()
        if request.method == 'POST':
            customer_id = request.form.get('customer_id') or None
            customer_name = request.form['customer_name'].strip()
            province = request.form.get('province', '')
            county = request.form.get('county', '')
            city = request.form.get('city') or request.form.get('city_manual') or ''
            customer_address = request.form.get('customer_address', '')
            customer_phone = request.form.get('customer_phone', '')
            equipment_manager_name = request.form.get('equipment_manager_name', '')
            equipment_manager_mobile = request.form.get('equipment_manager_mobile', '')
            contact_name = request.form.get('contact_name', '')
            contact_phone = request.form.get('contact_phone', '')
            visit_device_type = request.form.get('visit_device_type', '')
            visit_device_count = request.form.get('visit_device_count') or None
            assigned_technician = request.form.get('assigned_technician') or None
            hospital_request_desc = request.form.get('hospital_request_desc', '')
            is_paid_visit = 1 if request.form.get('is_paid_visit') == '1' else 0
            problem_desc = hospital_request_desc or 'درخواست بازدید'
            reception_date = _jalali_from_form('recep')
            # رایگان: مستقیم در انتظار انجام بازدید؛ غیررایگان: منتظر پیش‌فاکتور
            initial_status = (
                'در انتظار ارسال پیش‌فاکتور است' if is_paid_visit else 'در انتظار انجام بازدید'
            )
            if is_paid_visit:
                initial_status = 'در انتظار ارسال پیش‌فاکتور است'
            else:
                initial_status = 'در انتظار انجام بازدید'

            cur = conn.execute(
                '''INSERT INTO requests
                   (customer_name, customer_address, customer_phone, device_type, serial_number,
                    problem_desc, service_type, province, county, assigned_technician,
                    reception_date, request_category, status,
                    customer_id, city, equipment_manager_name, equipment_manager_mobile,
                    contact_name, contact_phone, hospital_request_desc,
                    is_paid_visit, visit_device_type, visit_device_count, request_subtype)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (customer_name, customer_address, customer_phone, visit_device_type or 'بازدید', None,
                 problem_desc, 'در محل', province, county, assigned_technician,
                 reception_date, 'بررسی و بازدید', initial_status,
                 customer_id, city, equipment_manager_name, equipment_manager_mobile,
                 contact_name, contact_phone, hospital_request_desc,
                 is_paid_visit, visit_device_type, visit_device_count, 'درخواست بازدید')
            )
            new_id = cur.lastrowid
            # باگ واقعی که با acceptance test فاز ۰ پیدا شد: assigned_technician بالا فقط در
            # ستون متنی ذخیره می‌شد و assigned_technician_id هیچ‌وقت sync نمی‌شد — یعنی
            # تکنسینی که همون لحظه‌ی ثبت درخواست تخصیص داده می‌شد، تا وقتی کسی از صفحه‌ی
            # پرونده دوباره ذخیره‌ش نمی‌کرد، هیچ‌وقت is_assigned_tech نمی‌شد و نمی‌تونست
            # روی پرونده‌ی خودش کاری انجام بده.
            if assigned_technician:
                try:
                    sync_request_technician(conn, new_id, assigned_technician, expected_role='تکنسین استانی', province=province)
                except Exception:
                    pass
            try:
                from core.reception_numbers import assign_reception_no
                assign_reception_no(conn, new_id)
                try:
                    from core.customer_notify import notify_request_received
                    notify_request_received(conn, new_id)
                except Exception:
                    pass
                try:
                    from core.history import stamp_create
                    stamp_create(conn, new_id, current_user.get('full_name') if current_user else None)
                except Exception:
                    pass
            except Exception:
                pass
            if reception_date:
                _set_stage_date(conn, new_id, 'درخواست ثبت شد', reception_date, 'ثبت درخواست بازدید')
                _set_stage_date(conn, new_id, initial_status, reception_date, None)
            conn.commit()
            conn.close()
            return redirect(f'/service/inspection/view/{new_id}')

        customers = conn.execute('SELECT id, name, province, city FROM customers ORDER BY name').fetchall()
        technicians = conn.execute(
            "SELECT id, full_name, province FROM users WHERE role = 'تکنسین استانی' ORDER BY full_name"
        ).fetchall()
        device_types = conn.execute('SELECT DISTINCT device_type FROM devices ORDER BY device_type').fetchall()
        conn.close()
        today = jdatetime.date.today()
        return render_template(
            'inspection_request_new.html',
            back=request.args.get('back'),
            customers=customers, technicians=technicians, device_types=device_types,
            provinces=(get_geo_provinces(conn) if get_geo_provinces else PROVINCES), statuses=VISIT_STATUSES,
            active_page='service-inspection-request-new',
            current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day
        , embed=_is_embed()
        )





    @app.route('/service/inspection/report-new', methods=['GET', 'POST'])
    def inspection_report_new():
        """ثبت گزارش بازدید (رایگان یا پس از انجام)."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')

        conn = get_db()
        if request.method == 'POST':
            customer_id = request.form.get('customer_id') or None
            customer_name = request.form['customer_name'].strip()
            province = request.form.get('province', '')
            county = request.form.get('county', '')
            city = request.form.get('city') or request.form.get('city_manual') or ''
            customer_address = request.form.get('customer_address', '')
            customer_phone = request.form.get('customer_phone', '')
            equipment_manager_name = request.form.get('equipment_manager_name', '')
            equipment_manager_mobile = request.form.get('equipment_manager_mobile', '')
            contact_name = request.form.get('contact_name', '')
            contact_phone = request.form.get('contact_phone', '')
            assigned_technician = request.form.get('assigned_technician') or None
            reception_date = _jalali_from_form('recep')
            problem_desc = 'گزارش بازدید'

            cur = conn.execute(
                '''INSERT INTO requests
                   (customer_name, customer_address, customer_phone, device_type, serial_number,
                    problem_desc, service_type, province, county, assigned_technician,
                    reception_date, request_category, status,
                    customer_id, city, equipment_manager_name, equipment_manager_mobile,
                    contact_name, contact_phone, is_paid_visit, request_subtype)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (customer_name, customer_address, customer_phone, 'بازدید', None,
                 problem_desc, 'در محل', province, county, assigned_technician,
                 reception_date, 'بررسی و بازدید', 'بازدید انجام شد',
                 customer_id, city, equipment_manager_name, equipment_manager_mobile,
                 contact_name, contact_phone, 0, 'گزارش بازدید')
            )
            new_id = cur.lastrowid
            try:
                from core.reception_numbers import assign_reception_no
                assign_reception_no(conn, new_id)
                try:
                    from core.customer_notify import notify_request_received
                    notify_request_received(conn, new_id)
                except Exception:
                    pass
                try:
                    from core.history import stamp_create
                    stamp_create(conn, new_id, current_user.get('full_name') if current_user else None)
                except Exception:
                    pass
            except Exception:
                pass
            if reception_date:
                _set_stage_date(conn, new_id, 'بازدید انجام شد', reception_date, 'ثبت گزارش')

            serials = request.form.getlist('visit_serial')
            descs = request.form.getlist('visit_desc')
            for i, serial in enumerate(serials):
                serial = (serial or '').strip()
                if not serial:
                    continue
                desc = descs[i] if i < len(descs) else ''
                conn.execute(
                    'INSERT INTO visit_serials (request_id, serial_number, visit_desc) VALUES (?, ?, ?)',
                    (new_id, serial, desc)
                )

            report_file = request.files.get('report_file')
            if report_file and report_file.filename:
                ext = report_file.filename.rsplit('.', 1)[-1].lower() if '.' in report_file.filename else ''
                if ext in ALLOWED_REPORT_EXTENSIONS:
                    filename = secure_filename(f"visit_report_{new_id}.{ext}")
                    save_uploaded_image(report_file, os.path.join(VISITS_FOLDER, filename))
                    conn.execute('UPDATE requests SET report_filename = ? WHERE id = ?', (filename, new_id))

            conn.commit()
            conn.close()
            return redirect(f'/service/inspection/view/{new_id}')

        customers = conn.execute('SELECT id, name, province, city FROM customers ORDER BY name').fetchall()
        technicians = conn.execute(
            "SELECT id, full_name, province FROM users WHERE role = 'تکنسین استانی' ORDER BY full_name"
        ).fetchall()
        conn.close()
        today = jdatetime.date.today()
        return render_template(
            'inspection_report_new.html',
            back=request.args.get('back'),
            customers=customers, technicians=technicians, provinces=(get_geo_provinces(conn) if get_geo_provinces else PROVINCES),
            active_page='service-inspection-report-new',
            current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day
        , embed=_is_embed()
        )





    @app.route('/service/inspection/list')
    def inspection_list():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM requests WHERE request_category = 'بررسی و بازدید' ORDER BY id DESC"
        ).fetchall()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        province = request.args.get('province', '').strip()
        status = request.args.get('status', '').strip()
        only_delayed = request.args.get('only_delayed') == '1'
        tab = request.args.get('tab', 'requests').strip() or 'requests'
        enriched = _enrich_delay(conn, rows)
        conn.close()
        enriched = _filter_by_date_range(enriched, date_from or None, date_to or None)
        enriched = _filter_rows(enriched, province=province or None, status=status or None, only_delayed=only_delayed)
        open_rows, closed_rows = _split_open_closed(enriched)
        # reports: open cases that are in report-related statuses
        report_statuses = {'در انتظار گزارش بازدید', 'بازدید انجام شد'}
        report_rows = [r for r in enriched if (r.get('status') or '') in report_statuses or (r.get('status') or '') == 'در انتظار انجام بازدید']
        if tab == 'reports':
            shown = list(open_rows)  # open visits for report workflow
            list_title = 'بررسی و بازدید انجام‌شده'
        else:
            shown = open_rows
            list_title = 'درخواست بررسی و بازدید'
            tab = 'requests'
        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        pg = paginate(shown, page=parse_page(request.args), per_page=parse_per_page(request.args, 25))
        pg_ctx = pagination_context(pg, request.args)
        section_tabs = [
            {'href': '/service/inspection/list?tab=requests', 'label': 'درخواست بررسی و بازدید', 'icon': '📝', 'active': tab == 'requests'},
            {'href': '/service/inspection/list?tab=reports', 'label': 'بررسی و بازدید انجام‌شده', 'icon': '📄', 'active': tab == 'reports'},
        ]
        fctx = _form_lookup_context()
        return render_template(
            'inspection_list.html', requests=pg['items'], statuses=VISIT_STATUSES,
            active_page='service-inspection-list', current_user=current_user,
            date_from=date_from, date_to=date_to, province=province, status=status,
            only_delayed=only_delayed, provinces=PROVINCES, delay_threshold=DELAY_THRESHOLD_DAYS,
            section_tabs=section_tabs, tab=tab, list_title=list_title,
            technicians=fctx['technicians_prov'],
            customers=fctx['customers'],
            device_types=fctx['device_types'],
            jalali_months=fctx['jalali_months'],
            today_year=fctx['today_year'], today_month=fctx['today_month'], today_day=fctx['today_day'],
            **pg_ctx,
        )





    @app.route('/service/inspection/view/<int:req_id>', methods=['GET', 'POST'])
    def inspection_view(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')

        conn = get_db()
        req = conn.execute(
            "SELECT * FROM requests WHERE id = ? AND request_category = 'بررسی و بازدید'",
            (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return redirect('/service/inspection/list')
        if not can_view_request(current_user, req):
            conn.close()
            return redirect('/cartable')

        can_edit = current_user['role'] in RECEPTION_ROLES
        is_finance = current_user['role'] == FINANCE_ROLE
        finance_statuses = _finance_allowed_statuses_for(req)
        is_assigned_tech = (
            current_user['role'] == 'تکنسین استانی'
            and bool(req['assigned_technician_id'])
            and int(req['assigned_technician_id']) == int(current_user['id'])
        )

        if request.method == 'POST' and (can_edit or is_assigned_tech or is_finance):
            action = request.form.get('action', 'save')

            if is_finance and not can_edit:
                if action == 'change_status':
                    new_status = (request.form.get('status') or '').strip()
                    if new_status not in finance_statuses:
                        conn.close()
                        return redirect(f'/service/inspection/view/{req_id}?err=finance_status_not_allowed')
                    try:
                        transition_request(
                            conn, req_id, new_status,
                            actor_name=current_user.get('full_name'),
                            expected_status=req['status'],
                            note='تغییر وضعیت توسط امور مالی از مسیر رسمی گردش‌کار',
                        )
                    except WorkflowError:
                        conn.close()
                        return redirect(f'/service/inspection/view/{req_id}?err=invalid_status_transition')
                    try:
                        from core.customer_notify import notify_status_change
                        notify_status_change(conn, req_id, new_status)
                    except Exception:
                        pass

                    try:
                        from core.wages import try_auto_wage_on_status
                        try_auto_wage_on_status(conn, req_id, new_status)
                    except Exception:
                        pass

                    _set_stage_date(conn, req_id, new_status, None, 'تغییر وضعیت توسط امور مالی')
                    conn.commit()
                elif action in ('save_fields', 'finance_save', 'save'):
                    updates, values = [], []
                    if 'proforma_confirmed' in request.form:
                        updates.append('proforma_confirmed = ?')
                        values.append(1 if request.form.get('proforma_confirmed') == '1' else 0)
                    if 'invoice_number' in request.form:
                        new_inv = (request.form.get('invoice_number') or '').strip()
                        # شماره فاکتور فقط یک‌بار: اگر قبلاً ثبت شده، تغییر داده نشود
                        try:
                            cur_inv = (req['invoice_number'] if hasattr(req, 'keys') else (req.get('invoice_number') if isinstance(req, dict) else None)) or ''
                        except Exception:
                            cur_inv = ''
                        if cur_inv and new_inv and new_inv != cur_inv:
                            pass  # نادیده — مقدار قبلی حفظ می‌شود
                        elif cur_inv and not new_inv:
                            pass  # خالی کردن مجاز نیست پس از ثبت
                        else:
                            try:
                                from core.history import invoice_is_duplicate
                                if new_inv and invoice_is_duplicate(conn, new_inv, exclude_request_id=req_id):
                                    # فاکتور تکراری در پرونده دیگر
                                    pass
                                else:
                                    updates.append('invoice_number = ?')
                                    values.append(new_inv)
                                    if new_inv and not cur_inv:
                                        try:
                                            write_audit(conn, current_user.get('full_name'), 'صدور فاکتور', 'request', req_id, new_inv)
                                        except Exception:
                                            pass
                            except Exception:
                                updates.append('invoice_number = ?')
                                values.append(new_inv)
                    if updates:
                        values.append(req_id)
                        conn.execute('UPDATE requests SET ' + ', '.join(updates) + ' WHERE id = ?', values)
                        conn.commit()
                conn.close()
                return redirect('/service/inspection/view/' + str(req_id))

            if action == 'save_fields' and can_edit:
                fields = [
                    'hospital_request_desc', 'technician_desc', 'actions_taken',
                    'tracking_number', 'invoice_number',
                    'city', 'customer_address', 'equipment_manager_name',
                    'equipment_manager_mobile', 'contact_name', 'contact_phone',
                    'visit_device_type',
                ]
                updates, values = [], []
                for f in fields:
                    if f in request.form:
                        updates.append(f'{f} = ?')
                        values.append(request.form.get(f) or None)
                if 'visit_device_count' in request.form:
                    updates.append('visit_device_count = ?')
                    values.append(request.form.get('visit_device_count') or None)
                if 'is_paid_visit' in request.form:
                    updates.append('is_paid_visit = ?')
                    values.append(1 if request.form.get('is_paid_visit') == '1' else 0)
                if 'proforma_confirmed' in request.form:
                    updates.append('proforma_confirmed = ?')
                    values.append(1 if request.form.get('proforma_confirmed') == '1' else 0)
                if updates:
                    values.append(req_id)
                    conn.execute(f"UPDATE requests SET {', '.join(updates)} WHERE id = ?", values)
                    if 'assigned_technician' in request.form:
                        try:
                            sync_request_technician(conn, req_id, request.form.get('assigned_technician'), expected_role='تکنسین استانی', province=req['province'])
                        except Exception:
                            pass
                    # خودکارسازی: تایید پیش‌فاکتور توسط پذیرش یعنی می‌توان بازدید را برنامه‌ریزی کرد
                    if 'proforma_confirmed' in request.form and request.form.get('proforma_confirmed') == '1':
                        if (req['status'] or '') == 'در انتظار دریافت تاییدیه پیش‌فاکتور است':
                            transition_request(
                                conn, req_id, 'در انتظار انجام بازدید',
                                actor_name=current_user.get('full_name'),
                                expected_status=req['status'],
                                note='تایید پیش‌فاکتور — پیشرفت خودکار وضعیت',
                            )
                            today_j = jdatetime.date.today()
                            sd = f"{today_j.year}/{str(today_j.month).zfill(2)}/{str(today_j.day).zfill(2)}"
                            _set_stage_date(conn, req_id, 'در انتظار انجام بازدید', sd, 'تایید پیش‌فاکتور — پیشرفت خودکار وضعیت')
                            try:
                                from core.customer_notify import notify_status_change
                                notify_status_change(conn, req_id, 'در انتظار انجام بازدید')
                            except Exception:
                                pass
                        elif (req['status'] or '') == 'در انتظار ارسال پیش‌فاکتور است':
                            raise WorkflowError('تایید پیش‌فاکتور قبل از ارسال پیش‌فاکتور مجاز نیست.')

            elif action == 'change_status' and can_edit:
                new_status = request.form.get('new_status')
                stage_date = request.form.get('stage_date') or _jalali_from_form('stage')
                stage_notes = request.form.get('stage_notes', '')
                if new_status and new_status in VISIT_STATUSES:
                    transition_request(
                        conn, req_id, new_status,
                        actor_name=current_user.get('full_name'),
                        expected_status=req['status'],
                        note=stage_notes or 'تغییر وضعیت بازدید از مسیر رسمی گردش‌کار',
                    )
                    try:
                        from core.customer_notify import notify_status_change
                        notify_status_change(conn, req_id, new_status)
                    except Exception:
                        pass

                    try:
                        from core.wages import try_auto_wage_on_status
                        try_auto_wage_on_status(conn, req_id, new_status)
                    except Exception:
                        pass

                    if stage_date:
                        _set_stage_date(conn, req_id, new_status, stage_date, stage_notes or None)

            elif action == 'add_serial' and (can_edit or is_assigned_tech):
                serial = (request.form.get('visit_serial') or '').strip()
                desc = request.form.get('visit_desc', '')
                if serial:
                    conn.execute(
                        'INSERT INTO visit_serials (request_id, serial_number, visit_desc) VALUES (?, ?, ?)',
                        (req_id, serial, desc)
                    )

            elif action == 'delete_serial' and can_edit:
                sid = request.form.get('serial_row_id')
                if sid:
                    conn.execute('DELETE FROM visit_serials WHERE id = ? AND request_id = ?', (sid, req_id))

            elif action == 'upload_report' and (can_edit or is_assigned_tech):
                report_file = request.files.get('report_file')
                report_uploaded_now = False
                if report_file and report_file.filename:
                    ext = report_file.filename.rsplit('.', 1)[-1].lower() if '.' in report_file.filename else ''
                    if ext in ALLOWED_REPORT_EXTENSIONS:
                        filename = secure_filename(f"visit_report_{req_id}.{ext}")
                        save_uploaded_image(report_file, os.path.join(VISITS_FOLDER, filename))
                        conn.execute('UPDATE requests SET report_filename = ? WHERE id = ?', (filename, req_id))
                        report_uploaded_now = True
                tech_desc = request.form.get('technician_desc', '')
                if tech_desc:
                    conn.execute('UPDATE requests SET technician_desc = ? WHERE id = ?', (tech_desc, req_id))
                # خودکارسازی: اگر خودِ نماینده/تکنسین گزارش را آپلود کرد ولی هنوز «اتمام» را
                # تیک نزده، پرونده به «در انتظار گزارش بازدید» می‌رود (نه فقط برای can_edit).
                if report_uploaded_now and request.form.get('mark_done') != '1' and (req['status'] or '') == 'در انتظار انجام بازدید':
                    transition_request(
                        conn, req_id, 'در انتظار گزارش بازدید',
                        actor_name=current_user.get('full_name'),
                        expected_status=req['status'],
                        note='گزارش آپلود شد',
                    )
                    _set_stage_date(conn, req_id, 'در انتظار گزارش بازدید', None, 'گزارش آپلود شد')
                # این بند دیگر به can_edit محدود نیست — خودِ تکنسین/نماینده‌ی تخصیص‌یافته هم
                # می‌تواند مرحله‌ی خودش را ببندد (هم‌راستا با الگوی صحیحی که در نصب هست).
                if request.form.get('mark_done') == '1':
                    transition_request(
                        conn, req_id, 'بازدید انجام شد',
                        actor_name=current_user.get('full_name'),
                        expected_status=req['status'],
                        note='گزارش ثبت شد',
                    )
                    try:
                        from core.customer_notify import notify_status_change
                        notify_status_change(conn, req_id, 'بازدید انجام شد')
                    except Exception:
                        pass

                    try:
                        from core.wages import try_auto_wage_on_status
                        try_auto_wage_on_status(conn, req_id, 'بازدید انجام شد')
                    except Exception:
                        pass

                    today_j = jdatetime.date.today()
                    sd = f"{today_j.year}/{str(today_j.month).zfill(2)}/{str(today_j.day).zfill(2)}"
                    _set_stage_date(conn, req_id, 'بازدید انجام شد', sd, 'گزارش ثبت شد')

            conn.commit()
            conn.close()
            return redirect(f'/service/inspection/view/{req_id}')

        stage_dates = conn.execute(
            'SELECT * FROM request_stage_dates WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        stage_map = {s['stage_name']: s for s in stage_dates}
        visit_serials = conn.execute(
            'SELECT * FROM visit_serials WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        technicians = conn.execute(
            "SELECT id, full_name, province FROM users WHERE role = 'تکنسین استانی' ORDER BY full_name"
        ).fetchall()
        attachments = _load_attachments(conn, req_id)
        conn.close()
        today = jdatetime.date.today()
        return render_template(
            'inspection_view.html',
            req=req, statuses=VISIT_STATUSES, stage_map=stage_map,
            visit_serials=visit_serials, technicians=technicians,
            attachments=attachments,
            active_page='service-inspection-list',
            current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day,
            can_edit=can_edit, is_assigned_tech=is_assigned_tech,
            is_finance=is_finance, finance_statuses=list(finance_statuses)
        )





    @app.route('/service/inspection/print/<int:req_id>')
    def inspection_print(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        company = _get_company_info(conn)
        req = conn.execute(
            "SELECT * FROM requests WHERE id = ? AND request_category = 'بررسی و بازدید'",
            (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return redirect('/service/inspection/list')
        stage_dates = conn.execute(
            'SELECT * FROM request_stage_dates WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        visit_serials = conn.execute(
            'SELECT * FROM visit_serials WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        attachments = _load_attachments(conn, req_id)
        conn.close()
        return render_template(
            'inspection_print.html',
            req=req, stage_dates=stage_dates, visit_serials=visit_serials,
            statuses=VISIT_STATUSES, current_user=current_user, company=company
        )


    # ---------- پیوست‌های پرونده ----------


    @app.route('/service/inspection/export')
    def inspection_export():
        current_user = get_current_user()
        if not current_user or current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM requests WHERE request_category = 'بررسی و بازدید' ORDER BY id"
        ).fetchall()
        conn.close()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'بازدیدها'
        ws.append(['کد', 'تاریخ', 'مشتری', 'نوع بازدید', 'نوع دستگاه', 'تعداد', 'استان', 'تکنسین', 'وضعیت'])
        for r in rows:
            ws.append([
                r['id'], r['reception_date'], r['customer_name'],
                'غیررایگان' if r['is_paid_visit'] else 'رایگان',
                r['visit_device_type'] or r['device_type'], r['visit_device_count'],
                r['province'], r['assigned_technician'], r['status'],
            ])
        out = BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(out, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, 
download_name='inspections.xlsx')

    # ---------- پیش‌نمایش پرونده از کارتابل ----------
