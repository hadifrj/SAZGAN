# -*- coding: utf-8 -*-
"""
انبارهای کنترلی خدمات پس از فروش (نه انبار اصلی)
================================================

1) انبار تعمیرات داخلی
   - گردش قطعه روی پرونده کارخانه
   - ورود با حواله اولیه/نهایی
   - خروج با گزارش نهایی (+ سریال سالم/داغی روی گزارش)
   - موجودی صفر عادی است

2) انبار خدمات پس از فروش — تعمیرات خارجی
   - قفسه‌ها = استان‌ها (استان از پرونده مشتری)
   - ورود → قفسه استان پرونده
   - خروج گزارش → همان قفسه استان
   - خروج قطعه استفاده‌نشده از حساب نماینده
   - موجودی صفر عادی است

ثبت:
  register_control_warehouse_routes(app, get_db, get_current_user)
"""
from __future__ import annotations

from flask import redirect, render_template, request, send_file


def _today():
    try:
        import jdatetime

        t = jdatetime.date.today()
        return f"{t.year}/{str(t.month).zfill(2)}/{str(t.day).zfill(2)}"
    except Exception:
        from datetime import date

        return date.today().isoformat()


def ensure_control_wh_schema(conn):
    # قطعات روی پرونده + سریال
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS request_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            part_id INTEGER,
            warehouse_code TEXT,
            part_name TEXT,
            quantity REAL DEFAULT 1,
            serial_good TEXT,
            serial_defective TEXT,
            source TEXT,
            phase TEXT,
            created_at TEXT
        )
        """
    )
    rp = {r[1] for r in conn.execute("PRAGMA table_info(request_parts)").fetchall()}
    # Fixed schema whitelist; identifiers are not sourced from HTTP input.
    for c in ("serial_good", "serial_defective", "warehouse_code", "part_name", "quantity", "source", "phase", "created_at", "part_id", "stage", "notes"):
        if c not in rp:
            try:
                conn.execute(f"ALTER TABLE request_parts ADD COLUMN {c} TEXT")
            except Exception:
                pass

    # حواله‌ها
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_no TEXT,
            voucher_type TEXT,
            request_id INTEGER,
            part_id INTEGER,
            warehouse_code TEXT,
            part_name TEXT,
            quantity REAL DEFAULT 1,
            serial_good TEXT,
            serial_defective TEXT,
            direction TEXT,
            warehouse_scope TEXT,
            province TEXT,
            representative_id INTEGER,
            representative_name TEXT,
            note TEXT,
            created_at TEXT,
            created_by TEXT
        )
        """
    )
    vc = {r[1] for r in conn.execute("PRAGMA table_info(warehouse_vouchers)").fetchall()}
    for c in (
        "serial_good", "serial_defective", "direction", "warehouse_scope",
        "province", "representative_id", "representative_name",
    ):
        if c not in vc:
            try:
                conn.execute(f"ALTER TABLE warehouse_vouchers ADD COLUMN {c} TEXT")
            except Exception:
                pass

    # موجودی کنترلی داخلی (روی پرونده) — پایه صفر
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS control_stock_internal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            warehouse_code TEXT,
            part_name TEXT,
            quantity REAL DEFAULT 0,
            updated_at TEXT,
            UNIQUE(request_id, warehouse_code, part_name)
        )
        """
    )

    # موجودی کنترلی خارجی — قفسه استان + نزد نماینده
    # shelf = province | with_rep
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS control_stock_external (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_code TEXT,
            part_name TEXT,
            province TEXT,
            representative_id INTEGER,
            representative_name TEXT,
            shelf_kind TEXT NOT NULL,
            quantity REAL DEFAULT 0,
            updated_at TEXT
        )
        """
    )
    # shelf_kind: 'province' | 'with_rep'

    cols = {r[1] for r in conn.execute("PRAGMA table_info(requests)").fetchall()}
    for c in ("warehouse_voucher_no",):
        if c not in cols:
            try:
                conn.execute(f"ALTER TABLE requests ADD COLUMN {c} TEXT")
            except Exception:
                pass
    conn.commit()


