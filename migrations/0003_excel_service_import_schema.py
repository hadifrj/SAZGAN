# -*- coding: utf-8 -*-
"""Prepare stable customer/service fields for the Excel migration pipeline."""

def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def upgrade(conn):
    customer_cols = _columns(conn, "customers")
    if "external_code" not in customer_cols:
        conn.execute("ALTER TABLE customers ADD COLUMN external_code TEXT")

    request_cols = _columns(conn, "requests")
    if "external_reception_no" not in request_cols:
        conn.execute("ALTER TABLE requests ADD COLUMN external_reception_no TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS service_import_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            source_sheet TEXT NOT NULL,
            source_row INTEGER NOT NULL,
            external_customer_code TEXT,
            external_reception_no TEXT,
            customer_id INTEGER,
            request_id INTEGER,
            match_status TEXT NOT NULL DEFAULT 'unmatched',
            needs_review INTEGER NOT NULL DEFAULT 0,
            serial_original TEXT,
            serial_normalized TEXT,
            service_type_raw TEXT,
            raw_json TEXT NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_file, source_sheet, source_row)
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_customers_external_code ON customers(external_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_external_reception_no ON requests(external_reception_no)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_match_status ON service_import_records(match_status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_needs_review ON service_import_records(needs_review)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_customer_code ON service_import_records(external_customer_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_reception_no ON service_import_records(external_reception_no)")
