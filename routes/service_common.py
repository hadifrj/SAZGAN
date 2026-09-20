# -*- coding: utf-8 -*-
"""مسیرهای مشترک بین انواع درخواست: repair-quote، customer-affairs، new/archive/delete عمومی (slug-based)، cartable-preview، pending-request."""
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
    @app.route('/service/repair-quote/<int:req_id>/upload', methods=['POST'])
    def repair_quote_upload(req_id):
        current_user = get_current_user()
        if not current_user: return redirect('/login')
        if current_user.get('role') not in FINANCE_ROLES: return redirect('/cartable')
        conn=get_db(); req=conn.execute("SELECT id, service_type, request_category, status FROM requests WHERE id=?", (req_id,)).fetchone()
        if not req or req['request_category'] != 'تعمیر': conn.close(); return redirect('/')
        if (req['status'] or '') != 'در انتظار ارسال پیش‌فاکتور است':
            slug = 'internal-repair' if req['service_type'] == 'کارخانه' else 'external-repair'
            conn.close(); return redirect(f'/service/{slug}/view/{req_id}?err=proforma_upload_not_allowed')
        try:
            # فایل پیش‌فاکتور صرفاً پیوست اختیاری است و هرگز Trigger تغییر Status نیست.
            _save_quote_upload(conn, req_id, request.files.get('quote_file'), 'original', current_user.get('full_name') or current_user.get('username'))
            try:
                from core.case_management import add_timeline
                add_timeline(conn, req_id, 'آپلود پیش‌فاکتور', 'فایل پیش‌فاکتور به‌صورت اختیاری به پرونده پیوست شد؛ وضعیت فقط با ثبت شماره و تاریخ پیش‌فاکتور تغییر می‌کند.', 'finance', 'staff', current_user.get('full_name'))
            except Exception:
                pass
            conn.commit()
        except Exception as exc:
            conn.rollback(); conn.close(); return redirect(request.referrer or '/')
        conn.close(); return redirect(request.referrer or '/')

    @app.route('/service/repair-quote/<int:req_id>/file/<int:file_id>')
    def repair_quote_download(req_id, file_id):
        current_user=get_current_user()
        if not current_user: return redirect('/login')
        conn=get_db()
        req = conn.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()
        if not req:
            conn.close(); return redirect('/')
        if not can_view_request(current_user, req):
            conn.close(); return redirect('/cartable')
        row=conn.execute("SELECT * FROM repair_quote_files WHERE id=? AND request_id=?", (file_id,req_id)).fetchone(); conn.close()
        if not row: return redirect('/')
        path=os.path.join(QUOTE_UPLOAD_DIR,row['stored_name'])
        if not os.path.isfile(path): return redirect('/')
        return send_file(path, as_attachment=True, download_name=row['original_name'])

    # دسترسی به هلپرها

    @app.route('/customer-affairs')
    def customer_affairs_hub():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not user_has_access(current_user, 'customer_affairs'):
            return redirect('/')
        return render_template(
            'customer_affairs_hub.html',
            active_page='ca-hub',
            current_user=current_user,
        )


    @app.route('/service/<slug>/new', methods=['GET', 'POST'])
    def service_new(slug):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        if slug not in SERVICE_CATEGORIES:
            return redirect('/')

        # --- فرم‌های تخصصی ---
        if slug == 'internal-repair':
            return internal_repair_new()
        if slug == 'external-repair':
            return external_repair_new()
        if slug == 'installation':
            return redirect('/service/installation/request-new')
        if slug == 'inspection':
            return redirect('/service/inspection/request-new')

        cfg = SERVICE_CATEGORIES[slug]
        conn = get_db()

        if request.method == 'POST':
            customer_name = request.form['customer_name']
            customer_address = request.form['customer_address']
            customer_phone = request.form['customer_phone']
            device_type = request.form['device_type']
            serial_number = request.form['serial_number']
            installation_date = request.form.get('installation_date', '')
            problem_desc = request.form['problem_desc']
            province = request.form['province']
            county = request.form.get('county', '')
            city = request.form.get('city') or request.form.get('city_manual') or request.form.get('city', '')
            assigned_technician = request.form.get('assigned_technician') or None
            reception_date = _jalali_from_form('recep')

            cur = conn.execute(
                '''INSERT INTO requests
                   (customer_name, customer_address, customer_phone, device_type, serial_number,
                    installation_date, problem_desc, service_type, province, county, city, assigned_technician,
                    reception_date, request_category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (customer_name, customer_address, customer_phone, device_type, serial_number,
                 installation_date, problem_desc, cfg['service_type'], province, county, city, assigned_technician,
                 reception_date, cfg['category'])
            )
            new_id = cur.lastrowid
            try:
                from core.reception_numbers import assign_reception_no
                assign_reception_no(conn, new_id, request_category=cfg.get('category') if isinstance(cfg, dict) else None)
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
            conn.commit()
            conn.close()
            return redirect(f'/service/{slug}/new')

        technicians = conn.execute(
            "SELECT id, full_name, role, province FROM users WHERE role IN ('تکنسین کارخانه', 'تکنسین استانی') ORDER BY full_name"
        ).fetchall()
        customers = conn.execute('SELECT id, name, province, city FROM customers ORDER BY name').fetchall()
        conn.close()

        today = jdatetime.date.today()
        return render_template(
            'service_new.html',
            slug=slug, cfg=cfg, customers=customers,
            provinces=(get_geo_provinces(conn) if get_geo_provinces else PROVINCES), technicians=technicians,
            active_page=f'service-{slug}-new',
            current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day
        , embed=_is_embed()
        )





    @app.route('/service/<slug>/archive')
    def service_archive(slug):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        if slug not in SERVICE_CATEGORIES:
            return redirect('/')

        cfg = SERVICE_CATEGORIES[slug]
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM requests WHERE request_category = ? AND service_type = ? AND (is_deleted IS NULL OR is_deleted = 0) ORDER BY id DESC",
            (cfg['category'], cfg['service_type'])
        ).fetchall()

        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        province = request.args.get('province', '').strip()
        city = request.args.get('city', '').strip()
        status = request.args.get('status', '').strip()
        technician = request.args.get('technician', '').strip()
        device_type = request.args.get('device_type', '').strip()
        device_model = request.args.get('device_model', '').strip()
        q = request.args.get('q', '').strip()
        only_delayed = request.args.get('only_delayed') == '1'

        enriched = _enrich_delay(conn, rows)
        conn.close()
        enriched = _filter_by_date_range(enriched, date_from or None, date_to or None)
        enriched = _filter_rows(
            enriched,
            province=province or None,
            status=status or None,
            only_delayed=only_delayed,
            city=city or None,
            technician=technician or None,
            device_type=device_type or None,
            device_model=device_model or None,
        )
        try:
            from core.request_utils import search_rows as _search_rows
            enriched = _search_rows(enriched, q)
        except Exception:
            pass

        filter_ctx = {
            'date_from': date_from, 'date_to': date_to, 'province': province,
            'city': city, 'status': status, 'technician': technician,
            'device_type': device_type, 'device_model': device_model, 'q': q,
            'only_delayed': only_delayed,
            'provinces': PROVINCES, 'delay_threshold': DELAY_THRESHOLD_DAYS,
        }

        open_rows, closed_rows = _split_open_closed(enriched)
        # بایگانی دیگه اینجا نشون داده نمی‌شه؛ پرونده‌های بسته از منوی «بایگانی» / گزارش عملکرد خدمات قابل مشاهده‌ست
        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        page = parse_page(request.args)
        per_page = parse_per_page(request.args, 25)
        pg = paginate(open_rows, page=page, per_page=per_page)
        shown = pg['items']
        filter_ctx.update(pagination_context(pg, request.args))

        if slug == 'internal-repair':
            fctx = _form_lookup_context()
            return render_template(
                'internal_repair_list.html',
                requests=shown, statuses=INTERNAL_REPAIR_STATUSES,
                active_page=f'service-{slug}-archive',
                current_user=current_user,
                list_title='لیست تعمیرات داخلی',
                technicians=fctx['technicians_factory'],
                customers=fctx['customers'],
                device_types=fctx['device_types'],
                jalali_months=fctx['jalali_months'],
                today_year=fctx['today_year'], today_month=fctx['today_month'], today_day=fctx['today_day'],
                **filter_ctx
            )
        if slug == 'external-repair':
            fctx = _form_lookup_context()
            return render_template(
                'external_repair_list.html',
                requests=shown, statuses=EXTERNAL_REPAIR_STATUSES,
                active_page=f'service-{slug}-archive',
                current_user=current_user,
                list_title='لیست تعمیرات خارجی',
                technicians=fctx['technicians_prov'],
                customers=fctx['customers'],
                device_types=fctx['device_types'],
                parts_catalog=fctx['parts_catalog'],
                jalali_months=fctx['jalali_months'],
                today_year=fctx['today_year'], today_month=fctx['today_month'], today_day=fctx['today_day'],
                **filter_ctx
            )
        if slug == 'installation':
            return redirect('/service/installation/requests')
        if slug == 'inspection':
            return redirect('/service/inspection/list')

        return render_template(
            'service_archive.html',
            slug=slug, cfg=cfg, requests=shown,
            active_page=f'service-{slug}-archive',
            current_user=current_user,
            **filter_ctx
        )





    @app.route('/service/<slug>/delete/<int:req_id>', methods=['POST'])
    def service_delete_request(slug, req_id):
        """حذف نرم یک درخواست — فقط مدیر سیستم.
        رکورد از لیست/کارتابل‌ها مخفی می‌شود اما برای حفظ یکپارچگی داده‌های
        مرتبط (قطعات، انبار، تاریخچه) به‌صورت فیزیکی حذف نمی‌شود.
        """
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not is_system_admin(current_user):
            return redirect('/')
        if not _validate_csrf():
            return ('خطای امنیتی CSRF — صفحه را تازه کنید و دوباره تلاش کنید.', 400)
        if slug not in SERVICE_CATEGORIES:
            return redirect('/')
        cfg = SERVICE_CATEGORIES[slug]

        conn = get_db()
        req = conn.execute(
            "SELECT id FROM requests WHERE id=? AND request_category=? AND service_type=? AND (is_deleted IS NULL OR is_deleted=0)",
            (req_id, cfg['category'], cfg['service_type'])
        ).fetchone()
        if req:
            ts = None
            try:
                from core.history import now_stamp
                ts = now_stamp()
            except Exception:
                pass
            conn.execute(
                "UPDATE requests SET is_deleted=1, deleted_at=?, deleted_by=? WHERE id=?",
                (ts, current_user.get('full_name'), req_id)
            )
            try:
                write_audit(conn, current_user.get('full_name'), 'حذف پرونده', 'request', req_id, '')
            except Exception:
                pass
            conn.commit()
        conn.close()

        back = request.referrer
        if back and back.startswith(request.host_url):
            return redirect(back)
        return redirect(f'/service/{slug}/archive')


    @app.route('/service/cartable-preview/<int:req_id>')
    def cartable_request_preview(req_id):
        """نمایش سریع و امن پرونده در مودال کارتابل؛ فرم‌های سنگین در صفحه کامل باز می‌شوند."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        conn = get_db()
        req = conn.execute('SELECT * FROM requests WHERE id=?', (req_id,)).fetchone()
        if not req:
            conn.close()
            return render_template('cartable_request_preview.html', req=None, current_user=current_user, error='پرونده موردنظر پیدا نشد.'), 404
        if (req['request_category'] or '') == 'تعمیر' and not can_view_request(current_user, req):
            conn.close()
            return render_template('cartable_request_preview.html', req=None, current_user=current_user, error='دسترسی به این پرونده مجاز نیست.'), 403

        category = (req['request_category'] or '')
        service_type = (req['service_type'] or '')
        status = (req['status'] or '')
        can_edit = current_user['role'] in RECEPTION_ROLES
        status_endpoint = None
        statuses = []

        if category == 'نصب و آموزش':
            detail_url = f'/service/installation/request-view/{req_id}'
            status_endpoint = f'/api/native/service/installation/request-action/{req_id}'
            statuses = list(INSTALLATION_REQUEST_STATUSES)
        elif category == 'بررسی و بازدید':
            detail_url = f'/service/inspection/view/{req_id}'
            status_endpoint = f'/api/native/service/inspection/action/{req_id}'
            statuses = list(VISIT_STATUSES)
        elif category == 'تعمیر' and service_type == 'در محل':
            detail_url = f'/service/external-repair/view/{req_id}'
            status_endpoint = f'/api/native/service/external-repair/action/{req_id}'
            statuses = list(EXTERNAL_REPAIR_STATUSES)
        elif category == 'تعمیر':
            detail_url = f'/service/internal-repair/view/{req_id}'
            status_endpoint = f'/api/native/service/internal-repair/action/{req_id}'
            statuses = list(INTERNAL_REPAIR_STATUSES)
        elif category in ('درخواست خدمات', 'اعلام خرابی', 'درخواست سرویس') and status not in ('بسته شد', 'پایان', 'پایان تعمیرات'):
            # تعیین مسیر فقط داخل پرونده کامل و در تب «اقدام» انجام می‌شود.
            detail_url = f'/service/pending-request/{req_id}'
        else:
            detail_url = f'/service/internal-repair/view/{req_id}'
            status_endpoint = f'/api/native/service/internal-repair/action/{req_id}'
            statuses = list(INTERNAL_REPAIR_STATUSES)

        # جلوگیری از گزینه‌های تکراری و حفظ ترتیب گردش‌کار قبلی.
        statuses = list(dict.fromkeys(statuses))
        conn.close()
        return render_template(
            'cartable_request_preview.html',
            req=req, detail_url=detail_url, current_user=current_user,
            can_edit=can_edit, statuses=statuses, status_endpoint=status_endpoint,
            active_page='cartable', error=None, embed=True,
        )

    # ---------- پذیرش درخواست خدمات مشتری (یکپارچه) ----------

    @app.route('/service/pending-request/<int:req_id>', methods=['GET', 'POST'])
    def pending_service_request(req_id):
        """بررسی و هدایت درخواست خدمات ثبت‌شده از پرتال مشتری."""
        current_user = get_current_user()
        if not current_user or current_user['role'] not in RECEPTION_ROLES:
            return redirect('/')
        conn = get_db()
        req = conn.execute('SELECT * FROM requests WHERE id=?', (req_id,)).fetchone()
        if not req:
            conn.close()
            return redirect('/cartable')
        cat = (req['request_category'] or '')
        allowed_cats = ('درخواست خدمات', 'اعلام خرابی', 'درخواست سرویس')
        if cat not in allowed_cats and (req['status'] or '') not in (
            'در انتظار بررسی پذیرش', 'در انتظار پذیرش',
        ):
            # اگر قبلاً به تعمیر تبدیل شده، به پرونده مربوطه برو
            if cat == 'تعمیر':
                conn.close()
                if (req['service_type'] or '') == 'در محل':
                    return redirect(f'/service/external-repair/view/{req_id}')
                return redirect(f'/service/internal-repair/view/{req_id}')
        error = None
        if request.method == 'POST':
            action = request.form.get('action') or ''
            # پذیرش ابتدا می‌تواند اطلاعات ثبت‌شده توسط مشتری را اصلاح کند؛
            # تبدیل پرونده فقط پس از ثبت همین اطلاعات انجام می‌شود.
            if action == 'save_details':
                editable_fields = (
                    'customer_name', 'customer_phone', 'customer_address',
                    'equipment_manager_name', 'equipment_manager_mobile',
                    'device_type', 'device_model', 'serial_number',
                    'installation_date', 'warranty_end_date', 'problem_desc',
                )
                updates = {field: (request.form.get(field) or '').strip() for field in editable_fields}
                if not updates['customer_name'] or not updates['device_type'] or not updates['serial_number']:
                    error = 'نام مشتری، نوع/نام دستگاه و شماره سریال الزامی است.'
                else:
                    set_clause = ', '.join(f"{field}=?" for field in editable_fields)
                    # ذخیره اطلاعات پذیرش نباید وضعیت گردش کار را تغییر دهد.
                    conn.execute(f"UPDATE requests SET {set_clause} WHERE id=?", (*updates.values(), req_id))
                    try:
                        from core.case_management import add_timeline
                        add_timeline(conn, req_id, 'اصلاح اطلاعات پذیرش', 'اطلاعات مشتری و دستگاه توسط مسئول پذیرش بررسی و به‌روزرسانی شد.', 'edit', 'staff', current_user.get('full_name'))
                    except Exception:
                        pass
                    conn.commit()
                    req = conn.execute('SELECT * FROM requests WHERE id=?', (req_id,)).fetchone()
                    error = 'اطلاعات با موفقیت ذخیره شد.'
            try:
                subtype = req['request_subtype'] if 'request_subtype' in req.keys() else ''
            except Exception:
                subtype = ''
            conversion_map = {
                'accept_external': ('تعمیر', 'در محل', 'پذیرش انجام شد', None, 'تعمیر خارجی', '/service/external-repair/view/{id}', 'درخواست به تعمیر خارجی (در محل) منتقل شد.'),
                'accept_install': ('نصب و آموزش', 'در محل', INSTALLATION_REQUEST_STATUSES[0], 'درخواست نصب', 'نصب و آموزش', '/service/installation/request-view/{id}', 'درخواست به مسیر نصب و آموزش منتقل شد.'),
                'accept_visit': ('بررسی و بازدید', 'در محل', VISIT_STATUSES[2] if len(VISIT_STATUSES) > 2 else VISIT_STATUSES[0], 'بازدید / بررسی', 'بازدید', '/service/inspection/view/{id}', 'درخواست به مسیر بررسی و بازدید منتقل شد.'),
                'accept_periodic': ('بررسی و بازدید', 'در محل', VISIT_STATUSES[2] if len(VISIT_STATUSES) > 2 else VISIT_STATUSES[0], 'سرویس دوره‌ای', 'سرویس دوره‌ای', '/service/inspection/view/{id}', 'درخواست سرویس دوره‌ای به مسیر بازدید/سرویس منتقل شد.'),
                'accept_demo': ('نصب Demo و امانی', 'در محل', 'درخواست ثبت شد', 'نصب Demo / امانی', 'Demo/امانی', '/service/demo/archive', 'درخواست به مسیر نصب Demo و امانی منتقل شد.'),
            }
            if action in conversion_map:
                category, service_type, new_status, forced_subtype, title, target, detail = conversion_map[action]
                try:
                    # تمام تغییرات تبدیل در یک تراکنش واحد انجام می‌شود.
                    if forced_subtype:
                        conn.execute(
                            "UPDATE requests SET request_category=?, service_type=?, status=?, request_subtype=? WHERE id=?",
                            (category, service_type, new_status, forced_subtype, req_id),
                        )
                    else:
                        conn.execute(
                            "UPDATE requests SET request_category=?, service_type=?, status=? WHERE id=?",
                            (category, service_type, new_status, req_id),
                        )
                    from core.reception_numbers import assign_reception_no
                    reception_no = assign_reception_no(conn, req_id, request_category=category)
                    if not reception_no:
                        raise RuntimeError('صدور شماره پذیرش ناموفق بود.')
                    try:
                        from core.case_management import add_timeline
                        add_timeline(conn, req_id, f'پذیرش — {title}', detail, 'status', 'staff', current_user.get('full_name'))
                    except Exception as timeline_exc:
                        raise RuntimeError(f'ثبت تاریخچه پرونده ناموفق بود: {timeline_exc}')
                    conn.commit()
                    conn.close()
                    return redirect(target.format(id=req_id))
                except Exception as exc:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    error = f'تبدیل درخواست انجام نشد: {exc}'
                    try:
                        req = conn.execute('SELECT * FROM requests WHERE id=?', (req_id,)).fetchone()
                    except Exception:
                        pass
            if action == 'close_reject':
                note = (request.form.get('note') or '').strip()
                conn.execute("UPDATE requests SET status=? WHERE id=?", ('بسته شد', req_id))
                try:
                    from core.case_management import add_timeline
                    add_timeline(conn, req_id, 'پاسخ نهایی پذیرش', note or 'درخواست توسط پذیرش بررسی و بسته شد.', 'status', 'staff', current_user.get('full_name'))
                except Exception:
                    pass
                conn.commit(); conn.close()
                return redirect('/cartable')
            error = 'اقدام نامعتبر'
        # timeline
        try:
            from core.case_management import case_timeline
            timeline = case_timeline(conn, req_id)
        except Exception:
            timeline = []
        conn.close()
        return render_template(
            'pending_service_request.html',
            req=req, timeline=timeline, error=error,
            current_user=current_user, active_page='cartable',
        )




