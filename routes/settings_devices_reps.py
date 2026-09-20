# -*- coding: utf-8 -*-
"""مسیرهای دستگاه‌ها و نمایندگان: devices، representatives(آرشیو/مشاهده/عکس/ویرایش/حذف)."""
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



def register(app):
    @app.route('/settings/devices', methods=['GET', 'POST'])
    def settings_devices():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        conn = get_db()
        try:
            cols = {r[1] for r in conn.execute('PRAGMA table_info(devices)').fetchall()}
            if 'photo_filename' not in cols:
                conn.execute('ALTER TABLE devices ADD COLUMN photo_filename TEXT')
                conn.commit()
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        if request.method == 'POST':
            action = (request.form.get('action') or 'add').strip()
            if action == 'add':
                device_type = (request.form.get('device_type') or '').strip()
                model = (request.form.get('model') or '').strip()
                if device_type and model:
                    cur = conn.execute(
                        'INSERT INTO devices (device_type, model) VALUES (?, ?)',
                        (device_type, model)
                    )
                    new_id = cur.lastrowid
                    photo = request.files.get('photo')
                    if photo and photo.filename:
                        ext = photo.filename.rsplit('.', 1)[-1].lower() if '.' in photo.filename else ''
                        if ext in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
                            folder = os.path.join('static', 'uploads', 'devices')
                            os.makedirs(folder, exist_ok=True)
                            filename = secure_filename('device_%s.%s' % (new_id, ext))
                            save_uploaded_image(photo, os.path.join(folder, filename))
                            conn.execute('UPDATE devices SET photo_filename=? WHERE id=?', (filename, new_id))
                    conn.commit()
            elif action == 'photo':
                device_id = request.form.get('device_id')
                photo = request.files.get('photo')
                if device_id and photo and photo.filename:
                    ext = photo.filename.rsplit('.', 1)[-1].lower() if '.' in photo.filename else ''
                    if ext in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
                        folder = os.path.join('static', 'uploads', 'devices')
                        os.makedirs(folder, exist_ok=True)
                        filename = secure_filename('device_%s.%s' % (device_id, ext))
                        save_uploaded_image(photo, os.path.join(folder, filename))
                        conn.execute('UPDATE devices SET photo_filename=? WHERE id=?', (filename, device_id))
                        conn.commit()
            conn.close()
            return redirect('/settings/devices')

        devices_list = conn.execute('SELECT * FROM devices ORDER BY id DESC').fetchall()
        conn.close()
        return render_template(
            'settings_devices.html', devices=devices_list,
            active_page='settings', current_user=current_user
        )




    @app.route('/settings/representatives', methods=['GET', 'POST'])
    def settings_representatives():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        conn = get_db()
        if request.method == 'POST':
            rep_type = request.form['rep_type']
            company_name = request.form.get('company_name') if rep_type == 'حقوقی' else None
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            father_name = request.form.get('father_name') if rep_type == 'حقیقی' else None
            national_id = request.form['national_id']
            phone = request.form['phone']
            province = request.form['province']
            county = request.form.get('county') or None
            city = request.form.get('city') or request.form.get('city_manual') or None
            address = request.form['address']
            contact_person_first_name = request.form.get('contact_person_first_name') if rep_type == 'حقوقی' else None
            contact_person_last_name = request.form.get('contact_person_last_name') if rep_type == 'حقوقی' else None
            contact_person_name = (' '.join([x for x in [contact_person_first_name, contact_person_last_name] if x])).strip() or None if rep_type == 'حقوقی' else None
            contact_person_phone = request.form.get('contact_person_phone') if rep_type == 'حقوقی' else None
            guarantee_status = request.form['guarantee_status']
            guarantee_amount = request.form.get('guarantee_amount') or None
            county = request.form.get('county') or None
            city = request.form.get('city') or request.form.get('city_manual') or None
            status = request.form['status']
            archive_reason = request.form.get('archive_reason') or None
            archive_date = None
            if status != 'فعال':
                try:
                    import jdatetime
                    td = jdatetime.date.today()
                    archive_date = f"{td.year}/{str(td.month).zfill(2)}/{str(td.day).zfill(2)}"
                except Exception:
                    archive_date = None
            conn.execute(
                '''INSERT INTO representatives
                   (rep_type, company_name, first_name, last_name, father_name, national_id,
                    phone, province, county, address, guarantee_status, status,
                    contact_person_name, contact_person_phone, city, guarantee_amount,
                    archive_date, archive_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (rep_type, company_name, first_name, last_name, father_name, national_id,
                 phone, province, county, address, guarantee_status, status,
                 contact_person_name, contact_person_phone, city, guarantee_amount,
                 archive_date, archive_reason)
            )
            conn.commit()
            conn.close()
            return redirect('/settings/representatives')

        reps_list = conn.execute(
            "SELECT * FROM representatives WHERE status = 'فعال' ORDER BY id DESC"
        ).fetchall()
        conn.close()
        return render_template(
            'settings_representatives.html', representatives=reps_list, provinces=(get_geo_provinces(conn) if get_geo_provinces else PROVINCES),
            active_page='settings', current_user=current_user
        )





    @app.route('/settings/representatives/archive')
    def archive_representatives():
        current_user = get_current_user()
        if not current_user:
            return redirect('/login')
        if not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        conn = get_db()
        reps_list = conn.execute(
            "SELECT * FROM representatives WHERE status != 'فعال' ORDER BY id DESC"
        ).fetchall()
        conn.close()
        return render_template(
            'archive_representatives.html', representatives=reps_list,
            active_page='settings', current_user=current_user
        )





    @app.route('/settings/representatives/view/<int:rep_id>')
    def view_representative(rep_id):
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        conn = get_db()
        rep = conn.execute('SELECT * FROM representatives WHERE id = ?', (rep_id,)).fetchone()
        conn.close()
        if not rep:
            return redirect('/settings/representatives')

        return render_template(
            'view_representative.html', rep=rep,
            active_page='settings', current_user=current_user
        )





    @app.route('/settings/representatives/upload_photo/<int:rep_id>', methods=['POST'])
    def upload_representative_photo(rep_id):
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        cropped_data = request.form.get('cropped_image')
        if cropped_data and cropped_data.startswith('data:image'):
            header, encoded = cropped_data.split(',', 1)
            filename = secure_filename(f"rep_{rep_id}.jpg")
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            save_uploaded_image(base64.b64decode(encoded), filepath)
            conn = get_db()
            conn.execute('UPDATE representatives SET photo_filename = ? WHERE id = ?', (filename, rep_id))
            conn.commit()
            conn.close()
            return redirect(f'/settings/representatives/view/{rep_id}')

        file = request.files.get('photo')
        if file and file.filename:
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext in ALLOWED_PHOTO_EXTENSIONS:
                filename = secure_filename(f"rep_{rep_id}.{ext}")
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                save_uploaded_image(file, filepath)
                conn = get_db()
                conn.execute('UPDATE representatives SET photo_filename = ? WHERE id = ?', (filename, rep_id))
                conn.commit()
                conn.close()

        return redirect(f'/settings/representatives/view/{rep_id}')





    @app.route('/settings/representatives/edit/<int:rep_id>', methods=['GET', 'POST'])
    def edit_representative(rep_id):
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        conn = get_db()
        rep = conn.execute('SELECT * FROM representatives WHERE id = ?', (rep_id,)).fetchone()
        if not rep:
            conn.close()
            return redirect('/settings/representatives')

        if request.method == 'POST':
            rep_type = request.form['rep_type']
            company_name = request.form.get('company_name') if rep_type == 'حقوقی' else None
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            father_name = request.form.get('father_name') if rep_type == 'حقیقی' else None
            national_id = request.form['national_id']
            phone = request.form['phone']
            province = request.form['province']
            county = request.form.get('county') or None
            city = request.form.get('city') or request.form.get('city_manual') or None
            address = request.form['address']
            contact_person_first_name = request.form.get('contact_person_first_name') if rep_type == 'حقوقی' else None
            contact_person_last_name = request.form.get('contact_person_last_name') if rep_type == 'حقوقی' else None
            contact_person_name = (' '.join([x for x in [contact_person_first_name, contact_person_last_name] if x])).strip() or None if rep_type == 'حقوقی' else None
            contact_person_phone = request.form.get('contact_person_phone') if rep_type == 'حقوقی' else None
            guarantee_status = request.form['guarantee_status']
            guarantee_amount = request.form.get('guarantee_amount') or None
            county = request.form.get('county') or None
            city = request.form.get('city') or request.form.get('city_manual') or None
            status = request.form['status']
            archive_reason = request.form.get('archive_reason') or None
            archive_date = None
            if status != 'فعال':
                try:
                    import jdatetime
                    td = jdatetime.date.today()
                    archive_date = f"{td.year}/{str(td.month).zfill(2)}/{str(td.day).zfill(2)}"
                except Exception:
                    archive_date = None
            conn.execute(
                '''UPDATE representatives SET
                   rep_type = ?, company_name = ?, first_name = ?, last_name = ?, father_name = ?,
                   national_id = ?, phone = ?, province = ?, county = ?, address = ?, guarantee_status = ?, status = ?,
                   contact_person_name = ?, contact_person_phone = ?,
                   city = ?, guarantee_amount = ?, archive_date = COALESCE(?, archive_date), archive_reason = ?
                   WHERE id = ?''',
                (rep_type, company_name, first_name, last_name, father_name, national_id,
                 phone, province, county, address, guarantee_status, status,
                 contact_person_name, contact_person_phone,
                 city, guarantee_amount, archive_date, archive_reason, rep_id)
            )
            conn.commit()
            conn.close()
            return redirect('/settings/representatives')

        conn.close()
        return render_template(
            'edit_representative.html', rep=rep, provinces=(get_geo_provinces(conn) if get_geo_provinces else PROVINCES),
            active_page='settings', current_user=current_user, embed=_is_embed()
        )





    @app.route('/settings/representatives/delete/<int:rep_id>', methods=['POST'])
    def delete_representative(rep_id):
        current_user = get_current_user()
        if not current_user or not (_is_reception(current_user) or user_has_access(current_user, 'parties')):
            return redirect('/')

        conn = get_db()
        # آرشیو نرم
        try:
            import jdatetime
            td = jdatetime.date.today()
            ad = f"{td.year}/{str(td.month).zfill(2)}/{str(td.day).zfill(2)}"
        except Exception:
            ad = None
        conn.execute(
            "UPDATE representatives SET status='غیرفعال', archive_date=COALESCE(?, archive_date), archive_reason=COALESCE(archive_reason, 'آرشیو از لیست') WHERE id=?",
            (ad, rep_id),
        )
        try:
            write_audit(conn, current_user.get('full_name'), 'آرشیو نماینده', 'representative', rep_id, '')
        except Exception as e:
            logger.exception("Silent exception in routes/settings.py")
        conn.commit()
        conn.close()
        return redirect('/settings/representatives')




