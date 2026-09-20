"""
Sazgan V2.3 Data Safety
Backup/restore/integrity/audit helpers.
"""
from __future__ import annotations
import hashlib, json, shutil, sqlite3, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

def now():
    return datetime.now(timezone.utc).isoformat()

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()

def integrity_check(db_path: str|Path) -> Dict[str,Any]:
    p=Path(db_path)
    if not p.exists():
        return {"ok":False,"exists":False,"error":"database_not_found"}
    con=sqlite3.connect(str(p))
    try:
        result=con.execute("PRAGMA integrity_check").fetchone()[0]
        return {"ok":result=="ok","exists":True,"integrity":result,"size":p.stat().st_size,"sha256":sha256(p)}
    finally: con.close()

def backup_database(db_path: str|Path, backup_dir: str|Path) -> Dict[str,Any]:
    src=Path(db_path)
    if not src.exists(): raise FileNotFoundError(src)
    destdir=Path(backup_dir); destdir.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    dest=destdir/f"sazgan-{stamp}.db"
    shutil.copy2(src,dest)
    meta={"created_at":now(),"source":str(src),"file":str(dest),"sha256":sha256(dest),"size":dest.stat().st_size}
    (dest.with_suffix(".json")).write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    return meta

def restore_database(backup_path: str|Path, db_path: str|Path, make_safety_backup: bool=True) -> Dict[str,Any]:
    src=Path(backup_path); dest=Path(db_path)
    if not src.exists(): raise FileNotFoundError(src)
    check=integrity_check(src)
    if not check.get("ok"): raise ValueError("backup_integrity_failed")
    safety=None
    if make_safety_backup and dest.exists():
        safety=backup_database(dest,dest.parent/"pre_restore")
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dest)
    return {"ok":True,"restored_from":str(src),"database":str(dest),"pre_restore_backup":safety,"sha256":sha256(dest)}

def ensure_audit_schema(db_path: str|Path):
    con=sqlite3.connect(str(db_path))
    try:
        con.execute("""CREATE TABLE IF NOT EXISTS data_safety_audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT NOT NULL,
            entity TEXT,
            entity_id TEXT,
            details TEXT,
            created_at TEXT NOT NULL
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_data_safety_audit_created ON data_safety_audit_log(created_at)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_data_safety_audit_user ON data_safety_audit_log(user_id)")
        con.commit()
    finally: con.close()

def audit(db_path: str|Path, user_id: str|None, action: str, entity: str|None=None,
          entity_id: str|None=None, details: Dict[str,Any]|None=None):
    ensure_audit_schema(db_path)
    con=sqlite3.connect(str(db_path))
    try:
        con.execute("INSERT INTO data_safety_audit_log(user_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?)",
                    (user_id,action,entity,entity_id,json.dumps(details or {},ensure_ascii=False),now()))
        con.commit()
    finally: con.close()

def list_audit(db_path: str|Path, limit:int=200)->List[Dict[str,Any]]:
    ensure_audit_schema(db_path)
    con=sqlite3.connect(str(db_path)); con.row_factory=sqlite3.Row
    try:
        return [dict(r) for r in con.execute("SELECT * FROM data_safety_audit_log ORDER BY id DESC LIMIT ?",(max(1,min(limit,1000)),)).fetchall()]
    finally: con.close()
