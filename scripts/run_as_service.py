# -*- coding: utf-8 -*-
"""ورود سرویس ویندوز — سازگان (بدون پنجره، بدون debug)."""
from __future__ import annotations

import os
import sys
import threading
import logging
from logging.handlers import RotatingFileHandler

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
sys.path.insert(0, BASE)

LOG_DIR = os.path.join(BASE, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def _setup_log():
    log = logging.getLogger("sazgan")
    log.setLevel(logging.INFO)
    if not log.handlers:
        h = RotatingFileHandler(
            os.path.join(LOG_DIR, "service.log"),
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(h)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        log.addHandler(sh)
    return log

def main():
    log = _setup_log()
    log.info("Sazgan service starting, cwd=%s", BASE)
    try:
        from app import app
        from core.db import init_db
        from core.backup import create_backup, _backup_scheduler
        init_db()
        try:
            create_backup("service-start")
        except Exception as e:
            log.warning("startup backup: %s", e)
        try:
            threading.Thread(target=_backup_scheduler, daemon=True).start()
        except Exception as e:
            log.warning("backup scheduler: %s", e)

        port = int(os.environ.get("SAZGAN_PORT", "5000"))
        host = os.environ.get("SAZGAN_HOST", "0.0.0.0")
        log.info("Listening on http://%s:%s", host, port)

        # waitress if available (پایدارتر)، وگرنه werkzeug
        try:
            from waitress import serve
            serve(app, host=host, port=port, threads=8)
        except ImportError:
            app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    except Exception:
        log.exception("Sazgan service crashed")
        raise

if __name__ == "__main__":
    main()
