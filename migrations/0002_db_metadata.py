# -*- coding: utf-8 -*-
"""Add an application-level database metadata table.

This is a real schema migration: it creates a small table used by future
releases to store database-level metadata without touching business tables.
"""

def upgrade(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS db_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
    ''')
    conn.execute(
        "INSERT OR IGNORE INTO db_metadata(key, value, updated_at) "
        "VALUES ('engine', 'sazgan-migration-engine', datetime('now'))"
    )
