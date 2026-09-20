from __future__ import annotations
from flask import Blueprint, jsonify, request, session, current_app
from core.chat_backend import (
    ensure_chat_state_schema, upsert_thread, mark_message_received,
    mark_read, archive, restore, list_state, toggle_reaction
)
from pathlib import Path

chat_api = Blueprint("chat_backend_api", __name__, url_prefix="/api/chat")

def _db_path():
    for key in ("DATABASE_PATH", "DB_PATH", "DATABASE"):
        value = current_app.config.get(key)
        if value:
            return value
    root = Path(current_app.root_path)
    candidates = [root/"sazgan.db", root/"data"/"sazgan.db"]
    for p in candidates:
        if p.exists():
            return str(p)
    # The application will create the runtime DB on first write in this path.
    return str(root/"data"/"sazgan.db")

def _login_required():
    from core.helpers import get_current_user
    if not get_current_user():
        return jsonify({"ok": False, "error": "auth"}), 401
    return None

def _user_id():
    return str(session.get("user_id") or session.get("user") or session.get("username") or "anonymous")

@chat_api.get("/state")
def state():
    denied = _login_required()
    if denied: return denied
    db=_db_path(); ensure_chat_state_schema(db)
    uid=_user_id()
    archived=request.args.get("archived","0")=="1"
    return jsonify({"ok":True,"items":list_state(db,uid,archived)})

@chat_api.post("/thread")
def thread():
    denied = _login_required()
    if denied: return denied
    body=request.get_json(silent=True) or {}
    tid=body.get("thread_id")
    if not tid: return jsonify({"ok":False,"error":"thread_id is required"}),400
    upsert_thread(_db_path(),_user_id(),tid)
    return jsonify({"ok":True})

@chat_api.post("/message-received")
def received():
    denied = _login_required()
    if denied: return denied
    body=request.get_json(silent=True) or {}
    tid=body.get("thread_id")
    if not tid: return jsonify({"ok":False,"error":"thread_id is required"}),400
    mark_message_received(_db_path(),_user_id(),tid)
    return jsonify({"ok":True})

@chat_api.post("/read")
def read():
    denied = _login_required()
    if denied: return denied
    body=request.get_json(silent=True) or {}
    tid=body.get("thread_id")
    if not tid: return jsonify({"ok":False,"error":"thread_id is required"}),400
    mark_read(_db_path(),_user_id(),tid)
    return jsonify({"ok":True})

@chat_api.post("/archive")
def archive_thread():
    denied = _login_required()
    if denied: return denied
    body=request.get_json(silent=True) or {}
    tid=body.get("thread_id")
    if not tid: return jsonify({"ok":False,"error":"thread_id is required"}),400
    archive(_db_path(),_user_id(),tid)
    return jsonify({"ok":True})

@chat_api.post("/restore")
def restore_thread():
    denied = _login_required()
    if denied: return denied
    body=request.get_json(silent=True) or {}
    tid=body.get("thread_id")
    if not tid: return jsonify({"ok":False,"error":"thread_id is required"}),400
    restore(_db_path(),_user_id(),tid)
    return jsonify({"ok":True})

@chat_api.post("/reaction")
def reaction():
    denied = _login_required()
    if denied: return denied
    body=request.get_json(silent=True) or {}
    required=("thread_id","message_id","emoji")
    if not all(body.get(k) for k in required):
        return jsonify({"ok":False,"error":"thread_id, message_id and emoji are required"}),400
    added=toggle_reaction(_db_path(),body["thread_id"],body["message_id"],_user_id(),str(body["emoji"]))
    return jsonify({"ok":True,"added":added})
