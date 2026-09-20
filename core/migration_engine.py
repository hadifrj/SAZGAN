# -*- coding: utf-8 -*-
"""Sazgan SQLite migration engine.

The engine is deliberately separate from application startup schema creation.
It provides:
- monotonic schema versions
- transactional migrations
- automatic pre-migration backups
- migration history
- a filesystem lock
- dry-run support for CLI
- explicit rollback on migration failure
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime

from core.constants import BASE_DIR, BACKUP_DIR, DB_NAME

SCHEMA_VERSION = 18
MIGRATION_TABLE = "schema_migrations"
LOCK_FILE = os.path.join(BASE_DIR, ".migration.lock")


def db_path() -> str:
    return os.path.join(BASE_DIR, DB_NAME)


def migration_dir() -> str:
    return os.path.join(BASE_DIR, "migrations")


def ensure_migration_table(conn: sqlite3.Connection) -> None:
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
    # سازگاری با دیتابیس‌های تست/قدیمی که جدول را بدون ستون‌های کامل ساخته‌اند
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


def current_version(conn: sqlite3.Connection) -> int:
    ensure_migration_table(conn)
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
    ).fetchone()
    return int(row["version"] if hasattr(row, "keys") else row[0])


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _migration_files() -> list[tuple[int, str, str]]:
    root = migration_dir()
    if not os.path.isdir(root):
        return []

    result = []
    for filename in os.listdir(root):
        if not filename.endswith(".py") or not filename[:4].isdigit():
            continue
        try:
            version = int(filename[:4])
        except ValueError:
            continue
        path = os.path.join(root, filename)
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
        name = filename[5:-3] if filename[4] == "_" else filename[:-3]
        result.append((version, name, source))
    return sorted(result)


def pending_migrations(conn: sqlite3.Connection) -> list[tuple[int, str, str]]:
    current = current_version(conn)
    return [m for m in _migration_files() if m[0] > current]


def _load_migration(source: str, filename: str):
    namespace = {}
    code = compile(source, filename, "exec")
    exec(code, namespace, namespace)
    up = namespace.get("upgrade")
    if not callable(up):
        raise RuntimeError(f"Migration {filename} must define upgrade(conn)")
    return up


def create_backup(reason: str = "migration") -> str | None:
    source = db_path()
    if not os.path.exists(source):
        return None

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = os.path.join(BACKUP_DIR, "migration")
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(
        target_dir,
        f"sazgan_{reason}_{stamp}.db"
    )

    # SQLite WAL can contain recent committed data outside the main file.
    # Use sqlite backup API instead of shutil.copy for a consistent snapshot.
    src_conn = sqlite3.connect(source)
    try:
        dst_conn = sqlite3.connect(target)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    return target


@contextmanager
def migration_lock(timeout: int = 30):
    start = time.time()
    while True:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
            os.close(fd)
            break
        except FileExistsError:
            if time.time() - start >= timeout:
                raise TimeoutError("Another Sazgan migration is already running.")
            time.sleep(0.25)

    try:
        yield
    finally:
        try:
            os.remove(LOCK_FILE)
        except FileNotFoundError:
            pass


def _mark_baseline(conn: sqlite3.Connection) -> None:
    """Mark the schema shipped with the 2.10.10 codebase as baseline version 1.

    Existing installs already receive their compatibility ALTERs from init_db().
    This baseline prevents those legacy startup ALTERs from being replayed as
    migrations and gives future releases a stable starting point.
    """
    ensure_migration_table(conn)
    if current_version(conn) == 0:
        source = "2.10.10 shipped schema baseline"
        baseline_source = None
        for version, name, migration_source in _migration_files():
            if version == 1:
                baseline_source = migration_source
                break
        checksum = _checksum(baseline_source if baseline_source is not None else source)
        conn.execute(
            """
            INSERT INTO schema_migrations
            (version, name, checksum, applied_at, duration_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                1,
                "baseline_2_10_10",
                checksum,
                datetime.now().isoformat(timespec="seconds"),
                0,
            ),
        )
        conn.commit()


def migrate(conn: sqlite3.Connection, *, dry_run: bool = False,
            backup: bool = True) -> dict:
    ensure_migration_table(conn)

    # Version 1 is the current shipped schema baseline.
    if current_version(conn) == 0:
        if dry_run:
            return {
                "current": 0,
                "target": SCHEMA_VERSION,
                "pending": ["0001_baseline_2_10_10"],
                "changed": False,
                "dry_run": True,
            }
        _mark_baseline(conn)

    pending = pending_migrations(conn)
    from core.migrations import pending_registered_migrations, run_registered_schema_migrations
    pending_registry = pending_registered_migrations(conn)

    if dry_run:
        pending_names = [f"{v:04d}_{n}" for v, n, _source in pending]
        pending_names.extend(f"{v:04d}_{n}" for v, n in pending_registry)
        return {
            "current": current_version(conn),
            "target": SCHEMA_VERSION,
            "pending": pending_names,
            "changed": False,
            "dry_run": True,
        }

    if not pending and not pending_registry:
        return {
            "current": current_version(conn),
            "target": max(SCHEMA_VERSION, current_version(conn)),
            "pending": [],
            "changed": False,
            "dry_run": False,
        }

    backup_path = create_backup("before_migration") if backup else None
    applied = []

    with migration_lock():
        for version, name, source in pending:
            started = time.perf_counter()
            filename = os.path.join(migration_dir(), f"{version:04d}_{name}.py")
            upgrade = _load_migration(source, filename)

            try:
                conn.execute("BEGIN")
                upgrade(conn)
                duration = int((time.perf_counter() - started) * 1000)
                conn.execute(
                    """
                    INSERT INTO schema_migrations
                    (version, name, checksum, applied_at, duration_ms)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        version,
                        name,
                        _checksum(source),
                        datetime.now().isoformat(timespec="seconds"),
                        duration,
                    ),
                )
                conn.commit()
                applied.append({"version": version, "name": name})
            except Exception:
                conn.rollback()
                raise

        registry_result = run_registered_schema_migrations(conn)
        applied.extend(registry_result.get("applied", []))

    return {
        "current": current_version(conn),
        "target": max(SCHEMA_VERSION, current_version(conn)),
        "pending": applied,
        "changed": bool(applied),
        "backup": backup_path,
        "dry_run": False,
    }


def verify_history(conn: sqlite3.Connection) -> dict:
    ensure_migration_table(conn)
    rows = conn.execute(
        "SELECT version, name, checksum, applied_at, duration_ms "
        "FROM schema_migrations ORDER BY version"
    ).fetchall()

    problems = []
    for row in rows:
        version = row["version"] if hasattr(row, "keys") else row[0]
        name = row["name"] if hasattr(row, "keys") else row[1]
        checksum = row["checksum"] if hasattr(row, "keys") else row[2]
        expected = None
        for v, n, source in _migration_files():
            if v == version:
                expected = _checksum(source)
                break
        if expected is not None and expected != checksum:
            problems.append(
                f"Migration {version} ({name}) source checksum changed."
            )

    return {
        "version": current_version(conn),
        "migration_count": len(rows),
        "problems": problems,
        "healthy": not problems,
    }
