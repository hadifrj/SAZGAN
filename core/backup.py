# -*- coding: utf-8 -*-
"""پشتیبان‌گیری دیتابیس و فایل‌ها."""
from __future__ import annotations

import logging

import os
import time
import shutil
import sqlite3

from core.constants import BASE_DIR, BACKUP_DIR, DB_NAME, UPLOAD_FOLDER

logger = logging.getLogger("sazgan")

def create_backup(reason='manual'):
    """پشتیبان بهینه: دیتابیس (WAL-safe) + پیوست‌ها + متادیتا + zip + پاکسازی هوشمند."""
    import hashlib
    import zipfile as zf

    ts = time.strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(BACKUP_DIR, f'backup_{ts}_{reason}')
    os.makedirs(dest, exist_ok=True)
    db_path = os.path.join(BASE_DIR, DB_NAME)

    # --- دیتابیس با checkpoint برای WAL ---
    db_copied = False
    try:
        if os.path.isfile(db_path):
            try:
                c = sqlite3.connect(db_path, timeout=30)
                c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                c.close()
            except Exception as e:
                logger.exception("Silent exception in core/backup.py")
            shutil.copy2(db_path, os.path.join(dest, DB_NAME))
            # کپی sidecarهای WAL/SHM اگر هنوز باشند
            for suf in ('-wal', '-shm'):
                side = db_path + suf
                if os.path.isfile(side):
                    try:
                        shutil.copy2(side, os.path.join(dest, DB_NAME + suf))
                    except Exception as e:
                        logger.exception("Silent exception in core/backup.py")
            db_copied = True
    except Exception as e:
        print('[backup] db:', e)

    # --- پیوست‌ها ---
    uploads_src = os.path.join(BASE_DIR, 'static', 'uploads')
    files_n = 0
    if os.path.isdir(uploads_src):
        try:
            for root, dirs, files in os.walk(uploads_src):
                # رد کردن کش/موقت
                dirs[:] = [d for d in dirs if d not in ('__pycache__', '.tmp')]
                rel = os.path.relpath(root, uploads_src)
                out_root = os.path.join(dest, 'uploads', rel) if rel != '.' else os.path.join(dest, 'uploads')
                os.makedirs(out_root, exist_ok=True)
                for f in files:
                    if f.startswith('.') or f.endswith('.tmp'):
                        continue
                    src_f = os.path.join(root, f)
                    try:
                        shutil.copy2(src_f, os.path.join(out_root, f))
                        files_n += 1
                    except Exception as e:
                        logger.exception("Silent exception in core/backup.py")
        except Exception as e:
            print('[backup] uploads:', e)

    # --- checksum دیتابیس ---
    checksum = ''
    dest_db = os.path.join(dest, DB_NAME)
    if os.path.isfile(dest_db):
        h = hashlib.sha256()
        with open(dest_db, 'rb') as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        checksum = h.hexdigest()

    # --- manifest ---
    try:
        with open(os.path.join(dest, 'manifest.txt'), 'w', encoding='utf-8') as mf:
            mf.write('sazgan-backup\n')
            mf.write('time=%s\n' % ts)
            mf.write('reason=%s\n' % reason)
            mf.write('db=%s\n' % ('yes' if db_copied else 'no'))
            mf.write('uploads_files=%s\n' % files_n)
            mf.write('sha256_db=%s\n' % checksum)
    except Exception as e:
        logger.exception("Silent exception in core/backup.py")
    # --- zip فشرده برای دانلود/انتقال ---
    zip_path = dest + '.zip'
    try:
        with zf.ZipFile(zip_path, 'w', zf.ZIP_DEFLATED, compresslevel=6) as z:
            for root, dirs, files in os.walk(dest):
                for f in files:
                    full = os.path.join(root, f)
                    arc = os.path.relpath(full, dest)
                    z.write(full, arc)
    except Exception as e:
        print('[backup] zip:', e)
        zip_path = None

    # --- پاکسازی: نگه‌داری حداکثر N بکاپ و حداکثر D روز ---
    max_keep = 20
    max_days = 30
    try:
        conn = sqlite3.connect(os.path.join(BASE_DIR, DB_NAME), timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT value FROM app_settings WHERE key='backup_max_keep'").fetchone()
            if row and str(row['value']).isdigit():
                max_keep = max(3, int(row['value']))
            row = conn.execute("SELECT value FROM app_settings WHERE key='backup_max_days'").fetchone()
            if row and str(row['value']).isdigit():
                max_days = max(7, int(row['value']))
        except Exception as e:
            logger.exception("Silent exception in core/backup.py")
        conn.close()
    except Exception as e:
        logger.exception("Silent exception in core/backup.py")
    cutoff = time.time() - max_days * 24 * 3600
    try:
        entries = []
        for name in os.listdir(BACKUP_DIR):
            path = os.path.join(BACKUP_DIR, name)
            if name.startswith('backup_') and (os.path.isdir(path) or name.endswith('.zip')):
                try:
                    entries.append((os.path.getmtime(path), path, name))
                except Exception as e:
                    logger.exception("Silent exception in core/backup.py")
        entries.sort(reverse=True)  # newest first
        for i, (mtime, path, name) in enumerate(entries):
            if i >= max_keep or mtime < cutoff:
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        os.remove(path)
                except Exception as e:
                    logger.exception("Silent exception in core/backup.py")
    except Exception as e:
        print('[backup] cleanup:', e)

    # --- کپی به مسیر شبکه ---
    net = os.environ.get('SAZGAN_BACKUP_PATH', '').strip()
    if not net:
        try:
            conn = sqlite3.connect(os.path.join(BASE_DIR, DB_NAME), timeout=5)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT value FROM app_settings WHERE key='backup_network_path'").fetchone()
            conn.close()
            if row:
                net = (row['value'] or '').strip()
        except Exception as e:
            logger.exception("Silent exception in core/backup.py")
    if net and os.path.isdir(net):
        try:
            if zip_path and os.path.isfile(zip_path):
                shutil.copy2(zip_path, os.path.join(net, os.path.basename(zip_path)))
            else:
                target = os.path.join(net, os.path.basename(dest))
                if os.path.exists(target):
                    shutil.rmtree(target, ignore_errors=True)
                shutil.copytree(dest, target)
        except Exception as e:
            print('[backup] network:', e)

    return dest




def _backup_scheduler():
    """بکاپ خودکار روزانه — قابل خاموش/روشن از تنظیمات پیشرفته."""
    time.sleep(3600)
    while True:
        try:
            enabled = True
            try:
                conn = sqlite3.connect(os.path.join(BASE_DIR, DB_NAME), timeout=5)
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT value FROM app_settings WHERE key='backup_auto_enabled'").fetchone()
                conn.close()
                if row is not None and str(row['value']).strip() in ('0', 'false', 'False', 'no'):
                    enabled = False
            except Exception as e:
                logger.exception("Silent exception in core/backup.py")
            if enabled:
                create_backup('daily')
        except Exception as e:
            print('[backup] daily failed:', e)
        time.sleep(24 * 3600)






