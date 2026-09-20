# -*- coding: utf-8 -*-
"""Store the date of the externally-issued final invoice."""

def upgrade(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(requests)").fetchall()}
    if "invoice_date" not in cols:
        conn.execute("ALTER TABLE requests ADD COLUMN invoice_date TEXT")
