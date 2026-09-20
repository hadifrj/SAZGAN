# -*- coding: utf-8 -*-
"""صدور حواله انبار (Word/PDF) برای تعمیر داخلی و خارجی."""
from __future__ import annotations

import os
from datetime import datetime
from flask import request, redirect, render_template_string, send_file, session
from io import BytesIO

try:
    import jdatetime
except ImportError:
    jdatetime = None


def _today():
    if jdatetime:
        d = jdatetime.date.today()
        return f"{d.year}/{d.month:02d}/{d.day:02d}"
    return datetime.now().strftime("%Y/%m/%d")


def _parts_for_request(conn, request_id, stage=None):
    if stage:
        rows = conn.execute(
            "SELECT * FROM request_parts WHERE request_id=? AND stage=? ORDER BY id",
            (request_id, stage),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM request_parts WHERE request_id=? ORDER BY id",
            (request_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        out.append({
            "warehouse_code": d.get("warehouse_code") or "",
            "part_name": d.get("part_name") or "",
            "quantity": d.get("quantity") or 1,
            "serial_good": d.get("serial_good") or d.get("serial_healthy") or "",
            "serial_defective": d.get("serial_defective") or d.get("serial_faulty") or "",
        })
    return out


def _audit(conn, user, action, detail):
    try:
        name = ""
        if user:
            name = user.get("full_name") if isinstance(user, dict) else user["full_name"]
        conn.execute(
            "INSERT INTO audit_log (user_name, action, detail, created_at) VALUES (?,?,?,?)",
            (name or "—", action, detail, _today()),
        )
        conn.commit()
    except Exception:
        pass


def _docx_bytes(title, meta_lines, parts, voucher_no):
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        return None
    doc = Document()
    h = doc.add_heading(title, level=1)
    h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for line in meta_lines:
        p = doc.add_paragraph(line)
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph("")
    table = doc.add_table(rows=1, cols=4)
    hdr = table.rows[0].cells
    hdr[0].text = "کد انبار"
    hdr[1].text = "نام قطعه"
    hdr[2].text = "تعداد"
    hdr[3].text = "سریال"
    for p in parts:
        row = table.add_row().cells
        row[0].text = str(p.get("warehouse_code") or "")
        row[1].text = str(p.get("part_name") or "")
        row[2].text = str(p.get("quantity") or "")
        ser = (p.get("serial_good") or p.get("serial_defective") or "")
        row[3].text = str(ser)
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def register_voucher_export_routes(app, get_db, get_current_user):
    @app.route("/service/<kind>/view/<int:req_id>/voucher/issue", methods=["POST"])
    def service_voucher_issue(kind, req_id):
        user = get_current_user()
        if not user:
            return redirect("/login")
        direction = (request.form.get("direction") or request.form.get("voucher_direction") or "").strip()
        vtype = (request.form.get("voucher_type") or "").strip()
        fmt = (request.form.get("format") or "docx").strip().lower()
        conn = get_db()
        req = conn.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()
        if not req:
            conn.close()
            return redirect("/")
        parts = _parts_for_request(conn, req_id)
        if kind in ('internal-repair', 'internal'):
            # فقط قطعات مربوط به مرحله فعال وارد حواله می‌شوند.
            active_stage = 'تعمیر اولیه' if (req['status'] or '') == 'در انتظار ارسال حواله تعمیر اولیه است' else ('تعمیر نهایی' if (req['status'] or '') == 'در انتظار ارسال حواله تعمیر نهایی است' else None)
            if active_stage:
                parts = _parts_for_request(conn, req_id, active_stage)
        province = ""
        try:
            province = req["province"] or ""
        except Exception:
            pass
        user_name = user.get("full_name") if isinstance(user, dict) else user["full_name"]
        vno = None
        try:
            from core.control_warehouses import (
                entry_internal,
                exit_internal_final_report,
                entry_external_province,
            )
        except Exception:
            try:
                from control_warehouses import (
                    entry_internal,
                    exit_internal_final_report,
                    entry_external_province,
                )
            except Exception as e:
                conn.close()
                return f"ماژول انبار در دسترس نیست: {e}", 500

        try:
            if kind in ("internal-repair", "internal"):
                # در محدوده مراحل ۱ تا ۶، صدور حواله فقط برای تعمیر اولیه و فقط
                # وقتی پرونده در صف همین Action است مجاز است. نوع حواله از Status
                # تعیین می‌شود و از فرم کاربر گرفته نمی‌شود.
                cur_st = req["status"] or ""
                if cur_st == "در انتظار ارسال حواله تعمیر اولیه است":
                    if user.get('role') not in ('تکنسین کارخانه','مدیر','مدیر سیستم','مسئول پذیرش'):
                        conn.close(); return redirect(f"/service/internal-repair/view/{req_id}?err=voucher_role_not_allowed")
                    vtype = "ورود — تعمیر اولیه"
                    parts = _parts_for_request(conn, req_id, 'تعمیر اولیه')
                    if not parts:
                        conn.close(); return redirect(f"/service/internal-repair/view/{req_id}?err=parts_required")
                    vno = entry_internal(conn, req_id, parts, vtype, user_name)
                    next_st = "در انتظار دریافت قطعه تعمیر اولیه است"
                    conn.execute("UPDATE requests SET status=? WHERE id=? AND status=?", (next_st, req_id, cur_st))
                    from core.helpers import _set_stage_date
                    _set_stage_date(conn, req_id, next_st, None, "صدور حواله تعمیر اولیه")
                    _audit(conn, user, "صدور حواله تعمیر اولیه", f"req={req_id} vno={vno} from={cur_st} to={next_st}")
                elif cur_st == "در انتظار ارسال حواله تعمیر نهایی است":
                    if user.get('role') not in ('تکنسین کارخانه','مدیر','مدیر سیستم','مسئول پذیرش'):
                        conn.close(); return redirect(f"/service/internal-repair/view/{req_id}?err=voucher_role_not_allowed")
                    vtype = "ورود — تعمیر نهایی"
                    parts = _parts_for_request(conn, req_id, 'تعمیر نهایی')
                    if not parts:
                        conn.close(); return redirect(f"/service/internal-repair/view/{req_id}?err=parts_required")
                    vno = entry_internal(conn, req_id, parts, vtype, user_name)
                    next_st = "در انتظار دریافت قطعه تعمیر نهایی است"
                    conn.execute("UPDATE requests SET status=? WHERE id=? AND status=?", (next_st, req_id, cur_st))
                    from core.helpers import _set_stage_date
                    _set_stage_date(conn, req_id, next_st, None, "صدور حواله تعمیر نهایی")
                    _audit(conn, user, "صدور حواله تعمیر نهایی", f"req={req_id} vno={vno} from={cur_st} to={next_st}")
                else:
                    conn.close(); return redirect(f"/service/internal-repair/view/{req_id}?err=voucher_action_not_allowed")
            else:
                # external — ورود استانی؛ انتقال/خروج در صورت نیاز از پنل با پارامترهای کامل
                if direction in ("ورود", "entry", "in") or "ورود" in (vtype or ""):
                    vno = entry_external_province(conn, req_id, parts, province, user_name)
                else:
                    # fallback: ورود استانی اگر نوع نامشخص
                    vno = entry_external_province(conn, req_id, parts, province, user_name)
            conn.commit()
            _audit(conn, user, "voucher_issue", f"req={req_id} kind={kind} vno={vno}")
        except Exception as e:
            conn.close()
            return f"خطا در صدور حواله: {e}", 500

        meta = [
            f"شماره حواله: {vno or '—'}",
            f"پرونده: #{req_id}",
            f"تاریخ: {_today()}",
            f"صادرکننده: {user_name or '—'}",
            f"نوع: {vtype or direction or kind}",
        ]
        title = f"حواله انبار — {vno or req_id}"

        if fmt == "pdf" or fmt == "html":
            rows = "".join(
                f"<tr><td>{p.get('warehouse_code') or ''}</td><td>{p.get('part_name') or ''}</td>"
                f"<td>{p.get('quantity') or ''}</td><td>{p.get('serial_good') or p.get('serial_defective') or ''}</td></tr>"
                for p in parts
            )
            html = f"""<!DOCTYPE html><html lang=fa dir=rtl><head><meta charset=utf-8>
            <title>{title}</title>
            <style>body{{font-family:Tahoma;padding:24px}} table{{width:100%;border-collapse:collapse}}
            th,td{{border:1px solid #ccc;padding:8px;text-align:right}} h1{{font-size:18px}}</style></head>
            <body onload="window.print()"><h1>{title}</h1>
            <p>{'<br>'.join(meta)}</p>
            <table><tr><th>کد انبار</th><th>نام قطعه</th><th>تعداد</th><th>سریال</th></tr>{rows}</table>
            </body></html>"""
            conn.close()
            return render_template_string(html)

        buf = _docx_bytes(title, meta, parts, vno)
        conn.close()
        if not buf:
            return "python-docx نصب نیست؛ فرمت HTML را انتخاب کنید.", 500
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"voucher_{vno or req_id}.docx",
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
