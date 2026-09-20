# -*- coding: utf-8 -*-
"""15 improvements for Sazgan"""
from __future__ import annotations

import io
import os
from datetime import datetime

from flask import redirect, render_template, request, jsonify, send_file, Response

STATUS_ALIASES = {
    "در انتظار پذیرش دستگاه است": "پذیرش",
    "در انتظار ارسال حواله تعمیر اولیه است": "تست اولیه / تعمیر اولیه",
    "در انتظار دریافت قطعه تعمیر اولیه است": "تست اولیه / تعمیر اولیه",
    "در انتظار تعمیر اولیه است": "تست اولیه / تعمیر اولیه",
    "در انتظار تست اولیه است": "تست اولیه / تعمیر اولیه",
    "در انتظار ارسال گزارش فنی است": "عیب‌یابی و گزارش فنی",
    "در انتظار ارسال پیش‌فاکتور است": "صدور پیش‌فاکتور",
    "در انتظار دریافت تاییدیه پیش‌فاکتور است": "منتظر تأیید پیش‌فاکتور",
    "پیش‌فاکتور رد شد — ارسال به مشتری": "رد پیش‌فاکتور — ارسال به مشتری",
    "پیش‌فاکتور رد شد — آماده ارسال": "رد پیش‌فاکتور — ارسال به مشتری",
    "در انتظار ارسال حواله تعمیر نهایی است": "حواله تعمیر نهایی",
    "در انتظار دریافت قطعه تعمیر نهایی است": "حواله تعمیر نهایی",
    "در انتظار گزارش نهایی است": "گزارش نهایی",
    "در انتظار تست نهایی و تحویل است": "تست نهایی",
    "در انتظار خروج از کارخانه است": "ارسال به مشتری",
    "در انتظار صدور فاکتور است": "بسته شد",
    "پایان تعمیرات": "بسته شد",
    "پذیرش انجام شد": "اعلام خرابی",
    "در انتظار بررسی پذیرش": "اعلام خرابی",
    "در انتظار ارسال حواله است": "حواله انبار",
    "در انتظار دریافت قطعه است": "دریافت قطعه — انبار استان",
    "در انتظار دریافت قطعه در انبار استان است": "دریافت قطعه — انبار استان",
    "در انتظار ارسال باربری برای نماینده است": "ارسال قطعه برای نماینده",
    "در انتظار دریافت قطعه توسط نماینده است": "دریافت قطعه توسط نماینده",
    "ماموریت در جریان (کارتابل نماینده)": "مأموریت نماینده — در جریان",
    "در انتظار گزارش تکنسین (نماینده) است": "تعمیر انجام‌شده — منتظر بررسی پذیرش",
    "در انتظار بررسی گزارش توسط پذیرش است": "تعمیر انجام‌شده — منتظر بررسی پذیرش",
    "پیش‌فاکتور رد شد — درخواست لغو شد": "لغو — رد پیش‌فاکتور",
    "در انتظار ثبت شماره فاکتور است": "فاکتور صادر شد",
}

try:
    from core.constants import CLOSED_STATUSES, REOPEN_ROLES
except Exception:
    CLOSED_STATUSES = {
        "بسته شد", "پایان تعمیرات", "پایان", "تحویل شد",
        "نصب انجام شد", "بازدید انجام شد",
        "پیش‌فاکتور رد شد — درخواست لغو شد",
        "پیش‌فاکتور رد شد — ارسال به مشتری",
    }
    REOPEN_ROLES = ("مدیر سیستم",)

WH_AUTO_ON_STATUS = {
    "حواله تعمیر نهایی": "entry_internal_final",
    "گزارش نهایی": "exit_internal_final",
    "حواله انبار": "entry_external_province",
    "دریافت قطعه — انبار استان": "entry_external_province",
    "مأموریت نماینده — در جریان": "transfer_to_rep",
}


def normalize_status(st):
    if not st:
        return st
    return STATUS_ALIASES.get(st, st)


