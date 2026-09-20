# -*- coding: utf-8 -*-
"""Central registry for application schema compatibility migrations.

The project already has a versioned file migration engine.  This module adds
one central registry for the older ``ensure_*_schema`` routines so startup
schema work is versioned and each registered routine is executed once per
installation.  The original ensure functions remain available as compatibility
APIs for request-time callers and tests.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime

logger = logging.getLogger("sazgan")

# Keep these versions above the existing file migrations (0001..0004).
# The migration_engine uses the same schema_migrations table.
REGISTRY_VERSION = 17


def _ensure_v5_improvements(conn):
    # Extracted startup portion of ensure_improvements_schema; dependent
    # feature/warehouse schemas are separate registry versions below.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS case_checklist ("
        "request_id INTEGER PRIMARY KEY,"
        "serial_ok INTEGER DEFAULT 0,"
        "parts_ok INTEGER DEFAULT 0,"
        "photo_ok INTEGER DEFAULT 0,"
        "match_ok INTEGER DEFAULT 0,"
        "updated_by TEXT,"
        "updated_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT)"
    )

def _ensure_v6_features(conn):
    from routes.features import ensure_features_schema
    ensure_features_schema(conn)


def _ensure_v7_control_warehouses(conn):
    from core.control_warehouses import ensure_control_wh_schema
    ensure_control_wh_schema(conn)


def _ensure_v8_geo(conn):
    # Geo schema is registered separately from distance schema so each version
    # has one responsibility and is recorded exactly once.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS geo_provinces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS geo_counties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            province_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(province_id, name),
            FOREIGN KEY (province_id) REFERENCES geo_provinces(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS geo_cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            province_id INTEGER NOT NULL,
            county_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(county_id, name),
            FOREIGN KEY (province_id) REFERENCES geo_provinces(id),
            FOREIGN KEY (county_id) REFERENCES geo_counties(id)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_geo_counties_prov ON geo_counties(province_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_geo_cities_county ON geo_cities(county_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_geo_cities_prov ON geo_cities(province_id)')
    for table in ('requests', 'customers', 'representatives'):
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}
        if 'county' not in cols:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN county TEXT')

def _ensure_v9_distance(conn):
    from core.distance import ensure_distance_schema
    ensure_distance_schema(conn)


def _ensure_v10_app_lists(conn):
    from core.app_lists import seed_all
    seed_all(conn)


def _ensure_v11_wages(conn):
    from core.wages import ensure_wage_schema, seed_default_wage_rates
    ensure_wage_schema(conn)
    seed_default_wage_rates(conn)


def _ensure_v12_history(conn):
    from core.history import ensure_history_schema
    ensure_history_schema(conn)


def _ensure_v13_push(conn):
    from core.push import ensure_push_schema
    ensure_push_schema(conn)


def _ensure_v14_reception(conn):
    from core.reception_numbers import ensure_reception_schema
    ensure_reception_schema(conn)


def _ensure_v15_customer_portal(conn):
    from core.customer_push import ensure_customer_push_schema
    from core.customer_notify import ensure_customer_notify_schema
    ensure_customer_push_schema(conn)
    ensure_customer_notify_schema(conn)


MIGRATIONS = {
    5: ("legacy_improvements_schema", _ensure_v5_improvements),
    6: ("legacy_features_schema", _ensure_v6_features),
    7: ("legacy_control_warehouses_schema", _ensure_v7_control_warehouses),
    8: ("legacy_geo_schema", _ensure_v8_geo),
    9: ("legacy_distance_schema", _ensure_v9_distance),
    10: ("legacy_app_lists_schema", _ensure_v10_app_lists),
    11: ("legacy_wages_schema", _ensure_v11_wages),
    12: ("legacy_history_schema", _ensure_v12_history),
    13: ("legacy_push_schema", _ensure_v13_push),
    14: ("legacy_reception_schema", _ensure_v14_reception),
    15: ("legacy_customer_portal_schema", _ensure_v15_customer_portal),
}


def _ensure_table(conn):
    """Create the shared migration history table if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(schema_migrations)").fetchall()}
        if "checksum" not in cols:
            conn.execute("ALTER TABLE schema_migrations ADD COLUMN checksum TEXT NOT NULL DEFAULT ''")
        if "applied_at" not in cols:
            conn.execute("ALTER TABLE schema_migrations ADD COLUMN applied_at TEXT NOT NULL DEFAULT ''")
        if "duration_ms" not in cols:
            conn.execute("ALTER TABLE schema_migrations ADD COLUMN duration_ms INTEGER NOT NULL DEFAULT 0")
        if "name" not in cols:
            conn.execute("ALTER TABLE schema_migrations ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass
    conn.commit()


def _current_version(conn) -> int:
    _ensure_table(conn)
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
    ).fetchone()
    return int(row["version"] if hasattr(row, "keys") else row[0])


