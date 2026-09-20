# -*- coding: utf-8 -*-
"""کارتابل، اعلام درخواست خدمات، پیوست، تاریخچه وضعیت، پیش‌نویس."""
from __future__ import annotations

import os
from datetime import datetime

from flask import jsonify, redirect, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from core.helpers import save_uploaded_image

DELAY_NOTIFICATIONS_ENABLED = False  # پیشنهاد ۸ — فعلاً غیرفعال

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "pdf", "doc", "docx", "xlsx", "xls"}


def _feat_today():
    try:
        import jdatetime

        t = jdatetime.date.today()
        return f"{t.year}/{str(t.month).zfill(2)}/{str(t.day).zfill(2)}"
    except Exception:
        return datetime.now().strftime("%Y/%m/%d")


def ensure_features_schema(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            from_status TEXT,
            to_status TEXT,
            changed_by TEXT,
            changed_at TEXT,
            note TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS request_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            filename TEXT,
            original_name TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT,
            note TEXT
        )
        """
    )
    _ra_cols = {r[1] for r in conn.execute("PRAGMA table_info(request_attachments)").fetchall()}
    if 'label' not in _ra_cols:
        try:
            conn.execute("ALTER TABLE request_attachments ADD COLUMN label TEXT")
        except Exception:
            pass
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS request_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            form_kind TEXT,
            payload TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS service_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_name TEXT,
            contact_name TEXT,
            contact_phone TEXT,
            province TEXT,
            city TEXT,
            device_type TEXT,
            serial_number TEXT,
            problem_brief TEXT,
            status TEXT DEFAULT 'جدید — نیاز به تماس',
            created_at TEXT,
            handled_by TEXT,
            handled_at TEXT,
            linked_request_id INTEGER
        )
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(requests)").fetchall()}
    # Fixed schema whitelist; identifiers are not sourced from HTTP input.
    for c in (
        "proforma_status",
        "proforma_decision_date",
        "proforma_note",
        "invoice_number",
        "invoice_status",
        "shipping_tracking_no",
        "qc_notes",
        "technical_report",
        "final_report",
        "warehouse_voucher_no",
    ):
        if c not in cols:
            try:
                conn.execute(f"ALTER TABLE requests ADD COLUMN {c} TEXT")
            except Exception:
                pass
    conn.commit()


def log_status_change(conn, request_id, from_status, to_status, user_name=None, note=None):
    ensure_features_schema(conn)
    conn.execute(
        """
        INSERT INTO status_history
        (request_id, from_status, to_status, changed_by, changed_at, note)
        VALUES (?,?,?,?,?,?)
        """,
        (request_id, from_status, to_status, user_name, _feat_today(), note),
    )
    conn.commit()


IR_TRANSITIONS = {
    "پذیرش": ["تست اولیه / تعمیر اولیه"],
    "تست اولیه / تعمیر اولیه": ["کنترل کیفیت اولیه"],
    "کنترل کیفیت اولیه": ["عیب‌یابی و گزارش فنی"],
    "عیب‌یابی و گزارش فنی": ["صدور پیش‌فاکتور"],
    "صدور پیش‌فاکتور": ["منتظر تأیید پیش‌فاکتور"],
    "منتظر تأیید پیش‌فاکتور": ["حواله تعمیر نهایی", "رد پیش‌فاکتور — ارسال به مشتری"],
    "رد پیش‌فاکتور — ارسال به مشتری": ["ارسال به مشتری", "بسته شد"],
    "حواله تعمیر نهایی": ["تعمیر نهایی"],
    "تعمیر نهایی": ["گزارش نهایی"],
    "گزارش نهایی": ["تست نهایی"],
    "تست نهایی": ["تحویل به پذیرش"],
    "تحویل به پذیرش": ["ارسال به مشتری"],
    "ارسال به مشتری": ["بسته شد"],
}

ER_TRANSITIONS = {
    "اعلام خرابی": ["ثبت قطعات احتمالی"],
    "ثبت قطعات احتمالی": ["صدور پیش‌فاکتور"],
    "صدور پیش‌فاکتور": ["منتظر تأیید پیش‌فاکتور"],
    "منتظر تأیید پیش‌فاکتور": ["حواله انبار", "لغو — رد پیش‌فاکتور"],
    "لغو — رد پیش‌فاکتور": ["بسته شد"],
    "حواله انبار": ["دریافت قطعه — انبار استان"],
    "دریافت قطعه — انبار استان": ["مأموریت نماینده — در جریان"],
    "مأموریت نماینده — در جریان": ["ارسال قطعه برای نماینده", "دریافت قطعه توسط نماینده"],
    "ارسال قطعه برای نماینده": ["دریافت قطعه توسط نماینده"],
    "دریافت قطعه توسط نماینده": ["تعمیر انجام‌شده — منتظر بررسی پذیرش"],
    "تعمیر انجام‌شده — منتظر بررسی پذیرش": ["پایان تعمیر"],
    "پایان تعمیر": ["فاکتور صادر شد"],
    "فاکتور صادر شد": ["بسته شد"],
}


def allowed_next_statuses(current, is_external=False):
    m = ER_TRANSITIONS if is_external else IR_TRANSITIONS
    return m.get(current, [])


def register_feature_routes(app, get_db, get_current_user):
    @app.route("/cartable")
    def my_cartable():
        # کارتابل برای همه‌ی نقش‌ها اکنون همان صفحه‌ی خانه (/) است.
        user = get_current_user()
        if not user:
            return redirect("/login")
        return redirect("/")


    @app.route("/api/public/serial-status")
    def api_public_serial_status():
        """وضعیت عمومی دستگاه با سریال — بدون لاگین."""
        serial = (request.args.get("serial") or "").strip()
        if not serial:
            return jsonify({"ok": False, "error": "سریال را وارد کنید"})
        conn = get_db()
        # گارانتی
        card = conn.execute(
            "SELECT * FROM warranty_cards WHERE serial_number=? ORDER BY id DESC LIMIT 1",
            (serial,),
        ).fetchone()
        warranty = None
        if card:
            keys = card.keys()
            warranty = {
                "found": True,
                "customer_name": card["customer_name"] if "customer_name" in keys else "",
                "device_type": card["device_type"] if "device_type" in keys else "",
                "model": card["model"] if "model" in keys else "",
                "warranty_status": card["warranty_status"] if "warranty_status" in keys else "",
                "warranty_end_date": card["warranty_end_date"] if "warranty_end_date" in keys else "",
                "installation_date": card["installation_date"] if "installation_date" in keys else "",
            }
        else:
            warranty = {"found": False}

        # آخرین درخواست‌های مرتبط با سریال
        rows = conn.execute(
            """SELECT id, reception_no, customer_name, device_type, device_model, status,
                      service_type, request_category, reception_date, province
               FROM requests WHERE serial_number=? ORDER BY id DESC LIMIT 5""",
            (serial,),
        ).fetchall()
        requests_out = []
        for r in rows:
            requests_out.append({
                "id": r["id"],
                "reception_no": r["reception_no"] or "",
                "customer_name": r["customer_name"] or "",
                "device_type": r["device_type"] or "",
                "model": r["device_model"] or "",
                "status": r["status"] or "",
                "service_type": r["service_type"] or "",
                "request_category": r["request_category"] or "",
                "reception_date": r["reception_date"] or "",
                "province": r["province"] or "",
            })
        conn.close()
        return jsonify({
            "ok": True,
            "serial": serial,
            "warranty": warranty,
            "requests": requests_out,
            "latest_status": requests_out[0]["status"] if requests_out else None,
        })


    def _lookup_public_track(mode, q):
        """منطق مشترک پیگیری عمومی مشتری (سریال / تلفن / کد گفتگو).

        هم توسط صفحه‌ی /track و هم تب «پیگیری» در همان لینک واحد /announce
        استفاده می‌شود تا رفتار یکسان بماند و دوباره‌کاری نداشته باشیم.
        برمی‌گرداند: (result_dict_or_None, error_str_or_None)
        """
        result = None
        error = None
        if not q:
            return None, "مقدار جستجو را وارد کنید."

        conn = get_db()
        try:
            from core.support_chat import ensure_support_schema, get_thread_by_token
            ensure_support_schema(conn)
        except Exception:
            pass

        if mode == "phone":
            conn.close()
            return None, "پیگیری با شماره تلفن غیرفعال است. لطفاً سریال دستگاه یا کد پیگیری را وارد کنید."

        if True:
            if True:
                # کد پیگیری (توکن گفتگویی که هنگام ثبت اعلام خرابی به مشتری داده می‌شود)
                if mode == "code" or (len(q) >= 12 and " " not in q and not q.isdigit()):
                    try:
                        from core.support_chat import get_thread_by_token, list_messages
                        th = get_thread_by_token(conn, q)
                        if th:
                            msgs = list_messages(conn, th["id"])
                            last_msg = msgs[-1] if msgs else None
                            result = {
                                "type": "chat",
                                "thread": dict(th),
                                "messages_count": len(msgs),
                                "last_message": dict(last_msg) if last_msg else None,
                                "token": q,
                            }
                        elif mode == "code":
                            error = "کد پیگیری یافت نشد."
                    except Exception as e:
                        print("[track] token:", e)

                # پیگیری با تلفن عمداً حذف شد: جست‌وجوی سراسری با شماره تلفن می‌توانست
                # پرونده‌ی سایر مشتریان را هم لو بدهد (کافی بود شماره را حدس بزنند).
                # طبق سیاست فعلی، مشتری فقط با «سریال دستگاه» یا «کد پیگیری» که هنگام
                # ثبت اعلام خرابی دریافت کرده می‌تواند پیگیری کند.

                # سریال (پیش‌فرض)
                if result is None:
                    serial = q
                    card = conn.execute(
                        "SELECT * FROM warranty_cards WHERE serial_number=? ORDER BY id DESC LIMIT 1",
                        (serial,),
                    ).fetchone()
                    reqs = conn.execute(
                        """SELECT id, reception_no, customer_name, serial_number, device_type, device_model, status,
                                  service_type, reception_date, province
                           FROM requests WHERE serial_number=? ORDER BY id DESC LIMIT 8""",
                        (serial,),
                    ).fetchall()
                    threads = []
                    try:
                        # threads linked by request_id or subject containing serial
                        threads = conn.execute(
                            """SELECT t.* FROM support_threads t
                               WHERE t.request_id IN (SELECT id FROM requests WHERE serial_number=?)
                                  OR IFNULL(t.subject,'') LIKE ?
                               ORDER BY IFNULL(t.last_message_at, t.created_at) DESC LIMIT 8""",
                            (serial, f"%{serial}%"),
                        ).fetchall()
                    except Exception:
                        pass
                    anns = conn.execute(
                        """SELECT * FROM service_announcements
                           WHERE serial_number=? ORDER BY id DESC LIMIT 5""",
                        (serial,),
                    ).fetchall()
                    if card or reqs or threads or anns:
                        w = None
                        if card:
                            keys = card.keys()
                            w = {
                                "customer_name": card["customer_name"] if "customer_name" in keys else "",
                                "device_type": card["device_type"] if "device_type" in keys else "",
                                "model": card["model"] if "model" in keys else "",
                                "warranty_status": card["warranty_status"] if "warranty_status" in keys else "",
                                "warranty_end_date": card["warranty_end_date"] if "warranty_end_date" in keys else "",
                                "installation_date": card["installation_date"] if "installation_date" in keys else "",
                            }
                        result = {
                            "type": "serial",
                            "serial": serial,
                            "warranty": w,
                            "requests": [dict(r) for r in reqs],
                            "threads": [dict(x) for x in threads],
                            "announcements": [dict(a) for a in anns],
                        }
                    else:
                        error = error or "با این سریال یا کد پیگیری موردی یافت نشد."

        conn.close()
        return result, error

    @app.route("/track", methods=["GET", "POST"])
    @app.route("/support/track", methods=["GET", "POST"])
    @app.route("/announce/track", methods=["GET", "POST"])
    def public_track():
        """یکپارچه با /announce — همهٔ کار مشتری در یک لینک."""
        from flask import url_for
        mode = (request.values.get("mode") or "serial").strip()
        q = (request.values.get("q") or request.values.get("serial") or request.values.get("phone") or request.values.get("code") or "").strip()
        # هدایت به هاب واحد اعلام/پیگیری/گفتگو
        qs = ["panel=track"]
        if mode and mode != "serial":
            qs.append("mode=" + mode)
        if q:
            qs.append("q=" + q)
        return redirect("/support?" + "&".join(qs))

    @app.route("/api/public/track")
    def api_public_track():
        """پیگیری با سریال/تلفن/کد به‌صورت JSON — برای تب «پیگیری» در لینک واحد /announce."""
        mode = (request.args.get("mode") or "serial").strip()
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"ok": False, "error": "مقدار جستجو را وارد کنید."})
        result, error = _lookup_public_track(mode, q)
        if error and not result:
            return jsonify({"ok": False, "error": error})
        return jsonify({"ok": True, "result": result})

    @app.route("/support/chat-start", methods=["POST"])
    def announce_chat_start_only():
        """شروع گفتگو بدون ثبت اعلام خرابی کامل."""
        name = (request.form.get("contact_name") or request.form.get("hospital_name") or "").strip()
        phone = (request.form.get("contact_phone") or "").strip()
        serial = (request.form.get("serial_number") or "").strip()
        body = (request.form.get("message") or request.form.get("problem_brief") or "").strip()
        hospital = (request.form.get("hospital_name") or name or "").strip()
        if not phone:
            return redirect("/support?chat_err=phone")
        if not body:
            return redirect("/support?chat_err=message")
        if not name:
            name = hospital or "مشتری"
        conn = get_db()
        request_id = None
        if serial:
            row = conn.execute(
                "SELECT id FROM requests WHERE serial_number=? ORDER BY id DESC LIMIT 1",
                (serial,),
            ).fetchone()
            if row:
                request_id = row["id"]
        try:
            from core.support_chat import create_public_thread, notify_users_bale, ensure_support_schema
            ensure_support_schema(conn)
            subject = "گفتگو با شرکت"
            if serial:
                subject += f" — سریال {serial}"
            if hospital:
                subject = f"{hospital} — {subject}"
            first = body
            _tid, token = create_public_thread(
                conn,
                subject=subject,
                contact_name=name,
                contact_phone=phone,
                announcement_id=None,
                request_id=request_id,
                first_message=first,
                serial_number=serial,
            )
            # source already public_announce - update to chat_only
            try:
                conn.execute(
                    "UPDATE support_threads SET source=? WHERE id=?",
                    ("public_chat", _tid),
                )
                conn.commit()
            except Exception:
                pass
            try:
                recs = conn.execute(
                    "SELECT id FROM users WHERE role IN ('مسئول پذیرش','مدیر سیستم','مدیر') AND IFNULL(is_active,1)=1"
                ).fetchall()
                notify_users_bale(
                    conn, [r["id"] for r in recs],
                    f"گفتگوی جدید مشتری (بدون اعلام)\n{name} / {phone}\n{body[:160]}",
                )
            except Exception:
                pass
            conn.close()
            return redirect(f"/support/chat/{token}")
        except Exception as e:
            print("[announce] chat-start:", e)
            conn.close()
            return redirect("/support?chat_err=server")

    @app.route("/announce", methods=["GET", "POST"])
    def legacy_public_service_announce():
        """Legacy URL kept for old bookmarks/links; /support is canonical."""
        target = "/support"
        if request.query_string:
            target += "?" + request.query_string.decode("utf-8", errors="ignore")
        return redirect(target, code=308)


    @app.route("/support", methods=["GET", "POST"])
    def public_service_announce():
        if request.method == "POST":
            hospital = (request.form.get("hospital_name") or "").strip()
            phone = (request.form.get("contact_phone") or "").strip()
            brief = (request.form.get("problem_brief") or "").strip()
            if not hospital or not phone or not brief:
                try:
                    from core.geo import get_geo_provinces
                    _provinces = get_geo_provinces(get_db()) or []
                except Exception:
                    from core.constants import PROVINCES
                    _provinces = list(PROVINCES)
                return render_template(
                    "public_announce.html",
                    error="نام مرکز، تلفن و شرح مختصر الزامی است.",
                    success=None,
                    provinces=_provinces,
                )
            conn = get_db()
            ensure_features_schema(conn)
            contact_name = (request.form.get("contact_name") or "").strip() or hospital
            cur = conn.execute(
                """
                INSERT INTO service_announcements
                (hospital_name, contact_name, contact_phone, province, city, device_type,
                 serial_number, problem_brief, status, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    hospital,
                    contact_name,
                    phone,
                    (request.form.get("province") or "").strip(),
                    (request.form.get("city") or request.form.get("city_manual") or "").strip(),
                    (request.form.get("device_type") or "").strip(),
                    (request.form.get("serial_number") or "").strip(),
                    brief,
                    "جدید — نیاز به تماس",
                    _feat_today(),
                ),
            )
            ann_id = cur.lastrowid
            conn.commit()
            # گفتگوی مشتری برای پیگیری همان اعلام
            chat_token = None
            try:
                from core.support_chat import create_public_thread, notify_users_bale, ensure_support_schema
                ensure_support_schema(conn)
                serial_v = (request.form.get("serial_number") or "").strip()
                req_id = None
                if serial_v:
                    rr = conn.execute(
                        "SELECT id FROM requests WHERE serial_number=? ORDER BY id DESC LIMIT 1",
                        (serial_v,),
                    ).fetchone()
                    if rr:
                        req_id = rr["id"]
                subject = f"اعلام خرابی — {hospital}"
                first = f"اعلام از فرم عمومی:\nمرکز: {hospital}\nتلفن: {phone}\nسریال: {serial_v or '—'}\nشرح: {brief}"
                _tid, chat_token = create_public_thread(
                    conn,
                    subject=subject,
                    contact_name=contact_name,
                    contact_phone=phone,
                    announcement_id=ann_id,
                    request_id=req_id,
                    first_message=first,
                )
                try:
                    recs = conn.execute(
                        "SELECT id FROM users WHERE role IN ('مسئول پذیرش','مدیر سیستم','مدیر') AND IFNULL(is_active,1)=1"
                    ).fetchall()
                    notify_users_bale(
                        conn, [r['id'] for r in recs],
                        f"اعلام خرابی جدید: {hospital}\n{brief[:160]}",
                    )
                except Exception:
                    pass
            except Exception as e:
                print('[announce] public thread:', e)
            conn.close()
            try:
                from core.geo import get_geo_provinces
                _provinces = get_geo_provinces(get_db()) or []
            except Exception:
                from core.constants import PROVINCES
                _provinces = list(PROVINCES)
            return render_template(
                "public_announce.html",
                error=None,
                success=True,
                provinces=_provinces,
                chat_token=chat_token,
            )
        try:
            from core.helpers import _ensure_csrf_token
            _ensure_csrf_token()
        except Exception:
            pass
        try:
            from core.geo import get_geo_provinces
            _provinces = get_geo_provinces(get_db()) or []
        except Exception:
            from core.constants import PROVINCES
            _provinces = list(PROVINCES)
        return render_template("public_announce.html", error=None, success=None, provinces=_provinces)

    @app.route("/announce/list")
    def announce_list():
        user = get_current_user()
        if not user:
            return redirect("/login")
        if user["role"] not in ("مسئول پذیرش", "مدیر سیستم"):
            return redirect("/")
        conn = get_db()
        ensure_features_schema(conn)
        rows = conn.execute(
            "SELECT * FROM service_announcements ORDER BY id DESC LIMIT 1000"
        ).fetchall()
        conn.close()
        from core.pagination import parse_page, parse_per_page, paginate, pagination_context
        pg = paginate(rows, page=parse_page(request.args), per_page=parse_per_page(request.args, 25))
        pg_ctx = pagination_context(pg, request.args)
        return render_template(
            "announce_list.html",
            rows=pg["items"],
            active_page="announce-list",
            current_user=user,
            **pg_ctx,
        )

    @app.route("/announce/<int:ann_id>/handled", methods=["POST"])
    def announce_handled(ann_id):
        user = get_current_user()
        if not user:
            return redirect("/login")
        conn = get_db()
        ensure_features_schema(conn)
        conn.execute(
            """
            UPDATE service_announcements SET status=?, handled_by=?, handled_at=? WHERE id=?
            """,
            ("تماس انجام شد", user["full_name"], _feat_today(), ann_id),
        )
        conn.commit()
        conn.close()
        return redirect("/announce/list")

    @app.route("/service/request/<int:req_id>/attachments", methods=["POST"])
    def upload_attachment(req_id):
        user = get_current_user()
        if not user:
            return redirect("/login")
        f = request.files.get("file")
        if not f or not f.filename:
            return redirect(request.referrer or "/")
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in ALLOWED_EXT:
            return "فرمت فایل مجاز نیست", 400
        fname = secure_filename(f"{req_id}_{int(datetime.now().timestamp())}_{f.filename}")
        path = os.path.join(UPLOAD_FOLDER, fname)
        save_uploaded_image(f, path)
        conn = get_db()
        ensure_features_schema(conn)
        conn.execute(
            """
            INSERT INTO request_attachments
            (request_id, filename, original_name, uploaded_by, uploaded_at, note)
            VALUES (?,?,?,?,?,?)
            """,
            (
                req_id,
                fname,
                f.filename,
                user["full_name"],
                _feat_today(),
                request.form.get("note"),
            ),
        )
        conn.commit()
        conn.close()
        return redirect(request.referrer or "/")

    @app.route("/uploads/<path:filename>")
    def serve_upload(filename):
        user = get_current_user()
        if not user:
            return redirect("/login")
        return send_from_directory(UPLOAD_FOLDER, filename)

    @app.route("/reports/management-features-legacy")
    def management_report_legacy():
        user = get_current_user()
        if not user:
            return redirect("/login")
        if user["role"] not in ("مسئول پذیرش", "مدیر سیستم", "مدیر", "امور مالی"):
            return redirect("/")
        conn = get_db()
        ensure_features_schema(conn)
        open_n = conn.execute(
            """
            SELECT COUNT(*) AS c FROM requests
            WHERE status NOT IN ('بسته شد','لغو — رد پیش‌فاکتور','پایان تعمیرات','پایان')
            """
        ).fetchone()["c"]
        closed_n = conn.execute(
            """
            SELECT COUNT(*) AS c FROM requests
            WHERE status IN ('بسته شد','لغو — رد پیش‌فاکتور','پایان تعمیرات','پایان')
            """
        ).fetchone()["c"]
        try:
            rejected_pf = conn.execute(
                "SELECT COUNT(*) AS c FROM requests WHERE proforma_status='رد شده'"
            ).fetchone()["c"]
        except Exception:
            rejected_pf = 0
        by_status = conn.execute(
            "SELECT status, COUNT(*) AS c FROM requests GROUP BY status ORDER BY c DESC LIMIT 20"
        ).fetchall()
        try:
            announces_new = conn.execute(
                "SELECT COUNT(*) AS c FROM service_announcements WHERE status LIKE 'جدید%'"
            ).fetchone()["c"]
        except Exception:
            announces_new = 0
        conn.close()
        return render_template(
            "management_report.html",
            open_n=open_n,
            closed_n=closed_n,
            rejected_pf=rejected_pf,
            by_status=by_status,
            announces_new=announces_new,
            delay_notifications_enabled=DELAY_NOTIFICATIONS_ENABLED,
            active_page="reports-management",
            current_user=user,
        )

    @app.route("/drafts/save", methods=["POST"])
    def save_draft():
        user = get_current_user()
        if not user:
            return redirect("/login")
        import json

        conn = get_db()
        ensure_features_schema(conn)
        kind = request.form.get("form_kind") or "internal"
        payload = {k: request.form.get(k) for k in request.form if k != "form_kind"}
        conn.execute(
            """
            INSERT INTO request_drafts (user_id, form_kind, payload, updated_at)
            VALUES (?,?,?,?)
            """,
            (user["id"], kind, json.dumps(payload, ensure_ascii=False), _feat_today()),
        )
        conn.commit()
        conn.close()
        return redirect(request.referrer or "/")
