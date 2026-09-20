# -*- coding: utf-8 -*-
"""JSON API endpoints added specifically for native_client/ (PyQt5 app).

Existing HTML routes in routes/*.py and core/control_warehouses.py are
untouched. Each endpoint here mirrors the same query logic as its HTML
counterpart, but returns JSON. Add one function here per screen as the
native client grows (see native_client/README.md).
"""
from __future__ import annotations

import logging

from flask import request, jsonify, current_app

logger = logging.getLogger("sazgan")

from core.helpers import *  # noqa: F401,F403  (get_db, get_current_user, ...)
from core.constants import *  # noqa: F401,F403
from core.control_warehouses import ensure_control_wh_schema
from routes.data_hub import EXPORT_TARGETS, IMPORT_TARGETS, _allowed_targets
from routes.features import ensure_features_schema, _feat_today


def register(app):

    def _as_user_dict(user):
        """Normalize get_current_user() result (sqlite3.Row or dict) to a plain dict.

        sqlite3.Row supports key access like row['role'] but does NOT implement
        .get(), so any code path that calls user.get(...) will crash unless we
        convert first.
        """
        if not user:
            return None
        if isinstance(user, dict):
            return user
        try:
            return dict(user)
        except (TypeError, ValueError):
            try:
                return {key: user[key] for key in user.keys()}
            except Exception:
                return None

    @app.route('/api/native/me')
    def native_me():
        current_user = _as_user_dict(get_current_user())
        if not current_user:
            return jsonify({'error':'auth_required'}), 401
        try:
            from core.helpers import user_has_access
            permissions = {}
            for key in ('customer_affairs','warehouse','finance','reports','dashboard','parties','system','products'):
                permissions[key] = bool(user_has_access(current_user, key))
        except Exception:
            permissions = {}
        import jdatetime
        today = jdatetime.date.today()
        return jsonify({
            'username': current_user.get('username') or '',
            'full_name': current_user.get('full_name') or current_user.get('name') or current_user.get('username') or '',
            'role': current_user.get('role') or '',
            'company_name': current_user.get('company_name') or 'سازگان',
            'header_date': f'{today.year}/{today.month:02d}/{today.day:02d}',
            'permissions': permissions,
        })


    @app.route('/api/native/search')
    def native_search():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error':'auth_required'}), 401
        q=(request.args.get('q') or '').strip(); results=[]
        if q:
            like=f'%{q}%'; conn=get_db()
            rows=conn.execute("""SELECT id, reception_no, customer_name, serial_number, device_type, status, request_category, reception_date
                FROM requests WHERE customer_name LIKE ? OR serial_number LIKE ? OR CAST(id AS TEXT)=?
                OR IFNULL(reception_no,'') LIKE ? OR IFNULL(invoice_number,'') LIKE ?
                OR IFNULL(tracking_number,'') LIKE ? OR problem_desc LIKE ?
                ORDER BY id DESC LIMIT 100""",(like,like,q,like,like,like,like)).fetchall()
            for r in rows:
                results.append({'type':'requests','type_label':'درخواست','title':f"درخواست تعمیر {r['device_type'] or ''}".strip(),'subtitle':r['reception_no'] or ('#'+str(r['id'])),'meta':[('مشتری',r['customer_name'] or '—'),('ثبت شده در',r['reception_date'] or '—'),('سریال',r['serial_number'] or '—')],'status':r['status'] or ''})
            conn.close()
        return jsonify({'q':q,'results':results})

    @app.route('/api/native/notifications')
    def native_notifications():
        current_user=get_current_user()
        if not current_user: return jsonify({'error':'auth_required'}),401
        conn=get_db(); rows=conn.execute('SELECT * FROM notifications WHERE user_name=? ORDER BY id DESC LIMIT 500',(current_user['full_name'],)).fetchall(); unread=sum(1 for r in rows if not r['is_read']); payload=[dict(r) for r in rows]; conn.close()
        return jsonify({'rows':payload,'unread_count':unread})

    @app.route('/api/native/notifications/read/<int:nid>', methods=['POST'])
    def native_notification_read(nid):
        current_user=get_current_user()
        if not current_user: return jsonify({'error':'auth_required'}),401
        conn=get_db(); conn.execute('UPDATE notifications SET is_read=1 WHERE id=? AND user_name=?',(nid,current_user['full_name'])); conn.commit(); conn.close(); return jsonify({'ok':True})

    @app.route('/api/native/notifications/read-all', methods=['POST'])
    def native_notifications_read_all():
        current_user=get_current_user()
        if not current_user: return jsonify({'error':'auth_required'}),401
        conn=get_db(); conn.execute('UPDATE notifications SET is_read=1 WHERE user_name=?',(current_user['full_name'],)); conn.commit(); conn.close(); return jsonify({'ok':True})


    # ---- CSRF: session-cookie POSTs from the native client need a token ----
    # (core/security.py enforces csrf_token on every POST once 'user_id' is
    # in session; the native client authenticates via the same session
    # cookie as the browser, so it needs a way to fetch that token too.)

    @app.route('/api/native/csrf-token')
    def native_csrf_token():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        from core.security import ensure_csrf_token
        return jsonify({'csrf_token': ensure_csrf_token()})

    # ---- Public login-screen info (no auth): company name + support ----
    # contact, mirroring _company_login_ctx() in routes/auth.py so the
    # native login screen can show the same support panel as the web one.
    @app.route('/api/native/login-info')
    def native_login_info():
        try:
            conn = get_db()
            def gs(k, d=''):
                try:
                    return get_setting(conn, k, d) or d
                except Exception:
                    return d
            info = {
                'company_name': gs('company_name', 'سازگان'),
                'company_mobile': gs('company_mobile', ''),
                'company_phone': gs('company_phone', ''),
                'company_address': gs('company_address', ''),
            }
            conn.close()
        except Exception:
            info = {'company_name': 'سازگان', 'company_mobile': '', 'company_phone': '', 'company_address': ''}
        return jsonify(info)

    # ---- support (internal staff chat - not the customer chat) ----

    @app.route('/api/native/support/inbox')
    def native_support_inbox():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        from core.support_chat import list_threads, ensure_support_schema
        from routes.support import _is_staff

        status = (request.args.get('status') or 'باز').strip()
        q = (request.args.get('q') or '').strip()
        if status not in ('باز', 'بسته', 'all'):
            status = 'باز'
        conn = get_db()
        ensure_support_schema(conn)
        staff = _is_staff(current_user)
        threads = list_threads(conn, status=status, q=q, user=current_user, is_staff=staff)
        open_n = conn.execute("SELECT COUNT(*) c FROM support_threads WHERE status='باز'").fetchone()['c']
        closed_n = conn.execute("SELECT COUNT(*) c FROM support_threads WHERE status='بسته'").fetchone()['c']
        conn.close()
        return jsonify({
            'threads': [dict(t) for t in threads],
            'open_count': open_n, 'closed_count': closed_n, 'is_staff': staff,
        })

    @app.route('/api/native/support/thread/<int:thread_id>/close', methods=['POST'])
    def native_support_close(thread_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        from core.support_chat import close_thread, reopen_thread, ensure_support_schema
        conn = get_db()
        ensure_support_schema(conn)
        action = (request.form.get('action') or 'close').strip()
        if action == 'reopen':
            reopen_thread(conn, thread_id)
        else:
            close_thread(conn, thread_id, current_user)
        conn.close()
        return jsonify({'ok': True})

    # ---- improvements.py -----------------------------------------

    @app.route('/api/native/finance/wage-report')
    def native_wage_report():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in ('مسئول پذیرش', 'امور مالی', 'مدیر', 'مدیر سیستم'):
            return jsonify({'error': 'forbidden'}), 403
        import jdatetime
        today = jdatetime.date.today()
        year = int(request.args.get('year') or today.year)
        month = int(request.args.get('month') or today.month)
        conn = get_db()
        rows = []
        try:
            for r in conn.execute('SELECT * FROM wage_calculations ORDER BY id DESC').fetchall():
                d = (r['calc_date'] or '') if 'calc_date' in r.keys() else ''
                p = d.replace('-', '/').split('/')
                try:
                    if len(p) >= 2 and int(p[0]) == year and int(p[1]) == month:
                        rows.append(dict(r))
                except Exception as e:
                    logger.exception("Silent exception in routes/native_api.py")
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        conn.close()
        total = sum(float(r.get('amount') or 0) for r in rows)
        return jsonify({'rows': rows, 'year': year, 'month': month, 'total': total})

    @app.route('/api/native/reports/manager-dashboard')
    def native_manager_dashboard():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم', 'امور مالی'):
            return jsonify({'error': 'forbidden'}), 403
        from routes.improvements import CLOSED_STATUSES
        conn = get_db()
        total = conn.execute('SELECT COUNT(*) AS c FROM requests').fetchone()['c']
        open_n = conn.execute(
            'SELECT COUNT(*) AS c FROM requests WHERE status NOT IN (%s)'
            % ','.join(['?'] * len(CLOSED_STATUSES)),
            tuple(CLOSED_STATUSES),
        ).fetchone()['c']
        rejected = conn.execute(
            "SELECT COUNT(*) AS c FROM requests WHERE status LIKE '%رد پیش‌فاکتور%'"
        ).fetchone()['c']
        by_prov = conn.execute(
            'SELECT province, COUNT(*) AS c FROM requests GROUP BY province ORDER BY c DESC LIMIT 15'
        ).fetchall()
        by_st = conn.execute(
            'SELECT status, COUNT(*) AS c FROM requests GROUP BY status ORDER BY c DESC LIMIT 15'
        ).fetchall()
        conn.close()
        return jsonify({
            'total': total, 'open': open_n, 'rejected': rejected,
            'by_province': [dict(r) for r in by_prov],
            'by_status': [dict(r) for r in by_st],
        })

    @app.route('/api/native/security/audit-filter')
    def native_audit_filter():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم'):
            return jsonify({'error': 'forbidden'}), 403
        q = (request.args.get('q') or '').strip()
        action = (request.args.get('action') or '').strip()
        conn = get_db()
        rows = []
        try:
            sql = 'SELECT * FROM audit_log WHERE 1=1'
            params = []
            if action:
                sql += ' AND action LIKE ?'
                params.append('%' + action + '%')
            if q:
                sql += " AND (IFNULL(details,'') LIKE ? OR IFNULL(user_name,'') LIKE ? OR CAST(entity_id AS TEXT) LIKE ?)"
                params.extend(['%' + q + '%', '%' + q + '%', '%' + q + '%'])
            sql += ' ORDER BY id DESC LIMIT 200'
            rows = conn.execute(sql, params).fetchall()
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        conn.close()
        return jsonify({'rows': [dict(r) for r in rows]})

    # ---- finance --------------------------------------------------

    def _ym(req):
        import jdatetime
        today = jdatetime.date.today()
        year, month = today.year, today.month
        try:
            if req.args.get('year'):
                year = int(req.args.get('year'))
            if req.args.get('month'):
                month = max(1, min(12, int(req.args.get('month'))))
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        return year, month

    @app.route('/api/native/finance/reps-dashboard')
    def native_finance_reps_dashboard():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        from core.wages import ensure_wage_schema, summarize_rep_wages, get_rep_bank_info

        year, month = _ym(request)
        conn = get_db()
        ensure_wage_schema(conn)
        reps = conn.execute(
            "SELECT * FROM representatives WHERE COALESCE(status,'فعال') != 'بایگانی' ORDER BY first_name, company_name"
        ).fetchall()
        rows = []
        for rep in reps:
            rid = rep['id']
            name = ((rep['first_name'] or '') + ' ' + (rep['last_name'] or '')).strip() or (rep['company_name'] or ('#' + str(rid)))
            s = summarize_rep_wages(conn, rid, year, month)
            rows.append({
                'id': rid, 'name': name,
                'province': rep['province'] if 'province' in rep.keys() else '',
                'month_total': s['month_total'], 'year_total': s['year_total'],
                'unpaid_month': s['unpaid_month'], 'paid_month': s['paid_month'],
                'settle_status': s['settle_status'],
            })
        conn.close()
        rows.sort(key=lambda x: (-x['unpaid_month'], -x['month_total'], x['name']))
        return jsonify({'rows': rows, 'year': year, 'month': month})

    @app.route('/api/native/finance/wage-history')
    def native_finance_wage_history():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        conn = get_db()
        calcs = conn.execute('SELECT * FROM wage_calculations ORDER BY id DESC LIMIT 500').fetchall()
        conn.close()
        return jsonify({'rows': [dict(r) for r in calcs]})

    @app.route('/api/native/finance/my-wages')
    def native_my_wages():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        from core.wages import ensure_wage_schema, summarize_rep_wages, get_rep_bank_info, month_name_fa

        year, month = _ym(request)
        try:
            rid = current_user['representative_id']
            rep_id = int(rid) if rid else None
        except Exception:
            rep_id = None

        conn = get_db()
        ensure_wage_schema(conn)
        summary = {'month_total': 0, 'year_total': 0, 'unpaid_month': 0, 'paid_month': 0, 'month_rows': []}
        if rep_id:
            summary = summarize_rep_wages(conn, rep_id, year, month)
        conn.close()
        return jsonify({
            'has_rep_link': bool(rep_id),
            'year': year, 'month': month, 'month_label': month_name_fa(month),
            'month_total': summary['month_total'], 'year_total': summary['year_total'],
            'unpaid_month': summary['unpaid_month'], 'paid_month': summary['paid_month'],
            'rows': [dict(r) for r in summary['month_rows']],
        })

    # ---- reports ---------------------------------------------------

    @app.route('/api/native/reports/dashboard')
    def native_reports_dashboard():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        conn = get_db()
        closed = ('پایان تعمیرات', 'پایان', 'تحویل شد', 'بسته شد', 'نصب انجام شد', 'بازدید انجام شد')
        all_rows = conn.execute('SELECT * FROM requests').fetchall()

        def is_closed(r):
            return (r['status'] or '') in closed

        open_rows = [r for r in all_rows if not is_closed(r)]
        closed_rows = [r for r in all_rows if is_closed(r)]

        by_cat = {'تعمیر داخلی': 0, 'تعمیر خارجی': 0, 'نصب و آموزش': 0, 'بررسی و بازدید': 0, 'سایر': 0}
        open_by_cat = dict(by_cat)
        for r, target in [(x, by_cat) for x in all_rows] + [(x, open_by_cat) for x in open_rows]:
            cat = r['request_category'] or ''
            st = r['service_type'] or ''
            if cat == 'تعمیر' and st == 'کارخانه':
                target['تعمیر داخلی'] += 1
            elif cat == 'تعمیر' and st == 'در محل':
                target['تعمیر خارجی'] += 1
            elif cat == 'نصب و آموزش':
                target['نصب و آموزش'] += 1
            elif cat == 'بررسی و بازدید':
                target['بررسی و بازدید'] += 1
            else:
                target['سایر'] += 1

        province_counts = {}
        for r in open_rows:
            prov = r['province'] or 'نامشخص'
            province_counts[prov] = province_counts.get(prov, 0) + 1
        province_top = sorted(province_counts.items(), key=lambda x: -x[1])[:12]

        enriched = _enrich_delay(conn, open_rows)
        delayed = [e for e in enriched if e.get('is_delayed')]
        days_list = [e.get('days_in_status') or 0 for e in enriched]
        avg_days = round(sum(days_list) / len(days_list), 1) if days_list else 0
        conn.close()

        return jsonify({
            'total': len(all_rows), 'open': len(open_rows), 'closed': len(closed_rows),
            'by_cat': by_cat, 'open_by_cat': open_by_cat,
            'province_top': province_top,
            'delayed_count': len(delayed), 'avg_days': avg_days,
        })

    @app.route('/api/native/reports/management')
    def native_reports_management():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        conn = get_db()
        all_rows = conn.execute("SELECT * FROM requests").fetchall()
        closed_set = ('پایان تعمیرات', 'پایان', 'تحویل شد', 'بسته شد', 'نصب انجام شد', 'بازدید انجام شد')
        open_rows = [r for r in all_rows if (r['status'] or '') not in closed_set]
        closed_rows = [r for r in all_rows if (r['status'] or '') in closed_set]
        enriched_open = _enrich_delay(conn, open_rows)
        delayed = [e for e in enriched_open if e.get('is_delayed')]

        def _cat(r):
            return r['request_category'] or ''

        def _svc(r):
            return r['service_type'] or ''

        n_internal = sum(1 for r in all_rows if _cat(r) == 'تعمیر' and _svc(r) == 'کارخانه')
        n_external = sum(1 for r in all_rows if _cat(r) == 'تعمیر' and _svc(r) == 'در محل')
        n_install = sum(1 for r in all_rows if _cat(r) == 'نصب و آموزش')
        n_visit = sum(1 for r in all_rows if _cat(r) == 'بررسی و بازدید')

        by_tech, by_prov = {}, {}
        for e in delayed:
            tech = e.get('assigned_technician') or 'بدون تکنسین'
            prov = e.get('province') or 'نامشخص'
            by_tech[tech] = by_tech.get(tech, 0) + 1
            by_prov[prov] = by_prov.get(prov, 0) + 1
        days = [e.get('days_in_status') or 0 for e in enriched_open]
        avg = round(sum(days) / len(days), 1) if days else 0
        conn.close()

        return jsonify({
            'by_tech': sorted(by_tech.items(), key=lambda x: -x[1]),
            'by_prov': sorted(by_prov.items(), key=lambda x: -x[1]),
            'avg_days': avg, 'delayed_total': len(delayed),
            'open_total': len(open_rows), 'closed_total': len(closed_rows),
            'total_accept': len(all_rows),
            'n_internal': n_internal, 'n_external': n_external,
            'n_install': n_install, 'n_visit': n_visit,
        })

    # ---- data hub (import/export) --------------------------------

    @app.route('/api/native/data-hub/targets')
    def native_data_hub_targets():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        return jsonify({
            'export_targets': _allowed_targets(EXPORT_TARGETS, current_user),
            'import_targets': _allowed_targets(IMPORT_TARGETS, current_user),
        })

    # ---- warehouse (mirrors core/control_warehouses.py) ----------

    @app.route('/api/native/warehouse/internal')
    def native_warehouse_internal():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401

        conn = get_db()
        ensure_control_wh_schema(conn)
        try:
            rows = conn.execute(
                """
                SELECT rp.id, rp.request_id, rp.warehouse_code, rp.part_name, rp.quantity,
                       rp.serial_good, rp.serial_defective, rp.serial_healthy, rp.serial_faulty,
                       COALESCE(rp.created_at, r.reception_date) AS created_at,
                       r.reception_no, r.device_type, r.device_model, r.assigned_technician, r.status
                FROM request_parts rp
                JOIN requests r ON r.id = rp.request_id
                WHERE IFNULL(rp.is_void,0)=0 AND r.service_type = 'کارخانه'
                ORDER BY rp.id DESC
                LIMIT 500
                """
            ).fetchall()
        except Exception:
            rows = []
        conn.close()

        q = (request.args.get('q') or '').strip().lower()
        result = [dict(r) for r in rows]
        if q:
            def _blob(d):
                return ' '.join(str(d.get(k) or '') for k in (
                    'reception_no', 'request_id', 'warehouse_code', 'part_name',
                    'serial_good', 'serial_defective', 'serial_healthy', 'serial_faulty',
                    'device_type', 'assigned_technician',
                )).lower()
            result = [d for d in result if q in _blob(d)]

        return jsonify({'rows': result})

    @app.route('/api/native/warehouse/external')
    def native_warehouse_external():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401

        province_filter = (request.args.get('province') or '').strip()
        q = (request.args.get('q') or '').strip().lower()

        conn = get_db()
        ensure_control_wh_schema(conn)
        try:
            rows = conn.execute(
                """
                SELECT rp.id, rp.request_id, rp.warehouse_code, rp.part_name, rp.quantity,
                       rp.serial_good, rp.serial_defective, rp.serial_healthy, rp.serial_faulty,
                       COALESCE(rp.created_at, r.reception_date) AS created_at,
                       r.reception_no, r.device_type, r.device_model, r.assigned_technician AS representative_name,
                       r.province, r.status
                FROM request_parts rp
                JOIN requests r ON r.id = rp.request_id
                WHERE IFNULL(rp.is_void,0)=0 AND r.service_type = 'در محل'
                  AND IFNULL(r.request_category,'') LIKE '%تعمیر%'
                ORDER BY rp.id DESC
                LIMIT 500
                """
            ).fetchall()
        except Exception:
            rows = []

        provinces = sorted({
            (r['province'] or '')
            for r in conn.execute(
                "SELECT DISTINCT province FROM requests WHERE service_type='در محل' AND province IS NOT NULL AND province != ''"
            ).fetchall()
            if r['province']
        })
        conn.close()

        result = [dict(r) for r in rows]
        if province_filter:
            result = [d for d in result if (d.get('province') or '') == province_filter]
        if q:
            def _blob(d):
                return ' '.join(str(d.get(k) or '') for k in (
                    'reception_no', 'request_id', 'warehouse_code', 'part_name',
                    'serial_good', 'serial_defective', 'serial_healthy', 'serial_faulty',
                    'province', 'representative_name', 'assigned_technician',
                )).lower()
            result = [d for d in result if q in _blob(d)]

        return jsonify({'rows': result, 'provinces': provinces})

    # ---- service.py (customer-affairs hub + archive/list layer) --

    @app.route('/api/native/service/hub')
    def native_service_hub():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if not user_has_access(current_user, 'customer_affairs'):
            return jsonify({'error': 'forbidden'}), 403
        cats = []
        for slug, cfg in SERVICE_CATEGORIES.items():
            cats.append({
                'slug': slug,
                'title': cfg.get('title'),
                'new_label': cfg.get('new_label'),
                'archive_label': cfg.get('archive_label'),
            })
        return jsonify({'categories': cats, 'can_reception': current_user['role'] in RECEPTION_ROLES})

    def _service_list_common(rows, args, extra_filter=True):
        """فیلترهای مشترک تاریخ/استان/وضعیت/تأخیر/جست‌وجو برای فهرست‌های خدمات."""
        conn = get_db()
        enriched = _enrich_delay(conn, rows)
        conn.close()
        date_from = (args.get('date_from') or '').strip()
        date_to = (args.get('date_to') or '').strip()
        province = (args.get('province') or '').strip()
        city = (args.get('city') or '').strip()
        status = (args.get('status') or '').strip()
        technician = (args.get('technician') or '').strip()
        device_type = (args.get('device_type') or '').strip()
        device_model = (args.get('device_model') or '').strip()
        q = (args.get('q') or '').strip()
        only_delayed = args.get('only_delayed') == '1'
        enriched = _filter_by_date_range(enriched, date_from or None, date_to or None)
        if extra_filter:
            enriched = _filter_rows(
                enriched, province=province or None, status=status or None,
                only_delayed=only_delayed, city=city or None, technician=technician or None,
                device_type=device_type or None, device_model=device_model or None,
            )
        else:
            enriched = _filter_rows(enriched, province=province or None, status=status or None, only_delayed=only_delayed)
        if q:
            try:
                from core.request_utils import search_rows as _search_rows
                enriched = _search_rows(enriched, q)
            except Exception as e:
                logger.exception("Silent exception in routes/native_api.py")
        return enriched, {
            'date_from': date_from, 'date_to': date_to, 'province': province, 'city': city,
            'status': status, 'technician': technician, 'device_type': device_type,
            'device_model': device_model, 'q': q, 'only_delayed': only_delayed,
        }

    def _paginated(rows, args):
        from core.pagination import parse_page, parse_per_page, paginate
        pg = paginate(rows, page=parse_page(args), per_page=parse_per_page(args, 25))
        return pg['items'], {
            'page': pg['page'], 'per_page': pg['per_page'], 'total': pg['total'],
            'total_pages': pg['total_pages'], 'has_prev': pg['has_prev'], 'has_next': pg['has_next'],
        }

    @app.route('/api/native/service/<slug>/archive')
    def native_service_archive(slug):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        if slug not in SERVICE_CATEGORIES:
            return jsonify({'error': 'not_found'}), 404
        if slug in ('installation', 'inspection'):
            return jsonify({'error': 'use_dedicated_endpoint'}), 400

        cfg = SERVICE_CATEGORIES[slug]
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM requests WHERE request_category = ? AND service_type = ? ORDER BY id DESC",
            (cfg['category'], cfg['service_type'])
        ).fetchall()
        conn.close()

        enriched, filters = _service_list_common(rows, request.args)
        open_rows, closed_rows = _split_open_closed(enriched)
        shown, pg = _paginated(open_rows, request.args)

        statuses = INTERNAL_REPAIR_STATUSES if slug == 'internal-repair' else (
            EXTERNAL_REPAIR_STATUSES if slug == 'external-repair' else [])
        return jsonify({
            'requests': shown, 'statuses': statuses, 'title': cfg.get('archive_label'),
            'filters': filters, 'pagination': pg,
        })

    @app.route('/api/native/service/installation/requests')
    def native_installation_requests():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        conn = get_db()
        rows = conn.execute(
            """SELECT * FROM requests
               WHERE request_category = 'نصب و آموزش' AND request_subtype = 'درخواست نصب'
               ORDER BY id DESC"""
        ).fetchall()
        conn.close()
        enriched, filters = _service_list_common(rows, request.args, extra_filter=False)
        open_rows, closed_rows = _split_open_closed(enriched)
        shown, pg = _paginated(open_rows, request.args)
        return jsonify({
            'requests': shown, 'statuses': INSTALLATION_REQUEST_STATUSES,
            'title': 'درخواست‌های نصب', 'filters': filters, 'pagination': pg,
        })

    @app.route('/api/native/service/installation/registers')
    def native_installation_registers():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        conn = get_db()
        rows = conn.execute(
            """SELECT * FROM requests
               WHERE request_category = 'نصب و آموزش' AND request_subtype = 'ثبت نصب'
               ORDER BY id DESC"""
        ).fetchall()
        conn.close()
        shown, pg = _paginated([dict(r) for r in rows], request.args)
        return jsonify({'requests': shown, 'title': 'نصب انجام‌شده', 'pagination': pg})

    @app.route('/api/native/service/inspection/list')
    def native_inspection_list():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM requests WHERE request_category = 'بررسی و بازدید' ORDER BY id DESC"
        ).fetchall()
        conn.close()
        tab = (request.args.get('tab') or 'requests').strip() or 'requests'
        enriched, filters = _service_list_common(rows, request.args, extra_filter=False)
        open_rows, closed_rows = _split_open_closed(enriched)
        if tab == 'reports':
            shown_all = list(open_rows)
            title = 'بررسی و بازدید انجام‌شده'
        else:
            shown_all = open_rows
            title = 'درخواست بررسی و بازدید'
            tab = 'requests'
        shown, pg = _paginated(shown_all, request.args)
        return jsonify({
            'requests': shown, 'statuses': VISIT_STATUSES, 'title': title,
            'tab': tab, 'filters': filters, 'pagination': pg,
        })

    # ---- service - new-record creation (native "ثبت جدید" tab) --
    # Rather than duplicating the insert/numbering/history logic, each
    # endpoint below calls the existing HTML-form view function *from within
    # this same request* (request.form/request.files are the same Flask
    # request-context proxy, so they see this request's POST body) and reads
    # the record id back off the Location header of the redirect it returns.
    # This guarantees identical business logic to the web form, at the cost
    # of the wrapped function occasionally rendering its own HTML error page
    # instead of redirecting (see installation/register-new below) - those
    # cases are reported as a generic failure since we don't scrape HTML.

    import re as _re

    def _id_from_redirect(resp):
        loc = resp.headers.get('Location', '') if hasattr(resp, 'headers') else ''
        m = _re.search(r'/(\d+)(?:$|\?)', loc)
        if m:
            return int(m.group(1)), loc
        m = _re.search(r'[?&]saved=(\d+)', loc)
        if m:
            return int(m.group(1)), loc
        return None, loc

    @app.route('/api/native/service/internal-repair/new', methods=['POST'])
    def native_internal_repair_new():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        from core.helpers import internal_repair_new
        resp = internal_repair_new()
        new_id, loc = _id_from_redirect(resp)
        if new_id:
            return jsonify({'ok': True, 'id': new_id})
        return jsonify({'ok': False, 'error': 'ثبت تعمیر داخلی ناموفق بود.'}), 400

    @app.route('/api/native/service/external-repair/new', methods=['POST'])
    def native_external_repair_new():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        from core.helpers import external_repair_new
        resp = external_repair_new()
        new_id, loc = _id_from_redirect(resp)
        if new_id:
            return jsonify({'ok': True, 'id': new_id})
        return jsonify({'ok': False, 'error': 'ثبت تعمیر خارجی ناموفق بود.'}), 400

    @app.route('/api/native/service/installation/request-new', methods=['POST'])
    def native_installation_request_new():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        # installation_request_new is a closure nested inside routes/service_installation.py's
        # register(app) (فاز ۳: قبلاً در routes/service.py بود، حالا تفکیک شده) — نه به‌عنوان
        # attribute ماژول import-پذیره، پس از طریق view-function registry فلسک صداش می‌زنیم؛
        # این کار می‌کنه چون هر ۵ فایل service_*.register(app) قبل از native_api.register(app)
        # در app.py صدا زده می‌شن.
        resp = current_app.view_functions['installation_request_new']()
        new_id, loc = _id_from_redirect(resp)
        if new_id:
            return jsonify({'ok': True, 'id': new_id})
        return jsonify({'ok': False, 'error': 'ثبت درخواست نصب ناموفق بود.'}), 400

    @app.route('/api/native/service/installation/register-new', methods=['POST'])
    def native_installation_register_new():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        resp = current_app.view_functions['installation_register_new']()
        new_id, loc = _id_from_redirect(resp)
        if new_id:
            return jsonify({'ok': True, 'id': new_id})
        # validation failure re-renders the HTML form (status 200) instead of
        # redirecting - most common causes are an unregistered/inactive
        # serial number or a missing report file, so we surface those.
        return jsonify({
            'ok': False,
            'error': 'ثبت ناموفق بود: سریال باید قبلاً در کارت‌های گارانتی ثبت شده باشد و آپلود فایل گزارش نصب الزامی است.',
        }), 400

    @app.route('/api/native/service/inspection/request-new', methods=['POST'])
    def native_inspection_request_new():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        resp = current_app.view_functions['inspection_request_new']()
        new_id, loc = _id_from_redirect(resp)
        if new_id:
            return jsonify({'ok': True, 'id': new_id})
        return jsonify({'ok': False, 'error': 'ثبت درخواست بازدید ناموفق بود.'}), 400

    @app.route('/api/native/service/inspection/report-new', methods=['POST'])
    def native_inspection_report_new():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        resp = current_app.view_functions['inspection_report_new']()
        new_id, loc = _id_from_redirect(resp)
        if new_id:
            return jsonify({'ok': True, 'id': new_id})
        return jsonify({'ok': False, 'error': 'ثبت گزارش بازدید ناموفق بود.'}), 400

    def _authorize_service_action(req_id, action, *, category=None, service_type=None, subtype=None):
        """Fail closed before delegating any native action to an HTML route.

        The legacy view remains responsible for form validation and side effects,
        but Native API no longer reaches it without the central object/action policy.
        """
        conn = get_db()
        sql = "SELECT * FROM requests WHERE id=?"
        params = [req_id]
        if category:
            sql += " AND request_category=?"; params.append(category)
        if service_type:
            sql += " AND service_type=?"; params.append(service_type)
        if subtype:
            sql += " AND request_subtype=?"; params.append(subtype)
        req = conn.execute(sql, tuple(params)).fetchone()
        conn.close()
        if not req:
            return None, (jsonify({'error': 'not_found'}), 404)
        from core.workflow import can_act_on_request
        if not can_act_on_request(_as_user_dict(get_current_user()), req, action):
            return req, (jsonify({'error': 'forbidden'}), 403)
        return req, None

    # ---- internal-repair "نمای کامل پرونده" (detail + actions) --
    _ERR_MESSAGES = {
        'serial_required': 'سریال سالم و سریال خراب هر دو الزامی است.',
        'serial_duplicate': 'این سریال قبلاً در پرونده دیگری ثبت شده است.',
    }

    def _native_edit_options(conn, req):
        """Reference choices used by Native Edit without duplicating web business rules."""
        try:
            province = (req['province'] or '') if req and 'province' in req.keys() else ''
        except Exception:
            province = ''
        try:
            from core.geo import ensure_geo_schema, get_geo_cities
            ensure_geo_schema(conn)
            cities = get_geo_cities(conn, province or '', '') if province else []
        except Exception:
            cities = []
        try:
            device_type = (req['device_type'] or '') if req and 'device_type' in req.keys() else ''
            rows = conn.execute(
                "SELECT DISTINCT model FROM devices WHERE IFNULL(model,'')!='' AND (?='' OR device_type=?) ORDER BY model",
                (device_type or '', device_type or '')
            ).fetchall()
            models = [r[0] for r in rows]
        except Exception:
            models = []
        try:
            # The web edit routes use factory technicians only for internal repair;
            # installation/inspection assignments are provincial.
            category = (req['request_category'] or '') if req and 'request_category' in req.keys() else ''
            service_type = (req['service_type'] or '') if req and 'service_type' in req.keys() else ''
            role_filter = "تکنسین کارخانه" if category == "تعمیر" and service_type == "کارخانه" else "تکنسین استانی"
        except Exception:
            role_filter = "تکنسین استانی"
        try:
            techs = [dict(r) for r in conn.execute(
                "SELECT id, full_name, province FROM users WHERE role = ? AND IFNULL(is_active,1)=1 ORDER BY full_name",
                (role_filter,)
            ).fetchall()]
        except Exception:
            techs = []
        return {'city': cities, 'device_model': models, 'assigned_technician': techs}

    def _action_result(resp, fallback_error='عملیات ناموفق بود (دسترسی غیرمجاز یا ورودی نامعتبر).'):
        """POST handlers on the web view functions redirect back to the same
        page on success (optionally with ?err=... on a soft-validation
        failure); anything else (200 HTML re-render) means the role/action
        check itself failed."""
        loc = resp.headers.get('Location', '') if hasattr(resp, 'headers') else ''
        if not loc:
            return jsonify({'ok': False, 'error': fallback_error}), 400
        if 'err=' in loc:
            from urllib.parse import urlparse, parse_qs
            err = parse_qs(urlparse(loc).query).get('err', [''])[0]
            return jsonify({'ok': False, 'error': _ERR_MESSAGES.get(err, err or fallback_error)}), 400
        return jsonify({'ok': True})

    @app.route('/api/native/service/internal-repair/detail/<int:req_id>')
    def native_internal_repair_detail(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        conn = get_db()
        req = conn.execute(
            "SELECT * FROM requests WHERE id = ? AND service_type = 'کارخانه' AND request_category = 'تعمیر'",
            (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return jsonify({'error': 'not_found'}), 404

        from core.helpers import _finance_allowed_statuses_for, _load_attachments
        from core.workflow import can_view_request
        can_edit = current_user['role'] in RECEPTION_ROLES
        is_finance = current_user['role'] == FINANCE_ROLE
        is_qc = current_user['role'] == 'کنترل کیفیت'
        if not can_view_request(current_user, req):
            conn.close()
            return jsonify({'error': 'forbidden'}), 403
        is_assigned_tech = (
            current_user['role'] == 'تکنسین کارخانه'
            and bool(req['assigned_technician_id'])
            and int(req['assigned_technician_id']) == int(current_user['id'])
        )
        stage_dates = conn.execute(
            'SELECT * FROM request_stage_dates WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        req_parts = conn.execute(
            'SELECT * FROM request_parts WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        req_parts_dicts = [dict(p) for p in req_parts]
        req_parts_dicts = [p for p in req_parts_dicts if not p.get('is_void')]
        parts_catalog = conn.execute('SELECT id, part_name, warehouse_code FROM parts ORDER BY part_name').fetchall()
        technicians = conn.execute(
            "SELECT id, full_name FROM users WHERE role = 'تکنسین کارخانه' ORDER BY full_name"
        ).fetchall()
        attachments = [dict(a) for a in _load_attachments(conn, req_id)]
        finance_statuses = _finance_allowed_statuses_for(req)
        edit_options = _native_edit_options(conn, req)
        conn.close()
        case_history = []
        try:
            from core.history import get_case_history
            conn2 = get_db()
            case_history = get_case_history(conn2, req_id)
            conn2.close()
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        return jsonify({
            'request': dict(req),
            'statuses': INTERNAL_REPAIR_STATUSES,
            'stage_dates': [dict(s) for s in stage_dates],
            'parts': req_parts_dicts,
            'parts_catalog': [dict(p) for p in parts_catalog],
            'technicians': [dict(t) for t in technicians],
            'attachments': attachments,
            'finance_statuses': list(finance_statuses) if finance_statuses else [],
            'case_history': [dict(h) for h in case_history] if case_history else [],
            'permissions': {
                'can_edit': can_edit, 'is_assigned_tech': is_assigned_tech,
                'is_qc': is_qc, 'is_finance': is_finance,
            },
            'edit_options': edit_options,
        })

    @app.route('/api/native/service/internal-repair/action/<int:req_id>', methods=['POST'])
    def native_internal_repair_action(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        action = request.form.get('action', 'save')
        _req, denial = _authorize_service_action(req_id, action, category='تعمیر', service_type='کارخانه')
        if denial:
            return denial
        resp = current_app.view_functions['internal_repair_view'](req_id)
        return _action_result(resp)

    # ---- external-repair "نمای کامل پرونده" (detail + actions) ----
    @app.route('/api/native/service/external-repair/detail/<int:req_id>')
    def native_external_repair_detail(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        conn = get_db()
        req = conn.execute(
            "SELECT * FROM requests WHERE id = ? AND service_type = 'در محل' AND request_category = 'تعمیر'",
            (req_id,)
        ).fetchone()
        if not req:
            conn.close()
            return jsonify({'error': 'not_found'}), 404

        from core.helpers import _finance_allowed_statuses_for, _load_attachments
        from core.workflow import can_view_request
        can_edit = current_user['role'] in RECEPTION_ROLES
        is_finance = current_user['role'] == FINANCE_ROLE
        if not can_view_request(current_user, req):
            conn.close()
            return jsonify({'error': 'forbidden'}), 403
        is_assigned_tech = (
            current_user['role'] == 'تکنسین استانی'
            and bool(req['assigned_technician_id'])
            and int(req['assigned_technician_id']) == int(current_user['id'])
            and ((not req['province']) or (not current_user.get('province')) or req['province'] == current_user.get('province'))
        )
        stage_dates = conn.execute(
            'SELECT * FROM request_stage_dates WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        req_parts = conn.execute(
            'SELECT * FROM request_parts WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        req_parts_dicts = [p for p in (dict(p) for p in req_parts) if not p.get('is_void')]
        parts_catalog = conn.execute('SELECT id, part_name, warehouse_code FROM parts ORDER BY part_name').fetchall()
        technicians = conn.execute(
            "SELECT id, full_name, province FROM users WHERE role = 'تکنسین استانی' ORDER BY full_name"
        ).fetchall()
        attachments = [dict(a) for a in _load_attachments(conn, req_id)]
        finance_statuses = _finance_allowed_statuses_for(req)
        edit_options = _native_edit_options(conn, req)
        conn.close()
        case_history = []
        try:
            from core.history import get_case_history
            conn2 = get_db()
            case_history = get_case_history(conn2, req_id)
            conn2.close()
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        allowed_statuses = list(EXTERNAL_REPAIR_STATUSES)
        return jsonify({
            'request': dict(req),
            'statuses': list(dict.fromkeys(allowed_statuses)),
            'stage_dates': [dict(s) for s in stage_dates],
            'parts': req_parts_dicts,
            'parts_catalog': [dict(p) for p in parts_catalog],
            'technicians': [dict(t) for t in technicians],
            'attachments': attachments,
            'finance_statuses': list(finance_statuses) if finance_statuses else [],
            'case_history': [dict(h) for h in case_history] if case_history else [],
            'permissions': {
                'can_edit': can_edit, 'is_assigned_tech': is_assigned_tech,
                'is_qc': False, 'is_finance': is_finance,
            },
            'edit_options': edit_options,
        })

    @app.route('/api/native/service/external-repair/action/<int:req_id>', methods=['POST'])
    def native_external_repair_action(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        action = request.form.get('action', 'save')
        _req, denial = _authorize_service_action(req_id, action, category='تعمیر', service_type='در محل')
        if denial:
            return denial
        resp = current_app.view_functions['external_repair_view'](req_id)
        return _action_result(resp)

    # ---- installation request/register + inspection detail -------
    def _detail_common(req_id, category=None, subtype=None, service_type=None):
        conn = get_db()
        sql = "SELECT * FROM requests WHERE id = ?"
        params = [req_id]
        if category:
            sql += " AND request_category = ?"
            params.append(category)
        if subtype:
            sql += " AND request_subtype = ?"
            params.append(subtype)
        if service_type:
            sql += " AND service_type = ?"
            params.append(service_type)
        req = conn.execute(sql, params).fetchone()
        if not req:
            conn.close()
            return None, None
        from core.helpers import _load_attachments
        attachments = [dict(a) for a in _load_attachments(conn, req_id)]
        stage_dates = conn.execute(
            'SELECT * FROM request_stage_dates WHERE request_id = ? ORDER BY id', (req_id,)
        ).fetchall()
        edit_options = _native_edit_options(conn, req)
        conn.close()
        return req, {
            'attachments': attachments,
            'stage_dates': [dict(s) for s in stage_dates],
            'edit_options': edit_options,
        }

    @app.route('/api/native/service/installation/request-detail/<int:req_id>')
    def native_installation_request_detail(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        req, extra = _detail_common(req_id, category='نصب و آموزش', subtype='درخواست نصب')
        if not req:
            return jsonify({'error': 'not_found'}), 404
        from core.workflow import can_view_request
        if not can_view_request(_as_user_dict(current_user), req):
            return jsonify({'error': 'forbidden'}), 403
        return jsonify({
            'request': dict(req), 'statuses': INSTALLATION_REQUEST_STATUSES,
            'can_edit': current_user['role'] in RECEPTION_ROLES,
            'permissions': {'can_edit': current_user['role'] in RECEPTION_ROLES},
            **extra,
        })

    @app.route('/api/native/service/installation/request-action/<int:req_id>', methods=['POST'])
    def native_installation_request_action(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        action = request.form.get('action', 'save')
        _req, denial = _authorize_service_action(req_id, action, category='نصب و آموزش', subtype='درخواست نصب')
        if denial:
            return denial
        resp = current_app.view_functions['installation_request_view'](req_id)
        return _action_result(resp)

    @app.route('/api/native/service/installation/register-detail/<int:req_id>')
    def native_installation_register_detail(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        req, extra = _detail_common(req_id, category='نصب و آموزش', subtype='ثبت نصب')
        if not req:
            return jsonify({'error': 'not_found'}), 404
        from core.workflow import can_view_request
        if not can_view_request(_as_user_dict(current_user), req):
            return jsonify({'error': 'forbidden'}), 403
        return jsonify({
            'request': dict(req), 'can_edit': current_user['role'] in RECEPTION_ROLES,
            'permissions': {'can_edit': current_user['role'] in RECEPTION_ROLES},
            **extra,
        })

    @app.route('/api/native/service/installation/register-action/<int:req_id>', methods=['POST'])
    def native_installation_register_action(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user['role'] not in RECEPTION_ROLES:
            return jsonify({'error': 'forbidden'}), 403
        action = request.form.get('action', 'save_fields')
        if action != 'save_fields':
            return jsonify({'error': 'unsupported_action'}), 400
        fields = [
            'city', 'customer_address', 'equipment_manager_name',
            'equipment_manager_mobile', 'contact_name', 'contact_phone',
            'install_unit', 'install_notes', 'assigned_technician',
        ]
        conn = get_db()
        req = conn.execute("SELECT * FROM requests WHERE id = ? AND request_subtype = 'ثبت نصب'", (req_id,)).fetchone()
        if not req:
            conn.close()
            return jsonify({'error': 'not_found'}), 404
        updates, values = [], []
        # SQL identifiers come only from this fixed whitelist; request.form is used only for bound values.
        for f in fields:
            if f in request.form:
                updates.append(f'{f} = ?')
                values.append(request.form.get(f) or None)
        if updates:
            values.append(req_id)
            conn.execute(f"UPDATE requests SET {', '.join(updates)} WHERE id = ?", values)
            if 'assigned_technician' in request.form:
                try:
                    sync_request_technician(conn, req_id, request.form.get('assigned_technician'), expected_role='تکنسین استانی', province=req['province'])
                except Exception as e:
                    logger.exception("Silent exception in routes/native_api.py")
        conn.commit(); conn.close()
        return jsonify({'ok': True})

    @app.route('/api/native/service/inspection/detail/<int:req_id>')
    def native_inspection_detail(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        req, extra = _detail_common(req_id, category='بررسی و بازدید')
        if not req:
            return jsonify({'error': 'not_found'}), 404
        from core.workflow import can_view_request
        if not can_view_request(_as_user_dict(current_user), req):
            return jsonify({'error': 'forbidden'}), 403
        return jsonify({
            'request': dict(req), 'statuses': VISIT_STATUSES,
            'can_edit': current_user['role'] in RECEPTION_ROLES,
            'permissions': {'can_edit': current_user['role'] in RECEPTION_ROLES},
            **extra,
        })

    @app.route('/api/native/service/inspection/action/<int:req_id>', methods=['POST'])
    def native_inspection_action(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        action = request.form.get('action', 'save')
        _req, denial = _authorize_service_action(req_id, action, category='بررسی و بازدید', subtype='درخواست بازدید')
        if denial:
            return denial
        resp = current_app.view_functions['inspection_view'](req_id)
        return _action_result(resp)

    # ---- main.py - home dashboard / role cartable -----------------

    @app.route('/api/native/home')
    def native_home():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        conn = get_db()

        if current_user['role'] == FINANCE_ROLE:
            tasks = _get_finance_tasks(conn)
            conn.close()
            return jsonify({
                'view': 'finance', 'tasks': tasks, 'open_count': len(tasks),
                'delay_threshold': DELAY_THRESHOLD_DAYS,
            })

        if current_user['role'] in TECHNICIAN_ROLES or current_user['role'] == 'کنترل کیفیت':
            is_qc = current_user['role'] == 'کنترل کیفیت'
            tasks = _get_qc_tasks(conn) if is_qc else _get_technician_tasks(conn, current_user)
            conn.close()
            open_count = len([t for t in tasks if not t['is_closed']])
            closed_count = len([t for t in tasks if t['is_closed']])
            qc_open = len([t for t in tasks if t.get('in_qc_stage')]) if is_qc else 0
            return jsonify({
                'view': 'qc' if is_qc else 'technician', 'tasks': tasks,
                'open_count': open_count, 'closed_count': closed_count,
                'total_count': len(tasks), 'qc_open': qc_open,
                'delay_threshold': DELAY_THRESHOLD_DAYS,
            })

        # کارتابل پیش‌فرض (پذیرش/مدیر/مدیر سیستم): لیست قدیمی جدول requests
        if current_user['role'] == 'مسئول پذیرش':
            rows = conn.execute(
                "SELECT * FROM requests WHERE request_category = 'تعمیر' ORDER BY id DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM requests WHERE request_category = 'تعمیر' AND status != 'تحویل شد' ORDER BY id DESC"
            ).fetchall()
        try:
            from core.request_utils import enrich_delay
            requests_list = enrich_delay(conn, rows, DELAY_THRESHOLD_DAYS)
        except Exception:
            requests_list = [dict(r) for r in rows]
        conn.close()
        return jsonify({
            'view': 'reception',
            'requests': requests_list,
            'total_count': len(requests_list),
            'pending_count': len([r for r in requests_list if r['status'] == 'در انتظار بررسی']),
            'repairing_count': len([r for r in requests_list if r['status'] in ('در حال تعمیر', 'در حال انجام')]),
            'delivered_count': len([r for r in requests_list if r['status'] in ('تحویل شد', 'پایان تعمیرات', 'پایان')]),
        })


    # ---- settings.py - user management (first slice) -------------

    @app.route('/api/native/settings/users')
    def native_settings_users():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return jsonify({'error': 'forbidden'}), 403
        from core.app_lists import roles_list
        from core.access import is_system_admin
        conn = get_db()
        try:
            cols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
            if 'is_active' not in cols:
                conn.execute('ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1')
                conn.execute('UPDATE users SET is_active=1 WHERE is_active IS NULL')
                conn.commit()
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        users = conn.execute(
            'SELECT id, full_name, username, role, province, created_at FROM users '
            'WHERE IFNULL(is_active,1)=1 ORDER BY id DESC'
        ).fetchall()
        reps = conn.execute(
            "SELECT id, first_name, last_name, company_name, rep_type, province FROM representatives "
            "WHERE status = 'فعال' ORDER BY first_name"
        ).fetchall()
        try:
            roles = roles_list(conn) or ROLES
        except Exception:
            roles = ROLES
        conn.close()
        return jsonify({
            'users': [dict(u) for u in users],
            'representatives': [dict(r) for r in reps],
            'roles': roles,
            'can_manage': is_system_admin(current_user),
        })

    @app.route('/api/native/settings/users/new', methods=['POST'])
    def native_settings_user_new():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return jsonify({'error': 'forbidden'}), 403
        role = (request.form.get('role') or '').strip()
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if not (role and username and password):
            return jsonify({'ok': False, 'error': 'نقش، نام کاربری و رمز عبور الزامی است.'}), 400

        conn = get_db()
        if conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
            conn.close()
            return jsonify({'ok': False, 'error': 'این نام کاربری قبلاً استفاده شده است.'}), 400

        created_at = jdatetime.date.today().togregorian().isoformat()
        if role == 'تکنسین استانی':
            rep_id = request.form.get('representative_id', type=int)
            rep = conn.execute('SELECT * FROM representatives WHERE id = ?', (rep_id,)).fetchone() if rep_id else None
            if not rep:
                conn.close()
                return jsonify({'ok': False, 'error': 'لطفاً یک نماینده را انتخاب کنید.'}), 400
            full_name = rep['company_name'] if (rep['rep_type'] == 'حقوقی' and rep['company_name']) \
                else f"{rep['first_name']} {rep['last_name']}"
            conn.execute(
                'INSERT INTO users (full_name, username, password_hash, role, province, representative_id, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (full_name, username, generate_password_hash(password), role, rep['province'], rep['id'], created_at),
            )
        else:
            full_name = (request.form.get('full_name') or '').strip()
            if not full_name:
                conn.close()
                return jsonify({'ok': False, 'error': 'نام کامل الزامی است.'}), 400
            conn.execute(
                'INSERT INTO users (full_name, username, password_hash, role, province, representative_id, created_at) '
                'VALUES (?, ?, ?, ?, NULL, NULL, ?)',
                (full_name, username, generate_password_hash(password), role, created_at),
            )
        conn.commit()
        new_id = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()['id']
        conn.close()
        return jsonify({'ok': True, 'id': new_id})

    @app.route('/api/native/settings/users/<int:user_id>/deactivate', methods=['POST'])
    def native_settings_user_deactivate(user_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        from core.access import is_system_admin
        if not is_system_admin(current_user):
            return jsonify({'ok': False, 'error': 'اجازه غیرفعال‌سازی فقط برای مدیر سیستم است.'}), 403
        if int(user_id) == int(current_user['id']):
            return jsonify({'ok': False, 'error': 'نمی‌توانید حساب خودتان را غیرفعال کنید.'}), 400
        conn = get_db()
        target = conn.execute('SELECT id, username, role FROM users WHERE id=?', (user_id,)).fetchone()
        if not target:
            conn.close()
            return jsonify({'ok': False, 'error': 'کاربر پیدا نشد.'}), 404
        if target['role'] in ('مسئول پذیرش', 'مدیر سیستم'):
            cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE role IN ('مسئول پذیرش','مدیر سیستم') "
                "AND IFNULL(is_active,1)=1 AND id!=?",
                (user_id,),
            ).fetchone()['c']
            if cnt < 1:
                conn.close()
                return jsonify({'ok': False, 'error': 'نمی‌توان آخرین مدیر سیستم فعال را غیرفعال کرد.'}), 400
        conn.execute('UPDATE users SET is_active=0 WHERE id=?', (user_id,))
        conn.commit()
        try:
            write_audit(conn, current_user['full_name'], 'غیرفعال‌سازی کاربر', 'user', user_id, target['username'])
            conn.commit()
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        conn.close()
        return jsonify({'ok': True})

    @app.route('/api/native/settings/users/<int:user_id>/activate', methods=['POST'])
    def native_settings_user_activate(user_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        from core.access import is_system_admin
        if not is_system_admin(current_user):
            return jsonify({'ok': False, 'error': 'اجازه فعال‌سازی فقط برای مدیر سیستم است.'}), 403
        conn = get_db()
        conn.execute('UPDATE users SET is_active=1 WHERE id=?', (user_id,))
        conn.commit()
        try:
            write_audit(conn, current_user['full_name'], 'فعال‌سازی کاربر', 'user', user_id, None)
            conn.commit()
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        conn.close()
        return jsonify({'ok': True})

    @app.route('/api/native/settings/users/archive')
    def native_settings_users_archive():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return jsonify({'error': 'forbidden'}), 403
        from core.access import is_system_admin
        conn = get_db()
        users = conn.execute(
            'SELECT id, full_name, username, role, province, created_at FROM users '
            'WHERE IFNULL(is_active,1)=0 ORDER BY id DESC'
        ).fetchall()
        conn.close()
        return jsonify({'users': [dict(u) for u in users], 'can_manage': is_system_admin(current_user)})

    # ---- settings.py - customers management (second slice) ------

    CUSTOMER_FIELDS = (
        'name', 'phone', 'national_id', 'economic_code', 'province', 'county',
        'city', 'address', 'postal_code', 'equipment_manager_name',
        'equipment_manager_mobile', 'person_type',
    )

    def _customer_form_dict():
        d = {k: (request.form.get(k) or '').strip() or None for k in CUSTOMER_FIELDS}
        if not d.get('city'):
            d['city'] = (request.form.get('city_manual') or '').strip() or None
        pt = d.get('person_type') or 'حقیقی'
        d['person_type'] = pt if pt in ('حقیقی', 'حقوقی') else 'حقیقی'
        return d

    @app.route('/api/native/settings/customers')
    def native_settings_customers():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return jsonify({'error': 'forbidden'}), 403
        conn = get_db()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
            "phone TEXT, national_id TEXT, economic_code TEXT, province TEXT, city TEXT, address TEXT, "
            "equipment_manager_name TEXT, equipment_manager_mobile TEXT)"
        )
        cust_cols = {row[1] for row in conn.execute('PRAGMA table_info(customers)').fetchall()}
        # Fixed schema whitelist; column names are never taken from request.args/form.
        for col in ('county', 'postal_code', 'person_type', 'is_archived', 'archive_date'):
            if col not in cust_cols:
                try:
                    conn.execute(f'ALTER TABLE customers ADD COLUMN {col} TEXT')
                except Exception as e:
                    logger.exception("Silent exception in routes/native_api.py")
        conn.commit()

        q = (request.args.get('q') or '').strip().lower()
        rows = conn.execute(
            'SELECT * FROM customers WHERE IFNULL(is_archived,0)=0 ORDER BY id DESC'
        ).fetchall()
        customers = [dict(r) for r in rows]
        if q:
            def _match(c):
                parts = [str(c.get(k) or '') for k in
                         ('id', 'name', 'phone', 'province', 'county', 'city', 'national_id',
                          'equipment_manager_name', 'equipment_manager_mobile')]
                return any(q in p.lower() for p in parts if p)
            customers = [c for c in customers if _match(c)]
        try:
            provinces = get_geo_provinces(conn) if get_geo_provinces else PROVINCES
        except Exception:
            provinces = PROVINCES
        conn.close()
        return jsonify({'customers': customers, 'provinces': provinces})

    @app.route('/api/native/settings/customers/new', methods=['POST'])
    def native_settings_customer_new():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return jsonify({'error': 'forbidden'}), 403
        d = _customer_form_dict()
        if not d.get('name') or not d.get('city'):
            return jsonify({'ok': False, 'error': 'نام طرف‌حساب و شهر الزامی است.'}), 400
        conn = get_db()
        conn.execute(
            'INSERT INTO customers (name, phone, national_id, economic_code, province, county, city, '
            'address, postal_code, equipment_manager_name, equipment_manager_mobile, person_type) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            tuple(d[k] for k in CUSTOMER_FIELDS),
        )
        conn.commit()
        new_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
        conn.close()
        return jsonify({'ok': True, 'id': new_id})

    @app.route('/api/native/settings/customers/<int:customer_id>/edit', methods=['POST'])
    def native_settings_customer_edit(customer_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return jsonify({'error': 'forbidden'}), 403
        conn = get_db()
        if not conn.execute('SELECT id FROM customers WHERE id=?', (customer_id,)).fetchone():
            conn.close()
            return jsonify({'ok': False, 'error': 'طرف‌حساب پیدا نشد.'}), 404
        d = _customer_form_dict()
        if not d.get('name') or not d.get('city'):
            conn.close()
            return jsonify({'ok': False, 'error': 'نام طرف‌حساب و شهر الزامی است.'}), 400
        conn.execute(
            'UPDATE customers SET name=?, phone=?, national_id=?, economic_code=?, province=?, county=?, '
            'city=?, address=?, postal_code=?, equipment_manager_name=?, equipment_manager_mobile=?, '
            'person_type=? WHERE id=?',
            tuple(d[k] for k in CUSTOMER_FIELDS) + (customer_id,),
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    @app.route('/api/native/settings/customers/<int:customer_id>/archive', methods=['POST'])
    def native_settings_customer_archive(customer_id):
        current_user = _as_user_dict(get_current_user())
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return jsonify({'error': 'forbidden'}), 403
        conn = get_db()
        try:
            ad = jdatetime.date.today()
            archive_date = f"{ad.year}/{str(ad.month).zfill(2)}/{str(ad.day).zfill(2)}"
        except Exception:
            archive_date = None
        conn.execute(
            'UPDATE customers SET is_archived=1, archive_date=COALESCE(?, archive_date) WHERE id=?',
            (archive_date, customer_id),
        )
        conn.commit()
        try:
            write_audit(conn, current_user.get('full_name'), 'آرشیو طرف حساب', 'customer', customer_id, '')
            conn.commit()
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        conn.close()
        return jsonify({'ok': True})

    # ---- Customer affairs: contacts (مخاطبین) -------------------
    CONTACT_FIELDS = (
        'name', 'company', 'mobile', 'phone', 'email', 'website',
        'city', 'status', 'group_name', 'address', 'notes',
    )

    def _contacts_ensure_schema(conn):
        cols = {r[1] for r in conn.execute('PRAGMA table_info(contacts)').fetchall()}
        # Fixed schema whitelist; request data never controls these identifiers.
        for col, col_type in (
            ('city', 'TEXT'), ('company', 'TEXT'), ('email', 'TEXT'),
            ('website', 'TEXT'), ('address', 'TEXT'), ('status', 'TEXT'),
            ('group_name', 'TEXT'), ('avatar_filename', 'TEXT'),
        ):
            if col not in cols:
                try:
                    conn.execute(f'ALTER TABLE contacts ADD COLUMN {col} {col_type}')
                except Exception as e:
                    logger.exception("Silent exception in routes/native_api.py")
        conn.commit()

    @app.route('/api/native/customer-affairs/contacts')
    def native_customer_affairs_contacts():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if not (_is_reception(current_user) or user_has_access(current_user, 'customer_affairs')):
            return jsonify({'error': 'forbidden'}), 403
        conn = get_db()
        _contacts_ensure_schema(conn)
        DEFAULT_STATUS = 'مشتری'
        DEFAULT_GROUP = 'مشتریان'
        rows = []
        try:
            for r in conn.execute(
                """SELECT id, name, mobile, phone, city, company, email, website,
                          address, status, group_name, notes, created_at
                   FROM contacts WHERE COALESCE(is_archived,0)=0
                   ORDER BY name"""
            ).fetchall():
                d = dict(r)
                d['key'] = 'manual-%s' % d['id']
                d['status'] = d.get('status') or DEFAULT_STATUS
                d['group_name'] = d.get('group_name') or DEFAULT_GROUP
                d['source_label'] = 'دستی'
                rows.append(d)
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        try:
            for r in conn.execute(
                """SELECT id, name,
                          equipment_manager_mobile AS mobile,
                          phone, city, address,
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
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        rows.sort(key=lambda x: (x.get('name') or ''))

        q = (request.args.get('q') or '').strip().lower()
        if q:
            def _match(c):
                hay = ' '.join(str(c.get(k) or '') for k in
                                ('name', 'company', 'mobile', 'phone', 'email', 'city', 'notes')).lower()
                return q in hay
            rows = [r for r in rows if _match(r)]
        conn.close()
        return jsonify({'contacts': rows})

    @app.route('/api/native/customer-affairs/contacts/new', methods=['POST'])
    def native_customer_affairs_contact_new():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if not (_is_reception(current_user) or user_has_access(current_user, 'customer_affairs')):
            return jsonify({'error': 'forbidden'}), 403
        name = (request.form.get('name') or '').strip()
        if not name:
            return jsonify({'ok': False, 'error': 'نام مخاطب الزامی است.'}), 400
        conn = get_db()
        _contacts_ensure_schema(conn)
        try:
            now = jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')
            d = {k: (request.form.get(k) or '').strip() or None for k in CONTACT_FIELDS if k != 'name'}
            conn.execute(
                '''INSERT INTO contacts
                   (name, mobile, phone, city, company, email, website, address, status, group_name, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (name, d.get('mobile'), d.get('phone'), d.get('city'), d.get('company'),
                 d.get('email'), d.get('website'), d.get('address'), d.get('status') or 'مشتری',
                 d.get('group_name') or 'مشتریان', d.get('notes'), now)
            )
            conn.commit()
            new_id = conn.execute('SELECT last_insert_rowid() AS id').fetchone()['id']
        except Exception:
            conn.close()
            return jsonify({'ok': False, 'error': 'ثبت مخاطب ناموفق بود.'}), 500
        conn.close()
        return jsonify({'ok': True, 'id': new_id})

    # ---- Customer affairs: public announcements (اعلام‌های عمومی) ----
    @app.route('/api/native/customer-affairs/announcements')
    def native_customer_affairs_announcements():
        current_user = _as_user_dict(get_current_user())
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user.get('role') not in ('مسئول پذیرش', 'مدیر سیستم'):
            return jsonify({'error': 'forbidden'}), 403
        conn = get_db()
        ensure_features_schema(conn)
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM service_announcements ORDER BY id DESC LIMIT 1000"
        ).fetchall()]
        conn.close()
        q = (request.args.get('q') or '').strip().lower()
        status_f = (request.args.get('status') or '').strip()
        if status_f:
            rows = [r for r in rows if (r.get('status') or '') == status_f]
        if q:
            def _match(r):
                hay = ' '.join(str(r.get(k) or '') for k in
                                ('hospital_name', 'contact_name', 'contact_phone', 'province',
                                 'city', 'serial_number', 'problem_brief')).lower()
                return q in hay
            rows = [r for r in rows if _match(r)]
        status_options = sorted({r.get('status') for r in rows if r.get('status')})
        return jsonify({'announcements': rows, 'status_options': status_options})

    @app.route('/api/native/customer-affairs/announcements/<int:ann_id>/handled', methods=['POST'])
    def native_customer_affairs_announcement_handled(ann_id):
        current_user = _as_user_dict(get_current_user())
        if not current_user:
            return jsonify({'error': 'auth_required'}), 401
        if current_user.get('role') not in ('مسئول پذیرش', 'مدیر سیستم'):
            return jsonify({'error': 'forbidden'}), 403
        conn = get_db()
        ensure_features_schema(conn)
        conn.execute(
            "UPDATE service_announcements SET status=?, handled_by=?, handled_at=? WHERE id=?",
            ("تماس انجام شد", current_user.get('full_name'), _feat_today(), ann_id),
        )
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    # ---- remaining native cards -------------------------------
    def _native_manage_allowed(user, module):
        user = _as_user_dict(user)
        if not user:
            return False
        role = user.get('role') or ''
        if role in ('مسئول پذیرش', 'مدیر سیستم'):
            return True
        try:
            return user_has_access(user, module)
        except Exception:
            return False

    @app.route('/api/native/finance/wage-rates')
    def native_wage_rates():
        u=get_current_user()
        if not _native_manage_allowed(u,'wages_settings'): return jsonify({'error':'forbidden'}),403
        from core.wages import ensure_wage_schema
        conn=get_db(); ensure_wage_schema(conn); q=(request.args.get('q') or '').strip().lower()
        rows=[dict(r) for r in conn.execute('SELECT * FROM wage_rates ORDER BY COALESCE(sort_order,999),id').fetchall()]
        conn.close()
        if q: rows=[r for r in rows if q in ' '.join(str(r.get(k) or '') for k in ('work_description','rate_code','category','device_type')).lower()]
        return jsonify({'rows':rows})

    @app.route('/api/native/finance/wage-rates/new', methods=['POST'])
    def native_wage_rate_new():
        u=get_current_user()
        if not _native_manage_allowed(u,'wages_settings'): return jsonify({'error':'forbidden'}),403
        from core.wages import ensure_wage_schema
        conn=get_db(); ensure_wage_schema(conn)
        try:
            conn.execute('INSERT INTO wage_rates (work_description,wage_amount,rate_code,amount_outside,is_per_km,category,sort_order,is_active) VALUES (?,?,?,?,?,?,?,1)',((request.form.get('work_description') or '').strip(),int(request.form.get('wage_amount') or 0),request.form.get('rate_code') or None,int(request.form.get('amount_outside') or 0) if request.form.get('amount_outside') else None,1 if request.form.get('is_per_km') else 0,request.form.get('category') or None,int(request.form.get('sort_order') or 99))); conn.commit(); out={'ok':True}
        except Exception as e: conn.close(); return jsonify({'ok':False,'error':str(e)}),400
        conn.close(); return jsonify(out)

    @app.route('/api/native/finance/files')
    def native_finance_files():
        u=get_current_user()
        if not _native_manage_allowed(u,'finance'): return jsonify({'error':'forbidden'}),403
        q=(request.args.get('q') or '').strip().lower(); conn=get_db(); rows=[dict(r) for r in conn.execute('SELECT * FROM requests ORDER BY id DESC LIMIT 1000').fetchall()]; conn.close()
        if q: rows=[r for r in rows if q in ' '.join(str(r.get(k) or '') for k in ('id','reception_no','customer_name','serial_number','invoice_number','tracking_number','device_type','status')).lower()]
        return jsonify({'rows':rows})

    @app.route('/api/native/reports/delay-matrix')
    def native_delay_matrix():
        u=get_current_user()
        if not _native_manage_allowed(u,'reports'): return jsonify({'error':'forbidden'}),403
        from core.delay_matrix import build_delay_matrix
        conn=get_db(); d=build_delay_matrix(conn,kind=(request.args.get('kind') or 'internal'),serial_filter=(request.args.get('serial') or '').strip(),province=(request.args.get('province') or '').strip(),only_delayed=request.args.get('only_delayed')=='1',limit=250); conn.close(); return jsonify(d)

    @app.route('/api/native/settings/products/devices')
    def native_products_devices():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        q=(request.args.get('q') or '').strip().lower(); conn=get_db(); rows=[dict(r) for r in conn.execute('SELECT * FROM devices ORDER BY id DESC').fetchall()]; conn.close();
        if q: rows=[r for r in rows if q in ' '.join(str(r.get(k) or '') for k in ('device_type','model')).lower()]
        return jsonify({'rows':rows})
    @app.route('/api/native/settings/products/devices/<int:item_id>/edit',methods=['POST'])
    def native_products_devices_edit(item_id):
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); conn.execute('UPDATE devices SET device_type=?, model=? WHERE id=?',((request.form.get('device_type') or '').strip(),(request.form.get('model') or '').strip(),item_id)); conn.commit(); conn.close(); return jsonify({'ok':True})
    @app.route('/api/native/settings/products/devices/<int:item_id>/delete',methods=['POST'])
    def native_products_devices_delete(item_id):
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); conn.execute('DELETE FROM devices WHERE id=?',(item_id,)); conn.commit(); conn.close(); return jsonify({'ok':True})
    @app.route('/api/native/settings/products/devices/new',methods=['POST'])
    def native_products_devices_new():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); cur=conn.execute('INSERT INTO devices(device_type,model) VALUES(?,?)',((request.form.get('device_type') or '').strip(),(request.form.get('model') or '').strip())); conn.commit(); i=cur.lastrowid; conn.close(); return jsonify({'ok':True,'id':i})
    @app.route('/api/native/settings/products/parts')
    def native_products_parts():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        q=(request.args.get('q') or '').strip().lower(); conn=get_db(); rows=[dict(r) for r in conn.execute('SELECT * FROM parts ORDER BY id DESC').fetchall()]; conn.close();
        if q: rows=[r for r in rows if q in ' '.join(str(r.get(k) or '') for k in ('warehouse_code','part_name','device_type','device_model')).lower()]
        return jsonify({'rows':rows})
    @app.route('/api/native/settings/products/parts/<int:item_id>/edit',methods=['POST'])
    def native_products_parts_edit(item_id):
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); conn.execute('UPDATE parts SET warehouse_code=?, part_name=?, device_type=?, device_model=? WHERE id=?',((request.form.get('warehouse_code') or '').strip(),(request.form.get('part_name') or '').strip(),(request.form.get('device_type') or '').strip(),(request.form.get('device_model') or '').strip(),item_id)); conn.commit(); conn.close(); return jsonify({'ok':True})
    @app.route('/api/native/settings/products/parts/<int:item_id>/delete',methods=['POST'])
    def native_products_parts_delete(item_id):
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); conn.execute('DELETE FROM parts WHERE id=?',(item_id,)); conn.commit(); conn.close(); return jsonify({'ok':True})
    @app.route('/api/native/settings/products/parts/new',methods=['POST'])
    def native_products_parts_new():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); cur=conn.execute('INSERT INTO parts(warehouse_code,part_name,device_type,device_model) VALUES(?,?,?,?)',((request.form.get('warehouse_code') or '').strip(),(request.form.get('part_name') or '').strip(),(request.form.get('device_type') or '').strip(),(request.form.get('device_model') or '').strip())); conn.commit(); i=cur.lastrowid; conn.close(); return jsonify({'ok':True,'id':i})
    @app.route('/api/native/settings/products/warranty')
    def native_products_warranty():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        q=(request.args.get('q') or '').strip().lower(); conn=get_db(); rows=[dict(r) for r in conn.execute('SELECT * FROM warranty_cards ORDER BY id DESC').fetchall()]; conn.close();
        if q: rows=[r for r in rows if q in ' '.join(str(r.get(k) or '') for k in ('serial_number','customer_name','device_type','model')).lower()]
        return jsonify({'rows':rows})
    @app.route('/api/native/settings/products/warranty/<int:item_id>/edit',methods=['POST'])
    def native_products_warranty_edit(item_id):
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); conn.execute('UPDATE warranty_cards SET customer_name=?, device_type=?, model=?, serial_number=?, production_date=?, installation_date=? WHERE id=?',((request.form.get('customer_name') or '').strip(),(request.form.get('device_type') or '').strip(),(request.form.get('model') or '').strip(),(request.form.get('serial_number') or '').strip(),(request.form.get('production_date') or '').strip(),(request.form.get('installation_date') or '').strip(),item_id)); conn.commit(); conn.close(); return jsonify({'ok':True})
    @app.route('/api/native/settings/products/warranty/<int:item_id>/delete',methods=['POST'])
    def native_products_warranty_delete(item_id):
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); conn.execute('DELETE FROM warranty_cards WHERE id=?',(item_id,)); conn.commit(); conn.close(); return jsonify({'ok':True})
    @app.route('/api/native/settings/products/warranty/new',methods=['POST'])
    def native_products_warranty_new():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db();
        try: cur=conn.execute('INSERT INTO warranty_cards(customer_name,device_type,model,serial_number,production_date,installation_date) VALUES(?,?,?,?,?,?)',((request.form.get('customer_name') or '').strip(),(request.form.get('device_type') or '').strip(),(request.form.get('model') or '').strip(),(request.form.get('serial_number') or '').strip(),(request.form.get('production_date') or '').strip(),(request.form.get('installation_date') or '').strip())); conn.commit(); i=cur.lastrowid
        except Exception as e: conn.close(); return jsonify({'ok':False,'error':str(e)}),400
        conn.close(); return jsonify({'ok':True,'id':i})

    @app.route('/api/native/settings/calendar')
    def native_calendar():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); rows=[dict(r) for r in list_calendar_holidays(conn)]; conn.close(); return jsonify({'rows':rows})
    @app.route('/api/native/settings/calendar/<int:item_id>/edit',methods=['POST'])
    def native_calendar_edit(item_id):
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); ok,err=False,None
        try:
            conn.execute('UPDATE calendar_holidays SET holiday_date=?, title=? WHERE id=?',((request.form.get('holiday_date') or '').strip(),(request.form.get('title') or '').strip(),item_id)); conn.commit(); ok=True
        except Exception as e: err=str(e)
        conn.close(); return (jsonify({'ok':True}) if ok else jsonify({'ok':False,'error':err}),200 if ok else 400)
    @app.route('/api/native/settings/calendar/<int:item_id>/delete',methods=['POST'])
    def native_calendar_delete(item_id):
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); conn.execute('DELETE FROM calendar_holidays WHERE id=?',(item_id,)); conn.commit(); conn.close(); return jsonify({'ok':True})
    @app.route('/api/native/settings/calendar/new',methods=['POST'])
    def native_calendar_new():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); ok,info=add_calendar_holiday(conn,request.form.get('holiday_date'),request.form.get('title'));
        if ok: conn.commit()
        conn.close(); return (jsonify({'ok':True,'info':info}) if ok else jsonify({'ok':False,'error':info}),200 if ok else 400)

    @app.route('/api/native/settings/company')
    def native_company():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); data={k:get_setting(conn,k,'') for k in ('company_name','company_mobile','company_phone','company_address','company_postal_code','company_logo')}; conn.close(); return jsonify({'data':data})
    @app.route('/api/native/settings/company/save',methods=['POST'])
    def native_company_save():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db();
        for k in ('company_name','company_mobile','company_phone','company_address','company_postal_code'): set_setting(conn,k,request.form.get(k,'') or '')
        conn.commit(); conn.close(); return jsonify({'ok':True})

    @app.route('/api/native/settings/app-lists')
    def native_app_lists():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.app_lists import ensure_app_lists_schema,seed_defaults_if_empty,get_list_items
        key=(request.args.get('key') or 'internal_repair_statuses'); conn=get_db(); ensure_app_lists_schema(conn); seed_defaults_if_empty(conn); rows=[dict(r) for r in get_list_items(conn,key)]; conn.close(); q=(request.args.get('q') or '').lower(); rows=[r for r in rows if not q or q in str(r.get('value') or '').lower()]; return jsonify({'rows':rows})
    @app.route('/api/native/settings/app-lists/<int:item_id>/edit',methods=['POST'])
    def native_app_lists_edit(item_id):
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); conn.execute('UPDATE app_list_items SET value=? WHERE id=? AND is_system=0',((request.form.get('value') or '').strip(),item_id)); conn.commit(); conn.close(); return jsonify({'ok':True})
    @app.route('/api/native/settings/app-lists/<int:item_id>/delete',methods=['POST'])
    def native_app_lists_delete(item_id):
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); conn.execute('UPDATE app_list_items SET is_active=0 WHERE id=? AND is_system=0',(item_id,)); conn.commit(); conn.close(); return jsonify({'ok':True})
    @app.route('/api/native/settings/app-lists/new',methods=['POST'])
    def native_app_lists_new():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.app_lists import ensure_app_lists_schema,add_item
        conn=get_db(); ensure_app_lists_schema(conn); ok,err=add_item(conn,request.form.get('list_key') or 'internal_repair_statuses',request.form.get('value'));
        if ok: conn.commit()
        conn.close(); return (jsonify({'ok':True}) if ok else jsonify({'ok':False,'error':err}),200 if ok else 400)

    @app.route('/api/native/settings/geo')
    def native_geo():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.geo import ensure_geo_schema,get_geo_provinces,geo_stats
        conn=get_db(); ensure_geo_schema(conn); stats=geo_stats(conn); prov=get_geo_provinces(conn); conn.close(); return jsonify({'stats':stats,'provinces':prov})
    @app.route('/api/native/settings/geo/cities')
    def native_geo_cities():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.geo import ensure_geo_schema,get_geo_cities
        conn=get_db(); ensure_geo_schema(conn); cities=get_geo_cities(conn,request.args.get('province') or '', ''); conn.close(); return jsonify({'cities':cities})

    @app.route('/api/native/settings/distance')
    def native_distance():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.distance import (
            ensure_distance_schema, coords_stats, get_road_factor,
            get_distance_method, get_osrm_base_url, DEFAULT_ROAD_FACTOR,
        )
        conn=get_db(); ensure_distance_schema(conn)
        try:
            stats=coords_stats(conn)
        except Exception:
            stats={}
        data={
            'road_factor': get_road_factor(conn),
            'distance_method': get_distance_method(conn),
            'osrm_url': get_osrm_base_url(conn),
            'stats': stats,
        }
        conn.close(); return jsonify(data)

    @app.route('/api/native/settings/distance/seed', methods=['POST'])
    def native_distance_seed():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.distance import ensure_distance_schema, seed_coordinates_from_json
        import json, os
        from core.constants import BASE_DIR
        u2=_as_user_dict(u)
        conn=get_db(); ensure_distance_schema(conn)
        coords_path=os.path.join(BASE_DIR,'data','iran_city_coords.json')
        if not os.path.isfile(coords_path):
            conn.close(); return jsonify({'ok':False,'error':'فایل مختصات پیدا نشد: data/iran_city_coords.json'}),400
        try:
            with open(coords_path,'r',encoding='utf-8') as f:
                data=json.load(f)
            updated, skipped, err = seed_coordinates_from_json(conn, data)
        except Exception as e:
            conn.close(); return jsonify({'ok':False,'error':str(e)}),400
        if err:
            conn.close(); return jsonify({'ok':False,'error':err}),400
        msg=f'مختصات به‌روز شد: {updated} شهر — رد شده/بدون تطبیق: {skipped}'
        try:
            write_audit(conn, (u2 or {}).get('full_name'), 'بارگذاری مختصات شهرها', 'geo', None, msg)
            conn.commit()
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        conn.close(); return jsonify({'ok':True,'message':msg,'updated':updated,'skipped':skipped})

    @app.route('/api/native/settings/distance/factor', methods=['POST'])
    def native_distance_factor():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.distance import ensure_distance_schema, DEFAULT_ROAD_FACTOR
        conn=get_db(); ensure_distance_schema(conn)
        try:
            f=float(request.form.get('road_factor') or DEFAULT_ROAD_FACTOR)
        except Exception:
            conn.close(); return jsonify({'ok':False,'error':'مقدار نامعتبر است'}),400
        if not (1.0 <= f <= 2.5):
            conn.close(); return jsonify({'ok':False,'error':'ضریب باید بین ۱ و ۲٫۵ باشد'}),400
        set_setting(conn,'distance_road_factor',str(f)); conn.commit(); conn.close()
        return jsonify({'ok':True,'message':f'ضریب جاده روی {f} تنظیم شد','road_factor':f})

    @app.route('/api/native/settings/distance/method', methods=['POST'])
    def native_distance_method():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.distance import ensure_distance_schema
        conn=get_db(); ensure_distance_schema(conn)
        method=(request.form.get('distance_method') or 'haversine').strip().lower()
        if method in ('1','haversine'):
            method='haversine'
        elif method in ('2','osrm'):
            method='osrm'
        else:
            conn.close(); return jsonify({'ok':False,'error':'روش نامعتبر است'}),400
        set_setting(conn,'distance_method',method)
        osrm_url=(request.form.get('osrm_url') or '').strip()
        if osrm_url:
            set_setting(conn,'distance_osrm_url',osrm_url.rstrip('/'))
        conn.commit(); conn.close()
        label='تقریبی (هوایی × ضریب)' if method=='haversine' else 'مسیر جاده‌ای OSRM'
        return jsonify({'ok':True,'message':f'روش محاسبه مسافت: {label}','distance_method':method})

    @app.route('/api/native/settings/system')
    def native_system():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        import os as _os
        from core.constants import BASE_DIR, DB_NAME
        return jsonify({
            'active_db_path': _os.path.join(BASE_DIR, DB_NAME),
            'active_host': request.host,
        })

    @app.route('/api/native/settings/about')
    def native_about():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.helpers import load_changelog_entries, load_app_version
        try:
            entries=load_changelog_entries()
        except Exception:
            entries=[]
        try:
            ver=load_app_version()
        except Exception:
            ver={}
        return jsonify({'entries':entries,'version':ver})

    @app.route('/api/native/settings/changelog')
    def native_changelog():
        u=get_current_user()
        if not u: return jsonify({'error':'auth_required'}),401
        from core.helpers import load_changelog_entries
        try:
            entries=load_changelog_entries()
        except Exception:
            entries=[]
        return jsonify({'entries':entries})

    @app.route('/api/native/settings/activation')
    def native_activation():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        conn=get_db()
        status=get_setting(conn,'license_status','') or 'inactive'
        key_stored=get_setting(conn,'license_key','') or ''
        masked=''
        if key_stored:
            if len(key_stored) > 8:
                masked = key_stored[:4] + '…' + key_stored[-4:]
            else:
                masked = key_stored[:2] + '…'
        owner=get_setting(conn,'license_owner','') or ''
        activated_at=get_setting(conn,'license_activated_at','') or ''
        conn.close()
        return jsonify({
            'license_status': status,
            'license_key_masked': masked,
            'license_owner': owner,
            'license_activated_at': activated_at,
        })

    @app.route('/api/native/settings/activation/activate', methods=['POST'])
    def native_activation_activate():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        u2=_as_user_dict(u)
        import re as _re, time as _time
        conn=get_db()
        key=(request.form.get('license_key') or '').strip().upper()
        owner=(request.form.get('license_owner') or '').strip()
        key_clean=_re.sub(r'\s+','',key)
        if len(key_clean) < 8:
            conn.close(); return jsonify({'ok':False,'error':'کلید فعال‌سازی معتبر نیست (حداقل ۸ کاراکتر).'}),400
        set_setting(conn,'license_key',key_clean)
        set_setting(conn,'license_status','active')
        set_setting(conn,'license_owner',owner)
        try:
            import jdatetime as _jd
            today=_jd.date.today()
            activated=f"{today.year}/{str(today.month).zfill(2)}/{str(today.day).zfill(2)}"
        except Exception:
            activated=_time.strftime('%Y/%m/%d')
        set_setting(conn,'license_activated_at',activated)
        try:
            write_audit(conn,(u2 or {}).get('full_name'),'فعال‌سازی نرم‌افزار','settings',None,owner or key_clean[:4]+'…')
        except Exception as e:
            logger.exception("Silent exception in routes/native_api.py")
        conn.commit(); conn.close()
        return jsonify({'ok':True,'message':'نرم‌افزار با موفقیت فعال شد.'})

    @app.route('/api/native/settings/help-tips')
    def native_help_tips():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.help_tips import list_help_tips
        conn=get_db(); rows=list_help_tips(conn); conn.close(); return jsonify({'rows':rows})
    @app.route('/api/native/settings/help-tips/save',methods=['POST'])
    def native_help_tips_save():
        u=get_current_user()
        if not _native_manage_allowed(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.help_tips import set_help_tip,HELP_TIP_CATALOG
        conn=get_db();
        for key in HELP_TIP_CATALOG:
            if key in request.form: set_help_tip(conn,key,request.form.get(key) or '')
        conn.commit(); conn.close(); return jsonify({'ok':True})

    @app.route('/api/native/settings/device-folders')
    def native_device_folders():
        u=get_current_user()
        if not _native_manage_allowed(u,'parties'): return jsonify({'error':'forbidden'}),403
        q=(request.args.get('q') or '').strip().lower(); conn=get_db(); devices=[dict(r) for r in conn.execute('SELECT id,serial_number,customer_name,device_type,model FROM warranty_cards ORDER BY id DESC').fetchall()];
        for d in devices:
            rr=conn.execute('SELECT reception_no,status FROM requests WHERE serial_number=? ORDER BY id DESC LIMIT 1',(d.get('serial_number'),)).fetchone(); d['status']=rr['status'] if rr else ''; d['reception_no']=rr['reception_no'] if rr else ''
        conn.close();
        if q: devices=[d for d in devices if q in ' '.join(str(d.get(k) or '') for k in ('serial_number','customer_name','device_type','model','status','reception_no')).lower()]
        return jsonify({'rows':devices})



    # ---- service form reference data -----------------------
    @app.route('/api/native/service/form-options')
    def native_service_form_options():
        u=get_current_user()
        if not u: return jsonify({'error':'auth_required'}),401
        conn=get_db()
        try:
            from core.geo import ensure_geo_schema,get_geo_provinces
            ensure_geo_schema(conn); provinces=get_geo_provinces(conn)
        except Exception:
            provinces=[]
        device_types=[r[0] for r in conn.execute("SELECT DISTINCT device_type FROM devices WHERE IFNULL(device_type,'')!='' ORDER BY device_type").fetchall()]
        models_by_type={}
        for r in conn.execute("SELECT DISTINCT device_type, model FROM devices WHERE IFNULL(device_type,'')!='' AND IFNULL(model,'')!='' ORDER BY device_type, model").fetchall():
            models_by_type.setdefault(r[0],[]).append(r[1])
        techs=[{'id':r['id'],'label':r['full_name'] or ('#'+str(r['id'])),'province':r['province'] or ''} for r in conn.execute("SELECT id,full_name,province FROM users WHERE role IN ('تکنسین استانی','تکنسین کارخانه') AND IFNULL(is_active,1)=1 ORDER BY full_name").fetchall()]
        conn.close()
        return jsonify({'provinces':provinces,'device_types':device_types,'models_by_type':models_by_type,'technicians':techs})

    # ---- Representatives + access matrix ---------------------------------
    @app.route('/api/native/settings/representatives')
    def native_settings_representatives():
        u=get_current_user()
        if not u or not user_has_access(u,'parties'): return jsonify({'error':'forbidden'}),403
        q=(request.args.get('q') or '').strip().lower(); conn=get_db()
        rows=[dict(r) for r in conn.execute("SELECT * FROM representatives WHERE COALESCE(status,'فعال')='فعال' ORDER BY id DESC").fetchall()]
        archived=[dict(r) for r in conn.execute("SELECT * FROM representatives WHERE COALESCE(status,'فعال')!='فعال' ORDER BY id DESC").fetchall()]
        conn.close()
        if q:
            rows=[r for r in rows if q in ' '.join(str(r.get(k) or '') for k in ('id','first_name','last_name','company_name','phone','province','city','national_id')).lower()]
        return jsonify({'rows':rows,'archived':archived})

    @app.route('/api/native/settings/representatives/new',methods=['POST'])
    def native_settings_representative_new():
        u=get_current_user()
        if not u or not user_has_access(u,'parties'): return jsonify({'error':'forbidden'}),403
        required=('rep_type','first_name','last_name','national_id','phone','province','address','guarantee_status','status')
        if any(not (request.form.get(k) or '').strip() for k in required): return jsonify({'ok':False,'error':'فیلدهای اصلی نماینده را کامل کنید.'}),400
        conn=get_db()
        try:
            cur=conn.execute('''INSERT INTO representatives(rep_type,company_name,first_name,last_name,father_name,national_id,phone,province,county,address,guarantee_status,status,contact_person_name,contact_person_phone,city,guarantee_amount,archive_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',tuple((request.form.get(k) or '').strip() or None for k in ('rep_type','company_name','first_name','last_name','father_name','national_id','phone','province','county','address','guarantee_status','status','contact_person_name','contact_person_phone','city','guarantee_amount','archive_reason')))
            conn.commit(); rid=cur.lastrowid
        except Exception as e: conn.close(); return jsonify({'ok':False,'error':str(e)}),400
        conn.close(); return jsonify({'ok':True,'id':rid})

    @app.route('/api/native/settings/representatives/<int:rep_id>/edit',methods=['POST'])
    def native_settings_representative_edit(rep_id):
        u=get_current_user()
        if not u or not user_has_access(u,'parties'): return jsonify({'error':'forbidden'}),403
        # Fixed whitelist: no request-controlled field names are interpolated into SQL.
        fields=['rep_type','company_name','first_name','last_name','father_name','national_id','phone','province','county','address','guarantee_status','status','contact_person_name','contact_person_phone','city','guarantee_amount','archive_reason']
        conn=get_db(); sets=', '.join(f'{f}=?' for f in fields); vals=[(request.form.get(f) or '').strip() or None for f in fields]+[rep_id]
        try: conn.execute(f'UPDATE representatives SET {sets} WHERE id=?',vals); conn.commit()
        except Exception as e: conn.close(); return jsonify({'ok':False,'error':str(e)}),400
        conn.close(); return jsonify({'ok':True})

    @app.route('/api/native/settings/representatives/<int:rep_id>/archive',methods=['POST'])
    def native_settings_representative_archive(rep_id):
        u=get_current_user()
        if not u or not user_has_access(u,'parties'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); conn.execute("UPDATE representatives SET status='آرشیو' WHERE id=?",(rep_id,)); conn.commit(); conn.close(); return jsonify({'ok':True})

    @app.route('/api/native/settings/access')
    def native_settings_access():
        u=get_current_user()
        if not u or not user_has_access(u,'system'): return jsonify({'error':'forbidden'}),403
        from core.access import ACCESS_MODULES,get_role_access_map,DEFAULT_ROLE_ACCESS
        conn=get_db(); amap=get_role_access_map(conn); counts={r['role']:r['c'] for r in conn.execute('SELECT role,COUNT(*) c FROM users GROUP BY role').fetchall()}; conn.close()
        return jsonify({'modules':[{'key':k,'label':v} for k,v in ACCESS_MODULES],'roles':list(amap.keys()),'access_map':amap,'role_user_counts':counts,'defaults':DEFAULT_ROLE_ACCESS})

    @app.route('/api/native/settings/access/save',methods=['POST'])
    def native_settings_access_save():
        u=get_current_user()
        if not u or not user_has_access(u,'system'): return jsonify({'error':'forbidden'}),403
        import json
        from core.access import ACCESS_MODULES
        raw=request.form.get('access_map') or '{}'
        try: amap=json.loads(raw)
        except Exception: return jsonify({'ok':False,'error':'ساختار دسترسی نامعتبر است.'}),400
        conn=get_db(); set_setting(conn,'role_access_map',json.dumps(amap,ensure_ascii=False)); conn.commit(); conn.close(); return jsonify({'ok':True})

    # ---- Finance advanced --------------------------------------------------
    @app.route('/api/native/finance/settlements')
    def native_finance_settlements():
        u=get_current_user()
        if not u or not user_has_access(u,'finance'): return jsonify({'error':'forbidden'}),403
        from core.wages import ensure_wage_schema,summarize_rep_wages
        year,month=_ym(request); q=(request.args.get('q') or '').strip().lower(); conn=get_db(); ensure_wage_schema(conn)
        reps=conn.execute("SELECT id,first_name,last_name,company_name,province,status FROM representatives ORDER BY id DESC").fetchall(); rows=[]
        for r in reps:
            name=((r['first_name'] or '')+' '+(r['last_name'] or '')).strip() or r['company_name'] or ('#'+str(r['id']))
            if q and q not in (name+' '+str(r['province'] or '')).lower(): continue
            sm=summarize_rep_wages(conn,r['id'],year,month)
            rows.append({'id':r['id'],'name':name,'province':r['province'] or '','month_total':sm['month_total'],'unpaid_month':sm['unpaid_month'],'paid_month':sm['paid_month'],'settle_status':sm['settle_status']})
        conn.close(); return jsonify({'rows':rows,'year':year,'month':month})

    @app.route('/api/native/finance/settlement/<int:rep_id>')
    def native_finance_settlement(rep_id):
        u=get_current_user()
        if not u or not user_has_access(u,'finance'): return jsonify({'error':'forbidden'}),403
        from core.wages import ensure_wage_schema,summarize_rep_wages,get_rep_bank_info
        year,month=_ym(request); conn=get_db(); ensure_wage_schema(conn); rep=conn.execute('SELECT * FROM representatives WHERE id=?',(rep_id,)).fetchone()
        if not rep: conn.close(); return jsonify({'error':'not_found'}),404
        sm=summarize_rep_wages(conn,rep_id,year,month); bank=get_rep_bank_info(conn,rep_id); conn.close()
        return jsonify({'rep':dict(rep),'year':year,'month':month,'summary':sm,'bank':bank})

    @app.route('/api/native/finance/settlement/<int:rep_id>',methods=['POST'])
    def native_finance_settlement_save(rep_id):
        u=get_current_user()
        if not u or not user_has_access(u,'finance'): return jsonify({'error':'forbidden'}),403
        from core.wages import ensure_wage_schema,summarize_rep_wages,get_rep_bank_info
        import jdatetime
        year,month=_ym(request); action=request.form.get('action','pay'); conn=get_db(); ensure_wage_schema(conn); sm=summarize_rep_wages(conn,rep_id,year,month)
        if action!='pay' or sm['month_total']<=0: conn.close(); return jsonify({'ok':False,'error':'مبلغی برای تسویه در این ماه وجود ندارد.'}),400
        bank=get_rep_bank_info(conn,rep_id); rep=conn.execute('SELECT * FROM representatives WHERE id=?',(rep_id,)).fetchone(); name=((rep['first_name'] or '')+' '+(rep['last_name'] or '')).strip() or rep['company_name'] or ('#'+str(rep_id)); today=jdatetime.date.today(); now=jdatetime.datetime.now(); paid_at=f'{today.year}/{today.month:02d}/{today.day:02d}'; receipt=f'WS-{year}{month:02d}-{rep_id}-{today.day:02d}{now.hour:02d}{now.minute:02d}'
        existing=conn.execute('SELECT id FROM wage_settlements WHERE representative_id=? AND year=? AND month=?',(rep_id,year,month)).fetchone()
        if existing:
            sid=existing['id']; conn.execute('UPDATE wage_settlements SET total_amount=?,paid_amount=?,status=?,paid_at=?,paid_by=?,receipt_no=?,notes=?,bank_sheba=?,bank_card=?,bank_owner=? WHERE id=?',(sm['month_total'],sm['unpaid_month'] or sm['month_total'],'paid',paid_at,(u['full_name'] if 'full_name' in u.keys() else '') or (u['username'] if 'username' in u.keys() else '') or '',receipt,request.form.get('notes') or '',bank.get('bank_sheba'),bank.get('bank_card'),bank.get('bank_owner'),sid))
        else:
            cur=conn.execute('INSERT INTO wage_settlements(representative_id,representative_name,year,month,total_amount,paid_amount,status,paid_at,paid_by,receipt_no,notes,bank_sheba,bank_card,bank_owner,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rep_id,name,year,month,sm['month_total'],sm['unpaid_month'] or sm['month_total'],'paid',paid_at,(u['full_name'] if 'full_name' in u.keys() else '') or (u['username'] if 'username' in u.keys() else '') or '',receipt,request.form.get('notes') or '',bank.get('bank_sheba'),bank.get('bank_card'),bank.get('bank_owner'),paid_at)); sid=cur.lastrowid
        ids=[r['id'] for r in sm['month_rows'] if (r['payment_status'] or 'unpaid')!='paid']
        if ids:
            ph=','.join('?'*len(ids)); conn.execute(f"UPDATE wage_calculations SET payment_status='paid',settlement_id=?,paid_at=? WHERE id IN ({ph})",[sid,paid_at]+ids)
        conn.commit(); conn.close(); return jsonify({'ok':True,'id':sid,'receipt_no':receipt})

    @app.route('/api/native/finance/settlement/receipt/<int:settlement_id>')
    def native_finance_settlement_receipt(settlement_id):
        u=get_current_user()
        if not u or not user_has_access(u,'finance'): return jsonify({'error':'forbidden'}),403
        conn=get_db(); s=conn.execute('SELECT * FROM wage_settlements WHERE id=?',(settlement_id,)).fetchone(); lines=conn.execute('SELECT * FROM wage_calculations WHERE settlement_id=? ORDER BY id',(settlement_id,)).fetchall() if s else [] ; conn.close()
        if not s: return jsonify({'error':'not_found'}),404
        return jsonify({'settlement':dict(s),'lines':[dict(x) for x in lines]})

    @app.route('/api/native/finance/invoices')
    def native_finance_invoices():
        u=get_current_user()
        if not u or not user_has_access(u,'finance'): return jsonify({'error':'forbidden'}),403
        q=(request.args.get('q') or '').strip().lower(); conn=get_db(); rows=[dict(r) for r in conn.execute("SELECT id,reception_no,customer_name,serial_number,device_type,status,invoice_number,reception_date FROM requests ORDER BY id DESC LIMIT 1000").fetchall()]; conn.close()
        if q: rows=[r for r in rows if q in ' '.join(str(r.get(k) or '') for k in ('id','reception_no','customer_name','serial_number','device_type','status','invoice_number')).lower()]
        return jsonify({'rows':rows})
    @app.route('/api/native/finance/invoices/<int:request_id>',methods=['POST'])
    def native_finance_invoice_save(request_id):
        u=get_current_user()
        if not u or not user_has_access(u,'finance'): return jsonify({'error':'forbidden'}),403
        no=(request.form.get('invoice_number') or '').strip()
        inv_date=(request.form.get('invoice_date') or '').strip()
        if not no: return jsonify({'ok':False,'error':'شماره فاکتور را وارد کنید.'}),400
        if not inv_date: return jsonify({'ok':False,'error':'تاریخ فاکتور را وارد کنید.'}),400
        conn=get_db()
        req=conn.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
        if not req: conn.close(); return jsonify({'ok':False,'error':'پرونده یافت نشد.'}),404
        if (req['request_category'] or '') != 'تعمیر' or (req['service_type'] or '') != 'کارخانه' or (req['status'] or '') != 'در انتظار صدور فاکتور است':
            conn.close(); return jsonify({'ok':False,'error':'این پرونده در مرحله ثبت فاکتور نهایی نیست.'}),409
        try:
            from core.history import invoice_is_duplicate
            if invoice_is_duplicate(conn, no, exclude_request_id=request_id):
                conn.close(); return jsonify({'ok':False,'error':'شماره فاکتور تکراری است.'}),409
            from core.workflow import transition_request
            transition_request(conn, request_id, 'پایان تعمیرات', actor_name=u.get('full_name'), actor_role=u.get('role'), expected_status='در انتظار صدور فاکتور است', note='ثبت اطلاعات فاکتور نهایی صادرشده در نرم‌افزار خارجی')
            conn.execute('UPDATE requests SET invoice_number=?, invoice_date=? WHERE id=?',(no,inv_date,request_id))
            conn.commit()
        except Exception as exc:
            conn.rollback(); conn.close(); return jsonify({'ok':False,'error':str(exc)}),400
        conn.close(); return jsonify({'ok':True,'id':request_id,'status':'پایان تعمیرات'})

    # ---- Reports: stage delays --------------------------------------------
    @app.route('/api/native/reports/stage-delays')
    def native_report_stage_delays():
        u=get_current_user()
        if not u or not user_has_access(u,'reports'): return jsonify({'error':'forbidden'}),403
        q=(request.args.get('q') or '').strip().lower(); conn=get_db()
        try:
            rows=conn.execute("SELECT r.id,r.reception_no,r.customer_name,r.serial_number,r.status,r.request_category,r.province,r.assigned_technician,COUNT(sd.id) stage_count FROM requests r LEFT JOIN request_stage_dates sd ON sd.request_id=r.id GROUP BY r.id ORDER BY r.id DESC LIMIT 500").fetchall()
        except Exception: rows=[]
        conn.close(); data=[dict(r) for r in rows]
        if q: data=[r for r in data if q in ' '.join(str(r.get(k) or '') for k in ('id','reception_no','customer_name','serial_number','status','request_category','province','assigned_technician')).lower()]
        return jsonify({'rows':data})

    # ---- Account -----------------------------------------------------------
    @app.route('/api/native/account/profile')
    def native_account_profile():
        u=get_current_user()
        if not u: return jsonify({'error':'auth_required'}),401
        conn=get_db(); row=conn.execute('SELECT id,full_name,username,role,province,city,created_at,bank_card,bank_sheba,bank_owner FROM users WHERE id=?',(u['id'],)).fetchone(); conn.close(); return jsonify({'data':dict(row) if row else {}})
    @app.route('/api/native/account/profile/save',methods=['POST'])
    def native_account_profile_save():
        u=get_current_user()
        if not u: return jsonify({'error':'auth_required'}),401
        name=(request.form.get('full_name') or '').strip()
        if not name: return jsonify({'ok':False,'error':'نام نمایشی الزامی است.'}),400
        bank_card=(request.form.get('bank_card') or '').strip()
        bank_sheba=(request.form.get('bank_sheba') or '').strip()
        bank_owner=(request.form.get('bank_owner') or '').strip()
        conn=get_db(); conn.execute('UPDATE users SET full_name=?, bank_card=?, bank_sheba=?, bank_owner=? WHERE id=?',(name,bank_card,bank_sheba,bank_owner,u['id'])); conn.commit(); conn.close(); return jsonify({'ok':True})
    @app.route('/api/native/account/password',methods=['POST'])
    def native_account_password():
        u=get_current_user()
        if not u: return jsonify({'error':'auth_required'}),401
        from werkzeug.security import check_password_hash,generate_password_hash
        cur=(request.form.get('current_password') or '').strip(); n1=(request.form.get('new_password') or '').strip(); n2=(request.form.get('new_password2') or '').strip()
        if not check_password_hash(u['password_hash'],cur): return jsonify({'ok':False,'error':'رمز فعلی اشتباه است.'}),400
        if len(n1)<8: return jsonify({'ok':False,'error':'رمز جدید باید حداقل ۸ کاراکتر باشد.'}),400
        if n1!=n2: return jsonify({'ok':False,'error':'تکرار رمز جدید مطابقت ندارد.'}),400
        conn=get_db(); conn.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(n1),u['id'])); conn.commit(); conn.close(); return jsonify({'ok':True})
