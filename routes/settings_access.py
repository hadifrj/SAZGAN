# -*- coding: utf-8 -*-
"""مسیرهای دسترسی/کاربران: access/activation/users(deactivate,activate,archive,view,edit)."""
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

from routes.settings_shared import _ensure_user_active_col


def register(app):
    @app.route('/settings/access', methods=['GET', 'POST'])
    def settings_access():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'system')):
            return redirect('/')
        import json
        conn = get_db()
        msg = None
        if request.method == 'POST':
            amap = {}
            roles_list = list(DEFAULT_ROLE_ACCESS.keys())
            # نقش‌های موجود در دیتابیس هم اضافه شود
            try:
                for r in conn.execute('SELECT DISTINCT role FROM users').fetchall():
                    if r['role'] and r['role'] not in roles_list:
                        roles_list.append(r['role'])
            except Exception as e:
                logger.exception("Silent exception in routes/settings.py")
            for role in roles_list:
                amap[role] = {}
                for mid, _label in ACCESS_MODULES:
                    key = 'perm__%s__%s' % (role, mid)
                    if role == 'مدیر سیستم':
                        amap[role][mid] = 1
                    else:
                        amap[role][mid] = 1 if request.form.get(key) else 0
            set_setting(conn, 'role_access_map', json.dumps(amap, ensure_ascii=False))
            write_audit(conn, current_user['full_name'], 'به‌روزرسانی ماتریس دسترسی', 'settings', None, None)
            conn.commit()
            msg = 'دسترسی‌ها ذخیره شد.'
        access_map = get_role_access_map(conn)
        roles_list = list(access_map.keys())
        # شمارش کاربران هر نقش
        role_user_counts = {}
        try:
            for r in conn.execute('SELECT role, COUNT(*) AS c FROM users GROUP BY role').fetchall():
                role_user_counts[r['role']] = r['c']
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        conn.close()
        return render_template(
            'settings_access.html',
            active_page='settings-access',
            current_user=current_user,
            modules=ACCESS_MODULES,
            roles=roles_list,
            access_map=access_map,
            role_user_counts=role_user_counts,
            msg=msg,
        )


    @app.route('/settings/access/reset', methods=['POST'])
    def settings_access_reset():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'system')):
            return redirect('/')
        conn = get_db()
        set_setting(conn, 'role_access_map', '')
        write_audit(conn, current_user['full_name'], 'بازنشانی ماتریس دسترسی', 'settings', None, None)
        conn.commit()
        conn.close()
        return redirect('/settings/access')





    @app.route('/settings/activation', methods=['GET', 'POST'])
    def settings_activation():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'system')):
            return redirect('/')
        conn = get_db()
        msg = error = None
        if request.method == 'POST':
            key = (request.form.get('license_key') or '').strip().upper()
            owner = (request.form.get('license_owner') or '').strip()
            # نرمال‌سازی: حذف فاصله
            key_clean = re.sub(r'\s+', '', key)
            if len(key_clean) < 8:
                error = 'کلید فعال‌سازی معتبر نیست (حداقل ۸ کاراکتر).'
            else:
                set_setting(conn, 'license_key', key_clean)
                set_setting(conn, 'license_status', 'active')
                set_setting(conn, 'license_owner', owner)
                try:
                    import jdatetime as _jd
                    today = _jd.date.today()
                    activated = f"{today.year}/{str(today.month).zfill(2)}/{str(today.day).zfill(2)}"
                except Exception:
                    activated = time.strftime('%Y/%m/%d')
                set_setting(conn, 'license_activated_at', activated)
                write_audit(conn, current_user['full_name'], 'فعال‌سازی نرم‌افزار', 'settings', None, owner or key_clean[:4] + '…')
                conn.commit()
                msg = 'نرم‌افزار با موفقیت فعال شد.'
        status = get_setting(conn, 'license_status', '') or 'inactive'
        key_stored = get_setting(conn, 'license_key', '') or ''
        masked = ''
        if key_stored:
            if len(key_stored) > 8:
                masked = key_stored[:4] + '…' + key_stored[-4:]
            else:
                masked = key_stored[:2] + '…'
        owner = get_setting(conn, 'license_owner', '') or ''
        activated_at = get_setting(conn, 'license_activated_at', '') or ''
        conn.close()
        return render_template(
            'settings_activation.html',
            active_page='settings-activation',
            current_user=current_user,
            license_status=status,
            license_key_masked=masked,
            license_owner=owner,
            license_activated_at=activated_at,
            msg=msg,
            error=error,
        )


    @app.route('/settings/users/deactivate/<int:user_id>', methods=['POST'])
    def deactivate_user(user_id):
        """غیرفعال‌سازی کاربر — حذف فیزیکی نداریم."""
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        from core.access import is_system_admin as _isa
        if not _isa(current_user):
            return 'اجازه غیرفعال‌سازی فقط برای مدیر سیستم است.', 403
        try:
            if int(user_id) == int(current_user['id']):
                return redirect('/settings')
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        try:
            if not _validate_csrf():
                return redirect('/settings')
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        conn = get_db()
        try:
            _ensure_user_active_col(conn)
            target = conn.execute('SELECT id, username, role, is_active FROM users WHERE id=?', (user_id,)).fetchone()
            if target:
                # آخرین مدیر سیستم فعال را غیرفعال نکن
                role = target['role'] if 'role' in target.keys() else ''
                if role in ('مسئول پذیرش', 'مدیر سیستم'):
                    cnt = conn.execute(
                        """SELECT COUNT(*) AS c FROM users
                           WHERE role IN ('مسئول پذیرش','مدیر سیستم')
                             AND IFNULL(is_active,1)=1 AND id!=?""",
                        (user_id,),
                    ).fetchone()['c']
                    if cnt < 1:
                        conn.close()
                        return redirect('/settings')
                conn.execute('UPDATE users SET is_active=0 WHERE id=?', (user_id,))
                conn.commit()
                try:
                    write_audit(conn, current_user['full_name'], 'غیرفعال‌سازی کاربر', 'user', user_id,
                                target['username'] if 'username' in target.keys() else '')
                    conn.commit()
                except Exception as e:
                    logger.exception("Silent exception in routes/settings.py")
        finally:
            try:
                conn.close()
            except Exception as e:
                logger.exception("Silent exception in routes/settings.py")
        return redirect('/settings')


    @app.route('/settings/users/activate/<int:user_id>', methods=['POST'])
    def activate_user(user_id):
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        from core.access import is_system_admin as _isa
        if not _isa(current_user):
            return 'اجازه فعال‌سازی فقط برای مدیر سیستم است.', 403
        try:
            if not _validate_csrf():
                return redirect('/settings/users/archive')
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        conn = get_db()
        try:
            _ensure_user_active_col(conn)
            conn.execute('UPDATE users SET is_active=1 WHERE id=?', (user_id,))
            conn.commit()
            try:
                write_audit(conn, current_user['full_name'], 'فعال‌سازی کاربر', 'user', user_id, None)
                conn.commit()
            except Exception as e:
                logger.exception("Silent exception in routes/settings.py")
        finally:
            try:
                conn.close()
            except Exception as e:
                logger.exception("Silent exception in routes/settings.py")
        return redirect('/settings/users/archive')


    @app.route('/settings/users/archive')
    def users_archive():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')
        conn = get_db()
        _ensure_user_active_col(conn)
        users_list = conn.execute(
            'SELECT * FROM users WHERE IFNULL(is_active,1)=0 ORDER BY id DESC'
        ).fetchall()
        conn.close()
        from core.access import is_system_admin as _isa
        return render_template(
            'settings_users_archive.html',
            users=users_list,
            current_user=current_user,
            can_manage=_isa(current_user),
            active_page='settings',
        )


    @app.route('/settings/users/view/<int:user_id>')
    def view_user(user_id):
        current_user = get_current_user()
        if not current_user or current_user['role'] not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم'):
            return redirect('/')
        conn = get_db()
        try:
            user_cols = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
            if 'photo_filename' not in user_cols:
                conn.execute('ALTER TABLE users ADD COLUMN photo_filename TEXT')
                conn.commit()
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        if not user:
            return redirect('/settings')
        is_self = False
        try:
            is_self = int(current_user['id']) == int(user_id)
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        return render_template(
            'view_user.html', user=user, is_self=is_self,
            active_page='settings', current_user=current_user
        )


    @app.route('/settings/users/edit/<int:user_id>', methods=['GET', 'POST'])
    def edit_user(user_id):
        current_user = get_current_user()
        if not current_user or current_user['role'] not in ('مسئول پذیرش', 'مدیر', 'مدیر سیستم'):
            return redirect('/')
        conn = get_db()
        try:
            user_cols = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
            if 'photo_filename' not in user_cols:
                conn.execute('ALTER TABLE users ADD COLUMN photo_filename TEXT')
                conn.commit()
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            conn.close()
            return redirect('/settings')
        error = None
        if request.method == 'POST':
            full_name = (request.form.get('full_name') or '').strip()
            username = (request.form.get('username') or '').strip()
            role = request.form.get('role') or user['role']
            province = request.form.get('province') or None
            representative_id = request.form.get('representative_id') or None
            password = request.form.get('password') or ''
            if not full_name or not username:
                error = 'نام و نام کاربری الزامی است.'
            else:
                other = conn.execute(
                    'SELECT id FROM users WHERE username = ? AND id != ?',
                    (username, user_id)
                ).fetchone()
                if other:
                    error = 'این نام کاربری قبلاً استفاده شده است.'
                else:
                    if role == 'تکنسین استانی' and representative_id:
                        rep = conn.execute(
                            'SELECT * FROM representatives WHERE id = ?', (representative_id,)
                        ).fetchone()
                        if rep:
                            province = rep['province'] or province
                            if rep['rep_type'] == 'حقوقی' and rep['company_name']:
                                full_name = rep['company_name']
                            else:
                                full_name = f"{rep['first_name']} {rep['last_name']}"
                    else:
                        representative_id = None
                    county = (request.form.get('county') or '').strip() or None
                    city = (request.form.get('city') or request.form.get('city_manual') or '').strip() or None
                    # اطمینان از وجود ستون‌ها
                    try:
                        cols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
                        if 'county' not in cols:
                            conn.execute('ALTER TABLE users ADD COLUMN county TEXT')
                        if 'city' not in cols:
                            conn.execute('ALTER TABLE users ADD COLUMN city TEXT')
                    except Exception as e:
                        logger.exception("Silent exception in routes/settings.py")
                    conn.execute(
                        'UPDATE users SET full_name=?, username=?, role=?, province=?, county=?, city=?, representative_id=? WHERE id=?',
                        (full_name, username, role, province, county, city, representative_id, user_id)
                    )
                    if password and len(password) >= 6:
                        conn.execute(
                            'UPDATE users SET password_hash=? WHERE id=?',
                            (generate_password_hash(password), user_id)
                        )
                    photo = request.files.get('photo')
                    if photo and photo.filename:
                        ext = photo.filename.rsplit('.', 1)[-1].lower() if '.' in photo.filename else ''
                        if ext in ALLOWED_PHOTO_EXTENSIONS:
                            os.makedirs(USER_UPLOAD_FOLDER, exist_ok=True)
                            filename = secure_filename(f'user_{user_id}.{ext}')
                            save_uploaded_image(photo, os.path.join(USER_UPLOAD_FOLDER, filename))
                            conn.execute(
                                'UPDATE users SET photo_filename=? WHERE id=?',
                                (filename, user_id)
                            )
                    # اطلاعات مالی نماینده
                    try:
                        cols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
                        for c in ('bank_card', 'bank_sheba', 'bank_owner'):
                            if c not in cols:
                                conn.execute('ALTER TABLE users ADD COLUMN %s TEXT' % c)
                        import re as _re
                        card = _re.sub(r'\D', '', (request.form.get('bank_card') or ''))
                        sheba = (request.form.get('bank_sheba') or '').strip().upper().replace(' ', '')
                        owner = (request.form.get('bank_owner') or '').strip()
                        conn.execute(
                            'UPDATE users SET bank_card=?, bank_sheba=?, bank_owner=? WHERE id=?',
                            (card or None, sheba or None, owner or None, user_id),
                        )
                    except Exception as e:
                        logger.exception("Silent exception in routes/settings.py")
                    conn.commit()
                    conn.close()
                    return redirect('/settings')
        reps_list = conn.execute(
            "SELECT * FROM representatives WHERE status = 'فعال' ORDER BY first_name"
        ).fetchall()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return render_template(
            'edit_user.html', user=user, roles=(roles_list(conn) if roles_list else ROLES), provinces=(get_geo_provinces(conn) if get_geo_provinces else PROVINCES),
            representatives=reps_list, error=error,
            active_page='settings', current_user=current_user, embed=_is_embed()
        )


