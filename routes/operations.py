# -*- coding: utf-8 -*-
"""عملیات، داشبورد نقش‌محور و گردش وضعیت پرونده."""
from flask import redirect, render_template, request
from core.db import get_db
from core.helpers import get_current_user, user_has_access, notify_user
from core.case_management import ensure_case_schema, set_case_status, case_timeline, add_timeline
from core.reception_numbers import assign_reception_no
from core.customer_notify import notify_status_change
from core.workflow import transition_request, WorkflowError

def register(app):
    @app.route('/operations/dashboard')
    def operations_dashboard():
        user = get_current_user()
        if not user: return redirect('/login')
        if not user_has_access(user, 'dashboard'): return redirect('/')
        conn=get_db(); ensure_case_schema(conn)
        role=user['role']
        open_cases=conn.execute("SELECT COUNT(*) c FROM requests WHERE COALESCE(status,'') NOT IN ('بسته شد','آماده تحویل')").fetchone()['c']
        waiting=conn.execute("SELECT COUNT(*) c FROM requests WHERE status='در انتظار بررسی پذیرش'").fetchone()['c']
        today=conn.execute("SELECT COUNT(*) c FROM requests WHERE DATE(reception_date)=DATE('now')").fetchone()['c']
        unread=conn.execute("SELECT COUNT(*) c FROM notifications WHERE user_name=? AND COALESCE(is_read,0)=0", (user['full_name'],)).fetchone()['c']
        by_status=conn.execute("SELECT COALESCE(status,'بدون وضعیت') status, COUNT(*) c FROM requests GROUP BY COALESCE(status,'بدون وضعیت') ORDER BY c DESC LIMIT 8").fetchall()
        recent=conn.execute("SELECT id,reception_no,customer_name,device_type,status,request_category FROM requests ORDER BY CASE WHEN status='در انتظار بررسی پذیرش' THEN 0 ELSE 1 END, id DESC LIMIT 20").fetchall()
        conn.close()
        return render_template('operations_dashboard.html', current_user=user, role=role, open_cases=open_cases, waiting=waiting, today=today, unread=unread, by_status=by_status, recent=recent, active_page='dashboard')


    @app.route('/operations/cases/<int:request_id>/reception-review', methods=['POST'])
    def operations_reception_review(request_id):
        user=get_current_user()
        if not user: return redirect('/login')
        if not user_has_access(user, 'customer_affairs'): return redirect('/')
        decision=(request.form.get('decision') or '').strip()
        if decision not in ('issue','no_need','more_info'): return redirect('/operations/dashboard')
        conn=get_db(); ensure_case_schema(conn)
        req=conn.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
        if req:
            # تعمیرات خارجی فقط از مسیر Workflow تعمیر عبور می‌کند؛
            # تصمیم‌های عمومی این داشبورد نباید وضعیت کانونیک تعمیر را دور بزنند.
            if (req['request_category'] or '') == 'تعمیر' and decision != 'issue':
                conn.close()
                return redirect('/operations/dashboard')
            if decision=='issue':
                no=assign_reception_no(conn, request_id, request_category=req['request_category'] or '')
                if (req['request_category'] or '') == 'تعمیر' and (req['service_type'] or '') == 'در محل':
                    try:
                        transition_request(conn, request_id, 'پذیرش انجام شد', actor_name=user['full_name'], expected_status='در انتظار بررسی پذیرش', note='تأیید پذیرش تعمیر خارجی')
                    except WorkflowError:
                        conn.rollback(); conn.close(); return redirect('/operations/dashboard')
                else:
                    set_case_status(conn, request_id, 'پذیرش شد', user['full_name'])
                add_timeline(conn, request_id, 'صدور شماره پذیرش', f'پس از بررسی پذیرش، شماره پذیرش {no} صادر شد.', 'reception', 'user', user['full_name'])
            elif decision=='no_need':
                set_case_status(conn, request_id, 'در حال رسیدگی بدون پذیرش', user['full_name'])
                add_timeline(conn, request_id, 'عدم نیاز به پذیرش', 'کارمند پذیرش تشخیص داد این درخواست به شماره پذیرش نیاز ندارد.', 'reception', 'user', user['full_name'])
            else:
                set_case_status(conn, request_id, 'نیاز به اطلاعات بیشتر', user['full_name'])
                add_timeline(conn, request_id, 'نیاز به اطلاعات بیشتر', 'پذیرش برای ادامه رسیدگی اطلاعات تکمیلی درخواست کرده است.', 'reception', 'user', user['full_name'])
            conn.commit()
        conn.close(); return redirect('/operations/dashboard')

    # تغییر وضعیت عمومی پرونده عمداً حذف شد؛ Transition باید از Workflow دامنه انجام شود.
