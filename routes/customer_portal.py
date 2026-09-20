# -*- coding: utf-8 -*-
"""پرتال مشتری — PWA سبک، بدون رمز عبور.

ورود: شماره موبایل + کد پیگیری (reception_no مثل P-1405-00042).
هیچ داده یا مسیر کارمندی (core/helpers, routes.auth, ...) توسط این ماژول
تغییر نمی‌کند؛ فقط از جدول موجود ``requests`` می‌خواند.
"""
from __future__ import annotations

from flask import request, session, redirect, render_template, jsonify, url_for, Response, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os, time, secrets
from werkzeug.utils import secure_filename

from core.db import get_db
from core.customer_auth import find_request_by_phone_and_code, normalize_phone
from core.customer_notify import stage_for_status, STAGE_RECEIVED
from core.push import get_vapid_public_key
from core.security import client_ip, login_is_locked, login_register_failure, login_clear_failures
from core.case_management import ensure_case_schema, upsert_device, add_timeline, case_timeline
from core.constants import INTERNAL_REPAIR_STATUSES, EXTERNAL_REPAIR_STATUSES, RECEPTION_ROLES

SESSION_KEY = "customer_verified"
PORTAL_SESSION_KEY = "customer_portal_customer_id"

# انواع درخواست خدمات در پرتال مشتری (ادغام اعلام خرابی + درخواست سرویس)
SERVICE_REQUEST_KINDS = (
    ("fault", "اعلام خرابی / تعمیر"),
    ("periodic", "سرویس دوره‌ای"),
    ("visit", "بازدید / بررسی"),
    ("install", "نصب و آموزش"),
    ("demo", "نصب Demo / امانی"),
    ("other", "سایر خدمات"),
)

PENDING_RECEPTION_STATUS = "در انتظار بررسی پذیرش"


def _notify_reception_staff(conn, request_id, title, body, url=None):
    """ثبت اعلان برای نقش‌های پذیرش/مدیر در هدر (notifications)، نه کارتابل."""
    try:
        from core.helpers import notify_user
        roles = tuple(RECEPTION_ROLES)
        ph = ",".join("?" * len(roles))
        rows = conn.execute(
            f"SELECT full_name FROM users WHERE role IN ({ph}) AND IFNULL(is_active,1)=1",
            roles,
        ).fetchall()
        for r in rows:
            name = r["full_name"] if hasattr(r, "keys") else r[0]
            if name:
                notify_user(conn, name, request_id, title, body, url=url or f"/service/request/{request_id}")
    except Exception:
        pass


def _verified_list():
    return session.get(SESSION_KEY) or []


def _stage_label(stage: str) -> str:
    return {
        "received": "پذیرش شد",
        "repair": "در حال بررسی/تعمیر",
        "ready": "آماده تحویل",
    }.get(stage, "در حال بررسی/تعمیر")


