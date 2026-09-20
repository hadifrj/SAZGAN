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
from core import helpers as H


from core.helpers import *  # noqa: F401,F403
from core.constants import *  # noqa: F401,F403

def register(app):
    """مسیرهای reports."""
    # دسترسی به هلپرها
    @app.route('/reports')
    def reports_hub():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'reports') or user_has_access(current_user, 'dashboard')):
            return redirect('/')
        return render_template(
            'reports_hub.html',
            active_page='reports-hub',
            current_user=current_user,
            can_dashboard=user_has_access(current_user, 'dashboard'),
            can_reports=user_has_access(current_user, 'reports'),
        )

    @app.route('/dashboard')
    def dashboard():
        """داشبورد آماری خدمات پس از فروش."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'reports')):
            return redirect('/')

        conn = get_db()
        closed = ('پایان تعمیرات', 'پایان', 'تحویل شد', 'بسته شد', 'نصب انجام شد', 'بازدید انجام شد')
        all_rows = conn.execute('SELECT * FROM requests').fetchall()

        def is_closed(r):
            return (r['status'] or '') in closed

        total = len(all_rows)
        open_rows = [r for r in all_rows if not is_closed(r)]
        closed_rows = [r for r in all_rows if is_closed(r)]

        by_cat = {
            'تعمیر داخلی': 0,
            'تعمیر خارجی': 0,
            'نصب و آموزش': 0,
            'بررسی و بازدید': 0,
            'سایر': 0,
        }
        for r in all_rows:
            cat = r['request_category'] or ''
            st = r['service_type'] or ''
            if cat == 'تعمیر' and st == 'کارخانه':
                by_cat['تعمیر داخلی'] += 1
            elif cat == 'تعمیر' and st == 'در محل':
                by_cat['تعمیر خارجی'] += 1
            elif cat == 'نصب و آموزش':
                by_cat['نصب و آموزش'] += 1
            elif cat == 'بررسی و بازدید':
                by_cat['بررسی و بازدید'] += 1
            else:
                by_cat['سایر'] += 1

        open_by_cat = {k: 0 for k in by_cat}
        for r in open_rows:
            cat = r['request_category'] or ''
            st = r['service_type'] or ''
            if cat == 'تعمیر' and st == 'کارخانه':
                open_by_cat['تعمیر داخلی'] += 1
            elif cat == 'تعمیر' and st == 'در محل':
                open_by_cat['تعمیر خارجی'] += 1
            elif cat == 'نصب و آموزش':
                open_by_cat['نصب و آموزش'] += 1
            elif cat == 'بررسی و بازدید':
                open_by_cat['بررسی و بازدید'] += 1
            else:
                open_by_cat['سایر'] += 1

        # استان
        province_counts = {}
        for r in open_rows:
            prov = r['province'] or 'نامشخص'
            province_counts[prov] = province_counts.get(prov, 0) + 1
        province_top = sorted(province_counts.items(), key=lambda x: -x[1])[:12]

        # تأخیر
        enriched = _enrich_delay(conn, open_rows)
        delayed = [e for e in enriched if e.get('is_delayed')]
        delayed_count = len(delayed)
        avg_days = 0
        if enriched:
            days_list = [e.get('days_in_status') or 0 for e in enriched]
            avg_days = round(sum(days_list) / len(days_list), 1)

        # بازدید رایگان / غیررایگان
        visits = [r for r in all_rows if (r['request_category'] or '') == 'بررسی و بازدید']
        visits_free = sum(1 for r in visits if not r['is_paid_visit'])
        visits_paid = sum(1 for r in visits if r['is_paid_visit'])

        # وضعیت تعمیر داخلی
        internal_status = {}
        for r in all_rows:
            if (r['request_category'] or '') == 'تعمیر' and (r['service_type'] or '') == 'کارخانه':
                s = r['status'] or 'نامشخص'
                internal_status[s] = internal_status.get(s, 0) + 1
        internal_status_sorted = sorted(internal_status.items(), key=lambda x: -x[1])[:10]

        # انبار کم‌موجود
        low_stock = conn.execute('''
            SELECT ws.quantity, p.part_name, p.warehouse_code, ws.location_type, ws.province
            FROM warehouse_stock ws
            JOIN parts p ON p.id = ws.part_id
            WHERE ws.quantity <= 3
            ORDER BY ws.quantity ASC
            LIMIT 15
        ''').fetchall()

        # داشبورد V4.1 — شاخص‌های پایه بدون تغییر در گردش‌کار
        try:
            customer_count = conn.execute("SELECT COUNT(*) AS c FROM customers").fetchone()["c"]
        except Exception:
            customer_count = 0
        try:
            active_user_count = conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE COALESCE(is_active, 1) = 1"
            ).fetchone()["c"]
        except Exception:
            active_user_count = 0
        try:
            low_stock_count = conn.execute('''
                SELECT COUNT(*) AS c
                FROM warehouse_stock ws
                WHERE ws.quantity <= 3
            ''').fetchone()["c"]
        except Exception:
            low_stock_count = len(low_stock)
        try:
            pending_action_count = len(delayed) + len(open_rows)
        except Exception:
            pending_action_count = len(open_rows)

        # ماه پذیرش (تقریبی از reception_date)
        month_counts = {}
        for r in all_rows:
            rd = r['reception_date'] or ''
            parts = rd.replace('-', '/').split('/')
            if len(parts) >= 2:
                key = f"{parts[0]}/{parts[1].zfill(2)}"
                month_counts[key] = month_counts.get(key, 0) + 1
        month_sorted = sorted(month_counts.items())[-8:]

        # درخواست‌های اخیر + تفکیک وضعیت کل
        recent_requests = []
        for r in sorted(all_rows, key=lambda x: x['id'] or 0, reverse=True)[:8]:
            recent_requests.append({
                'id': r['id'],
                'reception_number': r['reception_number'] if 'reception_number' in r.keys() else r['id'],
                'customer_name': r['customer_name'] or '—',
                'device_type': r['device_type'] or '—',
                'status': r['status'] or '—',
                'reception_date': r['reception_date'] or '—',
                'request_category': r['request_category'] or '',
                'service_type': r['service_type'] or '',
            })

        status_counts = {}
        for r in all_rows:
            s = r['status'] or 'نامشخص'
            status_counts[s] = status_counts.get(s, 0) + 1
        status_top = sorted(status_counts.items(), key=lambda x: -x[1])[:8]

        conn.close()

        max_cat = max(by_cat.values()) if by_cat else 1
        max_prov = max((c for _, c in province_top), default=1)
        max_month = max((c for _, c in month_sorted), default=1)
        max_status = max((c for _, c in internal_status_sorted), default=1)

        return render_template(
            'dashboard.html',
            total=total,
            open_count=len(open_rows),
            closed_count=len(closed_rows),
            delayed_count=delayed_count,
            avg_days=avg_days,
            by_cat=by_cat,
            open_by_cat=open_by_cat,
            province_top=province_top,
            visits_free=visits_free,
            visits_paid=visits_paid,
            visits_total=len(visits),
            internal_status_sorted=internal_status_sorted,
            low_stock=low_stock,
            month_sorted=month_sorted,
            max_cat=max_cat or 1,
            max_prov=max_prov or 1,
            max_month=max_month or 1,
            max_status=max_status or 1,
            delay_threshold=DELAY_THRESHOLD_DAYS,
            recent_requests=recent_requests,
            status_top=status_top,
            customer_count=customer_count,
            active_user_count=active_user_count,
            low_stock_count=low_stock_count,
            pending_action_count=pending_action_count,
            active_page='dashboard',
            current_user=current_user,
        )







    @app.route('/reports/delays')
    def report_delays_hub():
        """گزارش تأخیرها — تب‌های داخلی / خارجی / نصب / بازدید."""
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'reports')):
            return redirect('/')
        tab = request.args.get('tab', 'internal').strip() or 'internal'
        conn = get_db()
        if tab == 'external':
            rows = conn.execute(
                "SELECT * FROM requests WHERE request_category = 'تعمیر' AND service_type = 'در محل' ORDER BY id DESC LIMIT 300"
            ).fetchall()
            title = 'تأخیر تعمیرات خارجی'
        elif tab == 'installation':
            rows = conn.execute(
                "SELECT * FROM requests WHERE request_category = 'نصب و آموزش' ORDER BY id DESC LIMIT 300"
            ).fetchall()
            title = 'تأخیر نصب‌ها'
        elif tab == 'inspection':
            rows = conn.execute(
                "SELECT * FROM requests WHERE request_category = 'بررسی و بازدید' ORDER BY id DESC LIMIT 300"
            ).fetchall()
            title = 'تأخیر بازدیدها'
        else:
            tab = 'internal'
            rows = conn.execute(
                "SELECT * FROM requests WHERE request_category = 'تعمیر' AND service_type = 'کارخانه' ORDER BY id DESC LIMIT 300"
            ).fetchall()
            title = 'تأخیر تعمیرات داخلی'
        enriched = _enrich_delay(conn, rows)
        conn.close()
        delayed = [r for r in enriched if r.get('is_delayed')]
        section_tabs = [
            {'href': '/reports/delays?tab=internal', 'label': 'تعمیرات داخلی', 'icon': '🏭', 'active': tab == 'internal'},
            {'href': '/reports/delays?tab=external', 'label': 'تعمیرات خارجی', 'icon': '🚚', 'active': tab == 'external'},
            {'href': '/reports/delays?tab=installation', 'label': 'نصب‌ها', 'icon': '🔧', 'active': tab == 'installation'},
            {'href': '/reports/delays?tab=inspection', 'label': 'بازدیدها', 'icon': '🔍', 'active': tab == 'inspection'},
        ]
        return render_template(
            'report_delays_hub.html',
            requests=delayed, all_count=len(enriched), delayed_count=len(delayed),
            title=title, tab=tab, section_tabs=section_tabs,
            delay_threshold=DELAY_THRESHOLD_DAYS,
            active_page='report-delays', current_user=current_user,
        )




    @app.route('/reports/stage-delays')
    def report_stage_delays():
        """گزارش تاریخ مراحل تعمیرات داخلی برای مدیریت تأخیر."""
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'reports')):
            return redirect('/')
        conn = get_db()
        raw = conn.execute(
            """SELECT r.*
               FROM requests r
               WHERE r.status NOT IN ('پایان تعمیرات','پایان','تحویل شد','بسته شد','نصب انجام شد','بازدید انجام شد')
               ORDER BY r.id DESC LIMIT 200"""
        ).fetchall()
        enriched = _enrich_delay(conn, raw)
        try:
            from core.request_utils import search_rows as _sr
            if q:
                enriched = _sr(enriched, q)
        except Exception:
            pass
        rows = []
        for e in enriched:
            d = dict(e) if not isinstance(e, dict) else e
            d['stage'] = d.get('status')
            d['days'] = d.get('days_in_status')
            rows.append(d)
        conn.close()
        return render_template(
            'report_stage_delays.html',
            rows=rows, statuses=INTERNAL_REPAIR_STATUSES,
            active_page='report-delays', current_user=current_user
        )





    @app.route('/reports/delay-matrix')
    def report_delay_matrix():
        """ماتریس تأخیر سریال‌محور: ردیف=سریال، ستون=مرحله."""
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'reports')):
            return redirect('/')
        kind = (request.args.get('kind') or 'internal').strip()
        serial = (request.args.get('serial') or '').strip()
        province = (request.args.get('province') or '').strip()
        only_delayed = request.args.get('only_delayed') == '1'
        conn = get_db()
        from core.delay_matrix import build_delay_matrix
        data = build_delay_matrix(
            conn, kind=kind, serial_filter=serial, province=province,
            only_delayed=only_delayed, limit=250,
        )
        conn.close()
        section_tabs = [
            {'href': '/reports/delay-matrix?kind=internal', 'label': 'تعمیر داخلی', 'active': kind == 'internal'},
            {'href': '/reports/delay-matrix?kind=external', 'label': 'تعمیر خارجی', 'active': kind == 'external'},
            {'href': '/reports/delay-matrix?kind=install', 'label': 'نصب', 'active': kind == 'install'},
            {'href': '/reports/delay-matrix?kind=visit', 'label': 'بازدید', 'active': kind == 'visit'},
        ]
        return render_template(
            'report_delay_matrix.html',
            stages=data['stages'],
            rows=data['rows'],
            averages=data['averages'],
            caps=data['caps'],
            kind=kind,
            serial=serial,
            province=province,
            only_delayed=only_delayed,
            section_tabs=section_tabs,
            provinces=PROVINCES,
            active_page='report-delay-matrix',
            current_user=current_user,
        )

    @app.route('/reports/management')
    def report_management():
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'reports')):
            return redirect('/')
        conn = get_db()
        # delayed by province / tech
        all_rows = conn.execute("SELECT * FROM requests").fetchall()
        closed_set = ('پایان تعمیرات','پایان','تحویل شد','بسته شد','نصب انجام شد','بازدید انجام شد')
        open_rows = [r for r in all_rows if (r['status'] or '') not in closed_set]
        closed_rows = [r for r in all_rows if (r['status'] or '') in closed_set]
        enriched_open = _enrich_delay(conn, open_rows)
        delayed = [e for e in enriched_open if e.get('is_delayed')]
        def _cat(r, *keys):
            return (r['request_category'] if hasattr(r, 'keys') else r.get('request_category')) or ''
        def _svc(r):
            return (r['service_type'] if hasattr(r, 'keys') else r.get('service_type')) or ''
        n_internal = sum(1 for r in all_rows if _cat(r) == 'تعمیر' and _svc(r) == 'کارخانه')
        n_external = sum(1 for r in all_rows if _cat(r) == 'تعمیر' and _svc(r) == 'در محل')
        n_install = sum(1 for r in all_rows if _cat(r) == 'نصب و آموزش')
        n_visit = sum(1 for r in all_rows if _cat(r) == 'بررسی و بازدید')
        n_free = sum(1 for r in all_rows if not (r['is_paid_visit'] if 'is_paid_visit' in r.keys() else 0) and _cat(r) == 'بررسی و بازدید')
        n_paid = sum(1 for r in all_rows if (r['is_paid_visit'] if 'is_paid_visit' in r.keys() else 0))
        by_tech = {}
        by_prov = {}
        for e in delayed:
            tech = e.get('assigned_technician') or 'بدون تکنسین'
            prov = e.get('province') or 'نامشخص'
            by_tech[tech] = by_tech.get(tech, 0) + 1
            by_prov[prov] = by_prov.get(prov, 0) + 1
        days = [e.get('days_in_status') or 0 for e in enriched_open]
        avg = round(sum(days) / len(days), 1) if days else 0
        try:
            import jdatetime
            td = jdatetime.date.today()
            period = f"تا {td.year}/{str(td.month).zfill(2)}/{str(td.day).zfill(2)}"
        except Exception:
            period = '—'
        conn.close()
        return render_template(
            'report_management.html',
            by_tech=sorted(by_tech.items(), key=lambda x: -x[1]),
            by_prov=sorted(by_prov.items(), key=lambda x: -x[1]),
            avg_days=avg,
            delayed_total=len(delayed),
            open_total=len(open_rows),
            closed_total=len(closed_rows),
            total_accept=len(all_rows),
            n_internal=n_internal,
            n_external=n_external,
            n_install=n_install,
            n_visit=n_visit,
            n_free=n_free,
            n_paid=n_paid,
            amount_services=0,
            amount_parts=0,
            amount_invoices=0,
            period=period,
            current_user=current_user,
            active_page='report-mgmt'
        )




    @app.route('/reports/management/export')
    def report_management_export():
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'reports')):
            return redirect('/')
        conn = get_db()
        rows = conn.execute('SELECT * FROM requests ORDER BY id').fetchall()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'گزارش'
        ws.append(['کد', 'دسته', 'مشتری', 'سریال', 'استان', 'تکنسین', 'وضعیت', 'تاریخ'])
        for r in rows:
            ws.append([r['id'], r['request_category'], r['customer_name'], r['serial_number'], r['province'], r['assigned_technician'], r['status'], r['reception_date']])
        conn.close()
        out = BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(out, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name='management_report.xlsx')


    @app.route('/reports/service-performance')
    def report_service_performance():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or current_user['role'] in ('مدیر', 'مدیر سیستم', 'امور مالی') or user_has_access(current_user, 'reports')):
            # fallback soft: managers/reception
            if current_user['role'] not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم', 'امور مالی'):
                return redirect('/')

        date_from = (request.args.get('date_from') or '').strip()
        date_to = (request.args.get('date_to') or '').strip()
        service_kind = (request.args.get('service_kind') or '').strip()
        province = (request.args.get('province') or '').strip()
        status = (request.args.get('status') or '').strip()
        serial = (request.args.get('serial') or '').strip()
        customer = (request.args.get('customer') or '').strip()
        technician = (request.args.get('technician') or '').strip()
        q = (request.args.get('q') or '').strip()
        export_mode = (request.args.get('export') or '').strip()
        do_export = export_mode in ('1', 'xlsx', 'excel')
        do_pdf = export_mode == 'pdf'

        conn = get_db()
        sql = 'SELECT * FROM requests WHERE 1=1'
        params = []

        if service_kind == 'internal':
            sql += " AND request_category = 'تعمیر' AND service_type = 'کارخانه'"
        elif service_kind == 'external':
            sql += " AND request_category = 'تعمیر' AND service_type = 'در محل'"
        elif service_kind == 'installation':
            sql += " AND request_category = 'نصب و آموزش'"
        elif service_kind == 'inspection':
            sql += " AND request_category = 'بررسی و بازدید'"
        elif service_kind == 'demo':
            sql += " AND (request_category LIKE '%Demo%' OR request_category LIKE '%دمو%' OR request_subtype LIKE '%Demo%')"

        if province:
            sql += ' AND province = ?'
            params.append(province)
        if serial:
            sql += ' AND IFNULL(serial_number,'') LIKE ?'
            params.append('%' + serial + '%')
        if customer:
            sql += ' AND IFNULL(customer_name,'') LIKE ?'
            params.append('%' + customer + '%')
        if technician:
            sql += ' AND IFNULL(assigned_technician,'') LIKE ?'
            params.append('%' + technician + '%')

        sql += ' ORDER BY id DESC LIMIT 2000'
        raw = conn.execute(sql, params).fetchall()
        enriched = _enrich_delay(conn, raw)
        enriched = _filter_by_date_range(enriched, date_from or None, date_to or None, 'reception_date')

        closed_set = set(CLOSED_STATUSES)

        if status == 'open':
            enriched = [r for r in enriched if (r.get('status') or '') not in closed_set]
        elif status == 'closed':
            enriched = [r for r in enriched if (r.get('status') or '') in closed_set]
        elif status:
            enriched = [r for r in enriched if (r.get('status') or '') == status]

        if q:
            ql = q.lower()
            def _match_q(r):
                fields = [
                    str(r.get('id') or ''), r.get('customer_name') or '',
                    r.get('serial_number') or '', r.get('device_type') or '',
                    r.get('assigned_technician') or '', r.get('problem_desc') or '',
                ]
                return any(ql in (f or '').lower() for f in fields)
            enriched = [r for r in enriched if _match_q(r)]

        def service_label(r):
            cat = r.get('request_category') or ''
            st = r.get('service_type') or ''
            sub = r.get('request_subtype') or ''
            if cat == 'تعمیر' and st == 'کارخانه':
                return 'تعمیر داخلی'
            if cat == 'تعمیر' and st == 'در محل':
                return 'تعمیر خارجی'
            if cat == 'نصب و آموزش':
                return 'نصب — ' + (sub or 'آموزش')
            if cat == 'بررسی و بازدید':
                return 'بازدید'
            if 'Demo' in cat or 'دمو' in cat:
                return 'دمو / امانی'
            return cat or st or '—'

        for r in enriched:
            r['service_label'] = service_label(r)

        summary = {
            'total': len(enriched),
            'open': sum(1 for r in enriched if (r.get('status') or '') not in closed_set),
            'closed': sum(1 for r in enriched if (r.get('status') or '') in closed_set),
            'delayed': sum(1 for r in enriched if r.get('is_delayed')),
        }

        # status options from data
        status_options = sorted({(r.get('status') or '') for r in enriched if r.get('status')})

        # صفحه‌بندی (۱۰۰ پرونده در هر صفحه) - بعد از محاسبه summary تا آمار کلی درست بمونه
        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        pg = paginate(enriched, page=parse_page(request.args), per_page=parse_per_page(request.args, 50))
        page_rows = pg['items']
        pg_ctx = pagination_context(pg, request.args)
        page = pg_ctx['page']
        total_pages = pg_ctx['total_pages']
        total_rows = pg_ctx['total_rows']

        # حالت بایگانی: وقتی status=closed از منوی «بایگانی» وارد شده باشیم، عنوان و برچسب صفحه فرق می‌کنه
        archive_mode = (status == 'closed')

        if do_export:
            if openpyxl is None:
                conn.close()
                return 'openpyxl نصب نیست', 500
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = 'عملکرد خدمات'
            ws.append(['کد', 'تاریخ', 'نوع سرویس', 'مشتری', 'سریال', 'دستگاه', 'استان', 'تکنسین', 'وضعیت', 'روز در وضعیت'])
            for r in enriched:
                ws.append([
                    r.get('id'), r.get('reception_date'), r.get('service_label'),
                    r.get('customer_name'), r.get('serial_number'), r.get('device_type'),
                    r.get('province'), r.get('assigned_technician'), r.get('status'),
                    r.get('days_in_status'),
                ])
            conn.close()
            out = BytesIO()
            wb.save(out)
            out.seek(0)
            return send_file(
                out,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='service_performance.xlsx',
            )

        if do_pdf:
            try:
                from reportlab.lib.pagesizes import A4, landscape
                from reportlab.pdfgen import canvas
                from reportlab.lib.units import mm
                buf = BytesIO()
                c = canvas.Canvas(buf, pagesize=landscape(A4))
                width, height = landscape(A4)
                y = height - 12 * mm
                c.setFont('Helvetica-Bold', 11)
                c.drawString(12 * mm, y, 'Sazgan - Service Performance Report')
                y -= 7 * mm
                c.setFont('Helvetica', 8)
                for r in enriched[:200]:
                    line = '%s | %s | %s | %s | %s' % (
                        r.get('reception_no') or r.get('id') or '',
                        (r.get('customer_name') or '')[:28],
                        (r.get('service_label') or '')[:18],
                        (r.get('status') or '')[:22],
                        (r.get('invoice_number') or ''),
                    )
                    c.drawString(12 * mm, y, line)
                    y -= 4.5 * mm
                    if y < 10 * mm:
                        c.showPage()
                        y = height - 12 * mm
                        c.setFont('Helvetica', 8)
                c.save()
                buf.seek(0)
                conn.close()
                return send_file(
                    buf,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name='service_performance.pdf',
                )
            except Exception:
                pass

        # build export url with same filters
        from urllib.parse import urlencode
        export_q = {k: v for k, v in {
            'date_from': date_from, 'date_to': date_to, 'service_kind': service_kind,
            'province': province, 'status': status, 'serial': serial,
            'customer': customer, 'technician': technician, 'q': q, 'export': '1',
        }.items() if v}
        export_url = '/reports/service-performance?' + urlencode(export_q)

        # برای لینک‌های صفحه‌بندی، همه‌ی فیلترهای فعلی رو نگه می‌داریم و فقط page عوض می‌شه
        page_q = {k: v for k, v in {
            'date_from': date_from, 'date_to': date_to, 'service_kind': service_kind,
            'province': province, 'status': status, 'serial': serial,
            'customer': customer, 'technician': technician, 'q': q,
        }.items() if v}

        conn.close()
        return render_template(
            'report_service_performance.html',
            rows=page_rows,
            summary=summary,
            provinces=PROVINCES,
            status_options=status_options,
            date_from=date_from,
            date_to=date_to,
            service_kind=service_kind,
            province=province,
            status=status,
            serial=serial,
            customer=customer,
            technician=technician,
            q=q,
            export_url=export_url,
            page=page,
            total_pages=total_pages,
            total_rows=total_rows,
            page_qs=pg_ctx.get('page_qs') or urlencode(page_q),
            **{k: v for k, v in pg_ctx.items() if k not in ('page', 'total_pages', 'total_rows', 'page_qs')},
            archive_mode=archive_mode,
            active_page='archive' if archive_mode else 'report-service-performance',
            current_user=current_user,
        )

