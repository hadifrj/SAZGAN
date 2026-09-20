# -*- coding: utf-8 -*-
"""
routes/system.py — اطلاعات سیستمی مشترک (version / health)
============================================================
این ماژول تنها API عمومی نسخه‌ی برنامه است. Web UI، Native Client،
Installer، Updater و هر مصرف‌کننده‌ی دیگری باید از همین یک نقطه
(`GET /api/version`) نسخه را بخوانند؛ نه از خواندن مستقیم فایل VERSION.

منبع واقعی داده همیشه core/version.py است.
"""
from __future__ import annotations
from flask import jsonify

from core.version import get_version


def register(app):
    @app.route('/api/version')
    def api_version():
        ver = get_version()
        return jsonify({
            'version': ver.get('version', ''),
            'version_label': ver.get('version_label', 'v0.0.0'),
            'version_label_full': ver.get('version_label_full', 'v0.0.0'),
            'release_jalali': ver.get('release_jalali', ''),
            'build_info': ver.get('build_info', ''),
        })

    @app.route('/api/health')
    def api_health():
        ver = get_version()
        return jsonify({'status': 'ok', 'version': ver.get('version', '')})
