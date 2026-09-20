# -*- coding: utf-8 -*-
"""ایندکس پوشه پرونده دستگاه‌ها (سریال → مسیر).

ساختار واقعی روی دیسک:
  F:\\پرونده دستگاه ها\\SH 10\\V880768-BAM
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    import jdatetime
except ImportError:
    jdatetime = None

_SEP = "\\"


def _now() -> str:
    if jdatetime:
        d = jdatetime.datetime.now()
        return f"{d.year}/{d.month:02d}/{d.day:02d} {d.hour:02d}:{d.minute:02d}"
    return datetime.now().strftime("%Y/%m/%d %H:%M")


def normalize_serial(s: str) -> str:
    s = (s or "").strip().upper()
    s = re.sub(r"\s+", "", s)
    return s


def ensure_device_folder_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS device_folder_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial TEXT NOT NULL,
            serial_raw TEXT,
            sh_folder TEXT,
            relative_path TEXT,
            full_path TEXT,
            indexed_at TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dfi_serial ON device_folder_index(serial)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dfi_serial_raw ON device_folder_index(serial_raw)"
    )
    try:
        conn.commit()
    except Exception:
        pass


def get_root_path(conn) -> str:
    try:
        from core.db import get_setting
        return (get_setting(conn, "device_files_root", "") or "").strip()
    except Exception:
        return ""


def set_root_path(conn, path: str) -> None:
    from core.db import set_setting
    set_setting(conn, "device_files_root", (path or "").strip())


def resolve_full_path(conn, relative_path: str = "", stored_full: str = "") -> str:
    root = get_root_path(conn)
    rel = (relative_path or "").replace("/", os.sep).strip(os.sep)
    if root and rel:
        return os.path.normpath(os.path.join(root, rel))
    if stored_full:
        return os.path.normpath(stored_full)
    return ""


def _win_norm(path: str) -> str:
    return (path or "").replace("/", _SEP).rstrip(_SEP)


def _split_win(path: str) -> list:
    return [p for p in _win_norm(path).split(_SEP) if p]


def _canonical_sh(name: str) -> str:
    """SH10 / SH 10 / sh 07 → SH 10"""
    m = re.match(r"^SH\s*(\d+)$", (name or "").strip(), re.I)
    if m:
        return f"SH {int(m.group(1))}"
    return (name or "").strip()


def _parse_sh_and_serial_from_path(full_path: str) -> tuple:
    """برمی‌گرداند: serial_raw, sh_folder, relative_path"""
    parts = _split_win(full_path)
    if not parts:
        return "", "", ""
    leaf = parts[-1]

    # صحیح: ...\SH 10\V880768-BAM
    if len(parts) >= 2 and re.match(r"^SH\s*\d+$", parts[-2], re.I):
        sh = _canonical_sh(parts[-2])
        serial_raw = leaf.strip()
        rel = sh + _SEP + serial_raw
        return serial_raw, sh, rel

    # export چسبیده: ...\SH 10V880768-BAM یا ...\SH52T5251...
    m = re.match(r"^(SH\s*\d+)[\s_\-]*(.+)$", leaf, re.I)
    if m:
        sh = _canonical_sh(m.group(1))
        serial_raw = m.group(2).strip()
        rel = sh + _SEP + serial_raw
        return serial_raw, sh, rel

    return leaf, "", leaf


def normalize_stored_full_path(
    full_path: str,
    serial_raw: str = "",
    sh_folder: str = "",
    relative_path: str = "",
) -> str:
    """مسیر چسبیده را به شکل واقعی ریشه\\SH N\\SERIAL تبدیل می‌کند."""
    parts = _split_win(full_path)
    if not parts:
        return full_path or ""

    # از قبل تو در تو است
    if len(parts) >= 2 and re.match(r"^SH\s*\d+$", parts[-2], re.I):
        sh = _canonical_sh(parts[-2])
        serial = (serial_raw or parts[-1]).strip()
        parent = _SEP.join(parts[:-2])
        return (parent + _SEP if parent else "") + sh + _SEP + serial

    leaf = parts[-1]
    m = re.match(r"^(SH\s*\d+)[\s_\-]*(.+)$", leaf, re.I)
    if m:
        sh = _canonical_sh(m.group(1))
        serial = (serial_raw or m.group(2)).strip()
        parent = _SEP.join(parts[:-1])
        return (parent + _SEP if parent else "") + sh + _SEP + serial

    if sh_folder and serial_raw:
        parent = _SEP.join(parts[:-1]) if len(parts) > 1 else _SEP.join(parts[:-1])
        # اگر leaf همان سریال/چسبیده است parent = همه به‌جز leaf
        parent = _SEP.join(parts[:-1])
        return (parent + _SEP if parent else "") + _canonical_sh(sh_folder) + _SEP + serial_raw.strip()

    return _win_norm(full_path)


def clear_index(conn) -> None:
    ensure_device_folder_schema(conn)
    conn.execute("DELETE FROM device_folder_index")
    conn.commit()


def upsert_row(
    conn,
    serial_raw: str,
    full_path: str,
    sh_folder: str = "",
    relative_path: str = "",
) -> None:
    ensure_device_folder_schema(conn)
    serial_raw = (serial_raw or "").strip()
    full_path = (full_path or "").strip()

    if not serial_raw and full_path:
        serial_raw, sh_folder, relative_path = _parse_sh_and_serial_from_path(full_path)

    if not serial_raw:
        return

    if full_path:
        full_path = normalize_stored_full_path(full_path, serial_raw, sh_folder, relative_path)
        sr2, sh2, rel2 = _parse_sh_and_serial_from_path(full_path)
        serial_raw = serial_raw or sr2
        sh_folder = sh_folder or sh2
        relative_path = relative_path or rel2
    elif sh_folder and serial_raw:
        relative_path = relative_path or (_canonical_sh(sh_folder) + _SEP + serial_raw)

    if sh_folder:
        sh_folder = _canonical_sh(sh_folder)
    if not relative_path and sh_folder and serial_raw:
        relative_path = sh_folder + _SEP + serial_raw

    serial = normalize_serial(serial_raw)
    now = _now()
    conn.execute(
        "DELETE FROM device_folder_index WHERE serial=? AND IFNULL(full_path,'')=?",
        (serial, full_path),
    )
    conn.execute(
        """INSERT INTO device_folder_index
           (serial, serial_raw, sh_folder, relative_path, full_path, indexed_at)
           VALUES (?,?,?,?,?,?)""",
        (serial, serial_raw, sh_folder or "", relative_path or "", full_path, now),
    )


def import_from_rows(conn, rows: List[Dict[str, str]], replace: bool = True) -> dict:
    ensure_device_folder_schema(conn)
    if replace:
        clear_index(conn)
    n = 0
    for r in rows:
        serial = (r.get("serial") or "").strip()
        path = (r.get("path") or r.get("full_path") or "").strip()
        if not serial and not path:
            continue
        upsert_row(conn, serial, path)
        n += 1
    conn.commit()
    return {"imported": n, "total": index_count(conn)}


def import_from_excel(conn, file_storage, replace: bool = True) -> dict:
    try:
        import openpyxl
    except ImportError:
        return {"ok": False, "error": "openpyxl نصب نیست"}
    try:
        wb = openpyxl.load_workbook(file_storage, read_only=True, data_only=True)
    except Exception as e:
        return {"ok": False, "error": f"خواندن اکسل: {e}"}
    rows = []
    for sheet in wb.worksheets:
        headers = None
        for row in sheet.iter_rows(values_only=True):
            vals = [("" if c is None else str(c).strip()) for c in row]
            if not any(vals):
                continue
            if headers is None:
                if any("سریال" in v or "serial" in v.lower() for v in vals) or any(
                    "مسیر" in v or "path" in v.lower() for v in vals
                ):
                    headers = vals
                    continue
                if len(vals) >= 2 and vals[0] and vals[1]:
                    rows.append({"serial": vals[0], "path": vals[1]})
                continue
            data = dict(zip(headers, vals + [""] * max(0, len(headers) - len(vals))))
            serial = ""
            path = ""
            for k, v in data.items():
                kl = (k or "").lower()
                if "سریال" in (k or "") or "serial" in kl:
                    serial = v
                if "مسیر" in (k or "") or "path" in kl or "full" in kl:
                    path = v
            if not serial and len(vals) >= 1:
                serial = vals[0]
            if not path and len(vals) >= 2:
                path = vals[1]
            if serial or path:
                rows.append({"serial": serial, "path": path})
    wb.close()
    if not rows:
        return {"ok": False, "error": "ردیفی برای وارد کردن یافت نشد"}
    stats = import_from_rows(conn, rows, replace=replace)
    stats["ok"] = True
    return stats


def scan_disk_index(conn, root: Optional[str] = None, replace: bool = True) -> dict:
    """پیمایش: ریشه / SH N / SERIAL"""
    root = (root or get_root_path(conn) or "").strip()
    if not root or not os.path.isdir(root):
        return {"ok": False, "error": "مسیر ریشه معتبر نیست"}
    if replace:
        clear_index(conn)
    n = 0
    try:
        for name in os.listdir(root):
            sh_path = os.path.join(root, name)
            if not os.path.isdir(sh_path):
                continue
            if re.match(r"^SH\s*\d+$", name, re.I):
                sh = _canonical_sh(name)
                for serial_name in os.listdir(sh_path):
                    ser_path = os.path.join(sh_path, serial_name)
                    if not os.path.isdir(ser_path):
                        continue
                    rel = sh + _SEP + serial_name
                    upsert_row(conn, serial_name, ser_path, sh, rel)
                    n += 1
            else:
                # پوشه غیر SH در ریشه — نادیده یا ثبت به‌عنوان سریال
                continue
        conn.commit()
    except Exception as e:
        return {"ok": False, "error": str(e), "imported": n}
    return {"ok": True, "imported": n, "total": index_count(conn)}


def index_count(conn) -> int:
    ensure_device_folder_schema(conn)
    return int(conn.execute("SELECT COUNT(*) c FROM device_folder_index").fetchone()["c"])


def search_serial(conn, serial: str, limit: int = 20) -> List[dict]:
    ensure_device_folder_schema(conn)
    q = normalize_serial(serial)
    if not q:
        return []
    rows = conn.execute(
        """SELECT * FROM device_folder_index
           WHERE serial=? OR serial LIKE ? OR serial_raw LIKE ?
           ORDER BY CASE WHEN serial=? THEN 0 ELSE 1 END, id DESC
           LIMIT ?""",
        (q, f"%{q}%", f"%{serial.strip()}%", q, limit),
    ).fetchall()
    out = []
    root = get_root_path(conn)
    for r in rows:
        d = dict(r)
        rel = d.get("relative_path") or ""
        full = d.get("full_path") or ""
        if root and rel:
            d["resolved_path"] = os.path.normpath(os.path.join(root, rel.replace("/", os.sep)))
        else:
            d["resolved_path"] = full
        out.append(d)
    return out


def open_folder_windows(path: str) -> dict:
    path = (path or "").strip()
    if not path:
        return {"ok": False, "error": "مسیر خالی است"}
    if not os.path.exists(path):
        return {"ok": False, "error": f"مسیر روی دیسک یافت نشد:\n{path}"}
    try:
        if os.name == "nt":
            if os.path.isdir(path):
                os.startfile(path)  # noqa: S606
            else:
                os.startfile(os.path.dirname(path))  # noqa: S606
        else:
            import subprocess
            subprocess.Popen(
                ["xdg-open", path if os.path.isdir(path) else os.path.dirname(path)]
            )
        return {"ok": True, "path": path}
    except Exception as e:
        return {"ok": False, "error": str(e)}
