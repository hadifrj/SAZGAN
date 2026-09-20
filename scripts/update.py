# -*- coding: utf-8 -*-
"""SAZGAN safe in-place updater.

Usage:
    python scripts/update.py --package path\\to\\sazgan-app-vX.Y.Z.zip
    python scripts/update.py --status

The updater preserves the live database, secret key, uploads and backups.
Before an update it creates both a SQLite backup and an application-file
backup. Database migrations are then executed from the newly installed code.
If migration fails, the database and application files are restored.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
DB_FILE = ROOT / "sazgan.db"
BACKUP_ROOT = ROOT / "backups" / "updates"
RUNTIME_DIRS = [
    ROOT / "backups",
    ROOT / "backups" / "updates",
    ROOT / "data",
    ROOT / "config",
    ROOT / "logs",
    ROOT / "static" / "uploads",
]
PRESERVE = {
    "sazgan.db", ".secret_key", "backups", "static/uploads", "dist",
    "build", ".venv", "venv", "env", "logs"
}


def ensure_runtime_dirs() -> None:
    """Create mutable runtime directories without touching existing data."""
    for directory in RUNTIME_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


def version_tuple(value: str):
    parts = value.strip().lstrip("vV").split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid semantic version: {value}")
    return tuple(map(int, parts))


def read_version(path: Path = VERSION_FILE) -> str:
    if not path.exists():
        return "0.0.0"
    first = path.read_text(encoding="utf-8").splitlines()[0].strip()
    return first.lstrip("vV")


def find_package_root(extract: Path) -> Path:
    direct = extract / "sazgan-app"
    if (direct / "VERSION").exists():
        return direct
    if (extract / "VERSION").exists():
        return extract
    candidates = [p for p in extract.iterdir() if p.is_dir() and (p / "VERSION").exists()]
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError("The update ZIP does not contain a valid SAZGAN application root.")


def sqlite_backup(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def copy_tree_snapshot(root: Path, target: Path):
    """Snapshot application files while excluding mutable data."""
    ignore = shutil.ignore_patterns(
        "sazgan.db", ".secret_key", "backups", "uploads", "dist", "build",
        ".venv", "venv", "env", "__pycache__", "*.pyc", "*.log"
    )
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(root, target, ignore=ignore)


def restore_tree_snapshot(snapshot: Path, root: Path):
    if not snapshot.exists():
        return
    ignored = {"sazgan.db", ".secret_key", "backups", "static/uploads", "dist", "build", ".venv", "venv", "env", "logs"}
    # Remove files/dirs that belong to the application snapshot area.
    for item in list(root.iterdir()):
        rel = item.relative_to(root).as_posix()
        if rel in ignored or any(rel.startswith(x.rstrip("/") + "/") for x in ignored if x.endswith("/")):
            continue
        if item.name == "__pycache__":
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            try:
                item.unlink()
            except OSError:
                pass
    for item in snapshot.iterdir():
        dest = root / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


def copy_new_app(source: Path, root: Path):
    skip = {"sazgan.db", ".secret_key", "backups", "dist", "build", ".venv", "venv", "env", "logs"}
    for src in source.iterdir():
        if src.name in skip:
            continue
        dest = root / src.name
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def install_dependencies():
    req = ROOT / "requirements.txt"
    if not req.exists():
        return subprocess.CompletedProcess([], 0, "requirements.txt not found; skipped\n", "")
    wheel_dirs = [ROOT / "offline_packages", ROOT / "offline" / "packages"]
    wheel_dir = next((p for p in wheel_dirs if p.is_dir() and any(p.glob("*.whl"))), None)
    if wheel_dir:
        cmd = [sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(wheel_dir), "-r", str(req)]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(req)]
    return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)


def run_migrations():
    cmd = [sys.executable, str(ROOT / "scripts" / "migrate_db.py")]
    return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)


def health_check():
    script = ROOT / "scripts" / "health_check.py"
    if not script.exists():
        return True, "health_check.py not found; skipped"
    proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), text=True, capture_output=True)
    return proc.returncode == 0, proc.stdout + proc.stderr


def status():
    current = read_version()
    print(json.dumps({"app_version": current, "database": str(DB_FILE), "root": str(ROOT)}, ensure_ascii=False, indent=2))


def update(package: Path, force: bool = False):
    package = package.resolve()
    if not package.exists():
        raise FileNotFoundError(package)
    old_version = read_version()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = Path(tempfile.mkdtemp(prefix="sazgan_update_"))
    ensure_runtime_dirs()
    backup_dir = BACKUP_ROOT / stamp
    snapshot = backup_dir / "app_files"
    db_backup = backup_dir / "sazgan.db"
    backup_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(package) as zf:
            bad = zf.testzip()
            if bad:
                raise RuntimeError(f"Corrupt ZIP entry: {bad}")
            zf.extractall(work)
        source = find_package_root(work)
        new_version = read_version(source / "VERSION")
        if not force and version_tuple(new_version) <= version_tuple(old_version):
            raise RuntimeError(f"Update {new_version} is not newer than installed {old_version}. Use --force to override.")

        if DB_FILE.exists():
            sqlite_backup(DB_FILE, db_backup)
        copy_tree_snapshot(ROOT, snapshot)

        copy_new_app(source, ROOT)
        ensure_runtime_dirs()
        deps = install_dependencies()
        if deps.returncode != 0:
            raise RuntimeError("Dependency installation failed:\n" + deps.stdout + "\n" + deps.stderr)
        migration = run_migrations()
        if migration.returncode != 0:
            raise RuntimeError("Database migration failed:\n" + migration.stdout + "\n" + migration.stderr)

        ok, health = health_check()
        if not ok:
            raise RuntimeError("Health check failed:\n" + health)

        (backup_dir / "update.json").write_text(json.dumps({
            "from": old_version,
            "to": new_version,
            "timestamp": stamp,
            "package": str(package),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] SAZGAN updated: {old_version} -> {new_version}")
        print(f"[OK] Database backup: {db_backup if DB_FILE.exists() else 'not needed'}")
        print(f"[OK] Update backup: {backup_dir}")
        print("[OK] Dependencies installed/verified")
        print(migration.stdout)
    except Exception:
        restore_tree_snapshot(snapshot, ROOT)
        if db_backup.exists():
            try:
                tmp_db = ROOT / "sazgan.db.restore.tmp"
                shutil.copy2(db_backup, tmp_db)
                os.replace(tmp_db, DB_FILE)
            except Exception as exc:
                print(f"[CRITICAL] Database restore failed: {exc}", file=sys.stderr)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="SAZGAN Installer / Updater")
    ap.add_argument("--package", help="Path to SAZGAN update/source ZIP")
    ap.add_argument("--force", action="store_true", help="Allow same/older version")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    try:
        if args.status:
            status(); return 0
        if not args.package:
            ap.error("--package is required unless --status is used")
        update(Path(args.package), force=args.force)
        return 0
    except Exception as exc:
        print(f"[ERROR] Update failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
