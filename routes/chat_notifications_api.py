from __future__ import annotations
from flask import Blueprint, jsonify, request, session, current_app
from pathlib import Path
import sqlite3, time

notifications_api=Blueprint("chat_notifications_api",__name__,url_prefix="/api/notifications")

def _db():
    for k in ("DATABASE_PATH","DB_PATH","DATABASE"):
        if current_app.config.get(k): return Path(current_app.config[k])
    root=Path(current_app.root_path)
    for p in (root/"sazgan.db",root/"data"/"sazgan.db"):
        if p.exists(): return p
    return root/"data"/"sazgan.db"

def _uid():
    return str(session.get("user_id") or session.get("username") or session.get("user") or "anonymous")

@notifications_api.get("/chat")
def chat_notifications():
    db=_db()
    if not db.exists(): return jsonify({"ok":True,"items":[],"server_time":time.time()})
    con=sqlite3.connect(str(db)); con.row_factory=sqlite3.Row
    try:
        # Only unread, non-archived thread states are surfaced.
        try:
            rows=con.execute("""
                SELECT thread_id, unread_count, updated_at
                FROM chat_thread_state
                WHERE user_id=? AND archived_at IS NULL AND unread_count>0
                ORDER BY updated_at DESC
                LIMIT 50
            """,(_uid(),)).fetchall()
        except sqlite3.OperationalError:
            rows=[]
        return jsonify({"ok":True,"items":[dict(r) for r in rows],"server_time":time.time()})
    finally:
        con.close()
