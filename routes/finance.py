# -*- coding: utf-8 -*-
from __future__ import annotations
from flask import request, redirect, render_template
import jdatetime

from core.helpers import *  # noqa: F401,F403
from core.constants import *  # noqa: F401,F403

def register(app):
    """مسیرهای finance."""
    # دسترسی به هلپرها
    @app.route('/finance')
    def finance_hub():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or _is_finance(current_user) or user_has_access(current_user, 'finance')):
            return redirect('/')
        return render_template(
            'finance_hub.html',
            active_page='finance-hub',
            current_user=current_user,
        )

    @app.route('/finance/wage-calculation', methods=['GET', 'POST'])
    def finance_wage_calculation():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or _is_finance(current_user) or user_has_access(current_user, 'finance')):
            return redirect('/')

        from core.wages import (
            ensure_wage_schema, seed_default_wage_rates, get_rate,
            compute_travel, get_rep_city, save_wage_lines, travel_already_paid,
            is_same_city,
        )
        conn = get_db()
        ensure_wage_schema(conn)
        seed_default_wage_rates(conn)
        msg = error = None

        if request.method == 'POST':
            try:
                representative_id = request.form.get('representative_id') or None
                if representative_id:
                    representative_id = int(representative_id)
                representative_name = (request.form.get('representative_name') or '').strip()
                rate_id = request.form.get('rate_id')
                qty = int(request.form.get('qty') or 1)
                calc_date = request.form.get('calc_date') or _jalali_from_form('calc') or ''
                notes = request.form.get('notes') or ''
                customer_name = (request.form.get('customer_name') or '').strip()
                customer_city = (request.form.get('customer_city') or '').strip()
                customer_province = (request.form.get('customer_province') or '').strip()
                add_travel = bool(request.form.get('add_travel'))
                work_description = (request.form.get('work_description') or '').strip()
                amount = int(request.form.get('amount') or 0)

                rate_code = None
                if rate_id:
                    row = conn.execute('SELECT * FROM wage_rates WHERE id = ?', (int(rate_id),)).fetchone()
                    if row:
                        rate_code = row['rate_code'] if 'rate_code' in row.keys() else None
                        if not work_description:
                            work_description = row['work_description']
                        # recalculate from rate if amount empty
                        if not amount:
                            amount = int(row['wage_amount'] or 0) * qty
                        # repair outside adjustment
                        if rate_code == 'repair' and representative_id and customer_city:
                            rc, rp, _, rname = get_rep_city(conn, representative_id)
                            if not is_same_city(rc, customer_city) and row['amount_outside']:
                                amount = int(row['amount_outside']) * qty
                                work_description = row['work_description'] + ' (خارج محل نمایندگی)'
                            elif is_same_city(rc, customer_city):
                                work_description = row['work_description'] + ' (محل نمایندگی)'
                        if not representative_name and representative_id:
                            _, _, _, representative_name = get_rep_city(conn, representative_id)

                lines = [{
                    'rate_code': rate_code,
                    'description': work_description,
                    'amount': amount,
                    'qty': qty,
                }]

                if add_travel and representative_id:
                    if not travel_already_paid(conn, representative_id, customer_name or customer_city, calc_date):
                        rc, rp, _, _ = get_rep_city(conn, representative_id)
                        travel = compute_travel(conn, rc, rp, customer_city, customer_province)
                        lines.append({
                            'rate_code': travel['rate_code'],
                            'description': travel['description'],
                            'amount': travel['travel_amount'],
                            'qty': 1,
                            'is_local': travel['is_local'],
                            'distance_km': travel.get('distance_km'),
                        })
                    else:
                        notes = (notes + ' | ایاب این تاریخ/مشتری قبلاً ثبت شده').strip(' |')

                save_wage_lines(
                    conn, lines, representative_id, representative_name, calc_date,
                    customer_name=customer_name or None, source='manual', notes=notes,
                )
                msg = 'ثبت شد'
            except Exception as e:
                error = str(e)

        representatives = conn.execute(
            "SELECT * FROM representatives WHERE status = 'فعال' ORDER BY first_name"
        ).fetchall()
        wage_rates = conn.execute(
            'SELECT * FROM wage_rates WHERE COALESCE(is_active,1)=1 ORDER BY COALESCE(sort_order,999), id'
        ).fetchall()
        recent_calcs = conn.execute('SELECT * FROM wage_calculations ORDER BY id DESC LIMIT 20').fetchall()
        conn.close()

        today = jdatetime.date.today()
        return render_template(
            'finance_wage_calculation.html',
            representatives=representatives, wage_rates=wage_rates, recent_calcs=recent_calcs,
            active_page='finance-wage-calc', current_user=current_user,
            jalali_months=JALALI_MONTHS,
            today_year=today.year, today_month=today.month, today_day=today.day,
            msg=msg, error=error,
        )


    @app.route('/finance/wage-history')
    def finance_wage_history():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or _is_finance(current_user) or user_has_access(current_user, 'finance')):
            return redirect('/')

        conn = get_db()
        calcs = conn.execute('SELECT * FROM wage_calculations ORDER BY id DESC').fetchall()
        conn.close()

        return render_template(
            'finance_wage_history.html', calcs=calcs,
            active_page='finance-wage-history', current_user=current_user
        )




    @app.route('/finance/invoices', methods=['GET', 'POST'])
    def finance_invoices():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or _is_finance(current_user) or user_has_access(current_user, 'finance')):
            return redirect('/')

        conn = get_db()
        if request.method == 'POST':
            # ثبت فاکتور فقط از Action رسمی همان مرحله انجام می‌شود؛
            # این صفحه دیگر مجاز به UPDATE مستقیم invoice_number نیست.
            request_id = request.form.get('request_id')
            if request_id:
                conn.close()
                return redirect(f'/service/internal-repair/view/{int(request_id)}?err=use_invoice_workflow')
            conn.close()
            return redirect('/finance/invoices?err=use_invoice_workflow')

        rows = conn.execute('SELECT * FROM requests ORDER BY id DESC').fetchall()
        conn.close()

        return render_template(
            'finance_invoices.html', requests=rows,
            active_page='finance-invoices', current_user=current_user
        )

    def _ym_from_request():
        today = jdatetime.date.today()
        year, month = today.year, today.month
        try:
            if request.args.get('year'):
                year = int(request.args.get('year'))
            if request.args.get('month'):
                month = max(1, min(12, int(request.args.get('month'))))
        except Exception:
            pass
        return year, month

    def _user_rep_id(user):
        try:
            rid = user['representative_id']
            return int(rid) if rid else None
        except Exception:
            return None

    def _can_manage_finance(user):
        if not user:
            return False
        try:
            role = user['role'] or ''
        except Exception:
            role = ''
        if role in ('مسئول پذیرش', 'امور مالی', 'مدیر', 'مدیر سیستم'):
            return True
        try:
            return bool(user_has_access(user, 'finance'))
        except Exception:
            return False

    @app.route('/my-wages')
    def my_wages():
        """دستمزد نماینده: ماه/سال + وضعیت تسویه + اطلاعات بانکی."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')

        from core.wages import (
            ensure_wage_schema, summarize_rep_wages, get_rep_bank_info, month_name_fa,
        )

        year, month = _ym_from_request()
        rep_id = _user_rep_id(current_user)
        full_name = ''
        try:
            full_name = current_user['full_name'] or current_user['username'] or ''
        except Exception:
            pass

        conn = get_db()
        ensure_wage_schema(conn)

        rep_name = full_name
        bank = {'bank_card': '', 'bank_sheba': '', 'bank_owner': '', 'mobile': ''}
        summary = {
            'month_total': 0, 'year_total': 0, 'unpaid_month': 0, 'paid_month': 0,
            'month_rows': [], 'settlement': None, 'settle_status': 'empty',
        }

        if rep_id:
            summary = summarize_rep_wages(conn, rep_id, year, month)
            bank = get_rep_bank_info(conn, rep_id)
            try:
                if current_user['bank_sheba']:
                    bank['bank_sheba'] = current_user['bank_sheba']
                if current_user['bank_card']:
                    bank['bank_card'] = current_user['bank_card']
                if current_user['bank_owner']:
                    bank['bank_owner'] = current_user['bank_owner']
            except Exception:
                pass
            rep = conn.execute(
                'SELECT first_name, last_name, company_name FROM representatives WHERE id = ?',
                (int(rep_id),),
            ).fetchone()
            if rep:
                fn = ((rep['first_name'] or '') + ' ' + (rep['last_name'] or '')).strip()
                rep_name = fn or rep['company_name'] or full_name

                conn.close()
        return render_template(
            'my_wages.html',
            current_user=current_user,
            active_page='my-wages',
            year=year,
            month=month,
            month_label=month_name_fa(month),
            month_total=summary['month_total'],
            year_total=summary['year_total'],
            unpaid_month=summary['unpaid_month'],
            paid_month=summary['paid_month'],
            month_rows=summary['month_rows'],
            settle_status=summary['settle_status'],
            settlement=summary['settlement'],
            bank=bank,
            rep_name=rep_name,
            has_rep_link=bool(rep_id),
        )

    @app.route('/finance/reps-dashboard')
    def finance_reps_dashboard():
        """خلاصه مالی همه نمایندگان — برای مدیر/مالی."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not _can_manage_finance(current_user):
            return redirect('/')

        from core.wages import ensure_wage_schema, summarize_rep_wages, get_rep_bank_info, month_name_fa

        year, month = _ym_from_request()
        conn = get_db()
        ensure_wage_schema(conn)

        reps = conn.execute(
            "SELECT * FROM representatives WHERE COALESCE(status,'فعال') != 'بایگانی' ORDER BY first_name, company_name"
        ).fetchall()

        rows = []
        grand_month = grand_unpaid = grand_year = 0
        for rep in reps:
            rid = rep['id']
            name = ((rep['first_name'] or '') + ' ' + (rep['last_name'] or '')).strip() or (rep['company_name'] or ('#' + str(rid)))
            s = summarize_rep_wages(conn, rid, year, month)
            bank = get_rep_bank_info(conn, rid)
            rows.append({
                'id': rid,
                'name': name,
                'province': rep['province'] if 'province' in rep.keys() else '',
                'month_total': s['month_total'],
                'year_total': s['year_total'],
                'unpaid_month': s['unpaid_month'],
                'paid_month': s['paid_month'],
                'settle_status': s['settle_status'],
                'settlement': s['settlement'],
                'bank_sheba': bank.get('bank_sheba') or '',
                'bank_owner': bank.get('bank_owner') or '',
            })
            grand_month += s['month_total']
            grand_unpaid += s['unpaid_month']
            grand_year += s['year_total']

        rows.sort(key=lambda x: (-x['unpaid_month'], -x['month_total'], x['name']))

        conn.close()
        return render_template(
            'finance_reps_dashboard.html',
            current_user=current_user,
            active_page='finance-reps-dashboard',
            year=year,
            month=month,
            month_label=month_name_fa(month),
            rows=rows,
            grand_month=grand_month,
            grand_unpaid=grand_unpaid,
            grand_year=grand_year,
        )

    @app.route('/finance/settlement/<int:rep_id>', methods=['GET', 'POST'])
    def finance_settlement(rep_id):
        """تسویه ماهانه یک نماینده + تأیید پرداخت."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not _can_manage_finance(current_user):
            return redirect('/')

        from core.wages import (
            ensure_wage_schema, summarize_rep_wages, get_rep_bank_info, month_name_fa,
        )

        year, month = _ym_from_request()
        conn = get_db()
        ensure_wage_schema(conn)

        rep = conn.execute('SELECT * FROM representatives WHERE id = ?', (rep_id,)).fetchone()
        if not rep:
            return redirect('/finance/reps-dashboard')

        rep_name = ((rep['first_name'] or '') + ' ' + (rep['last_name'] or '')).strip() or (rep['company_name'] or ('#' + str(rep_id)))
        bank = get_rep_bank_info(conn, rep_id)
        msg = error = None

        if request.method == 'POST':
            action = request.form.get('action') or 'pay'
            notes = (request.form.get('notes') or '').strip()
            paid_by = ''
            try:
                paid_by = current_user['full_name'] or current_user['username'] or ''
            except Exception:
                paid_by = ''

            summary = summarize_rep_wages(conn, rep_id, year, month)
            unpaid_ids = []
            unpaid_sum = 0
            for r in summary['month_rows']:
                st = (r['payment_status'] if 'payment_status' in r.keys() else None) or 'unpaid'
                if st != 'paid':
                    unpaid_ids.append(r['id'])
                    unpaid_sum += int(r['amount'] or 0)

            if action == 'pay' and unpaid_sum <= 0 and summary['month_total'] <= 0:
                error = 'مبلغی برای تسویه در این ماه وجود ندارد.'
            elif action == 'pay':
                today = jdatetime.date.today()
                now = jdatetime.datetime.now()
                paid_at = f'{today.year}/{str(today.month).zfill(2)}/{str(today.day).zfill(2)}'
                receipt_no = f'WS-{year}{str(month).zfill(2)}-{rep_id}-{str(today.day).zfill(2)}{str(now.hour).zfill(2)}{str(now.minute).zfill(2)}'

                total_amount = summary['month_total']
                paid_amount = unpaid_sum if unpaid_sum > 0 else total_amount

                existing = conn.execute(
                    'SELECT id FROM wage_settlements WHERE representative_id = ? AND year = ? AND month = ?',
                    (rep_id, year, month),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE wage_settlements SET total_amount=?, paid_amount=?, status=?, paid_at=?, paid_by=?, receipt_no=?, notes=?, bank_sheba=?, bank_card=?, bank_owner=? WHERE id=?",
                        (
                            total_amount, paid_amount, 'paid', paid_at, paid_by,
                            receipt_no, notes, bank.get('bank_sheba'), bank.get('bank_card'),
                            bank.get('bank_owner'), existing['id'],
                        ),
                    )
                    settlement_id = existing['id']
                else:
                    cur = conn.execute(
                        "INSERT INTO wage_settlements (representative_id, representative_name, year, month, total_amount, paid_amount, status, paid_at, paid_by, receipt_no, notes, bank_sheba, bank_card, bank_owner, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            rep_id, rep_name, year, month, total_amount, paid_amount,
                            'paid', paid_at, paid_by, receipt_no, notes,
                            bank.get('bank_sheba'), bank.get('bank_card'), bank.get('bank_owner'), paid_at,
                        ),
                    )
                    settlement_id = cur.lastrowid

                if unpaid_ids:
                    placeholders = ','.join('?' * len(unpaid_ids))
                    conn.execute(
                        "UPDATE wage_calculations SET payment_status='paid', settlement_id=?, paid_at=? WHERE id IN (" + placeholders + ")",
                        [settlement_id, paid_at] + unpaid_ids,
                    )
                conn.commit()
                return redirect('/finance/settlement/receipt/' + str(settlement_id))
            elif action == 'unpay':
                s = summarize_rep_wages(conn, rep_id, year, month)
                for r in s['month_rows']:
                    conn.execute(
                        "UPDATE wage_calculations SET payment_status='unpaid', settlement_id=NULL, paid_at=NULL WHERE id=?",
                        (r['id'],),
                    )
                conn.execute(
                    "UPDATE wage_settlements SET status='pending', paid_amount=0, paid_at=NULL, receipt_no=NULL WHERE representative_id=? AND year=? AND month=?",
                    (rep_id, year, month),
                )
                conn.commit()
                msg = 'وضعیت به «در انتظار پرداخت» برگشت.'

        summary = summarize_rep_wages(conn, rep_id, year, month)
        conn.close()
        return render_template(
            'finance_settlement.html',
            current_user=current_user,
            active_page='finance-settlement',
            rep=rep,
            rep_id=rep_id,
            rep_name=rep_name,
            year=year,
            month=month,
            month_label=month_name_fa(month),
            summary=summary,
            bank=bank,
            msg=msg,
            error=error,
        )

    @app.route('/finance/settlement/receipt/<int:settlement_id>')
    def finance_settlement_receipt(settlement_id):
        """رسید تسویه ماهانه."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')

        from core.wages import ensure_wage_schema, month_name_fa, parse_calc_ym

        conn = get_db()
        ensure_wage_schema(conn)
        s = conn.execute('SELECT * FROM wage_settlements WHERE id = ?', (settlement_id,)).fetchone()
        if not s:
            conn.close()
            return redirect('/finance/reps-dashboard')

        if not _can_manage_finance(current_user):
            rid = _user_rep_id(current_user)
            if not rid or int(rid) != int(s['representative_id']):
                return redirect('/my-wages')

        lines = conn.execute(
            'SELECT * FROM wage_calculations WHERE settlement_id = ? ORDER BY id',
            (settlement_id,),
        ).fetchall()
        if not lines:
            all_paid = conn.execute(
                "SELECT * FROM wage_calculations WHERE representative_id = ? AND COALESCE(payment_status,'') = 'paid' ORDER BY id",
                (s['representative_id'],),
            ).fetchall()
            lines = []
            for r in all_paid:
                y, m = parse_calc_ym(r['calc_date'] if 'calc_date' in r.keys() else None)
                if y == s['year'] and m == s['month']:
                            conn.close()
        lines.append(r)

        return render_template(
            'finance_settlement_receipt.html',
            current_user=current_user,
            active_page='finance-settlement-receipt',
            settlement=s,
            lines=lines,
            month_label=month_name_fa(s['month']),
        )