def migrate_statuses(conn):
    """Normalize legacy labels only for non-repair workflows.

    Repair records are governed by the canonical workflow state machine and DB
    transition guard; legacy bulk rewrites must not bypass that invariant.
    """
    rows = conn.execute("SELECT id, status, request_category FROM requests").fetchall()
    n = 0
    for r in rows:
        # Empty database/new installs should never mutate canonical repair states
        # through this legacy compatibility helper.
        if (r["request_category"] or "") == "تعمیر":
            continue
        old = r["status"] or ""
        new = normalize_status(old)
        if new != old:
            conn.execute("UPDATE requests SET status=? WHERE id=?", (new, r["id"]))
            n += 1
    conn.commit()
    return n


def ensure_improvements_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS case_checklist ("
        "request_id INTEGER PRIMARY KEY,"
        "serial_ok INTEGER DEFAULT 0,"
        "parts_ok INTEGER DEFAULT 0,"
        "photo_ok INTEGER DEFAULT 0,"
        "match_ok INTEGER DEFAULT 0,"
        "updated_by TEXT,"
        "updated_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)"
    )
    try:
        from features_compat import ensure_features_schema
        ensure_features_schema(conn)
    except Exception:
        pass
    try:
        from core.control_warehouses import ensure_control_wh_schema
        ensure_control_wh_schema(conn)
    except Exception:
        pass
    conn.commit()


def checklist_complete(conn, request_id):
    row = conn.execute(
        "SELECT * FROM case_checklist WHERE request_id=?", (request_id,)
    ).fetchone()
    if not row:
        return False
    return all(int(row[k] or 0) for k in ("serial_ok", "parts_ok", "photo_ok", "match_ok"))


def _today():
    try:
        import jdatetime
        t = jdatetime.date.today()
        return "%d/%02d/%02d" % (t.year, t.month, t.day)
    except Exception:
        return datetime.now().strftime("%Y/%m/%d")


def try_auto_warehouse(conn, request_id, new_status, user_name=None):
    action = WH_AUTO_ON_STATUS.get(new_status)
    if not action:
        return
    try:
        from core.control_warehouses import (
            entry_internal,
            exit_internal_final_report,
            entry_external_province,
            transfer_external_to_rep,
        )
    except Exception:
        return
    req = conn.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
    if not req:
        return
    parts = [dict(p) for p in conn.execute(
        "SELECT * FROM request_parts WHERE request_id=?", (request_id,)
    ).fetchall()]
    if not parts:
        return
    stype = req["service_type"] if "service_type" in req.keys() else ""
    province = req["province"] if "province" in req.keys() else ""
    tech = req["assigned_technician"] if "assigned_technician" in req.keys() else None
    try:
        if action == "entry_internal_final" and stype == "کارخانه":
            entry_internal(conn, request_id, parts, "ورود — تعمیر نهایی", user_name)
        elif action == "exit_internal_final" and stype == "کارخانه":
            exit_internal_final_report(conn, request_id, parts, user_name)
        elif action == "entry_external_province" and stype == "در محل":
            entry_external_province(conn, request_id, parts, province, user_name)
        elif action == "transfer_to_rep" and stype == "در محل" and tech:
            transfer_external_to_rep(conn, request_id, parts, province, None, tech, user_name)
    except Exception as e:
        print("[auto-wh]", e)