def register(app):

    def _portal_customer_id():
        return session.get(PORTAL_SESSION_KEY)

    def _portal_account(conn, customer_id):
        return conn.execute("SELECT * FROM customer_portal_accounts WHERE customer_id=?", (customer_id,)).fetchone()

    def _ensure_customer_portal_schema(conn):
        """Schema کوچک فاز ۳ برای جداسازی مکالمات عمومی از پرونده‌های خدمات."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_portal_chat_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(customer_id, thread_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_portal_chat_links_customer ON customer_portal_chat_links(customer_id, thread_id)")
        conn.commit()

    def _ensure_portal_survey_schema(conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_portal_surveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(customer_id)
            )
        """)
        conn.commit()

    @app.route("/c/login", methods=["GET", "POST"])
    def customer_login():
        error = None
        if request.method == "POST":
            ip = client_ip()
            locked, remain = login_is_locked(ip)
            if locked:
                error = f"تعداد تلاش‌ها زیاد بود. لطفاً {remain} ثانیه دیگر دوباره امتحان کنید."
            else:
                national_id = (request.form.get("national_id") or "").strip().replace("-", "")
                password = request.form.get("password") or ""
                conn = get_db()
                customer = conn.execute("SELECT id, name, national_id FROM customers WHERE TRIM(national_id)=? AND COALESCE(is_archived,0)=0", (national_id,)).fetchone()
                if customer:
                    account = _portal_account(conn, customer["id"])
                    if not account:
                        conn.execute("INSERT INTO customer_portal_accounts(customer_id,password_hash,must_change_password,is_active) VALUES(?,?,1,1)", (customer["id"], generate_password_hash(national_id)))
                        conn.commit(); account = _portal_account(conn, customer["id"])
                    valid = account["is_active"] and check_password_hash(account["password_hash"], password)
                    if valid:
                        login_clear_failures(ip)
                        session.clear(); session[PORTAL_SESSION_KEY] = customer["id"]; session.permanent = True
                        conn.execute("UPDATE customer_portal_accounts SET last_login=?, updated_at=? WHERE customer_id=?", (datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), customer["id"])); conn.commit(); conn.close()
                        if account["must_change_password"]: return redirect(url_for("customer_change_password"))
                        return redirect(url_for("customer_home"))
                conn.close(); login_register_failure(ip); error = "نام کاربری یا رمز عبور صحیح نیست."
        return render_template("customer/login.html", error=error)

    @app.route("/c/change-password", methods=["GET", "POST"])
    def customer_change_password():
        cid = _portal_customer_id()
        if not cid: return redirect(url_for("customer_login"))
        error = None
        if request.method == "POST":
            current = request.form.get("current_password") or ""; new = request.form.get("new_password") or ""; confirm = request.form.get("confirm_password") or ""
            conn = get_db(); account = _portal_account(conn, cid)
            if not account or not check_password_hash(account["password_hash"], current): error = "رمز فعلی صحیح نیست."
            elif len(new) < 8: error = "رمز جدید باید حداقل ۸ کاراکتر باشد."
            elif new != confirm: error = "تکرار رمز جدید مطابقت ندارد."
            else:
                conn.execute("UPDATE customer_portal_accounts SET password_hash=?, must_change_password=0, updated_at=? WHERE customer_id=?", (generate_password_hash(new), datetime.utcnow().isoformat(), cid)); conn.commit(); conn.close(); return redirect(url_for("customer_home"))
            conn.close()
        return render_template("customer/change_password.html", error=error)

    @app.route("/c/logout")
    def customer_logout():
        session.pop(SESSION_KEY, None)
        session.pop(PORTAL_SESSION_KEY, None)
        return redirect(url_for("customer_login"))

    @app.route("/c/")
    @app.route("/c/home")
    def customer_home():
        cid = _portal_customer_id()
        if not cid:
            return redirect(url_for("customer_login"))
        conn = get_db()
        customer = conn.execute("SELECT name, phone FROM customers WHERE id=?", (cid,)).fetchone()
        ensure_case_schema(conn)
        service_count = conn.execute("SELECT COUNT(*) AS c FROM requests WHERE customer_id=?", (cid,)).fetchone()["c"]
        # سازگاری با دسته‌های قدیمی + دستهٔ یکپارچهٔ «درخواست خدمات»
        fault_count = conn.execute(
            """SELECT COUNT(*) AS c FROM requests WHERE customer_id=? AND (
                   request_category IN ('اعلام خرابی','درخواست سرویس','درخواست خدمات')
                   OR request_subtype IN ('اعلام خرابی','سرویس دوره‌ای','بازدید / بررسی')
               )""",
            (cid,),
        ).fetchone()["c"]
        request_service_count = fault_count
        device_count = conn.execute("SELECT COUNT(*) AS c FROM customer_devices WHERE customer_id=?", (cid,)).fetchone()["c"]
        chat_count = 0
        try:
            from core.support_chat import ensure_support_schema
            ensure_support_schema(conn)
            chat_count = conn.execute("""SELECT COUNT(DISTINCT st.id) c
                FROM support_threads st LEFT JOIN requests r ON r.id=st.request_id
                WHERE st.public_token IS NOT NULL AND (r.customer_id=? OR st.contact_phone=? OR st.opened_by_name=?)""",
                (cid, (customer["phone"] if customer else "") or "", (customer["name"] if customer else "") or "")).fetchone()["c"]
        except Exception:
            chat_count = 0
        conn.close()
        return render_template("customer/home.html", customer=customer, service_count=service_count, fault_count=fault_count, request_service_count=request_service_count, device_count=device_count, chat_count=chat_count)

    @app.route("/c/fault", methods=["GET", "POST"])
    @app.route("/c/service-request", methods=["GET", "POST"])
    def customer_fault():
        """درخواست خدمات یکپارچه (ادغام اعلام خرابی + درخواست سرویس).

        مسیرهای قدیمی /c/fault و /c/service-request هر دو به همین فرم می‌روند.
        دسته‌بندی با request_category='درخواست خدمات' و request_subtype=نوع سرویس.
        """
        cid = _portal_customer_id()
        if not cid:
            return redirect(url_for("customer_login"))
        conn = get_db()
        customer = conn.execute(
            "SELECT id,name,phone,address,province FROM customers WHERE id=?", (cid,)
        ).fetchone()
        ensure_case_schema(conn)
        category = "درخواست خدمات"
        # پیش‌فرض نوع بر اساس مسیر قدیمی (برای بوکمارک‌ها)
        default_kind = "periodic" if request.path.endswith("/service-request") else "fault"
        error = None
        if request.method == "POST":
            kind_key = (request.form.get("service_kind") or default_kind).strip().lower()
            kind_map = dict(SERVICE_REQUEST_KINDS)
            if kind_key not in kind_map:
                kind_key = "other"
            kind_label = kind_map[kind_key]
            subject = (request.form.get("subject") or kind_label).strip()
            device_type = (request.form.get("device_type") or "").strip()
            serial_number = (request.form.get("serial_number") or "").strip()
            problem_desc = (request.form.get("problem_desc") or "").strip()
            if not problem_desc:
                error = "لطفاً شرح درخواست یا خرابی را وارد کنید."
            else:
                # مسیر تعمیر توسط مشتری تعیین نمی‌شود؛ همه درخواست‌ها ابتدا برای بررسی پذیرش ثبت می‌شوند.
                if not serial_number:
                    error = "ثبت شماره سریال برای هر نوع درخواست الزامی است."
                if error:
                    conn.close()
                    return render_template(
                        "customer/fault.html", customer=customer, error=error, category=category,
                        service_kinds=SERVICE_REQUEST_KINDS, default_kind=kind_key, is_service=False,
                    )
                auto_repair = False

                cols = [
                    "customer_name", "customer_phone", "customer_address",
                    "device_type", "serial_number", "problem_desc",
                    "reception_date", "request_category", "customer_id",
                ]
                vals = [
                    customer["name"], customer["phone"] or "", customer["address"] or "",
                    device_type, serial_number, problem_desc,
                    datetime.utcnow().isoformat(), category, cid,
                ]
                # request_subtype برای مدیریت بر اساس نوع سرویس
                try:
                    cols_check = {r[1] for r in conn.execute("PRAGMA table_info(requests)").fetchall()}
                except Exception:
                    cols_check = set()
                if "request_subtype" in cols_check:
                    cols.append("request_subtype")
                    vals.append(kind_label)


                request_id = None
                try:
                    q = "INSERT INTO requests (%s) VALUES (%s)" % (
                        ",".join(cols), ",".join("?" * len(cols))
                    )
                    cur = conn.execute(q, vals)
                    request_id = cur.lastrowid
                    if auto_repair:
                        conn.execute(
                            "UPDATE requests SET request_category='تعمیر', service_type=?, status=? WHERE id=?",
                            (service_type, initial_status, request_id),
                        )
                    else:
                        conn.execute(
                            "UPDATE requests SET status=? WHERE id=?",
                            (PENDING_RECEPTION_STATUS, request_id),
                        )
                    device_id = upsert_device(
                        conn, cid, device_type or "دستگاه — درخواست خدمات", serial_number
                    )
                    conn.execute(
                        "UPDATE requests SET device_id=? WHERE id=?", (device_id, request_id)
                    )
                    msg = f"درخواست خدمات ({kind_label}) ثبت شد و در انتظار بررسی پذیرش است."

                    add_timeline(
                        conn, request_id, "ثبت درخواست مشتری", msg,
                        "request", "customer", customer["name"],
                    )
                except Exception:
                    if "customer_id" in cols:
                        idx = cols.index("customer_id")
                        cols.pop(idx)
                        vals.pop(idx)
                    q = "INSERT INTO requests (%s) VALUES (%s)" % (
                        ",".join(cols), ",".join("?" * len(cols))
                    )
                    cur = conn.execute(q, vals)
                    request_id = cur.lastrowid
                    if not auto_repair:
                        conn.execute(
                            "UPDATE requests SET status=? WHERE id=?",
                            (PENDING_RECEPTION_STATUS, request_id),
                        )
                    device_id = upsert_device(
                        conn, cid, device_type or "دستگاه — درخواست خدمات", serial_number
                    )
                    try:
                        conn.execute(
                            "UPDATE requests SET device_id=? WHERE id=?", (device_id, request_id)
                        )
                    except Exception:
                        pass
                    add_timeline(
                        conn, request_id, "ثبت درخواست مشتری",
                        f"درخواست خدمات ({kind_label}) ثبت شد و در انتظار بررسی پذیرش است.",
                        "request", "customer", customer["name"],
                    )

                # گفتگوی پرونده (اختیاری — مشتری می‌تواند بعداً از پرونده باز کند)
                from core.support_chat import ensure_support_schema, create_public_thread
                ensure_support_schema(conn)
                _tid, token = create_public_thread(
                    conn,
                    subject=subject or kind_label,
                    contact_name=customer["name"],
                    contact_phone=customer["phone"] or "",
                    request_id=request_id,
                    first_message=problem_desc,
                    serial_number=serial_number,
                )
                add_timeline(
                    conn, request_id, "کانال گفتگوی پرونده آماده شد",
                    "گفتگو از پرونده خدمات قابل دسترسی است.", "chat", "system",
                )

                # اعلان به پذیرش در هدر (نه badge کارتابل)
                detail_url = "/cartable"  # پذیرش پس از تأیید اعلان از کارتابل می‌بیند
                _notify_reception_staff(
                    conn,
                    request_id,
                    f"درخواست خدمات جدید — {kind_label}",
                    f"{customer['name']}: {(problem_desc or '')[:120]}",
                    url=detail_url,
                )

                conn.commit()
                conn.close()
                return render_template(
                    "customer/fault_success.html",
                    chat_url=f"/support/chat/{token}",
                )
                return redirect(url_for("customer_requests"))
        conn.close()
        return render_template(
            "customer/fault.html",
            customer=customer,
            error=error,
            category=category,
            service_kinds=SERVICE_REQUEST_KINDS,
            default_kind=default_kind,
            is_service=False,
        )

    @app.route("/c/chat/new", methods=["GET", "POST"])
    def customer_new_chat():
        """گفتگوی عمومی مستقل از درخواست خدمات؛ بدون ایجاد پرونده یا شماره پذیرش."""
        cid = _portal_customer_id()
        if not cid:
            return redirect(url_for("customer_login"))
        conn = get_db(); _ensure_customer_portal_schema(conn)
        customer = conn.execute("SELECT id,name,phone FROM customers WHERE id=?", (cid,)).fetchone()
        error = None
        if request.method == "POST":
            subject = (request.form.get("subject") or "گفتگو با پشتیبانی").strip()
            message = (request.form.get("message") or "").strip()
            if not message:
                error = "لطفاً پیام خود را بنویسید."
            else:
                from core.support_chat import ensure_support_schema, create_public_thread
                ensure_support_schema(conn)
                tid, token = create_public_thread(conn, subject=subject, contact_name=customer["name"], contact_phone=customer["phone"] or "", first_message=message)
                conn.execute("INSERT OR IGNORE INTO customer_portal_chat_links(customer_id,thread_id,created_at) VALUES(?,?,?)", (cid, tid, datetime.utcnow().isoformat()))
                conn.commit(); conn.close()
                return redirect(f"/support/chat/{token}")
        conn.close()
        return render_template("customer/chat_new.html", customer=customer, error=error)

    @app.route("/c/chats")
    def customer_chats():
        """فهرست قطعی گفتگوهای مشتری.

        گفتگو را هم از اتصال مستقیم پرونده به customer_id و هم از هویت عمومی
        thread پیدا می‌کنیم تا گفتگوهای قدیمی یا ساخته‌شده از فرم اعلام خرابی گم نشوند.
        """
        cid = _portal_customer_id()
        if not cid:
            return redirect(url_for("customer_login"))
        conn = get_db()
        try:
            from core.support_chat import ensure_support_schema
            ensure_support_schema(conn)
            customer = conn.execute("SELECT id, name, phone FROM customers WHERE id=?", (cid,)).fetchone()
            rows = conn.execute("SELECT id, reception_no, device_type FROM requests WHERE customer_id=? ORDER BY id DESC", (cid,)).fetchall()
            req_map = {r["id"]: r for r in rows}
            ids = list(req_map)
            phone = (customer["phone"] if customer else "") or ""
            name = (customer["name"] if customer else "") or ""
            _ensure_customer_portal_schema(conn)
            linked = [r["thread_id"] for r in conn.execute("SELECT thread_id FROM customer_portal_chat_links WHERE customer_id=?", (cid,)).fetchall()]
            clauses, params = [], []
            if linked:
                clauses.append("st.id IN (" + ",".join("?" * len(linked)) + ")")
                params.extend(linked)
            if ids:
                clauses.append("st.request_id IN (" + ",".join("?" * len(ids)) + ")")
                params.extend(ids)
            if phone:
                clauses.append("TRIM(COALESCE(st.contact_phone,''))=?")
                params.append(phone.strip())
            if name:
                clauses.append("TRIM(COALESCE(st.opened_by_name,''))=?")
                params.append(name.strip())
            chats = []
            if clauses:
                sql = ("SELECT st.id, st.request_id, st.public_token, st.status, st.subject, "
                       "st.last_message_at, st.created_at, "
                       "(SELECT body FROM support_messages m WHERE m.thread_id=st.id ORDER BY m.id DESC LIMIT 1) AS last_body "
                       "FROM support_threads st WHERE (" + " OR ".join(clauses) + ") "
                       "AND st.public_token IS NOT NULL "
                       "ORDER BY COALESCE(st.last_message_at, st.created_at) DESC, st.id DESC")
                seen = set()
                for tr in conn.execute(sql, params).fetchall():
                    token = tr["public_token"]
                    if not token or token in seen:
                        continue
                    seen.add(token)
                    req = req_map.get(tr["request_id"])
                    chats.append({
                        "reception_no": req["reception_no"] if req else None,
                        "device_type": req["device_type"] if req else None,
                        "subject": tr["subject"], "token": token, "status": tr["status"],
                        "last_body": tr["last_body"], "updated_at": tr["last_message_at"] or tr["created_at"],
                    })
        except Exception:
            chats = []
        finally:
            conn.close()
        return render_template("customer/chats.html", chats=chats)

    @app.route("/c/cases/<int:request_id>/quote/upload", methods=["POST"])
    def customer_quote_upload(request_id):
        cid=_portal_customer_id()
        if not cid: return redirect(url_for("customer_login"))
        conn=get_db(); case=conn.execute("SELECT id FROM requests WHERE id=? AND customer_id=?",(request_id,cid)).fetchone()
        if not case: conn.close(); return redirect(url_for("customer_requests"))
        f=request.files.get('signed_quote_file'); allowed={'.pdf','.jpg','.jpeg','.png'}
        try:
            ext=os.path.splitext(secure_filename(f.filename))[1].lower() if f and f.filename else ''
            if ext not in allowed: raise ValueError('نوع فایل مجاز نیست')
            f.stream.seek(0,2); size=f.stream.tell(); f.stream.seek(0)
            if size>10*1024*1024: raise ValueError('حجم فایل بیش از ۱۰ مگابایت است')
            folder=os.path.join(os.path.dirname(os.path.dirname(__file__)),'uploads','repair_quotes'); os.makedirs(folder,exist_ok=True)
            stored=f'{request_id}_signed_{int(time.time()*1000)}{ext}'; f.save(os.path.join(folder,stored))
            conn.execute("DELETE FROM repair_quote_files WHERE request_id=? AND file_role='signed'",(request_id,))
            conn.execute("INSERT INTO repair_quote_files(request_id,file_role,stored_name,original_name,mime_type,size_bytes,uploaded_by,status) VALUES(?,?,?,?,?,?,?,?)",(request_id,'signed',stored,secure_filename(f.filename),f.mimetype,size,'customer','waiting_finance'))
            conn.commit()
        except Exception:
            conn.rollback()
        finally: conn.close()
        return redirect(url_for('customer_case_detail',request_id=request_id))

    @app.route("/c/cases/<int:request_id>/quote/<int:file_id>")
    def customer_quote_download(request_id,file_id):
        cid=_portal_customer_id()
        if not cid: return redirect(url_for("customer_login"))
        conn=get_db(); row=conn.execute("SELECT q.* FROM repair_quote_files q JOIN requests r ON r.id=q.request_id WHERE q.id=? AND q.request_id=? AND r.customer_id=?",(file_id,request_id,cid)).fetchone(); conn.close()
        if not row: return redirect(url_for('customer_requests'))
        path=os.path.join(os.path.dirname(os.path.dirname(__file__)),'uploads','repair_quotes',row['stored_name'])
        if not os.path.isfile(path): return redirect(url_for('customer_case_detail',request_id=request_id))
        return send_file(path,as_attachment=True,download_name=row['original_name'])

    @app.route("/c/cases/<int:request_id>")
    def customer_case_detail(request_id):
        cid = _portal_customer_id()
        if not cid: return redirect(url_for("customer_login"))
        conn = get_db(); ensure_case_schema(conn)
        case = conn.execute("SELECT * FROM requests WHERE id=? AND customer_id=?", (request_id, cid)).fetchone()
        if not case:
            conn.close(); return redirect(url_for("customer_requests"))
        device = None
        if case["device_id"]:
            device = conn.execute("SELECT * FROM customer_devices WHERE id=? AND customer_id=?", (case["device_id"], cid)).fetchone()
        timeline = case_timeline(conn, request_id)
        token_row = conn.execute("SELECT public_token FROM support_threads WHERE request_id=? AND public_token IS NOT NULL ORDER BY id DESC LIMIT 1", (request_id,)).fetchone()
        chat_token = token_row["public_token"] if token_row else None
        quote_files = conn.execute("SELECT * FROM repair_quote_files WHERE request_id=? ORDER BY id DESC", (request_id,)).fetchall()
        conn.close()
        return render_template("customer/case_detail.html", case=case, device=device, timeline=timeline, chat_token=chat_token, quote_files=quote_files)

    @app.route("/c/devices")
    @app.route("/c/requests")
    def customer_devices():
        """صفحه یکپارچه درخواست‌ها، پیگیری و سوابق مشتری."""
        cid = _portal_customer_id()
        if not cid: return redirect(url_for("customer_login"))
        conn = get_db(); ensure_case_schema(conn)
        query = (request.args.get("q") or "").strip()
        show_archive = (request.args.get("archive") or "") == "1"
        sql = "SELECT * FROM requests WHERE customer_id=?"
        params = [cid]
        if query:
            like = "%" + query.lower() + "%"
            sql += " AND (LOWER(COALESCE(reception_no,'')) LIKE ? OR LOWER(COALESCE(serial_number,'')) LIKE ? OR LOWER(COALESCE(device_type,'')) LIKE ?)"
            params.extend([like, like, like])
        sql += " ORDER BY id DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        active, archived = [], []
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=183)
        closed_words = ("بسته", "پایان", "مختوم", "تحویل")
        for row in rows:
            data = dict(row)
            status = data.get("status") or "در حال بررسی"
            closed = any(w in status for w in closed_words)
            raw_date = data.get("updated_at") or data.get("reception_date") or data.get("created_at")
            recent = True
            if raw_date:
                try:
                    recent = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00")).replace(tzinfo=None) >= cutoff
                except Exception:
                    recent = True
            data["status"] = status
            data["is_closed"] = closed
            if closed:
                if recent: archived.append(data)
            else: active.append(data)
        items = archived if show_archive else active
        return render_template("customer/devices.html", items=items, query=query, show_archive=show_archive,
                               active_count=len(active), archive_count=len(archived))

    @app.route("/c/survey", methods=["GET", "POST"])
    def customer_survey():
        cid = _portal_customer_id()
        if not cid:
            return redirect(url_for("customer_login"))
        conn = get_db()
        _ensure_portal_survey_schema(conn)
        error = None
        saved = False
        if request.method == "POST":
            try:
                rating = int(request.form.get("rating") or 0)
            except ValueError:
                rating = 0
            comment = (request.form.get("comment") or "").strip()
            if rating < 1 or rating > 5:
                error = "لطفاً میزان رضایت را انتخاب کنید."
            else:
                conn.execute("""INSERT INTO customer_portal_surveys(customer_id,rating,comment,created_at)
                    VALUES(?,?,?,?) ON CONFLICT(customer_id) DO UPDATE SET
                    rating=excluded.rating, comment=excluded.comment, created_at=excluded.created_at""",
                    (cid, rating, comment, datetime.utcnow().isoformat()))
                conn.commit(); saved = True
        row = conn.execute("SELECT rating, comment, created_at FROM customer_portal_surveys WHERE customer_id=?", (cid,)).fetchone()
        conn.close()
        return render_template("customer/survey.html", survey=row, error=error, saved=saved)

    @app.route("/c/push/subscribe", methods=["POST"])
    def customer_push_subscribe():
        lst = _verified_list()
        if not lst:
            return jsonify({"ok": False, "error": "auth"}), 401

        phone = lst[-1]["phone"]
        sub = request.get_json(silent=True) or {}

        conn = get_db()
        from core.customer_push import ensure_customer_push_schema, save_customer_subscription

        ensure_customer_push_schema(conn)
        ok = save_customer_subscription(conn, phone, sub, request.headers.get("User-Agent", ""))
        conn.close()
        return jsonify({"ok": ok})

    @app.route("/c/push/unsubscribe", methods=["POST"])
    def customer_push_unsubscribe():
        if not _verified_list():
            return jsonify({"ok": False, "error": "auth"}), 401
        endpoint = (request.get_json(silent=True) or {}).get("endpoint", "")
        if not endpoint:
            return jsonify({"ok": False}), 400
        conn = get_db()
        from core.customer_push import remove_customer_subscription

        ok = remove_customer_subscription(conn, endpoint)
        conn.close()
        return jsonify({"ok": ok})

    @app.route("/c/manifest.webmanifest")
    def customer_manifest():
        manifest = {
            "name": "سازگان — پیگیری سرویس",
            "short_name": "سازگان",
            "start_url": "/c/home",
            "scope": "/c/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#7a1f2b",
            "dir": "rtl",
            "lang": "fa",
            "icons": [
                {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                {
                    "src": "/static/icons/icon-192-maskable.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        }
        import json

        return Response(json.dumps(manifest, ensure_ascii=False), mimetype="application/manifest+json")

    @app.route("/c/sw.js")
    def customer_sw():
        # ثبت‌شده روی مسیر /c/ تا scope سرویس‌ورکر فقط پرتال مشتری را بپوشاند
        # (مستقل از sw.js اصلی برنامه کارمندی).
        js = """
const CACHE = 'sazgan-customer-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch (e) {}
  const title = payload.title || 'سازگان';
  const options = {
    body: payload.body || '',
    icon: payload.icon || '/static/icons/icon-192.png',
    badge: payload.badge || '/static/icons/icon-96.png',
    dir: 'rtl',
    lang: 'fa',
    tag: payload.tag || 'sazgan-customer',
    data: payload.data || {},
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/c/home';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url.includes('/c/') && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
"""
        resp = Response(js, mimetype="application/javascript")
        resp.headers["Service-Worker-Allowed"] = "/c/"
        return resp
