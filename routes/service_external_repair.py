# -*- coding: utf-8 -*-
"""مسیرهای تعمیر بیرون‌شهری: /service/external-repair/*."""
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
    @app.route('/service/external-repair/view/<int:req_id>', methods=['GET', 'POST'])
    def external_repair_view(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')

        conn = get_db()
        req = conn.execute(
            "SELECT * FROM requests WHERE id = ? AND service_type = 'در محل' AND request_category = 'تعمیر'",
            (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return redirect('/')
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
            and ((not req['province']) or (not current_user.get('province')) or req['province'] == current_user.get('province'))
        )
        # پرونده در مرحله پایانی/بسته: نماینده/تکنسین دیگر اجازه ویرایش گزارش ندارد —
        # فقط نقش‌های پذیرش/مدیر (can_edit) و امور مالی (همیشه) می‌توانند بعد از این مرحله اقدام کنند.
        is_closed_for_ops = (req['status'] or '') in CLOSED_STATUSES

        if request.method == 'POST' and (can_edit or is_assigned_tech or is_finance):
            action = request.form.get('action', 'save')

            # پرونده بسته/پایان‌یافته: گزارش نماینده/تکنسین دیگر برای این نقش قابل ویرایش نیست
            if is_closed_for_ops and not can_edit and action == 'tech_report':
                conn.close()
                return redirect(f'/service/external-repair/view/{req_id}?err=stage_locked')

            if is_finance and not can_edit:
                note = request.form.get('finance_note', '').strip()
                if action == 'proforma_decision':
                    _apply_proforma_decision(
                        conn, req_id, request.form.get('decision', ''),
                        current_user.get('full_name'), note
                    )
                    conn.commit()
                elif action == 'change_status':
                    new_status = request.form.get('status', '')
                    if new_status in finance_statuses:
                        try:
                            transition_request(conn, req_id, new_status, actor_name=current_user.get('full_name'), note='تغییر وضعیت توسط امور مالی')
                        except WorkflowError:
                            conn.close()
                            return redirect(f'/service/external-repair/view/{req_id}?err=invalid_status_transition')
                        notify_status_change(conn, req_id, new_status)
                        try_auto_wage_on_status(conn, req_id, new_status)
                        _set_stage_date(conn, req_id, new_status, None, 'تغییر وضعیت توسط امور مالی')
                        conn.commit()
                elif action in ('save_fields', 'finance_save', 'save'):
                    updates, values = [], []
                    proforma_complete = bool((request.form.get('proforma_number') or '').strip() and (request.form.get('proforma_sent_date') or '').strip())
                    if proforma_complete:
                        if (req['status'] or '') != 'در انتظار ارسال پیش‌فاکتور است':
                            conn.close()
                            return redirect(f'/service/external-repair/view/{req_id}?err=proforma_not_allowed')
                        transition_request(conn, req_id, 'در انتظار دریافت تاییدیه پیش‌فاکتور است', actor_name=current_user.get('full_name'), expected_status='در انتظار ارسال پیش‌فاکتور است', note='ثبت پیش‌فاکتور')
                        try:
                            from core.case_management import add_timeline
                            add_timeline(conn, req_id, 'ثبت پیش‌فاکتور', 'شماره و تاریخ صدور پیش‌فاکتور ثبت شد؛ پرونده در انتظار تاییدیه پیش‌فاکتور است.', 'status', 'staff', current_user.get('full_name'))
                        except Exception:
                            pass
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
                        # پس از ثبت شماره فاکتور
                        # ثبت شماره فاکتور به‌تنهایی هرگز وضعیت پرونده را تغییر نمی‌دهد؛
                        # پایان پرونده فقط از Action رسمی issue_external_invoice انجام می‌شود.
                    if updates:
                        values.append(req_id)
                        conn.execute('UPDATE requests SET ' + ', '.join(updates) + ' WHERE id = ?', values)
                    if 'invoice_number' in request.form and (request.form.get('invoice_number') or '').strip():
                        new_inv = (request.form.get('invoice_number') or '').strip()
                        try:
                            from core.history import invoice_is_duplicate
                            if invoice_is_duplicate(conn, new_inv, exclude_request_id=req_id):
                                conn.close()
                                return redirect(f'/service/external-repair/view/{req_id}?err=invoice_duplicate')
                        except Exception:
                            conn.close()
                            return redirect(f'/service/external-repair/view/{req_id}?err=invoice_validation_failed')
                        if (req['status'] or '') != 'در انتظار ثبت شماره فاکتور است':
                            conn.close()
                            return redirect(f'/service/external-repair/view/{req_id}?err=invoice_action_not_allowed')
                        conn.execute('UPDATE requests SET invoice_number=? WHERE id=?', (new_inv, req_id))
                        try:
                            transition_request(conn, req_id, 'پایان تعمیرات', actor_name=current_user.get('full_name'), expected_status='در انتظار ثبت شماره فاکتور است', note='ثبت فاکتور نهایی تعمیر خارجی')
                        except WorkflowError:
                            conn.rollback(); conn.close()
                            return redirect(f'/service/external-repair/view/{req_id}?err=invalid_status_transition')
                        write_audit(conn, current_user.get('full_name'), 'صدور فاکتور نهایی', 'request', req_id, new_inv)
                    conn.commit()
                conn.close()
                return redirect('/service/external-repair/view/' + str(req_id))

            # مراحل قدیمی تأیید دریافت/ثبت اعلام خرابی حذف شدند؛ وضعیت فقط با اقدام واقعی تغییر می‌کند.
            elif action == 'save_fields' and can_edit:
                fields = [
                    'hospital_request_desc', 'technician_desc', 'actions_taken',
                    'tracking_number', 'shipping_method', 'invoice_number', 'carrier_name', 'carrier_delivery_date', 'device_model',
                    'warranty_end_date', 'installation_date', 'city', 'customer_address',
                    'equipment_manager_name', 'equipment_manager_mobile', 'contact_name', 'contact_phone',
                ]
                updates, values = [], []
                for f in fields:
                    if f in request.form:
                        updates.append(f'{f} = ?')
                        values.append(request.form.get(f) or None)
                if 'assigned_technician' in request.form:
                    try:
                        sync_request_technician(conn, req_id, request.form.get('assigned_technician'), expected_role='تکنسین استانی', province=req['province'])
                    except Exception:
                        conn.rollback(); conn.close()
                        return redirect('/service/external-repair/view/' + str(req_id) + '?err=technician_invalid')
                if updates:
                    values.append(req_id)
                    conn.execute(f"UPDATE requests SET {', '.join(updates)} WHERE id = ?", values)

            elif action == 'tech_report' and (can_edit or is_assigned_tech):
                technician_desc = request.form.get('technician_desc', '')
                actions_taken = request.form.get('actions_taken', '')
                conn.execute(
                    'UPDATE requests SET technician_desc = ?, actions_taken = ? WHERE id = ?',
                    (technician_desc, actions_taken, req_id)
                )
                report_file = request.files.get('report_file')
                if report_file and report_file.filename:
                    ext = report_file.filename.rsplit('.', 1)[-1].lower() if '.' in report_file.filename else ''
                    if ext in ALLOWED_REPORT_EXTENSIONS:
                        filename = secure_filename(f"ext_report_{req_id}.{ext}")
                        save_uploaded_image(report_file, os.path.join(REPORTS_FOLDER, filename))
                        conn.execute('UPDATE requests SET report_filename = ? WHERE id = ?', (filename, req_id))
                # اگر تکنسین گزارش داد، وضعیت را به مرحله گزارش ببر (اختیاری توسط پذیرش)
                if request.form.get('mark_report_done') == '1':
                    if (req['status'] or '') != 'ماموریت در جریان (کارتابل نماینده)':
                        conn.close()
                        return redirect(f'/service/external-repair/view/{req_id}?err=report_transition_not_allowed')
                    status = 'در انتظار بررسی گزارش توسط پذیرش است'
                    transition_request(conn, req_id, status, actor_name=current_user.get('full_name'), note='گزارش نماینده ثبت شد')
                    try:
                        from core.customer_notify import notify_status_change
                        notify_status_change(conn, req_id, status)
                    except Exception:
                        pass
                    try:
                        from core.wages import try_auto_wage_on_status
                        try_auto_wage_on_status(conn, req_id, status)
                    except Exception:
                        pass

                    today_j = jdatetime.date.today()
                    stage_date = f"{today_j.year}/{str(today_j.month).zfill(2)}/{str(today_j.day).zfill(2)}"
                    _set_stage_date(conn, req_id, status, stage_date, 'گزارش نماینده ثبت شد — منتظر بررسی پذیرش')

            elif action == 'proforma_decision' and can_edit:
                note = request.form.get('finance_note', '').strip()
                _apply_proforma_decision(
                    conn, req_id, request.form.get('decision', ''),
                    current_user.get('full_name'), note
                )

            elif action == 'change_status' and can_edit:
                new_status = request.form.get('new_status') or request.form.get('status')
                stage_date = request.form.get('stage_date') or _jalali_from_form('stage')
                stage_notes = request.form.get('stage_notes', '')
                allowed = set(EXTERNAL_REPAIR_STATUSES)
                if new_status and new_status in allowed:
                    try:
                        transition_request(conn, req_id, new_status, actor_name=current_user.get('full_name'), note=stage_notes or None)
                    except WorkflowError:
                        conn.close()
                        return redirect(f'/service/external-repair/view/{req_id}?err=invalid_status_transition')
                    try:
                        notify_status_change(conn, req_id, new_status)
                    except Exception:
                        pass
                    try:
                        try_auto_wage_on_status(conn, req_id, new_status)
                    except Exception:
                        pass
                    if stage_date:
                        _set_stage_date(conn, req_id, new_status, stage_date, stage_notes or None)
                    if new_status == 'در انتظار دریافت قطعه در انبار استان است':
                        _record_external_parts_to_province(conn, req_id, current_user.get('full_name'))

            elif action == 'add_part' and can_edit:
                part_id = request.form.get('part_id') or None
                part_name = request.form.get('part_name', '')
                warehouse_code = request.form.get('warehouse_code', '')
                try:
                    quantity = validate_positive_quantity(request.form.get('quantity') or 1)
                except WorkflowError:
                    conn.close()
                    return redirect('/service/external-repair/view/' + str(req_id) + '?err=invalid_quantity')
                stage = request.form.get('part_stage', '')
                notes = request.form.get('part_notes', '')
                serial_healthy = (request.form.get('serial_healthy') or '').strip()
                if part_id:
                    p = conn.execute('SELECT * FROM parts WHERE id = ?', (part_id,)).fetchone()
                    if p:
                        part_name = p['part_name']
                        warehouse_code = p['warehouse_code'] or ''
                if part_name:
                    ok, info, loc, prov = _issue_part_from_stock(
                        conn, int(part_id) if part_id else None, quantity, 'در محل', req['province']
                    )
                    if not ok:
                        conn.close()
                        from urllib.parse import quote
                        return redirect(f'/service/external-repair/view/{req_id}?stock_error=' + quote(str(info)))
                    conn.execute(
                        'INSERT INTO request_parts (request_id, part_id, part_name, warehouse_code, quantity, stage, notes, stock_applied, stock_location, stock_province, serial_healthy) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (req_id, part_id, part_name, warehouse_code, quantity, stage, notes, 1 if part_id else 0, loc, prov, serial_healthy or None)
                    )
                    # خودکارسازی وضعیت: ثبت قطعه با نوع «حواله انبار» یعنی حواله واقعاً صادر شده —
                    # پس پرونده مستقیم به «در انتظار دریافت قطعه در انبار استان» می‌رود.
                    if stage == 'حواله' and (req['status'] or '') == 'در انتظار ارسال حواله است':
                        next_st = 'در انتظار دریافت قطعه در انبار استان است'
                        transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status=req['status'], note='صدور حواله انبار — پیشرفت خودکار وضعیت')
                        today_j = jdatetime.date.today()
                        stage_date = f"{today_j.year}/{str(today_j.month).zfill(2)}/{str(today_j.day).zfill(2)}"
                        _set_stage_date(conn, req_id, next_st, stage_date, 'صدور حواله انبار — پیشرفت خودکار وضعیت')
                        try:
                            from core.customer_notify import notify_status_change
                            notify_status_change(conn, req_id, next_st)
                        except Exception:
                            pass
                    # خودکارسازی وضعیت: ثبت سریال قطعه‌ی دریافت‌شده یعنی قطعه واقعاً به انبار
                    # استان رسیده — طبق تصمیم کاربر، مراحل «ارسال باربری»/«دریافت توسط نماینده»
                    # فعلاً رد می‌شوند (ثبت بارنامه/تاریخ ارسال اختیاری و جدا از این جریان می‌ماند)
                    # و پرونده مستقیم به ماموریت نماینده می‌رود.
                    elif stage == 'دریافت انبار' and serial_healthy and (req['status'] or '') == 'در انتظار دریافت قطعه در انبار استان است':
                        next_st = 'ماموریت در جریان (کارتابل نماینده)'
                        transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status=req['status'], note='ثبت سریال قطعه در انبار — ارجاع خودکار به ماموریت نماینده')
                        today_j = jdatetime.date.today()
                        stage_date = f"{today_j.year}/{str(today_j.month).zfill(2)}/{str(today_j.day).zfill(2)}"
                        _set_stage_date(conn, req_id, next_st, stage_date, 'ثبت سریال قطعه در انبار — ارجاع خودکار به ماموریت نماینده')
                        try:
                            from core.customer_notify import notify_status_change
                            notify_status_change(conn, req_id, next_st)
                        except Exception:
                            pass

            elif action == 'send_to_finance' and can_edit:
                part_count = conn.execute('SELECT COUNT(*) AS c FROM request_parts WHERE request_id=? AND IFNULL(is_void,0)=0', (req_id,)).fetchone()['c']
                if part_count < 1:
                    conn.close()
                    return redirect(f'/service/external-repair/view/{req_id}?err=no_parts')
                new_status = 'در انتظار ارسال پیش‌فاکتور است'
                transition_request(conn, req_id, new_status, actor_name=current_user.get('full_name'), expected_status=req['status'], note='ارجاع به امور مالی')
                try:
                    from core.case_management import add_timeline
                    add_timeline(conn, req_id, 'ارجاع به امور مالی', 'قطعات موردنیاز ثبت شد و پرونده برای صدور پیش‌فاکتور به امور مالی ارجاع شد.', 'status', 'staff', current_user.get('full_name'))
                except Exception:
                    pass
                try:
                    from core.customer_notify import notify_status_change
                    notify_status_change(conn, req_id, new_status)
                except Exception:
                    pass

            elif action == 'delete_part' and can_edit:
                part_row_id = request.form.get('part_row_id')
                if part_row_id:
                    prow = conn.execute(
                        'SELECT * FROM request_parts WHERE id = ? AND request_id = ?',
                        (part_row_id, req_id)
                    ).fetchone()
                    if prow:
                        _restore_part_to_stock(conn, prow)
                    conn.execute(
                        'UPDATE request_parts SET is_void=1 WHERE id = ? AND request_id = ? AND IFNULL(is_void,0)=0',
                        (part_row_id, req_id)
                    )
                    write_audit(conn, current_user.get('full_name'), 'حذف نرم قطعه', 'request', req_id, str(part_row_id))

            conn.commit()
            conn.close()
            return redirect(f'/service/external-repair/view/{req_id}')

        stage_dates = conn.execute(
            'SELECT * FROM request_stage_dates WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        stage_map = {s['stage_name']: s for s in stage_dates}
        req_parts = conn.execute(
            'SELECT * FROM request_parts WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        lookup = H._form_lookup_context(conn)
        parts_catalog = lookup['parts_catalog']
        technicians = lookup['technicians_prov']
        attachments = _load_attachments(conn, req_id)
        recent_requests = []
        try:
            if req['customer_name']:
                recent_requests = conn.execute(
                    "SELECT id, status, service_type, reception_date FROM requests WHERE customer_name = ? AND id != ? ORDER BY id DESC LIMIT 8",
                    (req['customer_name'], req_id)
                ).fetchall()
        except Exception:
            pass
        tech_user = None
        try:
            if req['assigned_technician']:
                tech_user = conn.execute(
                    "SELECT full_name, province FROM users WHERE full_name = ? OR id = ? LIMIT 1",
                    (req['assigned_technician'], req['assigned_technician'] if str(req['assigned_technician']).isdigit() else -1)
                ).fetchone()
        except Exception:
            pass
        device_photo = None
        try:
            dt = req['device_type'] if 'device_type' in req.keys() else None
            dm = req['device_model'] if 'device_model' in req.keys() else None
            if dt and dm:
                drow = conn.execute('SELECT photo_filename FROM devices WHERE device_type=? AND model=? LIMIT 1', (dt, dm)).fetchone()
            elif dt:
                drow = conn.execute('SELECT photo_filename FROM devices WHERE device_type=? LIMIT 1', (dt,)).fetchone()
            else:
                drow = None
            if drow and drow['photo_filename']:
                device_photo = drow['photo_filename']
        except Exception:
            device_photo = None
        today = jdatetime.date.today()
        case_history = []
        try:
            from core.history import get_case_history
            case_history = get_case_history(conn, req_id)
        except Exception:
            pass
        quote_files = _quote_files(conn, req_id)
        conn.close()
        return render_template(
            'external_repair_view.html',
            case_history=case_history,
            req=req, statuses=EXTERNAL_REPAIR_STATUSES, stage_map=stage_map,
            req_parts=req_parts, parts_catalog=parts_catalog, technicians=technicians,
            attachments=attachments,
            quote_files=quote_files,
            recent_requests=recent_requests,
            tech_user=tech_user,
            device_photo=device_photo,
            active_page='service-external-repair-archive',
            current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day,
            can_edit=can_edit, is_assigned_tech=is_assigned_tech,
            is_finance=is_finance, finance_statuses=list(finance_statuses),
            is_closed_for_ops=is_closed_for_ops,
            visible_panels=_external_repair_visible_panels(can_edit, is_assigned_tech, is_finance, is_system_admin(current_user))
        )





    @app.route('/service/external-repair/print/<int:req_id>')
    def external_repair_print(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        company = _get_company_info(conn)
        req = conn.execute(
            "SELECT * FROM requests WHERE id = ? AND service_type = 'در محل' AND request_category = 'تعمیر'",
            (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return redirect('/service/external-repair/archive')
        if not can_view_request(current_user, req):
            conn.close()
            return redirect('/cartable')
        stage_dates = conn.execute(
            'SELECT * FROM request_stage_dates WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        req_parts = conn.execute(
            'SELECT * FROM request_parts WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        conn.close()
        return render_template(
            'external_repair_print.html',
            req=req, stage_dates=stage_dates, req_parts=req_parts, statuses=EXTERNAL_REPAIR_STATUSES,
            current_user=current_user, company=company
        )


    # ---------- نصب و آموزش ----------



    @app.route('/service/external-repair/export')
    def external_repair_export():
        current_user = get_current_user()
        if not current_user or current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM requests WHERE request_category = 'تعمیر' AND service_type = 'در محل' ORDER BY id"
        ).fetchall()
        conn.close()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'تعمیرات خارجی'
        ws.append(['کد', 'تاریخ پذیرش', 'مشتری', 'سریال', 'نوع دستگاه', 'استان', 'تکنسین', 'وضعیت', 'فاکتور', 'پیگیری'])
        for r in rows:
            ws.append([
                r['id'], r['reception_date'], r['customer_name'], r['serial_number'],
                r['device_type'], r['province'], r['assigned_technician'], r['status'],
                r['invoice_number'], r['tracking_number'],
            ])
        out = BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(out, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name='external_repairs.xlsx')