def register_improvements(app, get_db, get_current_user, helpers=None):
    helpers = helpers or {}

    @app.route("/admin/migrate-statuses", methods=["POST"])
    def admin_migrate_statuses():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", "مدیر", "مدیر سیستم"):
            return redirect("/")
        conn = get_db()
        n = migrate_statuses(conn)
        conn.close()
        return redirect("/reports/manager-dashboard?migrated=%d" % n)

    @app.route("/api/checklist/<int:req_id>", methods=["GET", "POST"])
    def api_checklist(req_id):
        user = get_current_user()
        if not user:
            return jsonify({"ok": False}), 401
        conn = get_db()
        ensure_improvements_schema(conn)
        if request.method == "POST":
            if user["role"] not in ("مسئول پذیرش", "مدیر", "مدیر سیستم"):
                conn.close()
                return jsonify({"ok": False}), 403
            data = {
                "serial_ok": 1 if request.form.get("serial_ok") in ("1", "on", "true") else 0,
                "parts_ok": 1 if request.form.get("parts_ok") in ("1", "on", "true") else 0,
                "photo_ok": 1 if request.form.get("photo_ok") in ("1", "on", "true") else 0,
                "match_ok": 1 if request.form.get("match_ok") in ("1", "on", "true") else 0,
            }
            conn.execute(
                "INSERT INTO case_checklist (request_id, serial_ok, parts_ok, photo_ok, match_ok, updated_by, updated_at) "
                "VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(request_id) DO UPDATE SET "
                "serial_ok=excluded.serial_ok, parts_ok=excluded.parts_ok, "
                "photo_ok=excluded.photo_ok, match_ok=excluded.match_ok, "
                "updated_by=excluded.updated_by, updated_at=excluded.updated_at",
                (req_id, data["serial_ok"], data["parts_ok"], data["photo_ok"], data["match_ok"],
                 user["full_name"], _today()),
            )
            conn.commit()
            conn.close()
            return jsonify({"ok": True, "complete": all(data.values())})
        row = conn.execute("SELECT * FROM case_checklist WHERE request_id=?", (req_id,)).fetchone()
        conn.close()
        if not row:
            return jsonify({"serial_ok": 0, "parts_ok": 0, "photo_ok": 0, "match_ok": 0, "complete": False})
        d = {k: row[k] for k in row.keys()}
        d["complete"] = all(int(d.get(k) or 0) for k in ("serial_ok", "parts_ok", "photo_ok", "match_ok"))
        return jsonify(d)

    @app.route("/api/cartable-badge")
    def api_cartable_badge():
        """شمارندهٔ کارهای معلق نقش — فقط برای کارتابل؛ اعلان‌ها از /notifications می‌آیند."""
        user = get_current_user()
        if not user:
            return jsonify({"count": 0, "delayed": 0})
        conn = get_db()
        count = 0
        try:
            role = user.get("role") if isinstance(user, dict) else user["role"]
            if role in ("مسئول پذیرش", "مدیر", "مدیر سیستم"):
                count = conn.execute(
                    """
                    SELECT COUNT(*) c FROM requests WHERE status IN (
                        'پذیرش','اعلام خرابی','تعمیر انجام‌شده — منتظر بررسی پذیرش',
                        'تحویل به پذیرش','رد پیش‌فاکتور — ارسال به مشتری',
                        'در انتظار پذیرش دستگاه است','پذیرش انجام شد',
                        'در انتظار بررسی پذیرش','در انتظار پذیرش'
                    )
                    OR (
                        request_category IN ('درخواست خدمات','اعلام خرابی','درخواست سرویس')
                        AND IFNULL(status,'') NOT IN (
                            'پایان تعمیرات','پایان','بسته شد','تحویل شد',
                            'نصب انجام شد','بازدید انجام شد',
                            'پیش‌فاکتور رد شد — درخواست لغو شد',
                            'پیش‌فاکتور رد شد — ارسال به مشتری'
                        )
                    )
                    """
                ).fetchone()["c"]
            elif role == "کنترل کیفیت":
                count = conn.execute(
                    """SELECT COUNT(*) c FROM requests
                       WHERE service_type='کارخانه' AND request_category='تعمیر'
                         AND (status LIKE '%تست%' OR status LIKE '%گزارش%')
                         AND IFNULL(status,'') NOT IN ('پایان تعمیرات','پایان','بسته شد','تحویل شد')"""
                ).fetchone()["c"]
            elif role in ("تکنسین کارخانه", "تکنسین استانی"):
                name = user.get("full_name") if isinstance(user, dict) else user["full_name"]
                count = conn.execute(
                    """SELECT COUNT(*) c FROM requests
                       WHERE assigned_technician=? AND IFNULL(status,'') NOT IN (
                            'پایان تعمیرات','پایان','بسته شد','تحویل شد','نصب انجام شد','بازدید انجام شد'
                       )""",
                    (name,),
                ).fetchone()["c"]
            else:
                count = 0
        except Exception:
            count = 0
        conn.close()
        return jsonify({"count": int(count or 0), "delayed": 0})

    @app.route("/api/case-timeline/<int:req_id>")
    def api_case_timeline(req_id):
        user = get_current_user()
        if not user:
            return jsonify([])
        conn = get_db()
        items = []
        for table, builder in (
            ("request_stage_dates", lambda s: {
                "type": "stage", "title": s["stage_name"], "date": s["stage_date"],
                "notes": s["notes"] if "notes" in s.keys() else "",
            }),
        ):
            try:
                for s in conn.execute(
                    "SELECT * FROM request_stage_dates WHERE request_id=? ORDER BY id", (req_id,)
                ).fetchall():
                    items.append(builder(s))
            except Exception:
                pass
        try:
            for a in conn.execute(
                "SELECT * FROM status_history WHERE request_id=? ORDER BY id DESC LIMIT 50", (req_id,)
            ).fetchall():
                items.append({
                    "type": "history",
                    "title": "%s → %s" % (a["from_status"] or "", a["to_status"] or ""),
                    "date": a["changed_at"], "user": a["changed_by"], "notes": a["note"],
                })
        except Exception:
            pass
        try:
            for a in conn.execute(
                "SELECT * FROM audit_log WHERE entity_type=? AND entity_id=? ORDER BY id DESC LIMIT 40",
                ("request", req_id),
            ).fetchall():
                items.append({
                    "type": "audit",
                    "title": a["action"] if "action" in a.keys() else "",
                    "date": a["created_at"] if "created_at" in a.keys() else "",
                    "user": a["user_name"] if "user_name" in a.keys() else "",
                    "notes": a["details"] if "details" in a.keys() else "",
                })
        except Exception:
            pass
        try:
            for a in conn.execute(
                "SELECT * FROM request_attachments WHERE request_id=? ORDER BY id DESC", (req_id,)
            ).fetchall():
                items.append({
                    "type": "file",
                    "title": "پیوست: " + (a["original_name"] or a["filename"] or ""),
                    "date": a["uploaded_at"], "user": a["uploaded_by"],
                })
        except Exception:
            pass
        conn.close()
        return jsonify(items)

    @app.route("/service/reopen/<int:req_id>", methods=["POST"])
    def reopen_case(req_id):
        """بازگشایی پرونده بسته — منبع واحد وضعیت و نقش."""
        user = get_current_user()
        role = user["role"] if user and not isinstance(user, dict) else (user.get("role") if user else None)
        if not user or role not in REOPEN_ROLES:
            return "فقط پذیرش", 403
        conn = get_db()
        req = conn.execute("SELECT status, service_type FROM requests WHERE id=?", (req_id,)).fetchone()
        if not req:
            conn.close()
            return redirect("/")
        # وضعیت شروع استاندارد از constants
        try:
            from core.constants import EXTERNAL_REPAIR_STATUSES, INTERNAL_REPAIR_STATUSES
            if req["service_type"] == "در محل":
                new_st = EXTERNAL_REPAIR_STATUSES[1]  # پذیرش انجام شد (نقطه شروع کانونیک، هم‌سو با accept_external)
            else:
                new_st = INTERNAL_REPAIR_STATUSES[0]  # پذیرش دستگاه انجام شد
        except Exception:
            new_st = "پذیرش انجام شد" if req["service_type"] == "در محل" else "پذیرش دستگاه انجام شد"
        try:
            from core.workflow import transition_request, WorkflowError
            transition_request(conn, req_id, new_st, actor_name=user["full_name"], actor_role=role, note="بازگشایی پرونده", allow_reopen=True)
        except WorkflowError:
            conn.close()
            target_slug = 'external-repair' if req['service_type'] == 'در محل' else 'internal-repair'
            return redirect(f'/service/{target_slug}/view/{req_id}?err=reopen_not_allowed')
        try:
            from core.helpers import write_audit
            write_audit(conn, user["full_name"], "بازگشایی پرونده", "request", req_id, f"{req["status"]} → {new_st}")
        except Exception:
            pass
        conn.commit()
        conn.close()
        return redirect(request.referrer or "/")

    @app.route("/finance/wage-report")
    def finance_wage_report():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", "امور مالی", "مدیر", "مدیر سیستم"):
            return redirect("/")
        parts = _today().split("/")
        year = int(request.args.get("year") or parts[0])
        month = int(request.args.get("month") or parts[1])
        conn = get_db()
        rows = []
        try:
            for r in conn.execute("SELECT * FROM wage_calculations ORDER BY id DESC").fetchall():
                d = (r["calc_date"] or "") if "calc_date" in r.keys() else ""
                p = d.replace("-", "/").split("/")
                try:
                    if len(p) >= 2 and int(p[0]) == year and int(p[1]) == month:
                        rows.append(r)
                except Exception:
                    pass
        except Exception:
            pass
        total = sum(float(r["amount"] or 0) for r in rows)
        conn.close()
        return render_template(
            "wage_report.html", rows=rows, year=year, month=month, total=total,
            current_user=user, active_page="wage-report",
        )

    @app.route("/finance/wage-report/export")
    def finance_wage_export():
        user = get_current_user()
        if not user:
            return redirect("/login")
        parts = _today().split("/")
        year = int(request.args.get("year") or parts[0])
        month = int(request.args.get("month") or parts[1])
        try:
            from openpyxl import Workbook
        except ImportError:
            return "openpyxl required", 500
        conn = get_db()
        try:
            allr = conn.execute("SELECT * FROM wage_calculations ORDER BY id DESC").fetchall()
        except Exception:
            allr = []
        conn.close()
        wb = Workbook()
        ws = wb.active
        ws.append(["id", "نماینده", "شرح", "مبلغ", "تاریخ", "یادداشت"])
        for r in allr:
            d = (r["calc_date"] or "") if "calc_date" in r.keys() else ""
            p = d.replace("-", "/").split("/")
            try:
                if len(p) >= 2 and int(p[0]) == year and int(p[1]) == month:
                    ws.append([
                        r["id"],
                        r["representative_name"] if "representative_name" in r.keys() else "",
                        r["work_description"] if "work_description" in r.keys() else "",
                        r["amount"], d,
                        r["notes"] if "notes" in r.keys() else "",
                    ])
            except Exception:
                pass
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name="wage_%s_%s.xlsx" % (year, month))

    @app.route("/api/warranty-hint")
    def api_warranty_hint():
        serial = (request.args.get("serial") or "").strip()
        if not serial:
            return jsonify({"status": "unknown", "message": ""})
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM warranty_cards WHERE serial_number=? ORDER BY id DESC LIMIT 1", (serial,)
        ).fetchone()
        conn.close()
        if not row:
            return jsonify({"status": "not_found", "message": "کارت گارانتی یافت نشد — مسیر غیررایگان محتمل"})
        end = row["warranty_end_date"] if "warranty_end_date" in row.keys() else None
        if end and end < _today():
            return jsonify({"status": "expired", "message": "گارانتی منقضی — مسیر غیررایگان", "end_date": end})
        if end:
            return jsonify({"status": "active", "message": "در دوره گارانتی — مسیر رایگان محتمل", "end_date": end})
        return jsonify({"status": "ok", "message": "گارانتی ثبت شده", "end_date": end or ""})

    @app.route("/announce/qr")
    def announce_qr():
        """یک QR / یک لینک برای اعلام + پیگیری + گفتگو."""
        base = request.host_url.rstrip("/")
        url = base + "/support"
        html = (
            "<!DOCTYPE html><html lang=fa dir=rtl><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>QR خدمات سازگان</title>"
            "<style>body{font-family:Tahoma,sans-serif;padding:24px;text-align:center;background:#f8fafc;color:#0f172a}"
            ".box{display:inline-block;padding:22px;border:1px solid #e2e8f0;border-radius:16px;background:#fff;"
            "box-shadow:0 8px 24px rgba(15,23,42,.06);max-width:440px}"
            "h2{margin:0 0 8px} p{color:#64748b;font-size:13.5px;line-height:1.7}"
            "code{display:block;background:#f1f5f9;padding:12px;border-radius:8px;word-break:break-all;direction:ltr;margin:10px 0}"
            "a.btn{display:inline-block;margin:8px 4px;padding:12px 18px;border-radius:10px;background:#2563eb;color:#fff;"
            "text-decoration:none;font-weight:700;font-size:13px}</style></head>"
            "<body><div class=box><h2>اعلام، پیگیری و گفتگو</h2>"
            "<p>یک لینک برای مشتری: ثبت اعلام خرابی، پیگیری با سریال، و گفتگو با شرکت.</p>"
            "<code>%s</code>"
            "<p><a class=btn href='%s'>باز کردن صفحه</a></p>"
            "<p style='font-size:12px'>همین لینک را به‌صورت QR چاپ کنید.</p>"
            "</div></body></html>"
        ) % (url, url)
        return Response(html, mimetype="text/html; charset=utf-8")

    @app.route("/reports/manager-dashboard")
    def manager_dashboard():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", "مدیر", "مدیر سیستم", "امور مالی"):
            return redirect("/")
        conn = get_db()
        try:
            migrate_statuses(conn)
        except Exception:
            pass
        total = conn.execute("SELECT COUNT(*) AS c FROM requests").fetchone()["c"]
        open_n = conn.execute(
            "SELECT COUNT(*) AS c FROM requests WHERE status NOT IN (%s)"
            % ",".join(["?"] * len(CLOSED_STATUSES)),
            tuple(CLOSED_STATUSES),
        ).fetchone()["c"]
        rejected = conn.execute(
            "SELECT COUNT(*) AS c FROM requests WHERE status LIKE '%رد پیش‌فاکتور%'"
        ).fetchone()["c"]
        by_prov = conn.execute(
            "SELECT province, COUNT(*) AS c FROM requests GROUP BY province ORDER BY c DESC LIMIT 15"
        ).fetchall()
        by_st = conn.execute(
            "SELECT status, COUNT(*) AS c FROM requests GROUP BY status ORDER BY c DESC LIMIT 15"
        ).fetchall()
        conn.close()
        return render_template(
            "manager_dashboard.html",
            total=total, open_n=open_n, rejected=rejected, by_prov=by_prov, by_st=by_st,
            current_user=user, active_page="manager-dashboard",
        )

    @app.route("/settings/backup-path", methods=["GET", "POST"])
    def settings_backup_path():
        """یکپارچه با /security/backups — مسیر شبکه همان‌جا تنظیم می‌شود."""
        return redirect("/security/backups")


    @app.route("/security/backup-network", methods=["POST"])
    def backup_network_now():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", "مدیر", "مدیر سیستم"):
            return redirect("/")
        conn = get_db()
        ensure_improvements_schema(conn)
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key='backup_network_path'"
        ).fetchone()
        conn.close()
        dest_root = (row["value"] if row else "") or ""
        create_backup = helpers.get("create_backup")
        local = create_backup("network") if create_backup else None
        copied = False
        if dest_root and local and os.path.isdir(dest_root):
            import shutil
            try:
                name = os.path.basename(str(local).rstrip("/\\"))
                shutil.copytree(local, os.path.join(dest_root, name), dirs_exist_ok=True)
                copied = True
            except Exception as e:
                print("[backup-net]", e)
        return redirect("/security/backups?copied=%s" % int(copied))

    @app.route("/security/audit-filter")
    def audit_filter():
        user = get_current_user()
        if not user or user["role"] not in ("مسئول پذیرش", "مدیر", "مدیر سیستم"):
            return redirect("/")
        q = (request.args.get("q") or "").strip()
        action = (request.args.get("action") or "").strip()
        conn = get_db()
        rows = []
        try:
            sql = "SELECT * FROM audit_log WHERE 1=1"
            params = []
            if action:
                sql += " AND action LIKE ?"
                params.append("%" + action + "%")
            if q:
                sql += " AND (IFNULL(details,'') LIKE ? OR IFNULL(user_name,'') LIKE ? OR CAST(entity_id AS TEXT) LIKE ?)"
                params.extend(["%" + q + "%", "%" + q + "%", "%" + q + "%"])
            sql += " ORDER BY id DESC LIMIT 200"
            rows = conn.execute(sql, params).fetchall()
        except Exception:
            pass
        conn.close()
        return render_template(
            "audit_filter.html", rows=rows, q=q, action=action,
            current_user=user, active_page="audit-filter",
        )

    print("[improvements] registered")
