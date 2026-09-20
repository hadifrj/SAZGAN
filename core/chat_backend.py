"""
Sazgan Chat Backend V2.2
Persistent inbox/read/archive/reaction helpers for the chat UI.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _connect(db_path: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con

def ensure_chat_state_schema(db_path: str | Path) -> None:
    con = _connect(db_path)
    try:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS chat_thread_state (
            user_id TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            archived_at TEXT,
            last_read_at TEXT,
            unread_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, thread_id)
        );
        CREATE TABLE IF NOT EXISTS chat_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            emoji TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(thread_id, message_id, user_id, emoji)
        );
        CREATE INDEX IF NOT EXISTS idx_chat_state_user
            ON chat_thread_state(user_id, archived_at, updated_at);
        CREATE INDEX IF NOT EXISTS idx_chat_reactions_message
            ON chat_reactions(thread_id, message_id);
        """)
        con.commit()
    finally:
        con.close()

def upsert_thread(db_path: str | Path, user_id: str, thread_id: str) -> None:
    ensure_chat_state_schema(db_path)
    con = _connect(db_path)
    try:
        con.execute("""
        INSERT INTO chat_thread_state(user_id,thread_id,updated_at)
        VALUES(?,?,?)
        ON CONFLICT(user_id,thread_id) DO UPDATE SET updated_at=excluded.updated_at
        """, (str(user_id), str(thread_id), _now()))
        con.commit()
    finally:
        con.close()

def mark_message_received(db_path: str | Path, user_id: str, thread_id: str) -> None:
    ensure_chat_state_schema(db_path)
    con = _connect(db_path)
    try:
        con.execute("""
        INSERT INTO chat_thread_state(user_id,thread_id,unread_count,updated_at)
        VALUES(?,?,1,?)
        ON CONFLICT(user_id,thread_id) DO UPDATE SET
            unread_count=chat_thread_state.unread_count+1,
            updated_at=excluded.updated_at
        """, (str(user_id), str(thread_id), _now()))
        con.commit()
    finally:
        con.close()

def mark_read(db_path: str | Path, user_id: str, thread_id: str) -> None:
    ensure_chat_state_schema(db_path)
    con = _connect(db_path)
    try:
        con.execute("""
        INSERT INTO chat_thread_state(user_id,thread_id,unread_count,last_read_at,updated_at)
        VALUES(?,?,0,?,?)
        ON CONFLICT(user_id,thread_id) DO UPDATE SET
            unread_count=0,last_read_at=excluded.last_read_at,updated_at=excluded.updated_at
        """, (str(user_id), str(thread_id), _now(), _now()))
        con.commit()
    finally:
        con.close()

def archive(db_path: str | Path, user_id: str, thread_id: str) -> None:
    ensure_chat_state_schema(db_path)
    con = _connect(db_path)
    try:
        con.execute("""
        INSERT INTO chat_thread_state(user_id,thread_id,archived_at,updated_at)
        VALUES(?,?,?,?)
        ON CONFLICT(user_id,thread_id) DO UPDATE SET
            archived_at=excluded.archived_at,updated_at=excluded.updated_at
        """, (str(user_id), str(thread_id), _now(), _now()))
        con.commit()
    finally:
        con.close()

def restore(db_path: str | Path, user_id: str, thread_id: str) -> None:
    ensure_chat_state_schema(db_path)
    con = _connect(db_path)
    try:
        con.execute("""
        UPDATE chat_thread_state SET archived_at=NULL,updated_at=?
        WHERE user_id=? AND thread_id=?
        """, (_now(), str(user_id), str(thread_id)))
        con.commit()
    finally:
        con.close()

def list_state(db_path: str | Path, user_id: str, archived: bool=False) -> List[Dict[str, Any]]:
    ensure_chat_state_schema(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute("""
        SELECT thread_id, archived_at, last_read_at, unread_count, updated_at
        FROM chat_thread_state
        WHERE user_id=? AND (archived_at IS NULL) = ?
        ORDER BY updated_at DESC
        """, (str(user_id), 0 if archived else 1)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()

def toggle_reaction(db_path: str | Path, thread_id: str, message_id: str, user_id: str, emoji: str) -> bool:
    ensure_chat_state_schema(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute("""
        SELECT id FROM chat_reactions
        WHERE thread_id=? AND message_id=? AND user_id=? AND emoji=?
        """, (str(thread_id), str(message_id), str(user_id), emoji))
        if cur.fetchone():
            con.execute("DELETE FROM chat_reactions WHERE thread_id=? AND message_id=? AND user_id=? AND emoji=?",
                        (str(thread_id), str(message_id), str(user_id), emoji))
            con.commit()
            return False
        con.execute("""
        INSERT INTO chat_reactions(thread_id,message_id,user_id,emoji,created_at)
        VALUES(?,?,?,?,?)
        """, (str(thread_id), str(message_id), str(user_id), emoji, _now()))
        con.commit()
        return True
    finally:
        con.close()
