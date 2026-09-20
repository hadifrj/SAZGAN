from __future__ import annotations
from flask import Blueprint, jsonify, request, session, current_app
from pathlib import Path
from core.data_safety import integrity_check, backup_database, restore_database, list_audit, audit
from core.helpers import get_current_user
from core.access import is_system_admin

safety_api=Blueprint("data_safety_api",__name__,url_prefix="/api/data-safety")

def _db():
    for k in ("DATABASE_PATH","DB_PATH","DATABASE"):
        if current_app.config.get(k): return Path(current_app.config[k])
    root=Path(current_app.root_path)
    for p in (root/"sazgan.db",root/"data"/"sazgan.db"):
        if p.exists(): return p
    return root/"data"/"sazgan.db"

def _uid(): return str(session.get("user_id") or session.get("username") or session.get("user") or "anonymous")

def _admin_required():
    user = get_current_user()
    if not user or not is_system_admin(user):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    return None

def _backup_dir():
    # Restore is intentionally limited to the application backup directory.
    root = Path(current_app.root_path).resolve()
    return (root / "backups").resolve()


@safety_api.get("/integrity")
def integrity():
    denied = _admin_required()
    if denied: return denied
    return jsonify(integrity_check(_db()))

@safety_api.post("/backup")
def backup():
    denied = _admin_required()
    if denied: return denied
    db=_db()
    if not db.exists(): return jsonify({"ok":False,"error":"database_not_found"}),404
    meta=backup_database(db,db.parent/"backups")
    audit(db,_uid(),"backup","database",None,{"file":meta["file"]})
    return jsonify({"ok":True,"backup":meta})

@safety_api.post("/restore")
def restore():
    denied = _admin_required()
    if denied: return denied
    body=request.get_json(silent=True) or {}
    path=body.get("backup_path")
    if not path: return jsonify({"ok":False,"error":"backup_path is required"}),400
    try:
        requested = Path(path).resolve()
        backup_dir = _backup_dir()
        requested.relative_to(backup_dir)
    except (OSError, ValueError):
        return jsonify({"ok":False,"error":"invalid_backup_path"}),400
    if requested.suffix.lower() != '.db':
        return jsonify({"ok":False,"error":"invalid_backup_file"}),400
    result=restore_database(requested,_db(),True)
    audit(_db(),_uid(),"restore","database",None,{"backup_path":path})
    return jsonify(result)

@safety_api.get("/audit")
def audit_list():
    denied = _admin_required()
    if denied: return denied
    return jsonify({"ok":True,"items":list_audit(_db(),request.args.get("limit",200,type=int))})
