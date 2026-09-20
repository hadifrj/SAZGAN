# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from flask import (
    request, session, redirect, render_template, jsonify, send_file, current_app
)

logger = logging.getLogger("sazgan")
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



def _ensure_user_active_col(conn):
    cols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
    if 'is_active' not in cols:
        try:
            conn.execute('ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1')
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        try:
            conn.execute('UPDATE users SET is_active=1 WHERE is_active IS NULL')
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        try:
            conn.commit()
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")

