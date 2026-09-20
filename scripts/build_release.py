#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated SAZGAN release builder
================================
Tasks:
  1) Read/update VERSION (version + Jalali date)
  2) Check CHANGELOG for the current version
  3) Build a zip named sazgan-app-vX.Y.Z.zip
  4) Calculate SHA-256 / MD5
  5) Write the .sha256 file next to the zip

Examples:
  python scripts/build_release.py
  python scripts/build_release.py --bump patch
  python scripts/build_release.py --bump minor --notes "Add a new report"
  python scripts/build_release.py --set 2.5.0 --jalali 1405/06/01
  python scripts/build_release.py --out-dir dist
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"

# Directories/patterns excluded from the release package
EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "backups",
    "uploads",
    "dist",
    ".idea",
    ".vscode",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log", ".tmp", ".bak"}
EXCLUDE_NAMES = {".DS_Store", "Thumbs.db"}


# ---------- Approximate Jalali date (without jdatetime dependency) ----------
def _gregorian_to_jalali(gy: int, gm: int, gd: int):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def today_jalali_str() -> str:
    t = date.today()
    jy, jm, jd = _gregorian_to_jalali(t.year, t.month, t.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


# ---------- VERSION ----------
def read_version() -> tuple[str, str]:
    if not VERSION_FILE.is_file():
        return "0.0.0", today_jalali_str()
    lines = [
        ln.strip()
        for ln in VERSION_FILE.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    ver = lines[0].lstrip("vV").strip() if lines else "0.0.0"
    jalali = lines[1] if len(lines) >= 2 else today_jalali_str()
    return ver, jalali


def write_version(ver: str, jalali: str) -> None:
    ver = ver.lstrip("vV").strip()
    VERSION_FILE.write_text(f"{ver}\n{jalali}\n", encoding="utf-8")


# ---------- RELEASE.json / BUILD_INFO.json ----------
# ✅ اصلاح‌شده: قبلاً این build ver را فقط داخل VERSION می‌نوشت؛ RELEASE.json
# و BUILD_INFO.json دستی و جدا نگه داشته می‌شدند و می‌توانستند از VERSION
# عقب بمانند (دقیقاً همان ریسکی که گزارش اصلاحات هشدار داده بود). حالا هر
# release هر سه فایل را هم‌زمان و از یک منبع (VERSION) به‌روزرسانی می‌کند.
def sync_release_metadata(ver: str, jalali: str, build_stamp: str, notes: str | None) -> None:
    release_path = ROOT / "RELEASE.json"
    if release_path.is_file():
        try:
            release = json.loads(release_path.read_text(encoding="utf-8"))
        except Exception:
            release = {}
    else:
        release = {}
    release["version"] = ver
    release["release_date"] = jalali
    release.setdefault("project", "Sazgan Service Management System")
    release.setdefault("status", "stable")
    release.setdefault("versioning", "semantic-versioning")
    if notes:
        release["last_changes"] = [n.strip() for n in notes.split("|") if n.strip()]
    release_path.write_text(
        json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    build_path = ROOT / "BUILD_INFO.json"
    if build_path.is_file():
        try:
            build = json.loads(build_path.read_text(encoding="utf-8"))
        except Exception:
            build = {}
    else:
        build = {}
    build["project"] = build.get("project", "Sazgan")
    build["version"] = ver
    build["build"] = build_stamp
    build.setdefault("release_channel", "stable")
    build_path.write_text(
        json.dumps(build, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def bump_version(ver: str, part: str) -> str:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", ver.strip())
    if not m:
        raise SystemExit(f"Invalid version in VERSION: {ver!r} (must be X.Y.Z)")
    major, minor, patch = map(int, m.groups())
    part = part.lower()
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1
    else:
        raise SystemExit(f"Invalid bump type: {part}")
    return f"{major}.{minor}.{patch}"


# ---------- CHANGELOG ----------
def changelog_has_version(ver: str) -> bool:
    if not CHANGELOG_FILE.is_file():
        return False
    text = CHANGELOG_FILE.read_text(encoding="utf-8")
    return bool(re.search(rf"##\s*\[v?{re.escape(ver)}\]", text))


def prepend_changelog(ver: str, jalali: str, notes: str | None, bump_kind: str | None) -> None:
    """Add an empty section or note when no section exists for this version."""
    label = f"v{ver.lstrip('vV')}"
    if changelog_has_version(ver):
        return
    section = "Feature" if bump_kind == "minor" else ("Breaking Change" if bump_kind == "major" else "Bug Fix")
    items = []
    if notes:
        for line in notes.split("|"):
            line = line.strip()
            if line:
                items.append(f"- {line}")
    if not items:
        items = ["- (Add details here)"]
    block = (
        f"## [{label}] — {jalali}\n\n"
        f"### {section}\n"
        + "\n".join(items)
        + "\n\n---\n\n"
    )
    if CHANGELOG_FILE.is_file():
        old = CHANGELOG_FILE.read_text(encoding="utf-8")
        # Insert after the main title
        lines = old.splitlines(keepends=True)
        insert_at = 0
        for i, ln in enumerate(lines):
            if ln.startswith("# "):
                insert_at = i + 1
                # Skip blank lines after the title
                while insert_at < len(lines) and lines[insert_at].strip() == "":
                    insert_at += 1
                # Skip the introductory paragraph until ## or end of file
                while insert_at < len(lines) and not lines[insert_at].startswith("## "):
                    insert_at += 1
                break
        new_text = "".join(lines[:insert_at]) + block + "".join(lines[insert_at:])
        CHANGELOG_FILE.write_text(new_text, encoding="utf-8")
    else:
        CHANGELOG_FILE.write_text(
            "# SAZGAN version history\n\n" + block, encoding="utf-8"
        )


# ---------- ZIP ----------
def should_exclude(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    for part in rel_parts:
        if part in EXCLUDE_DIRS:
            return True
        if part.startswith('.') and part not in {'.env.example'}:
            return True
    if path.name in EXCLUDE_NAMES:
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    return False


def build_zip(out_path: Path) -> int:
    count = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            # prune excluded dirs in-place
            dirnames[:] = [
                d for d in dirnames
                if d not in EXCLUDE_DIRS and not d.startswith(".")
            ]
            for name in filenames:
                fp = Path(dirpath) / name
                if should_exclude(fp):
                    continue
                # Do not include the dist output inside the zip
                try:
                    if out_path.resolve() == fp.resolve():
                        continue
                except Exception:
                    pass
                arc = Path("sazgan-app") / fp.relative_to(ROOT)
                zf.write(fp, arcname=str(arc).replace("\\", "/"))
                count += 1
    return count


def file_hashes(path: Path) -> dict[str, str]:
    data = path.read_bytes()
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "md5": hashlib.md5(data).hexdigest(),
        "size": str(len(data)),
    }


def write_release_manifest(out_dir: Path, ver: str, jalali: str, zip_name: str, file_count: int, hashes: dict[str, str]) -> None:
    """Write a small manifest next to the release package (not inside the package)."""
    manifest = {
        "product": "SAZGAN",
        "version": ver,
        "release_date_jalali": jalali,
        "package": zip_name,
        "file_count": file_count,
        "sha256": hashes["sha256"],
        "size_bytes": int(hashes["size"]),
        "runtime_dirs_created_by_installer": [
            "backups",
            "backups/updates",
            "data",
            "config",
            "logs",
            "static/uploads",
        ],
        "persistent_files": [
            "sazgan.db",
            ".secret_key",
            "static/uploads",
            "backups",
            "config",
        ],
        "database_policy": "Never replace the live database from a release package; run versioned migrations instead.",
    }
    (out_dir / f"sazgan-app-v{ver}.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the SAZGAN release package")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], help="Automatically bump the version")
    parser.add_argument("--set", dest="set_ver", help="Set version manually as X.Y.Z")
    parser.add_argument("--jalali", help="Jalali release date YYYY/MM/DD (default: today)")
    parser.add_argument("--notes", help="Changelog notes; separate multiple items with |")
    parser.add_argument("--out-dir", default=str(ROOT / "dist"), help="Output directory")
    parser.add_argument("--skip-changelog", action="store_true", help="Do not modify CHANGELOG")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing files")
    args = parser.parse_args(argv)

    cur_ver, cur_jalali = read_version()
    ver = cur_ver
    bump_kind = None
    if args.set_ver:
        ver = args.set_ver.lstrip("vV")
    elif args.bump:
        bump_kind = args.bump
        ver = bump_version(cur_ver, args.bump)
    jalali = args.jalali or today_jalali_str()

    label = f"v{ver}"
    out_dir = Path(args.out_dir)
    zip_name = f"sazgan-app-{label}.zip"
    out_path = out_dir / zip_name

    print("=== SAZGAN build ===")
    print(f"Current version : v{cur_ver} ({cur_jalali})")
    print(f"Build version : {label} ({jalali})")
    print(f"Output     : {out_path}")

    if args.dry_run:
        print("(dry-run — no files were written)")
        return 0

    write_version(ver, jalali)
    build_stamp = datetime.now().strftime("%Y%m%d-%H%M")
    sync_release_metadata(ver, jalali, build_stamp, args.notes)
    print(f"VERSION updated → {ver} / {jalali}")
    print(f"RELEASE.json / BUILD_INFO.json synced → version {ver}, build {build_stamp}")

    if not args.skip_changelog:
        prepend_changelog(ver, jalali, args.notes, bump_kind)
        if changelog_has_version(ver):
            print("CHANGELOG ready for", label)
        else:
            print("WARNING: No CHANGELOG section found for this version")

    out_dir.mkdir(parents=True, exist_ok=True)
    n = build_zip(out_path)
    hashes = file_hashes(out_path)
    sha_path = out_path.with_suffix(out_path.suffix + ".sha256")
    sha_path.write_text(
        f"{hashes['sha256']}  {zip_name}\n",
        encoding="utf-8",
    )
    write_release_manifest(out_dir, ver, jalali, zip_name, n, hashes)

    print(f"Files in zip : {n}")
    print(f"Size           : {int(hashes['size']) // 1024} KB")
    print(f"SHA-256       : {hashes['sha256']}")
    print(f"MD5           : {hashes['md5']}")
    print(f"Hash file       : {sha_path.name}")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
