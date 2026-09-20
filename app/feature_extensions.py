# -*- coding: utf-8 -*-
"""Optional feature routes: alerts, public fault report, timeline, checklists."""
import os, json
from flask import request, redirect, render_template, jsonify, send_file
import jdatetime
from core.constants import EXTERNAL_REPAIR_STATUSES

def _urow(user, key, default=None):
    """دسترسی امن به فیلد کاربر (dict یا sqlite3.Row)."""
    if user is None:
        return default
    try:
        if isinstance(user, dict):
            return user.get(key, default)
        return user[key]
    except Exception:
        return default


try:
    from core.constants import CLOSED_STATUSES as CLOSED_LOCK, REOPEN_ROLES
except Exception:
    CLOSED_LOCK = {
        "پایان تعمیرات", "پایان", "بسته شد", "تحویل شد",
        "نصب انجام شد", "بازدید انجام شد",
        "پیش‌فاکتور رد شد — درخواست لغو شد",
        "پیش‌فاکتور رد شد — ارسال به مشتری",
    }
    REOPEN_ROLES = ('مدیر سیستم',)

def register_extensions(app, H):
    get_db, get_current_user, write_audit, create_backup = (
        H["get_db"], H["get_current_user"], H["write_audit"], H["create_backup"]
    )
    DELAY = H.get("DELAY_THRESHOLD_DAYS", 3)
    PROVINCES = H.get("PROVINCES", [])
    FINANCE_ROLE = H.get("FINANCE_ROLE", "امور مالی")
    JALALI_MONTHS = H.get("JALALI_MONTHS", [])

    @app.route("/api/delay-alerts")
    def api_delay_alerts():
        user = get_current_user()
        if not user:
            return jsonify({"items": []})
        from app import _days_since, _stage_date_for_status
        conn = get_db()
        rows = conn.execute(
            "SELECT id, customer_name, status, reception_date FROM requests ORDER BY id DESC LIMIT 300"
        ).fetchall()
        items = []
        for r in rows:
            st = r["status"] or ""
            if st in CLOSED_LOCK:
                continue
            ref = _stage_date_for_status(conn, r["id"], st) or r["reception_date"]
            days = _days_since(ref) or 0
            if days >= DELAY:
                items.append({"id": r["id"], "customer": r["customer_name"], "status": st, "days": days})
        conn.close()
        return jsonify({"items": items[:40], "threshold": DELAY})

    @app.route("/public/fault-report", methods=["GET", "POST"])
    def public_fault_report():
        msg = err = None
        conn = get_db()
        if request.method == "POST":
            name = (request.form.get("customer_name") or "").strip()
            phone = (request.form.get("customer_phone") or "").strip()
            province = request.form.get("province") or ""
            serial = (request.form.get("serial_number") or "").strip()
            device = (request.form.get("device_type") or "").strip() or "—"
            desc = (request.form.get("problem_desc") or "").strip()
            if not name or not desc:
                err = "نام و شرح خرابی الزامی است"
            else:
                today = jdatetime.date.today()
                rd = "%d/%02d/%02d" % (today.year, today.month, today.day)
                cur = conn.execute(
                    """INSERT INTO requests
                    (customer_name, customer_phone, province, serial_number, device_type,
                     problem_desc, hospital_request_desc, service_type, request_category,
                     status, reception_date)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, phone, province, serial, device, desc, desc,
                     "در محل", "تعمیر", EXTERNAL_REPAIR_STATUSES[0], rd),
                )
                nid = cur.lastrowid
                rno = None
                try:
                    from core.reception_numbers import assign_reception_no
                    rno = assign_reception_no(conn, nid)
                except Exception:
                    pass
                try:
                    write_audit(conn, "عمومی", "اعلام خرابی عمومی", "request", nid, desc[:200])
                except Exception:
                    pass
                conn.commit()
                msg = "ثبت شد. شماره پذیرش: %s" % (rno or nid)
        conn.close()
        return render_template("public_fault_report.html", provinces=PROVINCES, msg=msg, err=err)

    @app.before_request
    def _lock_closed_and_manager():
        if request.method != "POST":
            return
        user = get_current_user()
        if not user:
            return
        if _urow(user, "role") == "مدیر" and "/login" not in (request.path or ""):
            if request.path.startswith("/public"):
                return
            return "دسترسی مدیر فقط‌خواندنی است.", 403
        path = request.path or ""
        if "/view/" not in path:
            return
        try:
            rid = int(path.rstrip("/").split("/")[-1])
        except Exception:
            return
        if request.form.get("action") == "reopen":
            return
        conn = get_db()
        row = conn.execute("SELECT status FROM requests WHERE id=?", (rid,)).fetchone()
        conn.close()
        if row and (row["status"] or "") in CLOSED_LOCK:
            act = request.form.get("action")
            if _urow(user, "role") == "مسئول پذیرش" and act in ("reopen", "change_status", "finance_save"):
                return
            if _urow(user, "role") == FINANCE_ROLE and act in ("finance_save",):
                return
            return "پرونده بسته یا لغو شده و قفل است.", 403

    @app.route("/api/timeline/<int:req_id>")
    def api_timeline(req_id):
        if not get_current_user():
            return jsonify([])
        conn = get_db()
        stages = conn.execute(
            "SELECT * FROM request_stage_dates WHERE request_id=? ORDER BY id", (req_id,)
        ).fetchall()
        audits = conn.execute(
            "SELECT * FROM audit_log WHERE entity_type=? AND entity_id=? ORDER BY id DESC LIMIT 80",
            ("request", req_id),
        ).fetchall()
        conn.close()
        items = []
        for s in stages:
            items.append({"type": "stage", "title": s["stage_name"], "date": s["stage_date"],
                          "notes": s["notes"] if "notes" in s.keys() else ""})
        for a in audits:
            items.append({"type": "audit", "title": a["action"],
                          "date": a["created_at"] if "created_at" in a.keys() else "",
                          "user": a["user_name"] if "user_name" in a.keys() else "",
                          "notes": a["details"] if "details" in a.keys() else ""})
        return jsonify(items)

    @app.route("/api/warranty-check")
    def api_warranty_check():
        serial = (request.args.get("serial") or "").strip()
        if not serial:
            return jsonify({"status": "unknown"})
        from app import _compute_warranty_status
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM warranty_cards WHERE serial_number=? ORDER BY id DESC LIMIT 1", (serial,)
        ).fetchone()
        conn.close()
        if not row:
            return jsonify({"status": "not_found", "message": "کارت گارانتی یافت نشد"})
        st = _compute_warranty_status(row)
        msgs = {"فعال": "در دوره گارانتی (مسیر رایگان محتمل)", "منقضی": "گارانتی منقضی — غیررایگان", "ابطال": "گارانتی ابطال شده"}
        return jsonify({"status": st, "message": msgs.get(st, st)})

    @app.route("/service/copy/<int:req_id>", methods=["POST"])
    def copy_request(req_id):
        user = get_current_user()
        if not user or user["role"] != "مسئول پذیرش":
            return redirect("/")
        conn = get_db()
        r = conn.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()
        if not r:
            conn.close()
            return redirect("/")
        today = jdatetime.date.today()
        rd = "%d/%02d/%02d" % (today.year, today.month, today.day)
        k = r.keys()
        st0 = EXTERNAL_REPAIR_STATUSES[1] if r["service_type"] == "در محل" else "پذیرش دستگاه انجام شد"
        cur = conn.execute(
            """INSERT INTO requests
            (customer_name, customer_address, customer_phone, device_type, serial_number,
             problem_desc, service_type, province, city, request_category, status, reception_date,
             hospital_request_desc, equipment_manager_name, equipment_manager_mobile,
             contact_name, contact_phone, customer_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["customer_name"], r["customer_address"], r["customer_phone"], r["device_type"], "",
             r["problem_desc"], r["service_type"], r["province"],
             r["city"] if "city" in k else "", r["request_category"], st0, rd,
             r["hospital_request_desc"] if "hospital_request_desc" in k else "",
             r["equipment_manager_name"] if "equipment_manager_name" in k else "",
             r["equipment_manager_mobile"] if "equipment_manager_mobile" in k else "",
             r["contact_name"] if "contact_name" in k else "",
             r["contact_phone"] if "contact_phone" in k else "",
             r["customer_id"] if "customer_id" in k else None),
        )
        nid = cur.lastrowid
        try:
            from core.reception_numbers import assign_reception_no
            assign_reception_no(conn, nid)
        except Exception:
            pass
        try:
            write_audit(conn, user["full_name"], "کپی پرونده", "request", nid, "از #%s" % req_id)
        except Exception:
            pass
        conn.commit()
        conn.close()
        if r["service_type"] == "کارخانه":
            return redirect("/service/internal-repair/view/%s" % nid)
        return redirect("/service/external-repair/view/%s" % nid)

    @app.route("/finance/wage-monthly")
    def finance_wage_monthly():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", FINANCE_ROLE, "مدیر"):
            return redirect("/")
        today = jdatetime.date.today()
        year = int(request.args.get("year") or today.year)
        month = int(request.args.get("month") or today.month)
        conn = get_db()
        rows = conn.execute("SELECT * FROM wage_calculations ORDER BY id DESC").fetchall()
        conn.close()
        filtered = []
        for r in rows:
            d = (r["calc_date"] or "") if "calc_date" in r.keys() else ""
            parts = d.replace("-", "/").split("/")
            try:
                if len(parts) >= 2 and int(parts[0]) == year and int(parts[1]) == month:
                    filtered.append(r)
            except Exception:
                pass
        total = sum(float(r["amount"] or 0) for r in filtered)
        return render_template(
            "finance_wage_monthly.html", rows=filtered, year=year, month=month, total=total,
            current_user=user, active_page="finance-wage-monthly", jalali_months=JALALI_MONTHS,
        )

    @app.route("/finance/wage-monthly/export")
    def finance_wage_monthly_export():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", FINANCE_ROLE, "مدیر"):
            return redirect("/")
        from openpyxl import Workbook
        today = jdatetime.date.today()
        year = int(request.args.get("year") or today.year)
        month = int(request.args.get("month") or today.month)
        conn = get_db()
        rows = conn.execute("SELECT * FROM wage_calculations ORDER BY id DESC").fetchall()
        conn.close()
        wb = Workbook()
        ws = wb.active
        ws.append(["id", "نماینده", "شرح", "مبلغ", "تاریخ", "یادداشت"])
        for r in rows:
            d = (r["calc_date"] or "") if "calc_date" in r.keys() else ""
            parts = d.replace("-", "/").split("/")
            try:
                if len(parts) >= 2 and int(parts[0]) == year and int(parts[1]) == month:
                    ws.append([r["id"], r["representative_name"] if "representative_name" in r.keys() else "",
                               r["work_description"] if "work_description" in r.keys() else "",
                               r["amount"], d, r["notes"] if "notes" in r.keys() else ""])
            except Exception:
                pass
        path = os.path.join(app.root_path, "wage_export.xlsx")
        wb.save(path)
        return send_file(path, as_attachment=True, download_name="wage_%s_%s.xlsx" % (year, month))

    @app.route("/reports/executive")
    def reports_executive():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", "مدیر", FINANCE_ROLE, "مدیر سیستم"):
            return redirect("/")
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) AS c FROM requests").fetchone()["c"]
        open_c = conn.execute(
            "SELECT COUNT(*) AS c FROM requests WHERE status NOT IN (%s)"
            % ",".join(["?"] * len(CLOSED_LOCK)),
            tuple(CLOSED_LOCK),
        ).fetchone()["c"]
        internal = conn.execute(
            "SELECT COUNT(*) AS c FROM requests WHERE service_type=? AND request_category=?",
            ("کارخانه", "تعمیر"),
        ).fetchone()["c"]
        external = conn.execute(
            "SELECT COUNT(*) AS c FROM requests WHERE service_type=? AND request_category=?",
            ("در محل", "تعمیر"),
        ).fetchone()["c"]
        rejected = conn.execute(
            "SELECT COUNT(*) AS c FROM requests WHERE proforma_confirmed=2"
        ).fetchone()["c"]
        by_status = conn.execute(
            "SELECT status, COUNT(*) AS c FROM requests GROUP BY status ORDER BY c DESC LIMIT 15"
        ).fetchall()
        raw = conn.execute(
            "SELECT * FROM requests ORDER BY id DESC LIMIT 300"
        ).fetchall()
        try:
            from core.helpers import enrich_delay as _ed
            rows = _ed(conn, raw)
        except Exception:
            try:
                from core.request_utils import enrich_delay as _ed
                rows = _ed(conn, raw)
            except Exception:
                rows = [dict(r) for r in raw]
        conn.close()
        return render_template(
            "report_executive.html",
            total=total, open_c=open_c, internal=internal, external=external,
            rejected=rejected, by_status=by_status, rows=rows,
            current_user=user, active_page="report-executive",
        )


    # ---- ایندکس پرونده دستگاه‌ها (سریال → پوشه) ----
    @app.route("/settings/device-folders", methods=["GET", "POST"])
    def settings_device_folders():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", "مدیر", "مدیر سیستم"):
            return redirect("/")
        from core.device_folders import (
            ensure_device_folder_schema, get_root_path, set_root_path,
            index_count, import_from_excel, scan_disk_index, search_serial,
        )
        conn = get_db()
        ensure_device_folder_schema(conn)
        msg = err = None
        if request.method == "POST":
            action = (request.form.get("action") or "save").strip()
            if action == "save":
                set_root_path(conn, request.form.get("root_path") or "")
                msg = "مسیر ریشه ذخیره شد."
            elif action == "import_excel":
                f = request.files.get("excel")
                if not f or not f.filename:
                    err = "فایل اکسل را انتخاب کنید."
                else:
                    res = import_from_excel(conn, f, replace=True)
                    if res.get("ok"):
                        msg = f"وارد شد: {res.get('imported')} ردیف (جمع ایندکس: {res.get('total')})"
                    else:
                        err = res.get("error") or "خطا در ورود اکسل"
            elif action == "scan_disk":
                res = scan_disk_index(conn, replace=True)
                if res.get("ok"):
                    msg = f"اسکن دیسک: {res.get('imported')} پوشه (جمع: {res.get('total')})"
                else:
                    err = res.get("error") or "خطا در اسکن"
            elif action == "clear":
                from core.device_folders import clear_index
                clear_index(conn)
                msg = "ایندکس پاک شد."
        root = get_root_path(conn)
        total = index_count(conn)
        q = (request.args.get("q") or "").strip()
        sample = search_serial(conn, q, limit=30) if q else []
        conn.close()
        return render_template(
            "settings_device_folders.html",
            current_user=user,
            active_page="settings-device-folders",
            root_path=root,
            index_total=total,
            msg=msg,
            err=err,
            q=q,
            sample=sample,
        )

    @app.route("/api/device-folder")
    def api_device_folder():
        serial = (request.args.get("serial") or "").strip()
        if not serial:
            return jsonify({"ok": False, "error": "سریال خالی است"})
        from core.device_folders import ensure_device_folder_schema, search_serial
        conn = get_db()
        ensure_device_folder_schema(conn)
        rows = search_serial(conn, serial, limit=10)
        conn.close()
        return jsonify({
            "ok": True,
            "serial": serial,
            "results": [
                {
                    "serial": r.get("serial_raw") or r.get("serial"),
                    "sh_folder": r.get("sh_folder") or "",
                    "path": r.get("resolved_path") or r.get("full_path") or "",
                    "relative_path": r.get("relative_path") or "",
                }
                for r in rows
            ],
        })

    @app.route("/api/device-folder/open", methods=["POST", "GET"])
    def api_device_folder_open():
        user = get_current_user()
        if not user:
            return jsonify({"ok": False, "error": "auth"}), 401
        path = (request.values.get("path") or "").strip()
        serial = (request.values.get("serial") or "").strip()
        from core.device_folders import ensure_device_folder_schema, search_serial, open_folder_windows
        conn = get_db()
        ensure_device_folder_schema(conn)
        if not path and serial:
            rows = search_serial(conn, serial, limit=1)
            if rows:
                path = rows[0].get("resolved_path") or rows[0].get("full_path") or ""
        conn.close()
        res = open_folder_windows(path)
        return jsonify(res)

    @app.route("/settings/customer-comms")
    @app.route("/settings/customer-communication")
    def settings_customer_comms():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", "مدیر", "مدیر سیستم"):
            return redirect("/")
        return render_template(
            "settings_customer_comms.html",
            current_user=user,
            active_page="settings-customer-comms",
        )

    @app.route("/settings/messaging", methods=["GET", "POST"])
    def settings_messaging():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", "مدیر", "مدیر سیستم"):
            return redirect("/")
        conn = get_db()
        if request.method == "POST":
            conf = {
                "provider": request.form.get("provider") or "none",
                "api_key": request.form.get("api_key") or "",
                "sender": request.form.get("sender") or "",
                "enabled": request.form.get("enabled") == "1",
            }
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                ("messaging", json.dumps(conf, ensure_ascii=False)),
            )
            conn.commit()
        row = conn.execute("SELECT value FROM app_settings WHERE key=?", ("messaging",)).fetchone()
        conf = json.loads(row["value"]) if row else {"provider": "none", "enabled": False}
        conn.close()
        return render_template(
            "settings_messaging.html", conf=conf, current_user=user, active_page="settings-messaging"
        )

    @app.route("/security/backup-now", methods=["POST"])
    def backup_now():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", "مدیر"):
            return redirect("/")
        dest = create_backup("manual-ui")
        conn = get_db()
        try:
            write_audit(conn, user["full_name"], "پشتیبان‌گیری", "backup", None, str(dest))
            conn.commit()
        except Exception:
            pass
        conn.close()
        return redirect("/security/backups")

    @app.route("/api/save-checklist/<int:req_id>", methods=["POST"])
    def save_checklist(req_id):
        user = get_current_user()
        if not user or user["role"] != "مسئول پذیرش":
            return jsonify({"ok": False}), 403
        data = {
            "serial_ok": request.form.get("serial_ok") == "1",
            "parts_ok": request.form.get("parts_ok") == "1",
            "photo_ok": request.form.get("photo_ok") == "1",
            "match_ok": request.form.get("match_ok") == "1",
        }
        if not all(data.values()):
            return jsonify({"ok": False, "error": "همه موارد چک‌لیست الزامی است"}), 400
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            ("checklist_%s" % req_id, json.dumps(data)),
        )
        try:
            write_audit(conn, user["full_name"], "تأیید چک‌لیست گزارش", "request", req_id, json.dumps(data, ensure_ascii=False))
        except Exception:
            pass
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    print("[features] OK")
