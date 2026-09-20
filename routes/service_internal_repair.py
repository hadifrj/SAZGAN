# -*- coding: utf-8 -*-
"""مسیرهای تعمیر داخلی: /service/internal-repair/*."""
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
    @app.route('/service/internal-repair/view/<int:req_id>', methods=['GET', 'POST'])
    def internal_repair_view(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')

        conn = get_db()
        req = conn.execute(
            "SELECT * FROM requests WHERE id = ? AND service_type = 'کارخانه' AND request_category = 'تعمیر'",
            (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return redirect('/')
        if req['is_deleted'] and not is_system_admin(current_user):
            conn.close()
            return redirect('/')
        if not can_view_request(current_user, req):
            conn.close()
            return redirect('/cartable')

        can_edit = current_user['role'] in RECEPTION_ROLES
        is_finance = current_user['role'] == FINANCE_ROLE
        is_qc = current_user['role'] == 'کنترل کیفیت'
        is_assigned_tech = (
            current_user['role'] == 'تکنسین کارخانه'
            and bool(req['assigned_technician_id'])
            and int(req['assigned_technician_id']) == int(current_user['id'])
        )
        finance_statuses = _finance_allowed_statuses_for(req)
        # پرونده در مرحله پایانی/بسته: تکنسین و QC دیگر اجازه ویرایش گزارش ندارند —
        # فقط نقش‌های پذیرش/مدیر (can_edit) و امور مالی (همیشه) می‌توانند بعد از این مرحله اقدام کنند.
        is_closed_for_ops = (req['status'] or '') in CLOSED_STATUSES

        if request.method == 'POST' and (can_edit or is_assigned_tech or is_qc or is_finance):
            action = request.form.get('action', 'save')

            # پرونده بسته/پایان‌یافته: گزارش QC و تکنسین دیگر برای این نقش‌ها قابل ویرایش نیست
            if is_closed_for_ops and not can_edit and action in ('qc_report', 'tech_report'):
                conn.close()
                return redirect(f'/service/internal-repair/view/{req_id}?err=stage_locked')

            # امور مالی: فقط پیش‌فاکتور، تاییدیه، شماره فاکتور و وضعیت‌های مجاز
            if is_finance and not can_edit:
                note = request.form.get('finance_note', '').strip()
                if action == 'proforma_decision':
                    if (req['status'] or '') != 'در انتظار دریافت تاییدیه پیش‌فاکتور است':
                        conn.close()
                        return redirect(f'/service/internal-repair/view/{req_id}?err=proforma_decision_not_allowed')
                    _apply_proforma_decision(
                        conn, req_id, request.form.get('decision', ''),
                        current_user.get('full_name'), note
                    )
                    conn.commit()
                elif action == 'change_status':
                    conn.close()
                    return redirect(f'/service/internal-repair/view/{req_id}?err=manual_status_disabled')
                elif action == 'issue_final_invoice':
                    if (req['status'] or '') != 'در انتظار صدور فاکتور است':
                        conn.close(); return redirect(f'/service/internal-repair/view/{req_id}?err=invoice_action_not_allowed')
                    inv = (request.form.get('invoice_number') or '').strip()
                    inv_date = (request.form.get('invoice_date') or '').strip()
                    if not inv:
                        conn.close(); return redirect(f'/service/internal-repair/view/{req_id}?err=invoice_required')
                    if not inv_date:
                        conn.close(); return redirect(f'/service/internal-repair/view/{req_id}?err=invoice_date_required')
                    try:
                        from core.history import invoice_is_duplicate
                        if invoice_is_duplicate(conn, inv, exclude_request_id=req_id):
                            conn.close(); return redirect(f'/service/internal-repair/view/{req_id}?err=invoice_duplicate')
                    except Exception:
                        pass
                    transition_request(conn, req_id, 'پایان تعمیرات', actor_name=current_user.get('full_name'), expected_status='در انتظار صدور فاکتور است', note='ثبت اطلاعات فاکتور نهایی صادرشده در نرم‌افزار خارجی')
                    conn.execute('UPDATE requests SET invoice_number=?, invoice_date=? WHERE id=?', (inv, inv_date, req_id))
                    _set_stage_date(conn, req_id, 'پایان تعمیرات', None, 'ثبت شماره و تاریخ فاکتور نهایی خارجی و پایان خودکار پرونده')
                    try: write_audit(conn, current_user.get('full_name'), 'صدور فاکتور نهایی', 'request', req_id, inv)
                    except Exception: pass
                    try: notify_status_change(conn, req_id, 'پایان تعمیرات')
                    except Exception: pass
                    conn.commit()
                elif action in ('save_fields', 'finance_save', 'save'):
                    if (req['status'] or '') not in ('در انتظار ارسال پیش‌فاکتور است', 'در انتظار دریافت تاییدیه پیش‌فاکتور است'):
                        # امور مالی در مراحل دیگر فقط از Action رسمی همان مرحله استفاده می‌کند.
                        conn.close()
                        return redirect(f'/service/internal-repair/view/{req_id}?err=finance_action_not_allowed')
                    updates = []
                    values = []
                    if 'proforma_number' in request.form:
                        new_pn = (request.form.get('proforma_number') or '').strip()
                        try:
                            cur_pn = (req['proforma_number'] if hasattr(req, 'keys') and 'proforma_number' in req.keys() else '') or ''
                        except Exception:
                            cur_pn = ''
                        if new_pn and new_pn != cur_pn:
                            updates.append('proforma_number = ?')
                            values.append(new_pn)
                            try:
                                write_audit(conn, current_user.get('full_name'), 'ثبت شماره پیش‌فاکتور', 'request', req_id, new_pn)
                            except Exception:
                                pass
                    if 'proforma_sent_date' in request.form:
                        new_psd = (request.form.get('proforma_sent_date') or '').strip()
                        if new_psd:
                            updates.append('proforma_sent_date = ?')
                            values.append(new_psd)
                    # تأیید/رد پیش‌فاکتور فقط از Action رسمی proforma_decision انجام می‌شود؛
                    # فرم ذخیره عمومی حق تغییر این فیلد را ندارد.
                    # شماره فاکتور فقط از Action رسمی issue_final_invoice ثبت می‌شود.
                    # فرم ذخیره عمومی اجازه‌ی تغییر invoice_number ندارد.
                    if updates:
                        values.append(req_id)
                        conn.execute('UPDATE requests SET ' + ', '.join(updates) + ' WHERE id = ?', values)
                    # باگ واقعی که با acceptance test فاز ۰ پیدا شد: این بلوکِ خودِ نقشِ امور
                    # مالی (نه بلوک save_fields عمومیِ can_edit که قبلاً اصلاح شده بود) اصلاً
                    # این خودکارسازی را نداشت — یعنی وقتی خودِ امور مالی (نه پذیرش) شماره و
                    # تاریخ پیش‌فاکتور را ثبت می‌کرد، پرونده هرگز جلو نمی‌رفت.
                    proforma_complete = bool((request.form.get('proforma_number') or '').strip() and (request.form.get('proforma_sent_date') or '').strip())
                    if proforma_complete and (req['status'] or '') == 'در انتظار ارسال پیش‌فاکتور است':
                        transition_request(conn, req_id, 'در انتظار دریافت تاییدیه پیش‌فاکتور است', actor_name=current_user.get('full_name'), expected_status='در انتظار ارسال پیش‌فاکتور است', note='ثبت پیش‌فاکتور')
                        try:
                            from core.case_management import add_timeline
                            add_timeline(conn, req_id, 'ثبت پیش‌فاکتور', 'شماره و تاریخ صدور پیش‌فاکتور ثبت شد؛ پرونده در انتظار تاییدیه پیش‌فاکتور است.', 'status', 'staff', current_user.get('full_name'))
                        except Exception:
                            pass
                    if note and str(request.form.get('proforma_confirmed', '')) not in ('1', '2'):
                        try:
                            write_audit(conn, current_user['full_name'], 'یادداشت مالی', 'request', req_id, note)
                        except Exception:
                            pass
                    conn.commit()
                conn.close()
                return redirect('/service/internal-repair/view/' + str(req_id))

            if action == 'confirm_receipt' and can_edit:
                if (req['status'] or '') in (
                    'در انتظار پذیرش',
                    'در انتظار پذیرش دستگاه است',
                    'پذیرش دستگاه انجام شد',
                    'در انتظار بررسی پذیرش',
                ):
                    # این ویو فقط رکوردهای service_type='کارخانه' را برمی‌گرداند (نگاه کنید به SELECT بالا)،
                    # پس مرحلهٔ بعدی همیشه مرحلهٔ بعدیِ گردش‌کار تعمیر داخلی است.
                    next_st = INTERNAL_REPAIR_STATUSES[1] if len(INTERNAL_REPAIR_STATUSES) > 1 else 'در انتظار ارسال حواله تعمیر اولیه است'
                    try:
                        transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), note='تأیید پذیرش')
                    except WorkflowError:
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=invalid_status_transition')
                    try:
                        from core.reception_numbers import assign_reception_no
                        assign_reception_no(conn, req_id, request_category='تعمیر')
                    except Exception:
                        pass
                    try:
                        from core.case_management import add_timeline
                        add_timeline(conn, req_id, 'تایید پذیرش', f'پذیرش انجام شد؛ وضعیت: {next_st}', 'status', 'staff', current_user.get('full_name'))
                    except Exception:
                        pass
                    _set_stage_date(conn, req_id, next_st, None, 'تایید پذیرش — تاریخ مرحله خودکار توسط سیستم')
                    try:
                        from core.customer_notify import notify_status_change
                        notify_status_change(conn, req_id, next_st)
                    except Exception:
                        pass

            elif action == 'save_fields' and can_edit:
                fields = [
                    'hospital_request_desc', 'initial_qc_desc', 'technician_desc',
                    'final_qc_desc', 'actions_taken', 'accompanying_items', 'appearance_status',
                    'tracking_number', 'shipping_method', 'carrier_name', 'carrier_delivery_date', 'device_model',
                    'warranty_end_date', 'installation_date', 'city', 'customer_address',
                    'equipment_manager_name', 'equipment_manager_mobile', 'contact_name', 'contact_phone',
                    'proforma_number', 'proforma_sent_date',
                ]
                updates = []
                values = []
                # SQL identifiers come only from the fixed local whitelist above; request.form supplies values only.
                for f in fields:
                    if f in request.form:
                        updates.append(f'{f} = ?')
                        values.append(request.form.get(f) or None)
                # همگام‌سازی نام باربری با shipping_method برای سازگاری گزارش‌ها
                if 'carrier_name' in request.form and request.form.get('carrier_name') is not None:
                    updates.append('shipping_method = ?')
                    values.append(request.form.get('carrier_name') or None)
                    try:
                        write_audit(conn, current_user.get('full_name'), 'ثبت اطلاعات باربری', 'request', req_id,
                                    (request.form.get('carrier_name') or '') + ' / ' + (request.form.get('tracking_number') or ''))
                    except Exception:
                        pass
                requested_can_initial_test = None
                if 'can_initial_test' in request.form:
                    requested_can_initial_test = 1 if request.form.get('can_initial_test') == '1' else 0
                    updates.append('can_initial_test = ?')
                    values.append(requested_can_initial_test)
                if 'assigned_technician' in request.form:
                    try:
                        sync_request_technician(conn, req_id, request.form.get('assigned_technician'), expected_role='تکنسین کارخانه')
                    except Exception:
                        conn.rollback(); conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=technician_invalid')
                # باگ واقعی که با acceptance test فاز ۰ پیدا شد: بر خلاف همین بلوک در
                # external-repair (که ذخیره‌ی هم‌زمان شماره+تاریخ پیش‌فاکتور را خودکار به
                # «در انتظار دریافت تاییدیه پیش‌فاکتور است» می‌برد)، اینجا این منطق اصلاً
                # وجود نداشت — یعنی امور مالی شماره/تاریخ را ذخیره می‌کرد ولی پرونده هرگز
                # جلو نمی‌رفت و تایید/رد پیش‌فاکتور همیشه بی‌اثر می‌ماند.
                proforma_complete = bool((request.form.get('proforma_number') or '').strip() and (request.form.get('proforma_sent_date') or '').strip())
                if proforma_complete:
                    if (req['status'] or '') != 'در انتظار ارسال پیش‌فاکتور است':
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=proforma_not_allowed')
                    transition_request(conn, req_id, 'در انتظار دریافت تاییدیه پیش‌فاکتور است', actor_name=current_user.get('full_name'), expected_status='در انتظار ارسال پیش‌فاکتور است', note='ثبت پیش‌فاکتور')
                    try:
                        from core.case_management import add_timeline
                        add_timeline(conn, req_id, 'ثبت پیش‌فاکتور', 'شماره و تاریخ صدور پیش‌فاکتور ثبت شد؛ پرونده در انتظار تاییدیه پیش‌فاکتور است.', 'status', 'staff', current_user.get('full_name'))
                    except Exception:
                        pass
                if updates:
                    values.append(req_id)
                    conn.execute(f"UPDATE requests SET {', '.join(updates)} WHERE id = ?", values)
                    # can_initial_test فقط «اطلاعات پذیرش» است و نباید Status را تغییر دهد.
                    # تصمیم قابل‌تست/غیرقابل‌تست فقط در Action رسمی QC (ثبت نتیجه تست اولیه) گرفته می‌شود.
            elif action == 'qc_report' and is_qc:
                initial_qc_desc = request.form.get('initial_qc_desc', '').strip()
                final_qc_desc = request.form.get('final_qc_desc', '').strip()
                result = request.form.get('initial_test_result', '').strip()
                final_result = request.form.get('final_test_result', '').strip()

                # مرحله ۱۳: تست نهایی QC
                if (req['status'] or '') == 'در انتظار تست نهایی و تحویل است':
                    if final_result not in ('passed', 'failed'):
                        conn.close()
                        return redirect(f'/service/internal-repair/view/{req_id}?err=final_test_result_required')
                    conn.execute('UPDATE requests SET final_qc_desc=? WHERE id=?', (final_qc_desc, req_id))
                    if final_result == 'passed':
                        next_st = 'در انتظار خروج از کارخانه است'
                        result_text = 'تست نهایی موفق'
                    else:
                        next_st = 'در انتظار گزارش نهایی است'
                        result_text = 'تست نهایی ناموفق؛ بازگشت به تکنسین برای اصلاح'
                    transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status='در انتظار تست نهایی و تحویل است', note=result_text)
                    _set_stage_date(conn, req_id, next_st, None, result_text)
                    try: write_audit(conn, current_user.get('full_name'), 'ثبت تست نهایی QC', 'request', req_id, f'{result_text}؛ انتقال به {next_st}')
                    except Exception: pass
                    try: notify_status_change(conn, req_id, next_st)
                    except Exception: pass
                else:
                    conn.execute(
                        'UPDATE requests SET initial_qc_desc = ?, final_qc_desc = ? WHERE id = ?',
                    (initial_qc_desc, final_qc_desc, req_id)
                    )

                    # مرحله ۲: QC فقط «نتیجه تست» را ثبت می‌کند؛ Status بعدی توسط سیستم تعیین می‌شود.
                    if (req['status'] or '') == 'در انتظار تست اولیه است' and result in ('passed', 'untestable'):
                        if result == 'passed':
                            next_st = 'در انتظار ارسال گزارش فنی است'
                            result_text = 'تست اولیه موفق'
                        else:
                            next_st = 'در انتظار ارسال حواله تعمیر اولیه است'
                            result_text = 'دستگاه قابل تست اولیه نیست'

                        transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status='در انتظار تست اولیه است', note=result_text)
                        try:
                            from core.case_management import add_timeline
                            add_timeline(
                                conn, req_id, 'ثبت نتیجه تست اولیه',
                                f'{result_text}؛ انتقال خودکار به: {next_st}',
                                'status', 'staff', current_user.get('full_name')
                            )
                        except Exception:
                            pass
                        try:
                            notify_status_change(conn, req_id, next_st)
                        except Exception:
                            pass
                        try:
                            try_auto_wage_on_status(conn, req_id, next_st)
                        except Exception:
                            pass
                        try:
                            _set_stage_date(conn, req_id, next_st, None, f'ثبت نتیجه QC: {result_text}')
                        except Exception:
                            pass
                    elif result:
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=invalid_qc_transition')

            elif action == 'tech_report' and is_assigned_tech:
                technician_desc = request.form.get('technician_desc', '').strip()
                actions_taken = request.form.get('actions_taken', '').strip()
                cur_status = (req['status'] or '')

                # مرحله ۵: پایان تعمیر اولیه -> بازگشت خودکار به QC
                if cur_status == 'در انتظار تعمیر اولیه است':
                    if not technician_desc and not actions_taken:
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=tech_report_required')

                    conn.execute(
                        'UPDATE requests SET technician_desc = ?, actions_taken = ? WHERE id = ?',
                        (technician_desc, actions_taken, req_id)
                    )
                    next_st = 'در انتظار تست اولیه است'
                    transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status=cur_status)
                    _set_stage_date(conn, req_id, next_st, None, 'پایان تعمیر اولیه — ارجاع مجدد به QC')
                    try:
                        write_audit(
                            conn, current_user.get('full_name'), 'ثبت پایان تعمیر اولیه',
                            'request', req_id, f'از {cur_status} به {next_st}'
                        )
                    except Exception:
                        pass
                    try:
                        from core.case_management import add_timeline
                        add_timeline(conn, req_id, 'پایان تعمیر اولیه',
                                     'تعمیر اولیه انجام شد؛ پرونده برای تست اولیه مجدد به QC ارجاع شد.',
                                     'status', 'staff', current_user.get('full_name'))
                    except Exception:
                        pass
                    try:
                        notify_status_change(conn, req_id, next_st)
                    except Exception:
                        pass

                # مرحله ۶: گزارش فنی + قطعات نهایی -> مالی
                elif cur_status == 'در انتظار ارسال گزارش فنی است':
                    final_parts = conn.execute(
                        "SELECT COUNT(*) AS c FROM request_parts WHERE request_id=? AND stage='تعمیر نهایی'",
                        (req_id,)
                    ).fetchone()
                    if not technician_desc and not actions_taken:
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=tech_report_required')
                    if not final_parts or int(final_parts['c'] or 0) == 0:
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=final_parts_required')

                    conn.execute(
                        'UPDATE requests SET technician_desc = ?, actions_taken = ? WHERE id = ?',
                        (technician_desc, actions_taken, req_id)
                    )
                    next_st = 'در انتظار ارسال پیش‌فاکتور است'
                    transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status=cur_status, note='تکمیل گزارش فنی و قطعات نهایی')
                    _set_stage_date(conn, req_id, next_st, None, 'تکمیل گزارش فنی و قطعات نهایی — ارجاع به امور مالی')
                    try:
                        write_audit(
                            conn, current_user.get('full_name'), 'ثبت گزارش فنی و قطعات نهایی',
                            'request', req_id, f'از {cur_status} به {next_st}'
                        )
                    except Exception:
                        pass
                    try:
                        from core.case_management import add_timeline
                        add_timeline(conn, req_id, 'ارجاع به امور مالی',
                                     'گزارش فنی و قطعات نهایی تکمیل شد؛ پرونده به امور مالی ارجاع شد.',
                                     'status', 'staff', current_user.get('full_name'))
                    except Exception:
                        pass
                    try:
                        notify_status_change(conn, req_id, next_st)
                    except Exception:
                        pass

                elif cur_status == 'در انتظار گزارش نهایی است':
                    technician_desc = request.form.get('technician_desc', '').strip()
                    actions_taken = request.form.get('actions_taken', '').strip()
                    if not technician_desc and not actions_taken:
                        conn.close()
                        return redirect(f'/service/internal-repair/view/{req_id}?err=final_report_required')
                    conn.execute(
                        'UPDATE requests SET technician_desc = ?, actions_taken = ? WHERE id = ?',
                        (technician_desc, actions_taken, req_id)
                    )
                    next_st = 'در انتظار تست نهایی و تحویل است'
                    transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status=cur_status)
                    _set_stage_date(conn, req_id, next_st, None, 'ثبت گزارش نهایی — ارجاع خودکار به QC برای تست نهایی')
                    try:
                        write_audit(conn, current_user.get('full_name'), 'ثبت گزارش نهایی', 'request', req_id, f'انتقال به {next_st}')
                    except Exception:
                        pass
                    try:
                        notify_status_change(conn, req_id, next_st)
                    except Exception:
                        pass

            elif action == 'send_final_voucher' and can_edit:
                # مرحله ۹->۱۰: پذیرش حواله‌ی قطعات تعمیر نهایی (که در مرحله «ارسال گزارش فنی»
                # قبلاً توسط تکنسین ثبت شده‌اند) را صادر/ارسال می‌کند تا تکنسین دریافتشان را ثبت کند.
                if (req['status'] or '') != 'در انتظار ارسال حواله تعمیر نهایی است':
                    conn.close()
                    return redirect(f'/service/internal-repair/view/{req_id}?err=final_voucher_not_allowed')
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM request_parts WHERE request_id=? AND stage='تعمیر نهایی'",
                    (req_id,)
                ).fetchone()
                if not row or int(row['c'] or 0) == 0:
                    conn.close()
                    return redirect(f'/service/internal-repair/view/{req_id}?err=final_parts_required')
                next_st = 'در انتظار دریافت قطعه تعمیر نهایی است'
                transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status='در انتظار ارسال حواله تعمیر نهایی است')
                _set_stage_date(conn, req_id, next_st, None, 'صدور حواله قطعات تعمیر نهایی')
                try:
                    write_audit(conn, current_user.get('full_name'), 'صدور حواله تعمیر نهایی', 'request', req_id, f'انتقال به {next_st}')
                except Exception:
                    pass
                try:
                    notify_status_change(conn, req_id, next_st)
                except Exception:
                    pass

            elif action == 'receive_final_parts' and is_assigned_tech:
                # مرحله ۱۱: تکنسین دریافت قطعات تعمیر نهایی را تأیید می‌کند.
                if (req['status'] or '') != 'در انتظار دریافت قطعه تعمیر نهایی است':
                    conn.close()
                    return redirect(f'/service/internal-repair/view/{req_id}?err=final_parts_receive_not_allowed')
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM request_parts WHERE request_id=? AND stage='تعمیر نهایی'",
                    (req_id,)
                ).fetchone()
                if not row or int(row['c'] or 0) == 0:
                    conn.close()
                    return redirect(f'/service/internal-repair/view/{req_id}?err=final_parts_required')
                conn.execute(
                    "UPDATE request_parts SET voucher_recorded=1 WHERE request_id=? AND stage='تعمیر نهایی'",
                    (req_id,)
                )
                next_st = 'در انتظار گزارش نهایی است'
                transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status='در انتظار دریافت قطعه تعمیر نهایی است')
                _set_stage_date(conn, req_id, next_st, None, 'دریافت قطعات تعمیر نهایی توسط تکنسین')
                try:
                    write_audit(conn, current_user.get('full_name'), 'ثبت دریافت قطعات تعمیر نهایی', 'request', req_id, f'انتقال به {next_st}')
                except Exception:
                    pass
                try:
                    notify_status_change(conn, req_id, next_st)
                except Exception:
                    pass

            elif action == 'receive_initial_parts' and is_assigned_tech:
                # مرحله ۴: تکنسین دریافت قطعات تعمیر اولیه را تأیید می‌کند.
                if (req['status'] or '') != 'در انتظار دریافت قطعه تعمیر اولیه است':
                    conn.close()
                    return redirect(f'/service/internal-repair/view/{req_id}?err=initial_parts_receive_not_allowed')
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM request_parts WHERE request_id=? AND stage='تعمیر اولیه'",
                    (req_id,)
                ).fetchone()
                if not row or int(row['c'] or 0) == 0:
                    conn.close()
                    return redirect(f'/service/internal-repair/view/{req_id}?err=initial_parts_required')
                conn.execute(
                    "UPDATE request_parts SET voucher_recorded=1 WHERE request_id=? AND stage='تعمیر اولیه'",
                    (req_id,)
                )
                next_st = 'در انتظار تعمیر اولیه است'
                transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status='در انتظار دریافت قطعه تعمیر اولیه است')
                _set_stage_date(conn, req_id, next_st, None, 'دریافت قطعات تعمیر اولیه توسط تکنسین')
                try:
                    write_audit(conn, current_user.get('full_name'), 'ثبت دریافت قطعات تعمیر اولیه', 'request', req_id, f'انتقال به {next_st}')
                except Exception:
                    pass
                try:
                    notify_status_change(conn, req_id, next_st)
                except Exception:
                    pass

            elif action == 'final_exit' and can_edit:
                # مرحله ۱۴: خروج فیزیکی دستگاه از کارخانه پس از تأیید نهایی QC.
                if (req['status'] or '') != 'در انتظار خروج از کارخانه است':
                    conn.close()
                    return redirect(f'/service/internal-repair/view/{req_id}?err=final_exit_not_allowed')
                next_st = 'در انتظار صدور فاکتور است'
                transition_request(conn, req_id, next_st, actor_name=current_user.get('full_name'), expected_status='در انتظار خروج از کارخانه است')
                _set_stage_date(conn, req_id, next_st, None, 'ثبت خروج دستگاه از کارخانه و ارجاع به امور مالی')
                try:
                    write_audit(conn, current_user.get('full_name'), 'ثبت خروج دستگاه از کارخانه', 'request', req_id, f'انتقال به {next_st}')
                except Exception:
                    pass
                try:
                    notify_status_change(conn, req_id, next_st)
                except Exception:
                    pass

            elif action == 'proforma_decision' and can_edit:
                note = request.form.get('finance_note', '').strip()
                _apply_proforma_decision(
                    conn, req_id, request.form.get('decision', ''),
                    current_user.get('full_name'), note
                )

            elif action == 'change_status' and can_edit:
                # گردش‌کار تعمیر داخلی Action-driven است؛ هیچ Status یا تاریخ مرحله‌ای
                # از طریق فرم عمومی قابل ثبت نیست.
                conn.close()
                return redirect('/service/internal-repair/view/' + str(req_id) + '?err=manual_status_disabled')

            elif action == 'add_part' and (can_edit or is_assigned_tech):
                part_id = request.form.get('part_id') or None
                part_name = request.form.get('part_name', '')
                warehouse_code = request.form.get('warehouse_code', '')
                try:
                    quantity = validate_positive_quantity(request.form.get('quantity') or 1)
                except WorkflowError:
                    conn.close()
                    return redirect('/service/internal-repair/view/' + str(req_id) + '?err=invalid_quantity')
                cur_status = (req['status'] or '')
                # ثبت قطعه در Workflow تعمیر داخلی فقط توسط تکنسین مسئول انجام می‌شود.
                if cur_status in ('در انتظار دریافت قطعه تعمیر اولیه است', 'در انتظار تعمیر اولیه است', 'در انتظار ارسال گزارش فنی است') and not is_assigned_tech:
                    conn.close()
                    return redirect('/service/internal-repair/view/' + str(req_id) + '?err=part_role_not_allowed')
                # مرحله قطعه از Status جاری تعیین می‌شود؛ کاربر اجازه انتخاب stage ندارد.
                if cur_status in ('در انتظار دریافت قطعه تعمیر اولیه است', 'در انتظار ارسال حواله تعمیر اولیه است'):
                    stage = 'تعمیر اولیه'
                elif cur_status == 'در انتظار ارسال گزارش فنی است':
                    stage = 'تعمیر نهایی'
                else:
                    stage = ''
                notes = request.form.get('part_notes', '')
                try:
                    from core.helpers import part_serials_from_form
                    serial_healthy, serial_faulty = part_serials_from_form()
                except Exception:
                    serial_healthy = (request.form.get('serial_healthy') or request.form.get('serial_good') or '').strip()
                    serial_faulty = (request.form.get('serial_faulty') or request.form.get('serial_defective') or '').strip()
                if part_id:
                    p = conn.execute('SELECT * FROM parts WHERE id = ?', (part_id,)).fetchone()
                    if p:
                        part_name = p['part_name']
                        warehouse_code = p['warehouse_code'] or ''
                if part_name:
                    if not stage:
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=part_action_not_allowed')
                    if not (serial_healthy and serial_faulty):
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=serial_required')
                    # جلوگیری از سریال تکراری ورودی/داغی
                    dup = conn.execute(
                        """SELECT id FROM request_parts
                           WHERE (serial_good = ? OR serial_healthy = ? OR serial_defective = ? OR serial_faulty = ?
                                  OR serial_good = ? OR serial_healthy = ? OR serial_defective = ? OR serial_faulty = ?)
                           LIMIT 1""",
                        (serial_healthy, serial_healthy, serial_healthy, serial_healthy,
                         serial_faulty, serial_faulty, serial_faulty, serial_faulty),
                    ).fetchone()
                    if dup:
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=serial_duplicate')
                    conn.execute(
                        'INSERT INTO request_parts (request_id, part_id, part_name, warehouse_code, quantity, stage, notes, stock_applied, serial_healthy, serial_faulty, serial_good, serial_defective, voucher_recorded) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 0)',
                        (req_id, part_id, part_name, warehouse_code, quantity, stage, notes, serial_healthy, serial_faulty, serial_healthy, serial_faulty)
                    )
                    try:
                        write_audit(conn, current_user.get('full_name'), 'ثبت قطعه', 'request', req_id, (part_name or '') + ' / ' + (serial_healthy or ''))
                    except Exception:
                        pass
                    # ثبت قطعه در مرحله «ارسال حواله تعمیر اولیه» پرونده را به مرحله
                    # «در انتظار دریافت قطعه تعمیر اولیه» می‌برد (نه مستقیم به تعمیر اولیه)؛
                    # ورود واقعی به تعمیر با تأیید دریافتِ تکنسین (receive_initial_parts) انجام می‌شود.
                    # در مرحله گزارش فنی، قطعات نهایی صرفاً ثبت می‌شوند و Transition توسط
                    # tech_report و پس از تکمیل گزارش انجام می‌شود.
                    auto_next = None
                    if stage == 'تعمیر اولیه' and cur_status == 'در انتظار ارسال حواله تعمیر اولیه است':
                        auto_next = 'در انتظار دریافت قطعه تعمیر اولیه است'
                    if auto_next:
                        transition_request(conn, req_id, auto_next, actor_name=current_user.get('full_name'), expected_status=cur_status, note='ثبت قطعه — پیشرفت خودکار وضعیت')
                        _set_stage_date(conn, req_id, auto_next, None, 'ثبت قطعه — پیشرفت خودکار وضعیت')
                        try:
                            from core.customer_notify import notify_status_change
                            notify_status_change(conn, req_id, auto_next)
                        except Exception:
                            pass

            elif action == 'edit_part' and (can_edit or is_assigned_tech):
                part_row_id = request.form.get('part_row_id')
                if (req['status'] or '') not in (
                    'در انتظار ارسال حواله تعمیر اولیه است',
                    'در انتظار دریافت قطعه تعمیر اولیه است',
                    'در انتظار تعمیر اولیه است',
                    'در انتظار ارسال گزارش فنی است'
                ):
                    conn.close()
                    return redirect('/service/internal-repair/view/' + str(req_id) + '?err=part_action_not_allowed')
                if part_row_id:
                    sg = (request.form.get('serial_healthy') or request.form.get('serial_good') or '').strip()
                    sd = (request.form.get('serial_faulty') or request.form.get('serial_defective') or '').strip()
                    if not sg or not sd:
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=serial_required')
                    dup = conn.execute(
                        """SELECT id FROM request_parts
                           WHERE id <> ? AND IFNULL(is_void,0)=0
                             AND (serial_good IN (?,?) OR serial_healthy IN (?,?) OR serial_defective IN (?,?) OR serial_faulty IN (?,?))
                           LIMIT 1""",
                        (part_row_id, sg, sd, sg, sd, sg, sd, sg, sd),
                    ).fetchone()
                    if dup:
                        conn.close()
                        return redirect('/service/internal-repair/view/' + str(req_id) + '?err=serial_duplicate')
                    conn.execute(
                        "UPDATE request_parts SET quantity=?, serial_healthy=?, serial_faulty=?, serial_good=?, serial_defective=?, stage=?, notes=?, warehouse_code=COALESCE(NULLIF(?, ''), warehouse_code), part_name=COALESCE(NULLIF(?, ''), part_name) WHERE id=? AND request_id=? AND IFNULL(is_void,0)=0",
                        (
                            validate_positive_quantity(request.form.get('quantity') or 1),
                            sg, sd, sg, sd,
                            ('تعمیر اولیه' if (req['status'] or '') in ('در انتظار ارسال حواله تعمیر اولیه است', 'در انتظار دریافت قطعه تعمیر اولیه است', 'در انتظار تعمیر اولیه است') else
                             'تعمیر نهایی' if (req['status'] or '') == 'در انتظار ارسال گزارش فنی است' else None),
                            request.form.get('part_notes') or None,
                            request.form.get('warehouse_code') or '',
                            request.form.get('part_name') or '',
                            part_row_id, req_id
                        )
                    )

            elif action == 'delete_part' and (can_edit or is_assigned_tech):
                part_row_id = request.form.get('part_row_id')
                if (req['status'] or '') not in (
                    'در انتظار ارسال حواله تعمیر اولیه است',
                    'در انتظار دریافت قطعه تعمیر اولیه است',
                    'در انتظار تعمیر اولیه است',
                    'در انتظار ارسال گزارش فنی است'
                ):
                    conn.close()
                    return redirect('/service/internal-repair/view/' + str(req_id) + '?err=part_action_not_allowed')
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

            elif action == 'set_stage_date':
                # تاریخ/Status در تعمیر داخلی فقط توسط Actionهای رسمی Workflow ساخته می‌شود.
                conn.close()
                return redirect('/service/internal-repair/view/' + str(req_id) + '?err=manual_stage_date_disabled')

            conn.commit()
            conn.close()
            return redirect(f'/service/internal-repair/view/{req_id}')

        stage_dates = conn.execute(
            'SELECT * FROM request_stage_dates WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        stage_map = {s['stage_name']: s for s in stage_dates}
        req_parts = conn.execute(
            'SELECT * FROM request_parts WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        lookup = H._form_lookup_context(conn)
        parts_catalog = lookup['parts_catalog']
        technicians = lookup['technicians_factory']
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
            'internal_repair_view.html',
            case_history=case_history,
            req=req, statuses=INTERNAL_REPAIR_STATUSES, stage_map=stage_map,
            req_parts=req_parts, parts_catalog=parts_catalog, technicians=technicians,
            attachments=attachments,
            quote_files=quote_files,
            recent_requests=recent_requests,
            tech_user=tech_user,
            device_photo=device_photo,
            active_page='service-internal-repair-archive',
            current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day,
            can_edit=can_edit, is_assigned_tech=is_assigned_tech, is_qc=is_qc, is_finance=is_finance, finance_statuses=finance_statuses,
            is_closed_for_ops=is_closed_for_ops,
            visible_panels=_internal_repair_visible_panels(can_edit, is_qc, is_assigned_tech, is_finance, is_system_admin(current_user))
        )






    @app.route('/service/internal-repair/bijak/<int:req_id>')
    def internal_repair_bijak(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        req = conn.execute(
            "SELECT * FROM requests WHERE id = ? AND service_type = 'کارخانه'", (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return redirect('/service/internal-repair/archive')
        if not can_view_request(current_user, req):
            conn.close()
            return redirect('/cartable')
        req = dict(req)
        customer = {}
        cid = req.get('customer_id')
        if cid:
            row = conn.execute('SELECT * FROM customers WHERE id = ?', (cid,)).fetchone()
            if row:
                customer = dict(row)
        # اگر آدرس روی پرونده خالی است از مشتری پر شود
        if not req.get('customer_address') and customer.get('address'):
            req['customer_address'] = customer.get('address')
        if not req.get('city') and customer.get('city'):
            req['city'] = customer.get('city')
        if not req.get('province') and customer.get('province'):
            req['province'] = customer.get('province')
        if not req.get('customer_phone') and customer.get('phone'):
            req['customer_phone'] = customer.get('phone')
        company = _get_company_info(conn)
        conn.close()
        return render_template(
            'internal_repair_bijak.html',
            req=req,
            customer=customer,
            company=company,
            current_user=current_user,
        )


    @app.route('/service/internal-repair/print/<int:req_id>')
    def internal_repair_print(req_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        company = _get_company_info(conn)
        req = conn.execute(
            "SELECT * FROM requests WHERE id = ? AND service_type = 'کارخانه'", (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return redirect('/service/internal-repair/archive')
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
            'internal_repair_print.html',
            req=req, stage_dates=stage_dates, req_parts=req_parts, statuses=INTERNAL_REPAIR_STATUSES,
            current_user=current_user, company=company
        )





    @app.route('/service/internal-repair/export')
    def internal_repair_export():
        current_user = get_current_user()
        if not current_user or current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM requests WHERE request_category = 'تعمیر' AND service_type = 'کارخانه' AND (is_deleted IS NULL OR is_deleted=0) ORDER BY id"
        ).fetchall()
        conn.close()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'تعمیرات داخلی'
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
                         as_attachment=True, download_name='internal_repairs.xlsx')




