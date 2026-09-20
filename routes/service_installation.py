# -*- coding: utf-8 -*-
"""مسیرهای نصب و آموزش: /service/installation/*."""
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
    @app.route('/service/installation/request-new', methods=['GET', 'POST'])
    def installation_request_new():
        """ثبت درخواست نصب."""
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
            install_notes = request.form.get('install_notes', '')
            device_models_text = (request.form.get('device_models_text') or '').strip()
            # چند مدل بدون الزام سریال — ذخیره در یادداشت و ستون مدل
            models_line = ' | '.join([ln.strip() for ln in device_models_text.splitlines() if ln.strip()])
            problem_desc = install_notes or 'درخواست نصب و آموزش'
            if models_line:
                problem_desc = (problem_desc + ' | مدل‌ها: ' + models_line).strip(' |')
            reception_date = _jalali_from_form('recep')

            cur = conn.execute(
                '''INSERT INTO requests
                   (customer_name, customer_address, customer_phone, device_type, serial_number,
                    problem_desc, service_type, province, county, assigned_technician,
                    reception_date, request_category, status,
                    customer_id, city, equipment_manager_name, equipment_manager_mobile,
                    contact_name, contact_phone, install_notes, request_subtype, device_model)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (customer_name, customer_address, customer_phone, 'نصب و آموزش', None,
                 problem_desc, 'در محل', province, county, assigned_technician,
                 reception_date, 'نصب و آموزش', INSTALLATION_REQUEST_STATUSES[0],
                 customer_id, city, equipment_manager_name, equipment_manager_mobile,
                 contact_name, contact_phone, install_notes, 'درخواست نصب', models_line or None)
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
                _set_stage_date(conn, new_id, INSTALLATION_REQUEST_STATUSES[0], reception_date, 'ثبت درخواست')
            conn.commit()
            conn.close()
            return redirect(f'/service/installation/request-view/{new_id}')

        customers = conn.execute('SELECT id, name, province, city FROM customers ORDER BY name').fetchall()
        technicians = conn.execute(
            "SELECT id, full_name, province FROM users WHERE role = 'تکنسین استانی' ORDER BY full_name"
        ).fetchall()
        conn.close()
        today = jdatetime.date.today()
        return render_template(
            'installation_request_new.html',
            back=request.args.get('back'),
            customers=customers, technicians=technicians, provinces=(get_geo_provinces(conn) if get_geo_provinces else PROVINCES),
            statuses=INSTALLATION_REQUEST_STATUSES,
            active_page='service-installation-request-new',
            current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day
        , embed=_is_embed()
        )





    @app.route('/service/installation/register-new', methods=['GET', 'POST'])
    def installation_register_new():
        """ثبت نصب دستگاه؛ فعال‌سازی گارانتی و بستن درخواست نصب مبدأ."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        conn = get_db(); error = None
        if request.method == 'POST':
            customer_id = request.form.get('customer_id') or None
            customer_name = request.form['customer_name'].strip()
            province = request.form.get('province', ''); county = request.form.get('county', '')
            city = request.form.get('city') or request.form.get('city_manual') or ''
            customer_address = request.form.get('customer_address', ''); customer_phone = request.form.get('customer_phone', '')
            equipment_manager_name = request.form.get('equipment_manager_name', ''); equipment_manager_mobile = request.form.get('equipment_manager_mobile', '')
            contact_name = request.form.get('contact_name', ''); contact_phone = request.form.get('contact_phone', '')
            serial_number = request.form.get('serial_number', '').strip(); install_unit = request.form.get('install_unit', '')
            install_notes = request.form.get('install_notes', ''); assigned_technician = request.form.get('assigned_technician') or None
            source_request_id_raw = request.form.get('source_request_id') or ''; reception_date = _jalali_from_form('recep')
            card = conn.execute('SELECT * FROM warranty_cards WHERE serial_number = ?', (serial_number,)).fetchone() if serial_number else None
            report_file_check = request.files.get('report_file'); source_request = None
            if source_request_id_raw:
                try: source_request_id = int(source_request_id_raw)
                except (TypeError, ValueError): source_request_id = None
                if source_request_id:
                    source_request = conn.execute("SELECT * FROM requests WHERE id=? AND request_subtype='درخواست نصب' AND request_category='نصب و آموزش' AND status != 'بسته شد'", (source_request_id,)).fetchone()
                    if source_request and serial_number and source_request['serial_number'] and str(source_request['serial_number']).strip() != serial_number:
                        source_request = None; error = 'درخواست نصب انتخاب‌شده با سریال این دستگاه مطابقت ندارد.'
            else:
                clauses = ["request_category='نصب و آموزش'", "request_subtype='درخواست نصب'", "status != 'بسته شد'", 'serial_number=?']; params=[serial_number]
                if customer_id: clauses.append('customer_id=?'); params.append(customer_id)
                elif customer_name: clauses.append('customer_name=?'); params.append(customer_name)
                candidates = conn.execute('SELECT * FROM requests WHERE '+' AND '.join(clauses)+' ORDER BY id DESC', tuple(params)).fetchall() if serial_number else []
                if len(candidates) == 1: source_request = candidates[0]
            if not serial_number or not card:
                error = 'سریال باید قبلاً در کارت‌های گارانتی ثبت (فعال) شده باشد.'
            elif card['installation_date']:
                error = 'این سریال قبلاً نصب ثبت شده است.'
            else:
                card_state = enrich_warranty_row(card)
                if card_state.get('warranty_status') == 'ابطال': error = 'این کارت گارانتی ابطال شده است و امکان ثبت نصب ندارد.'
                elif card_state.get('warranty_status') != 'تولید شده': error = f"وضعیت کارت گارانتی «{card_state.get('warranty_status') or 'نامشخص'}» است و امکان ثبت نصب ندارد."
            if not error and (not report_file_check or not report_file_check.filename): error = 'آپلود عکس/فایل گزارش نصب الزامی است.'
            if not error and not reception_date: error = 'تاریخ ثبت نصب معتبر نیست.'
            if not error and card and card['warranty_months'] is None: error = 'ماه گارانتی این کارت مشخص نشده است و امکان محاسبه پایان گارانتی وجود ندارد.'
            if not error:
                device_type = card['device_type'] or '—'; installation_date = reception_date
                warranty_end_date = add_jalali_months(reception_date, card['warranty_months'])
                problem_desc = install_notes or f'ثبت نصب — {install_unit}'
                try:
                    cur = conn.execute("""INSERT INTO requests
                       (customer_name,customer_address,customer_phone,device_type,serial_number,installation_date,problem_desc,service_type,province,county,assigned_technician,reception_date,request_category,status,customer_id,city,equipment_manager_name,equipment_manager_mobile,contact_name,contact_phone,install_unit,install_notes,request_subtype,source_request_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (customer_name,customer_address,customer_phone,device_type,serial_number,installation_date,problem_desc,'در محل',province,county,assigned_technician,reception_date,'نصب و آموزش','نصب انجام شد',customer_id,city,equipment_manager_name,equipment_manager_mobile,contact_name,contact_phone,install_unit,install_notes,'ثبت نصب',source_request['id'] if source_request else None))
                    new_id=cur.lastrowid
                    conn.execute("UPDATE warranty_cards SET installation_date=?, warranty_end_date=?, warranty_status='فعال' WHERE id=? AND installation_date IS NULL", (installation_date,warranty_end_date,card['id']))
                    if conn.execute('SELECT changes()').fetchone()[0] != 1: raise RuntimeError('کارت گارانتی همزمان تغییر کرده یا قبلاً نصب شده است.')
                    try:
                        from core.reception_numbers import assign_reception_no; assign_reception_no(conn,new_id)
                        try:
                            from core.customer_notify import notify_request_received; notify_request_received(conn,new_id)
                        except Exception: pass
                        try:
                            from core.history import stamp_create; stamp_create(conn,new_id,current_user.get('full_name') if current_user else None)
                        except Exception: pass
                    except Exception: pass
                    if reception_date: _set_stage_date(conn,new_id,'نصب انجام شد',reception_date,'ثبت نصب دستگاه')
                    if source_request:
                        source_status = (source_request['status'] or '')
                        # ثبت «نصب انجام شد» یعنی درخواست مبدأ واقعاً انجام شده است؛
                        # مسیر رسمی Workflow را از هر مرحله بازِ نصب عبور می‌دهیم و سپس می‌بندیم.
                        if source_status == 'درخواست ثبت شد':
                            transition_request(conn, source_request['id'], 'در انتظار انجام نصب', actor_name=current_user.get('full_name'), expected_status=source_status, note=f'ثبت نصب #{new_id} — پیشرفت خودکار')
                            source_status = 'در انتظار انجام نصب'
                        if source_status == 'در انتظار انجام نصب':
                            transition_request(conn, source_request['id'], 'نصب انجام شد', actor_name=current_user.get('full_name'), expected_status=source_status, note=f'ثبت نصب #{new_id}')
                            source_status = 'نصب انجام شد'
                        if source_status == 'نصب انجام شد':
                            transition_request(conn, source_request['id'], 'بسته شد', actor_name=current_user.get('full_name'), expected_status=source_status, note=f'با ثبت نصب #{new_id} بسته شد.')
                    report_file=request.files.get('report_file')
                    if report_file and report_file.filename:
                        ext=report_file.filename.rsplit('.',1)[-1].lower() if '.' in report_file.filename else ''
                        if ext in ALLOWED_REPORT_EXTENSIONS:
                            os.makedirs(REPORTS_FOLDER,exist_ok=True); filename=secure_filename(f'install_reg_{new_id}.{ext}')
                            save_uploaded_image(report_file,os.path.join(REPORTS_FOLDER,filename)); conn.execute('UPDATE requests SET report_filename=? WHERE id=?',(filename,new_id))
                    conn.commit()
                except Exception as exc:
                    conn.rollback(); error='ثبت نصب انجام نشد. اطلاعات گارانتی و درخواست مبدأ تغییر نکرد.'
                    try: current_app.logger.exception('installation_register_new failed: %s',exc)
                    except Exception: pass
                else:
                    if request.form.get('next_serial')=='1':
                        conn.close(); from urllib.parse import urlencode
                        q=urlencode({'customer_id':customer_id or '','customer_name':customer_name or '','province':province or '','city':city or '','customer_address':customer_address or '','customer_phone':customer_phone or '','equipment_manager_name':equipment_manager_name or '','equipment_manager_mobile':equipment_manager_mobile or '','contact_name':contact_name or '','contact_phone':contact_phone or '','assigned_technician':assigned_technician or '','saved':str(new_id)})
                        return redirect(f'/service/installation/register-new?{q}')
                    conn.close(); return redirect(f'/service/installation/register-view/{new_id}')
        customers=conn.execute('SELECT id,name,province,city FROM customers ORDER BY name').fetchall()
        technicians=conn.execute("SELECT id,full_name,province FROM users WHERE role='تکنسین استانی' ORDER BY full_name").fetchall()
        open_install_requests=conn.execute("SELECT id,customer_name,serial_number,status,reception_date FROM requests WHERE request_category='نصب و آموزش' AND request_subtype='درخواست نصب' AND status != 'بسته شد' ORDER BY id DESC").fetchall()
        provinces=get_geo_provinces(conn) if get_geo_provinces else PROVINCES; conn.close(); today=jdatetime.date.today()
        prefill={k:(request.args.get(k) or '') for k in ('customer_id','customer_name','province','city','customer_address','customer_phone','equipment_manager_name','equipment_manager_mobile','contact_name','contact_phone','assigned_technician','saved')}
        return render_template('installation_register_new.html',back=request.args.get('back'),customers=customers,technicians=technicians,provinces=provinces,open_install_requests=open_install_requests,error=error,prefill=prefill,active_page='service-installation-register-new',current_user=current_user,jalali_months=JALALI_MONTHS,today_year=today.year,today_month=today.month,today_day=today.day,embed=_is_embed())




    @app.route('/service/installation/requests')
    def installation_requests_list():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        conn = get_db()
        rows = conn.execute(
            """SELECT * FROM requests
               WHERE request_category = 'نصب و آموزش' AND request_subtype = 'درخواست نصب'
               ORDER BY id DESC"""
        ).fetchall()
        enriched = _enrich_delay(conn, rows)
        conn.close()
        open_rows, closed_rows = _split_open_closed(enriched)
        # بایگانی دیگه اینجا نشون داده نمی‌شه؛ پرونده‌های بسته از منوی «بایگانی» / گزارش عملکرد خدمات قابل مشاهده‌ست
        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        pg = paginate(open_rows, page=parse_page(request.args), per_page=parse_per_page(request.args, 25))
        shown = pg['items']
        pg_ctx = pagination_context(pg, request.args)
        section_tabs = [
            {'href': '/service/installation/requests', 'label': 'درخواست نصب‌ها', 'icon': '📝', 'active': True},
            {'href': '/service/installation/registers', 'label': 'ثبت نصب دستگاه‌ها', 'icon': '🔧', 'active': False},
        ]
        fctx = _form_lookup_context()
        return render_template(
            'installation_requests_list.html',
            requests=shown, statuses=INSTALLATION_REQUEST_STATUSES,
            active_page='service-installation-requests',
            current_user=current_user, section_tabs=section_tabs,
            list_title='درخواست‌های نصب',
            technicians=fctx['technicians_prov'],
            customers=fctx['customers'],
            device_types=fctx['device_types'],
            jalali_months=fctx['jalali_months'],
            today_year=fctx['today_year'], today_month=fctx['today_month'], today_day=fctx['today_day'],
            provinces=fctx['provinces'],
            **pg_ctx,
        )





    @app.route('/service/installation/registers')
    def installation_registers_list():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        conn = get_db()
        rows = conn.execute(
            """SELECT * FROM requests
               WHERE request_category = 'نصب و آموزش' AND request_subtype = 'ثبت نصب'
               ORDER BY id DESC"""
        ).fetchall()
        conn.close()
        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        pg = paginate(rows, page=parse_page(request.args), per_page=parse_per_page(request.args, 25))
        pg_ctx = pagination_context(pg, request.args)
        section_tabs = [
            {'href': '/service/installation/requests', 'label': 'درخواست نصب‌ها', 'icon': '📝', 'active': False},
            {'href': '/service/installation/registers', 'label': 'ثبت نصب دستگاه‌ها', 'icon': '🔧', 'active': True},
        ]
        return render_template(
            'installation_registers_list.html',
            requests=pg['items'],
            active_page='service-installation-registers',
            current_user=current_user, section_tabs=section_tabs,
            list_title='نصب انجام‌شده',
            **pg_ctx,
        )





    @app.route('/service/installation/request-view/<int:req_id>', methods=['GET', 'POST'])
    def installation_request_view(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        req = conn.execute(
            """SELECT * FROM requests WHERE id = ? AND request_subtype = 'درخواست نصب'""",
            (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return redirect('/service/installation/requests')
        if not can_view_request(current_user, req):
            conn.close()
            return redirect('/cartable')

        can_edit = current_user['role'] in RECEPTION_ROLES
        # مالک پرونده فقط از assigned_technician_id تعیین می‌شود؛
        # نام نمایشی/رشته‌ی آزاد دیگر مبنای مجوز نیست.
        is_assigned_tech = False
        try:
            uid = current_user.get('id') if isinstance(current_user, dict) else current_user['id']
            role = current_user.get('role') if isinstance(current_user, dict) else current_user['role']
            assigned_id = req['assigned_technician_id'] if 'assigned_technician_id' in req.keys() else None
            is_assigned_tech = (
                role in ('تکنسین استانی', 'تکنسین کارخانه')
                and bool(assigned_id)
                and int(assigned_id) == int(uid)
            )
        except (TypeError, ValueError, KeyError):
            is_assigned_tech = False

        if request.method == 'POST' and (can_edit or is_assigned_tech):
            action = request.form.get('action', 'save')
            if action == 'save_fields' and can_edit:
                fields = [
                    'city', 'customer_address', 'equipment_manager_name', 'equipment_manager_mobile',
                    'contact_name', 'contact_phone', 'install_notes',
                ]
                updates, values = [], []
                for f in fields:
                    if f in request.form:
                        updates.append(f'{f} = ?')
                        values.append(request.form.get(f) or None)
                if updates:
                    values.append(req_id)
                    conn.execute(f"UPDATE requests SET {', '.join(updates)} WHERE id = ?", values)
                # باگ واقعی که با acceptance test فاز ۰ پیدا شد: این بلوک قبلاً *داخل*
                # «if updates:» بالا بود — یعنی وقتی فقط assigned_technician فرستاده می‌شد
                # (بدون هیچ فیلد دیگری از لیست fields)، updates خالی می‌موند و کل این بخش
                # (هم sync_request_technician هم خودکارسازی ادغام هماهنگی+انجام) اصلاً
                # اجرا نمی‌شد — یعنی تخصیص تکنسین به‌تنهایی همیشه بی‌اثر بود.
                if 'assigned_technician' in request.form:
                    sync_request_technician(
                        conn, req_id, request.form.get('assigned_technician'),
                        expected_role='تکنسین استانی', province=req['province']
                    )
                    # خودکارسازی: طبق تصمیم کاربر، «هماهنگی» و «انجام نصب» یک مرحله شدن —
                    # همان لحظه‌ی تخصیص تکنسین مستقیم به «در انتظار انجام نصب» می‌رود.
                    if (request.form.get('assigned_technician') or '').strip() and (req['status'] or '') == INSTALLATION_REQUEST_STATUSES[0]:
                        transition_request(
                            conn, req_id, 'در انتظار انجام نصب',
                            actor_name=current_user.get('full_name'),
                            expected_status=INSTALLATION_REQUEST_STATUSES[0],
                            note='تخصیص تکنسین — پیشرفت خودکار وضعیت (هماهنگی+انجام ادغام شد)',
                        )
                        _set_stage_date(conn, req_id, 'در انتظار انجام نصب', None, 'تخصیص تکنسین — پیشرفت خودکار وضعیت (هماهنگی+انجام ادغام شد)')
                        try:
                            from core.customer_notify import notify_status_change
                            notify_status_change(conn, req_id, 'در انتظار انجام نصب')
                        except Exception:
                            pass
            elif action == 'change_status' and can_edit:
                new_status = request.form.get('new_status')
                stage_date = request.form.get('stage_date') or _jalali_from_form('stage')
                stage_notes = request.form.get('stage_notes', '')
                if new_status and new_status in INSTALLATION_REQUEST_STATUSES:
                    transition_request(
                        conn, req_id, new_status,
                        actor_name=current_user.get('full_name'),
                        expected_status=req['status'],
                        note=stage_notes or 'تغییر وضعیت نصب از مسیر رسمی گردش‌کار',
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
            elif action == 'upload_report' and (can_edit or is_assigned_tech):
                # آپلود گزارش نصب توسط نماینده/پذیرش
                report_file = request.files.get('report_file')
                notes = (request.form.get('install_notes') or '').strip()
                if notes:
                    conn.execute('UPDATE requests SET install_notes = ? WHERE id = ?', (notes, req_id))
                if report_file and report_file.filename:
                    ext = report_file.filename.rsplit('.', 1)[-1].lower() if '.' in report_file.filename else ''
                    if ext in ALLOWED_REPORT_EXTENSIONS:
                        os.makedirs(REPORTS_FOLDER, exist_ok=True)
                        filename = secure_filename(f"install_req_{req_id}.{ext}")
                        save_uploaded_image(report_file, os.path.join(REPORTS_FOLDER, filename))
                        conn.execute('UPDATE requests SET report_filename = ? WHERE id = ?', (filename, req_id))
                # اختیاری: علامت انجام نصب
                if request.form.get('mark_done') == '1':
                    st = 'نصب انجام شد'
                    transition_request(
                        conn, req_id, st,
                        actor_name=current_user.get('full_name'),
                        expected_status=req['status'],
                        note='گزارش نصب توسط نماینده',
                    )
                    try:
                        from core.customer_notify import notify_status_change
                        notify_status_change(conn, req_id, st)
                    except Exception:
                        pass
                    today_j = jdatetime.date.today()
                    stage_date = f"{today_j.year}/{str(today_j.month).zfill(2)}/{str(today_j.day).zfill(2)}"
                    _set_stage_date(conn, req_id, st, stage_date, 'گزارش نصب توسط نماینده')
            conn.commit()
            conn.close()
            return redirect(f'/service/installation/request-view/{req_id}')

        stage_dates = conn.execute(
            'SELECT * FROM request_stage_dates WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        stage_map = {s['stage_name']: s for s in stage_dates}
        technicians = conn.execute(
            "SELECT id, full_name, province FROM users WHERE role = 'تکنسین استانی' ORDER BY full_name"
        ).fetchall()
        # پرونده‌های ثبت نصب مرتبط (بر اساس مشتری)
        related_registers = []
        try:
            related_registers = conn.execute(
                """SELECT id, reception_no, serial_number, status, reception_date, report_filename
                   FROM requests
                   WHERE request_category = 'نصب و آموزش' AND request_subtype = 'ثبت نصب'
                     AND customer_name = ?
                   ORDER BY id DESC LIMIT 20""",
                (req['customer_name'],)
            ).fetchall()
        except Exception:
            related_registers = []
        conn.close()
        today = jdatetime.date.today()
        return render_template(
            'installation_request_view.html',
            req=req, statuses=INSTALLATION_REQUEST_STATUSES, stage_map=stage_map,
            technicians=technicians,
            related_registers=related_registers,
            active_page='service-installation-requests',
            current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day,
            can_edit=can_edit,
            is_assigned_tech=is_assigned_tech,
        )





    @app.route('/service/installation/register-view/<int:req_id>', methods=['GET', 'POST'])
    def installation_register_view(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        can_edit = current_user['role'] in RECEPTION_ROLES
        conn = get_db()
        req = conn.execute(
            """SELECT * FROM requests WHERE id = ? AND request_subtype = 'ثبت نصب'""",
            (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return redirect('/service/installation/registers')
        if not can_view_request(current_user, req):
            conn.close()
            return redirect('/cartable')

        if request.method == 'POST' and can_edit:
            action = request.form.get('action', 'save_fields')
            if action == 'save_fields':
                fields = [
                    'city', 'customer_address', 'equipment_manager_name',
                    'equipment_manager_mobile', 'contact_name', 'contact_phone',
                    'install_unit', 'install_notes', 'assigned_technician',
                ]
                updates, values = [], []
                for f in fields:
                    if f in request.form:
                        updates.append(f'{f} = ?')
                        values.append(request.form.get(f) or None)
                if updates:
                    values.append(req_id)
                    conn.execute(f"UPDATE requests SET {', '.join(updates)} WHERE id = ?", values)
                    if 'assigned_technician' in request.form:
                        sync_request_technician(
                            conn, req_id, request.form.get('assigned_technician'),
                            expected_role='تکنسین استانی', province=req['province']
                        )
                conn.commit()
            conn.close()
            if request.path.startswith('/api/native/'):
                return jsonify({'ok': True})
            return redirect(f'/service/installation/register-view/{req_id}')

        conn.close()
        return render_template(
            'installation_register_view.html',
            req=req,
            active_page='service-installation-registers',
            current_user=current_user,
            can_edit=can_edit
        )





    @app.route('/service/installation/request-print/<int:req_id>')
    def installation_request_print(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        company = _get_company_info(conn)
        req = conn.execute(
            """SELECT * FROM requests WHERE id = ? AND request_subtype = 'درخواست نصب'""",
            (req_id,)
        ).fetchone()
        stage_dates = []
        if req:
            stage_dates = conn.execute(
                'SELECT * FROM request_stage_dates WHERE request_id = ? ORDER BY id', (req_id,)
            ).fetchall()
        conn.close()
        if not req:
            return redirect('/service/installation/requests')
        return render_template(
            'installation_request_print.html',
            req=req, stage_dates=stage_dates, statuses=INSTALLATION_REQUEST_STATUSES,
            current_user=current_user, company=company
        )





    @app.route('/service/installation/register-print/<int:req_id>')
    def installation_register_print(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        company = _get_company_info(conn)
        req = conn.execute(
            """SELECT * FROM requests WHERE id = ? AND request_subtype = 'ثبت نصب'""",
            (req_id,)
        ).fetchone()
        conn.close()
        if not req:
            return redirect('/service/installation/registers')
        return render_template(
            'installation_register_print.html',
            req=req, current_user=current_user, company=company
        )



    # ---------- بررسی و بازدید ----------



    @app.route('/service/installation/export')
    def installation_export():
        current_user = get_current_user()
        if not current_user or current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM requests WHERE request_category = 'نصب و آموزش' ORDER BY id"
        ).fetchall()
        conn.close()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'نصب و آموزش'
        ws.append(['کد', 'زیرنوع', 'تاریخ', 'مشتری', 'سریال', 'نوع دستگاه', 'بخش', 'استان', 'تکنسین', 'وضعیت'])
        for r in rows:
            ws.append([
                r['id'], r['request_subtype'], r['reception_date'], r['customer_name'],
                r['serial_number'], r['device_type'], r['install_unit'], r['province'],
                r['assigned_technician'], r['status'],
            ])
        out = BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(out, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name='installations.xlsx')




