# -*- coding: utf-8 -*-
from __future__ import annotations
from flask import (
    request, session, redirect, render_template, jsonify, send_file, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from io import BytesIO
import os, re, sqlite3, base64, time
import jdatetime
try:
    import openpyxl
except ImportError:
    openpyxl = None

from core.constants import *
from core import helpers as H


from core.helpers import *  # noqa: F401,F403
from core.constants import *  # noqa: F401,F403

def register(app):
    """مسیرهای warehouse + انبار کنترلی."""
    @app.route('/warehouse')
    def warehouse_hub():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not user_has_access(current_user, 'warehouse'):
            return redirect('/')
        return render_template(
            'warehouse_hub.html',
            active_page='warehouse-hub',
            current_user=current_user,
        )

    # انبار کنترلی (داخلی/خارجی) — ادغام با دامنه انبار
    try:
        from core.control_warehouses import register_control_warehouse_routes, ensure_control_wh_schema
        try:
            conn = get_db()
            ensure_control_wh_schema(conn)
            conn.close()
        except Exception as e:
            print('[warehouse] schema:', e)
        register_control_warehouse_routes(app, get_db, get_current_user)
    except Exception as e:
        print('[warehouse] control routes:', e)



    # ---------- لیست قطعات (تنظیمات) ----------