def _checksum(version: int, name: str) -> str:
    source = f"sazgan-registry:{version}:{name}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()



def _ensure_v16_workflow_integrity(conn):
    """Integrity constraints for canonical repair workflow and request parts."""
    from core.workflow import INTERNAL_TRANSITIONS, EXTERNAL_TRANSITIONS

    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_status_transitions (
            service_type TEXT NOT NULL,
            request_category TEXT NOT NULL,
            from_status TEXT NOT NULL,
            to_status TEXT NOT NULL,
            PRIMARY KEY(service_type, request_category, from_status, to_status)
        )
    """)

    rows = []
    for source, targets in INTERNAL_TRANSITIONS.items():
        for target in targets:
            rows.append(("کارخانه", "تعمیر", source, target))
    for source, targets in EXTERNAL_TRANSITIONS.items():
        for target in targets:
            rows.append(("در محل", "تعمیر", source, target))
    # بازگشایی فقط از وضعیت بسته به نقطه شروع همان Workflow؛ مجوز نقش در service layer اعمال می‌شود.
    rows.extend([
        ("کارخانه", "تعمیر", "پیش‌فاکتور رد شد — ارسال به مشتری", "پذیرش دستگاه انجام شد"),
        ("کارخانه", "تعمیر", "پایان تعمیرات", "پذیرش دستگاه انجام شد"),
        ("در محل", "تعمیر", "پیش‌فاکتور رد شد — درخواست لغو شد", "پذیرش انجام شد"),
        ("در محل", "تعمیر", "پایان تعمیرات", "پذیرش انجام شد"),
    ])
    conn.executemany(
        "INSERT OR IGNORE INTO workflow_status_transitions(service_type,request_category,from_status,to_status) VALUES(?,?,?,?)",
        rows,
    )

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_repair_status_transition_guard
        BEFORE UPDATE OF status ON requests
        FOR EACH ROW
        WHEN OLD.status IS NOT NEW.status
         AND OLD.request_category = 'تعمیر'
         AND NEW.request_category = 'تعمیر'
         AND OLD.service_type = NEW.service_type
         AND NEW.service_type IN ('کارخانه','در محل')
         AND NOT EXISTS (
             SELECT 1 FROM workflow_status_transitions w
             WHERE w.service_type=NEW.service_type
               AND w.request_category=NEW.request_category
               AND w.from_status=OLD.status
               AND w.to_status=NEW.status
         )
        BEGIN
            SELECT RAISE(ABORT, 'workflow.invalid_status_transition');
        END;
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_request_parts_serial_good ON request_parts(serial_good) WHERE serial_good IS NOT NULL AND TRIM(serial_good) <> '' AND IFNULL(is_void,0)=0")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_request_parts_serial_defective ON request_parts(serial_defective) WHERE serial_defective IS NOT NULL AND TRIM(serial_defective) <> '' AND IFNULL(is_void,0)=0")
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_request_parts_qty_positive_insert
        BEFORE INSERT ON request_parts
        FOR EACH ROW WHEN NEW.quantity IS NULL OR NEW.quantity <= 0
        BEGIN SELECT RAISE(ABORT, 'request_parts.quantity_must_be_positive'); END;
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_request_parts_qty_positive_update
        BEFORE UPDATE OF quantity ON request_parts
        FOR EACH ROW WHEN NEW.quantity IS NULL OR NEW.quantity <= 0
        BEGIN SELECT RAISE(ABORT, 'request_parts.quantity_must_be_positive'); END;
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_request_parts_serial_insert
        BEFORE INSERT ON request_parts
        FOR EACH ROW WHEN IFNULL(NEW.is_void,0)=0
        BEGIN
            SELECT RAISE(ABORT, 'request_parts.serial_duplicate')
            WHERE EXISTS(
                SELECT 1 FROM request_parts p
                WHERE IFNULL(p.is_void,0)=0 AND (
                    (NULLIF(TRIM(NEW.serial_good),'') IS NOT NULL AND NEW.serial_good IN (p.serial_good,p.serial_healthy,p.serial_defective,p.serial_faulty))
                    OR (NULLIF(TRIM(NEW.serial_healthy),'') IS NOT NULL AND NEW.serial_healthy IN (p.serial_good,p.serial_healthy,p.serial_defective,p.serial_faulty))
                    OR (NULLIF(TRIM(NEW.serial_defective),'') IS NOT NULL AND NEW.serial_defective IN (p.serial_good,p.serial_healthy,p.serial_defective,p.serial_faulty))
                    OR (NULLIF(TRIM(NEW.serial_faulty),'') IS NOT NULL AND NEW.serial_faulty IN (p.serial_good,p.serial_healthy,p.serial_defective,p.serial_faulty))
                )
            );
        END;
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_request_parts_serial_update
        BEFORE UPDATE OF serial_good, serial_healthy, serial_defective, serial_faulty, is_void ON request_parts
        FOR EACH ROW WHEN IFNULL(NEW.is_void,0)=0
        BEGIN
            SELECT RAISE(ABORT, 'request_parts.serial_duplicate')
            WHERE EXISTS(
                SELECT 1 FROM request_parts p
                WHERE IFNULL(p.is_void,0)=0 AND p.id<>OLD.id AND (
                    (NULLIF(TRIM(NEW.serial_good),'') IS NOT NULL AND NEW.serial_good IN (p.serial_good,p.serial_healthy,p.serial_defective,p.serial_faulty))
                    OR (NULLIF(TRIM(NEW.serial_healthy),'') IS NOT NULL AND NEW.serial_healthy IN (p.serial_good,p.serial_healthy,p.serial_defective,p.serial_faulty))
                    OR (NULLIF(TRIM(NEW.serial_defective),'') IS NOT NULL AND NEW.serial_defective IN (p.serial_good,p.serial_healthy,p.serial_defective,p.serial_faulty))
                    OR (NULLIF(TRIM(NEW.serial_faulty),'') IS NOT NULL AND NEW.serial_faulty IN (p.serial_good,p.serial_healthy,p.serial_defective,p.serial_faulty))
                )
            );
        END;
    """)

    # assigned_technician_id فقط باید به تکنسین فعال و متناسب با service_type اشاره کند.
    assignment_predicate = """
        NOT EXISTS(
            SELECT 1 FROM users u
            WHERE u.id=NEW.assigned_technician_id AND IFNULL(u.is_active,1)=1
              AND ((NEW.request_category='تعمیر' AND NEW.service_type='کارخانه' AND u.role='تکنسین کارخانه')
                OR (NEW.request_category='تعمیر' AND NEW.service_type='در محل' AND u.role='تکنسین استانی'
                    AND (COALESCE(NEW.province,'')='' OR COALESCE(u.province,'')=COALESCE(NEW.province,'')))
                OR (NEW.request_category<>'تعمیر' AND u.role='تکنسین استانی'
                    AND (COALESCE(NEW.province,'')='' OR COALESCE(u.province,'')=COALESCE(NEW.province,''))))
        )
    """
    conn.execute(f"""
        CREATE TRIGGER IF NOT EXISTS trg_request_assignment_integrity_insert
        BEFORE INSERT ON requests FOR EACH ROW
        WHEN NEW.assigned_technician_id IS NOT NULL AND ({assignment_predicate})
        BEGIN SELECT RAISE(ABORT, 'requests.invalid_technician_assignment'); END;
    """)
    conn.execute(f"""
        CREATE TRIGGER IF NOT EXISTS trg_request_assignment_integrity_update
        BEFORE UPDATE OF assigned_technician_id, service_type, request_category, province ON requests FOR EACH ROW
        WHEN NEW.assigned_technician_id IS NOT NULL AND ({assignment_predicate})
        BEGIN SELECT RAISE(ABORT, 'requests.invalid_technician_assignment'); END;
    """)


