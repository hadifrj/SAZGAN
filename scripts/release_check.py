# -*- coding: utf-8 -*-
"""
Sazgan Release Verification Tool
بررسی آمادگی پروژه قبل از انتشار نسخه نهایی
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

errors = []
warnings = []


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Invalid JSON {path.name}: {e}")
        return {}


# Required files
required = [
    "VERSION",
    "RELEASE.json",
    "BUILD_INFO.json",
    "CHANGELOG.md",
]

for item in required:
    if not (ROOT / item).exists():
        errors.append(f"Missing required file: {item}")

if errors:
    print("FAILED: required files check")
else:
    # ✅ اصلاح‌شده: قبلاً کل محتوای فایل VERSION (شامل خط تاریخ/بیلد در
    # نسخه‌های چندخطی) به‌عنوان نسخه در نظر گرفته می‌شد و باعث می‌شد این
    # بررسی همیشه با RELEASE.json/BUILD_INFO.json «ناهماهنگ» تشخیص داده
    # شود. حالا فقط خط اول (نسخه‌ی semantic) خوانده می‌شود — دقیقاً همان
    # چیزی که core/version.py هم برمی‌گرداند.
    version_lines = [
        ln.strip() for ln in (ROOT / "VERSION").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    version = version_lines[0].lstrip("vV") if version_lines else ""
    release = read_json(ROOT / "RELEASE.json")
    build = read_json(ROOT / "BUILD_INFO.json")

    print("Sazgan Release Check")
    print("-------------------")
    print("Version:", version)

    if release.get("version") != version:
        errors.append(
            f"VERSION ({version}) does not match RELEASE.json ({release.get('version')})"
        )

    if build.get("version") and build.get("version") != version:
        errors.append(
            f"VERSION ({version}) does not match BUILD_INFO.json ({build.get('version')})"
        )

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if version not in changelog:
        warnings.append("Current version was not found in CHANGELOG.md")

    if not release.get("last_changes"):
        warnings.append("No last_changes found in RELEASE.json")

    print("Checked:")
    print("✓ Version files")
    print("✓ Release metadata")
    print("✓ Build information")
    print("✓ Changelog")
    
if warnings:
    print("\nWarnings:")
    for w in warnings:
        print("-", w)

if errors:
    print("\nFAILED")
    for e in errors:
        print("-", e)
    sys.exit(1)

print("\nREADY: Project is ready for release")
