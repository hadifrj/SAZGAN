# -*- coding: utf-8 -*-
"""
core/version.py — تنها مرجع نسخه برنامه (Single Source of Truth)
==================================================================
هدف: هیچ بخشی از برنامه (Web UI/API، Native Client، Installer، Updater،
Release Builder) نباید مستقیماً فایل VERSION را بخواند یا نسخه را حدس
بزند. همه از get_version() همینجا استفاده می‌کنند.

فایل VERSION در ریشه پروژه منبع اصلی است و می‌تواند تا ۳ خط داشته باشد:
  خط ۱: نسخه semantic (مثلاً 1.0.9)  — الزامی
  خط ۲: تاریخ انتشار جلالی           — اختیاری
  خط ۳: اطلاعات build                 — اختیاری

استفاده:
    from core.version import get_version
    ver = get_version()
    ver['version']              # "1.0.9"
    ver['version_label']        # "v1.0.9"
    ver['version_label_full']   # "v1.0.9 (1405/06/07)"
"""
from __future__ import annotations

import os
import re
import time

_VERSION_FILE_NAME = 'VERSION'
_CACHE_TTL_SEC = 60
_cache = {'ts': 0.0, 'data': None}

_SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')

_DEFAULT = {
    'version': '0.0.0',
    'version_label': 'v0.0.0',
    'version_label_full': 'v0.0.0',
    'release_jalali': '',
    'build_info': '',
}


def _base_dir():
    from core.constants import BASE_DIR
    return BASE_DIR


def _read_version_file():
    out = dict(_DEFAULT)
    try:
        path = os.path.join(_base_dir(), _VERSION_FILE_NAME)
        if not os.path.isfile(path):
            return out
        lines = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith('#'):
                    lines.append(s)
        if lines:
            ver = lines[0].lstrip('vV').strip()
            out['version'] = ver
            out['version_label'] = 'v' + ver
            out['version_label_full'] = 'v' + ver
        if len(lines) >= 2:
            out['release_jalali'] = lines[1]
            out['version_label_full'] = f"v{out['version']} ({lines[1]})"
        if len(lines) >= 3:
            out['build_info'] = lines[2]
    except Exception:
        pass
    return out


def get_version(force_reload: bool = False) -> dict:
    """dict شامل version, version_label, version_label_full, release_jalali, build_info.

    نتیجه به مدت ۶۰ ثانیه کش می‌شود تا هر request مجبور به خواندن دوباره‌ی
    فایل نباشد (VERSION تقریباً هیچ‌وقت در طول اجرای برنامه تغییر نمی‌کند)."""
    now = time.time()
    if force_reload or not _cache['data'] or (now - _cache['ts']) > _CACHE_TTL_SEC:
        _cache['data'] = _read_version_file()
        _cache['ts'] = now
    return _cache['data']


def get_version_string() -> str:
    return get_version()['version']


def is_valid_semver(ver: str) -> bool:
    return bool(_SEMVER_RE.match((ver or '').strip()))
