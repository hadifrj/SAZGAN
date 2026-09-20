# -*- coding: utf-8 -*-
"""Performance indexes for high-traffic repair detail routes."""

def upgrade(conn):
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_request_stage_dates_request ON request_stage_dates(request_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_request_attachments_request ON request_attachments(request_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_request ON audit_log(entity_type, entity_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_users_full_name ON users(full_name)",
        "CREATE INDEX IF NOT EXISTS idx_devices_type_model ON devices(device_type, model)",
        "CREATE INDEX IF NOT EXISTS idx_request_parts_request_id ON request_parts(request_id, id)",
    ]
    for sql in indexes:
        conn.execute(sql)
