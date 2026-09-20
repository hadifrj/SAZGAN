# -*- coding: utf-8 -*-
"""Track daily Excel import batches and prevent re-importing the same file."""

def upgrade(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            file_sha256 TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            customers_new INTEGER DEFAULT 0,
            customers_changed INTEGER DEFAULT 0,
            customers_unchanged INTEGER DEFAULT 0,
            services_new INTEGER DEFAULT 0,
            services_changed INTEGER DEFAULT 0,
            services_unchanged INTEGER DEFAULT 0,
            services_review INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'completed',
            backup_path TEXT
        )
    """)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_import_batch_hash "
        "ON import_batches(file_sha256)"
    )