def _delta_internal(conn, request_id, code, name, delta):
    code = (code or "").strip()
    name = (name or "").strip()
    row = conn.execute(
        """
        SELECT id, quantity FROM control_stock_internal
        WHERE request_id=? AND IFNULL(warehouse_code,'')=? AND IFNULL(part_name,'')=?
        """,
        (request_id, code, name),
    ).fetchone()
    if row:
        q = max(0.0, float(row["quantity"] or 0) + float(delta))
        conn.execute(
            "UPDATE control_stock_internal SET quantity=?, updated_at=? WHERE id=?",
            (q, _today(), row["id"]),
        )
    else:
        q = max(0.0, float(delta))
        conn.execute(
            """
            INSERT INTO control_stock_internal (request_id, warehouse_code, part_name, quantity, updated_at)
            VALUES (?,?,?,?,?)
            """,
            (request_id, code, name, q, _today()),
        )


def _delta_external(conn, *, shelf_kind, code, name, delta, province=None, rep_id=None, rep_name=None):
    code = (code or "").strip()
    name = (name or "").strip()
    prov = (province or "").strip()
    if shelf_kind == "province":
        row = conn.execute(
            """
            SELECT id, quantity FROM control_stock_external
            WHERE shelf_kind='province'
              AND IFNULL(warehouse_code,'')=? AND IFNULL(part_name,'')=?
              AND IFNULL(province,'')=?
            """,
            (code, name, prov),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT id, quantity FROM control_stock_external
            WHERE shelf_kind='with_rep'
              AND IFNULL(warehouse_code,'')=? AND IFNULL(part_name,'')=?
              AND IFNULL(representative_id,0)=?
            """,
            (code, name, rep_id or 0),
        ).fetchone()
    if row:
        q = max(0.0, float(row["quantity"] or 0) + float(delta))
        conn.execute(
            "UPDATE control_stock_external SET quantity=?, updated_at=? WHERE id=?",
            (q, _today(), row["id"]),
        )
    else:
        q = max(0.0, float(delta))
        conn.execute(
            """
            INSERT INTO control_stock_external
            (warehouse_code, part_name, province, representative_id, representative_name,
             shelf_kind, quantity, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (code, name, prov or None, rep_id, rep_name, shelf_kind, q, _today()),
        )


def write_voucher_rows(conn, *, voucher_no, voucher_type, direction, scope, request_id, parts,
                       province=None, rep_id=None, rep_name=None, user_name=None, note=None):
    for p in parts:
        d = dict(p)
        conn.execute(
            """
            INSERT INTO warehouse_vouchers
            (voucher_no, voucher_type, request_id, part_id, warehouse_code, part_name,
             quantity, serial_good, serial_defective, direction, warehouse_scope,
             province, representative_id, representative_name, note, created_at, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                voucher_no,
                voucher_type,
                request_id,
                d.get("part_id"),
                d.get("warehouse_code"),
                d.get("part_name"),
                float(d.get("quantity") or 1),
                d.get("serial_good") or d.get("serial_healthy"),
                d.get("serial_defective") or d.get("serial_faulty"),
                direction,
                scope,
                province,
                rep_id,
                rep_name,
                note,
                _today(),
                user_name,
            ),
        )
    try:
        conn.execute("UPDATE requests SET warehouse_voucher_no=? WHERE id=?", (voucher_no, request_id))
    except Exception:
        pass
    conn.commit()


def entry_internal(conn, request_id, parts, voucher_type, user_name=None):
    """حواله ورود انبار تعمیرات داخلی."""
    ensure_control_wh_schema(conn)
    from datetime import datetime

    vno = f"IN-IR-{request_id}-{_today().replace('/','')}-{int(datetime.now().timestamp())%10000}"
    for p in parts:
        d = dict(p)
        qty = float(d.get("quantity") or 1)
        _delta_internal(conn, request_id, d.get("warehouse_code"), d.get("part_name"), qty)
    write_voucher_rows(
        conn,
        voucher_no=vno,
        voucher_type=voucher_type or "ورود — تعمیر نهایی",
        direction="ورود",
        scope="تعمیرات داخلی",
        request_id=request_id,
        parts=parts,
        user_name=user_name,
        note="ورود کنترلی انبار تعمیرات داخلی",
    )
    return vno


def exit_internal_final_report(conn, request_id, parts=None, user_name=None):
    """خروج با گزارش نهایی — صفر کردن موجودی کنترلی پرونده."""
    ensure_control_wh_schema(conn)
    from datetime import datetime

    vno = f"OUT-IR-{request_id}-{_today().replace('/','')}-{int(datetime.now().timestamp())%10000}"
    if not parts:
        stock = conn.execute(
            "SELECT warehouse_code, part_name, quantity FROM control_stock_internal WHERE request_id=? AND quantity>0",
            (request_id,),
        ).fetchall()
        parts = [dict(r) for r in stock]
        # merge serials from request_parts if any
        rp = {
            ((r["warehouse_code"] or ""), (r["part_name"] or "")): dict(r)
            for r in conn.execute("SELECT * FROM request_parts WHERE request_id=?", (request_id,)).fetchall()
        }
        for p in parts:
            key = ((p.get("warehouse_code") or ""), (p.get("part_name") or ""))
            if key in rp:
                row = rp[key]
                p["serial_good"] = (row.get("serial_good") or row.get("serial_healthy") or "") or None
                p["serial_defective"] = (row.get("serial_defective") or row.get("serial_faulty") or "") or None
    for p in parts:
        d = dict(p)
        qty = float(d.get("quantity") or 0)
        _delta_internal(conn, request_id, d.get("warehouse_code"), d.get("part_name"), -qty)
    write_voucher_rows(
        conn,
        voucher_no=vno,
        voucher_type="خروج — گزارش نهایی",
        direction="خروج",
        scope="تعمیرات داخلی",
        request_id=request_id,
        parts=parts,
        user_name=user_name,
        note="خروج کنترلی با گزارش نهایی — موجودی صفر",
    )
    return vno


def entry_external_province(conn, request_id, parts, province, user_name=None):
    """ورود به قفسه استان (انبار خدمات پس از فروش تعمیرات خارجی)."""
    ensure_control_wh_schema(conn)
    from datetime import datetime

    province = (province or "").strip()
    vno = f"IN-EX-{request_id}-{_today().replace('/','')}-{int(datetime.now().timestamp())%10000}"
    for p in parts:
        d = dict(p)
        qty = float(d.get("quantity") or 1)
        _delta_external(
            conn,
            shelf_kind="province",
            code=d.get("warehouse_code"),
            name=d.get("part_name"),
            delta=qty,
            province=province,
        )
    write_voucher_rows(
        conn,
        voucher_no=vno,
        voucher_type="ورود — قفسه استان",
        direction="ورود",
        scope="تعمیرات خارجی",
        request_id=request_id,
        parts=parts,
        province=province,
        user_name=user_name,
        note=f"ورود به قفسه استان {province}",
    )
    return vno


def transfer_external_to_rep(conn, request_id, parts, province, rep_id, rep_name, user_name=None):
    """از قفسه استان → در دست نماینده."""
    ensure_control_wh_schema(conn)
    from datetime import datetime

    vno = f"TR-EX-{request_id}-{_today().replace('/','')}-{int(datetime.now().timestamp())%10000}"
    for p in parts:
        d = dict(p)
        qty = float(d.get("quantity") or 1)
        _delta_external(
            conn, shelf_kind="province", code=d.get("warehouse_code"), name=d.get("part_name"),
            delta=-qty, province=province,
        )
        _delta_external(
            conn, shelf_kind="with_rep", code=d.get("warehouse_code"), name=d.get("part_name"),
            delta=qty, province=province, rep_id=rep_id, rep_name=rep_name,
        )
    write_voucher_rows(
        conn,
        voucher_no=vno,
        voucher_type="ورود — به حساب نماینده",
        direction="ورود",
        scope="تعمیرات خارجی",
        request_id=request_id,
        parts=parts,
        province=province,
        rep_id=rep_id,
        rep_name=rep_name,
        user_name=user_name,
        note="منظور به حساب نماینده",
    )
    return vno


def exit_external_from_report(conn, request_id, parts, province, user_name=None):
    """خروج با گزارش از قفسه استان پرونده."""
    ensure_control_wh_schema(conn)
    from datetime import datetime

    vno = f"OUT-EX-{request_id}-{_today().replace('/','')}-{int(datetime.now().timestamp())%10000}"
    for p in parts:
        d = dict(p)
        qty = float(d.get("quantity") or 1)
        _delta_external(
            conn, shelf_kind="province", code=d.get("warehouse_code"), name=d.get("part_name"),
            delta=-qty, province=province,
        )
    write_voucher_rows(
        conn,
        voucher_no=vno,
        voucher_type="خروج — گزارش از قفسه استان",
        direction="خروج",
        scope="تعمیرات خارجی",
        request_id=request_id,
        parts=parts,
        province=province,
        user_name=user_name,
        note=f"خروج از قفسه استان {province}",
    )
    return vno


def exit_unused_from_rep(conn, request_id, parts, province, rep_id, rep_name, user_name=None):
    """خروج قطعات استفاده‌نشده از حساب نماینده."""
    ensure_control_wh_schema(conn)
    from datetime import datetime

    vno = f"OUT-REP-{request_id}-{_today().replace('/','')}-{int(datetime.now().timestamp())%10000}"
    for p in parts:
        d = dict(p)
        qty = float(d.get("quantity") or 1)
        _delta_external(
            conn, shelf_kind="with_rep", code=d.get("warehouse_code"), name=d.get("part_name"),
            delta=-qty, province=province, rep_id=rep_id, rep_name=rep_name,
        )
    write_voucher_rows(
        conn,
        voucher_no=vno,
        voucher_type="خروج — قطعه استفاده‌نشده از حساب نماینده",
        direction="خروج",
        scope="تعمیرات خارجی",
        request_id=request_id,
        parts=parts,
        province=province,
        rep_id=rep_id,
        rep_name=rep_name,
        user_name=user_name,
        note="خروج قطعه استفاده‌نشده از حساب نماینده",
    )
    return vno


def register_control_warehouse_routes(app, get_db, get_current_user):
    @app.route("/warehouse/internal")
    def warehouse_internal_control():
        """کنترل قطعات تعمیرات داخلی (رهگیری — نه انبار)."""
        current_user = get_current_user()
        if not current_user:
            return redirect("/login")
        conn = get_db()
        ensure_control_wh_schema(conn)
        # اطمینان از وجود ستون is_void
        rows = []
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
            try:
                rows = conn.execute(
                    """
                    SELECT rp.id, rp.request_id, rp.warehouse_code, rp.part_name, rp.quantity,
                           rp.serial_good, rp.serial_defective, rp.serial_healthy, rp.serial_faulty,
                           COALESCE(rp.created_at, r.reception_date) AS created_at,
                           r.reception_no, r.device_type, r.device_model, r.assigned_technician, r.status
                    FROM request_parts rp
                    JOIN requests r ON r.id = rp.request_id
                    WHERE r.service_type = 'کارخانه'
                    ORDER BY rp.id DESC
                    LIMIT 500
                    """
                ).fetchall()
            except Exception:
                rows = []
        q = (request.args.get("q") or "").strip().lower()
        if q:
            filtered = []
            for r in rows:
                d = dict(r)
                blob = " ".join(str(d.get(k) or "") for k in (
                    "reception_no", "request_id", "warehouse_code", "part_name",
                    "serial_good", "serial_defective", "serial_healthy", "serial_faulty",
                    "device_type", "assigned_technician",
                )).lower()
                if q in blob:
                    filtered.append(r)
            rows = filtered
        conn.close()
        return render_template(
            "warehouse_internal.html",
            rows=rows,
            q=q,
            active_page="warehouse-internal",
            current_user=current_user,
        )

    @app.route("/warehouse/external")
    def warehouse_external_control():
        """کنترل قطعات نمایندگان (رهگیری — نه انبار)."""
        current_user = get_current_user()
        if not current_user:
            return redirect("/login")
        province_filter = (request.args.get("province") or "").strip()
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
                    WHERE r.service_type = 'در محل'
                    ORDER BY rp.id DESC
                    LIMIT 500
                    """
                ).fetchall()
            except Exception:
                rows = []
        if province_filter:
            rows = [r for r in rows if (r["province"] or "") == province_filter]
        provinces = sorted(
            {
                (r["province"] or "")
                for r in conn.execute(
                    "SELECT DISTINCT province FROM requests WHERE service_type='در محل' AND province IS NOT NULL AND province != ''"
                ).fetchall()
                if r["province"]
            }
        )
        q = (request.args.get("q") or "").strip().lower()
        if q:
            filtered = []
            for r in rows:
                d = dict(r)
                blob = " ".join(str(d.get(k) or "") for k in (
                    "reception_no", "request_id", "warehouse_code", "part_name",
                    "serial_good", "serial_defective", "serial_healthy", "serial_faulty",
                    "province", "representative_name", "assigned_technician",
                )).lower()
                if q in blob:
                    filtered.append(r)
            rows = filtered
        conn.close()
        return render_template(
            "warehouse_external.html",
            rows=rows,
            q=q,
            provinces=provinces,
            province_filter=province_filter,
            active_page="warehouse-external",
            current_user=current_user,
        )