MIGRATIONS[16] = ("workflow_integrity", _ensure_v16_workflow_integrity)


def _ensure_v17_service_workflow_integrity(conn):
    """DB-level guard for installation/inspection state transitions.

    This blocks direct SQL/status manipulation and makes the domain rule hold
    even if a future route forgets to call core.workflow.transition_request.
    """
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_installation_status_transition
        BEFORE UPDATE OF status ON requests
        FOR EACH ROW
        WHEN NEW.request_category='نصب و آموزش'
         AND NEW.request_subtype='درخواست نصب'
         AND NEW.status <> OLD.status
         AND NOT (
             (OLD.status='درخواست ثبت شد' AND NEW.status='در انتظار انجام نصب')
             OR (OLD.status='در انتظار انجام نصب' AND NEW.status='نصب انجام شد')
             OR (OLD.status='نصب انجام شد' AND NEW.status='بسته شد')
         )
        BEGIN SELECT RAISE(ABORT, 'workflow.invalid_installation_status_transition'); END;
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_inspection_status_transition
        BEFORE UPDATE OF status ON requests
        FOR EACH ROW
        WHEN NEW.request_category='بررسی و بازدید'
         AND NEW.request_subtype='درخواست بازدید'
         AND NEW.status <> OLD.status
         AND NOT (
             (OLD.status='در انتظار ارسال پیش‌فاکتور است' AND NEW.status='در انتظار دریافت تاییدیه پیش‌فاکتور است')
             OR (OLD.status='در انتظار دریافت تاییدیه پیش‌فاکتور است' AND NEW.status='در انتظار انجام بازدید')
             OR (OLD.status='در انتظار انجام بازدید' AND NEW.status IN ('در انتظار گزارش بازدید','بازدید انجام شد'))
             OR (OLD.status='در انتظار گزارش بازدید' AND NEW.status='بازدید انجام شد')
             OR (OLD.status='بازدید انجام شد' AND NEW.status='بسته شد')
         )
        BEGIN SELECT RAISE(ABORT, 'workflow.invalid_inspection_status_transition'); END;
    """)


MIGRATIONS[17] = ("service_workflow_integrity", _ensure_v17_service_workflow_integrity)


def pending_registered_migrations(conn) -> list[tuple[int, str]]:
    """Return registry migrations that have not yet been recorded."""
    current = _current_version(conn)
    return [
        (version, name)
        for version, (name, _upgrade) in sorted(MIGRATIONS.items())
        if version > current
    ]


def run_registered_schema_migrations(conn) -> dict:
    """Run pending compatibility-schema migrations in version order."""
    _ensure_table(conn)
    current = _current_version(conn)
    applied = []

    for version in sorted(MIGRATIONS):
        if version <= current:
            continue
        name, upgrade = MIGRATIONS[version]
        started = __import__("time").perf_counter()
        logger.info("schema migration start version=%s name=%s", version, name)
        try:
            upgrade(conn)
            duration_ms = int((__import__("time").perf_counter() - started) * 1000)
            conn.execute(
                """
                INSERT INTO schema_migrations
                (version, name, checksum, applied_at, duration_ms)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    version,
                    name,
                    _checksum(version, name),
                    datetime.now().isoformat(timespec="seconds"),
                    duration_ms,
                ),
            )
            conn.commit()
            applied.append({"version": version, "name": name})
            current = version
            logger.info("schema migration complete version=%s name=%s", version, name)
        except Exception:
            conn.rollback()
            logger.exception("Schema migration failed version=%s name=%s", version, name)
            raise

    return {
        "current": current,
        "target": REGISTRY_VERSION,
        "applied": applied,
        "changed": bool(applied),
    }
