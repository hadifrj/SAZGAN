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
    """مسیرهای api."""
    # دسترسی به هلپرها
    @app.route('/api/lookup_warranty/<serial>')
    def lookup_warranty(serial):
        conn = get_db()
        card = conn.execute(
            'SELECT * FROM warranty_cards WHERE serial_number = ?', (serial,)
        ).fetchone()
        conn.close()
        if card:
            d = _enrich_warranty_row(card)
            return jsonify({
                'found': True,
                'installation_date': d.get('installation_date') or '',
                'customer_name': d.get('customer_name') or '',
                'device_type': d.get('device_type') or '',
                'model': d.get('model') or '',
                'shahriar': d.get('shahriar') or '',
                'warranty_end_date': d.get('warranty_end_date') or '',
                'production_date': d.get('production_date') or '',
                'warranty_status': d.get('warranty_status') or '',
                'warranty_months': d.get('warranty_months') or '',
                'active': d.get('warranty_status') == 'فعال',
            })
        return jsonify({'found': False})




    @app.route('/api/customer/<int:customer_id>')
    def api_customer(customer_id):
        conn = get_db()
        c = conn.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()
        conn.close()
        if not c:
            return jsonify({'found': False})
        return jsonify({
            'found': True,
            'id': c['id'],
            'name': c['name'],
            'phone': c['phone'] or '',
            'province': c['province'] or '',
            'county': (c['county'] if 'county' in c.keys() else '') or '',
            'city': c['city'] or '',
            'address': c['address'] or '',
            'equipment_manager_name': c['equipment_manager_name'] or '',
            'equipment_manager_mobile': c['equipment_manager_mobile'] or '',
        })

    @app.route('/api/geo/counties')
    def api_geo_counties():
        province = (request.args.get('province') or '').strip()
        conn = get_db()
        try:
            from core.geo import get_geo_counties
            items = get_geo_counties(conn, province)
        except Exception:
            items = []
        finally:
            conn.close()
        return jsonify({'items': items})

    @app.route('/api/geo/cities')
    def api_geo_cities():
        province = (request.args.get('province') or '').strip()
        county = (request.args.get('county') or '').strip()
        conn = get_db()
        try:
            from core.geo import get_geo_cities
            items = get_geo_cities(conn, province, county)
        except Exception:
            items = []
        finally:
            conn.close()
        return jsonify({'items': items})






    @app.route('/api/geo/distance')
    def api_geo_distance():
        from_city = (request.args.get('from_city') or '').strip()
        to_city = (request.args.get('to_city') or '').strip()
        from_province = (request.args.get('from_province') or '').strip()
        to_province = (request.args.get('to_province') or '').strip()
        conn = get_db()
        try:
            from core.distance import calculate_distance, ensure_distance_schema
            ensure_distance_schema(conn)
            result = calculate_distance(
                conn,
                from_city=from_city,
                to_city=to_city,
                from_province=from_province,
                to_province=to_province,
            )
        except Exception as e:
            result = {'ok': False, 'error': str(e)}
        finally:
            conn.close()
        return jsonify(result)

    @app.route('/api/geo/distance/request/<int:req_id>')
    def api_geo_distance_request(req_id):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'login'}), 401
        conn = get_db()
        try:
            from core.distance import distance_for_request, ensure_distance_schema
            ensure_distance_schema(conn)
            req = conn.execute('SELECT * FROM requests WHERE id = ?', (req_id,)).fetchone()
            if not req:
                return jsonify({'ok': False, 'error': 'پرونده یافت نشد'})
            # تکنسین/نماینده پرونده یا کاربر فعلی
            tech = None
            tech_id = req['assigned_technician_id'] if 'assigned_technician_id' in req.keys() else None
            if tech_id:
                tech = conn.execute('SELECT * FROM users WHERE id = ?', (tech_id,)).fetchone()
            if not tech:
                tech = current_user
            result = distance_for_request(conn, req, tech)
            result['customer_city'] = (req['city'] if 'city' in req.keys() else '') or ''
            result['customer_province'] = (req['province'] if 'province' in req.keys() else '') or ''
        except Exception as e:
            result = {'ok': False, 'error': str(e)}
        finally:
            conn.close()
        return jsonify(result)


    @app.route('/api/wage/travel')
    def api_wage_travel():
        conn = get_db()
        try:
            from core.wages import compute_travel, get_rate, ensure_wage_schema
            ensure_wage_schema(conn)
            if request.args.get('local') == '1':
                rate = get_rate(conn, 'travel_local')
                return jsonify({
                    'ok': True,
                    'is_local': True,
                    'travel_amount': int(rate['wage_amount']) if rate else 2500000,
                    'description': rate['work_description'] if rate else 'ایاب و ذهاب داخل شهر',
                })
            result = compute_travel(
                conn,
                request.args.get('from_city') or '',
                request.args.get('from_province') or '',
                request.args.get('to_city') or '',
                request.args.get('to_province') or '',
            )
            return jsonify({'ok': True, **result})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e), 'travel_amount': 0})
        finally:
            conn.close()


    # ------------------------------------------------------------------
    # Web Push API
    # ------------------------------------------------------------------
    @app.route('/api/push/vapid-public-key')
    def api_push_vapid_public_key():
        try:
            from core.push import get_vapid_public_key, ensure_vapid_keys
            ensure_vapid_keys()
            key = get_vapid_public_key()
            if not key:
                return jsonify({'ok': False, 'error': 'vapid_unavailable'}), 503
            return jsonify({'ok': True, 'key': key})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/push/subscribe', methods=['POST'])
    def api_push_subscribe():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'auth'}), 401
        data = request.get_json(silent=True) or {}
        endpoint = (data.get('endpoint') or '').strip()
        keys = data.get('keys') or {}
        if not endpoint or not keys.get('p256dh') or not keys.get('auth'):
            return jsonify({'ok': False, 'error': 'invalid_subscription'}), 400
        try:
            from core.push import save_subscription, ensure_push_schema
            conn = get_db()
            ensure_push_schema(conn)
            ok = save_subscription(
                conn,
                user_name=current_user['full_name'],
                subscription={'endpoint': endpoint, 'keys': keys},
                user_agent=(data.get('user_agent') or request.headers.get('User-Agent') or '')[:300],
            )
            conn.close()
            return jsonify({'ok': bool(ok)})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/push/unsubscribe', methods=['POST'])
    def api_push_unsubscribe():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'auth'}), 401
        data = request.get_json(silent=True) or {}
        endpoint = (data.get('endpoint') or '').strip()
        try:
            from core.push import remove_subscription
            conn = get_db()
            if endpoint:
                remove_subscription(conn, endpoint=endpoint)
            conn.close()
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/display-prefs', methods=['GET'])
    def api_display_prefs_get():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'auth'}), 401
        try:
            raw = current_user['display_prefs']
        except Exception:
            raw = None
        prefs = None
        if raw:
            try:
                import json as _json
                prefs = _json.loads(raw)
            except Exception:
                prefs = None
        return jsonify({'ok': True, 'prefs': prefs})

    @app.route('/api/display-prefs', methods=['POST'])
    def api_display_prefs_set():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'auth'}), 401
        data = request.get_json(silent=True) or {}
        prefs = data.get('prefs')
        if not isinstance(prefs, dict):
            return jsonify({'ok': False, 'error': 'invalid_prefs'}), 400
        # حفاظت در برابر داده حجیم/نامعتبر
        ALLOWED_KEYS = {
            'theme', 'accent', 'bg', 'sidebar', 'font', 'size', 'density', 'radius',
            'printFont', 'printSize', 'colorThemeId', 'reduceMotion', 'increaseContrast', 'amoled'
        }
        clean = {k: v for k, v in prefs.items() if k in ALLOWED_KEYS}
        try:
            import json as _json
            payload = _json.dumps(clean)[:4000]
            conn = get_db()
            conn.execute('UPDATE users SET display_prefs = ? WHERE id = ?', (payload, current_user['id']))
            conn.commit()
            conn.close()
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/push/unread-count')
    def api_push_unread_count():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'count': 0})
        try:
            from core.push import get_unread_count
            conn = get_db()
            n = get_unread_count(conn, current_user['full_name'])
            conn.close()
            return jsonify({'count': n})
        except Exception:
            return jsonify({'count': 0})

    @app.route('/api/push/mark-read/<int:nid>', methods=['POST'])
    def api_push_mark_read(nid):
        current_user = get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'auth'}), 401
        try:
            conn = get_db()
            row = conn.execute(
                'SELECT request_id, title FROM notifications WHERE id=? AND user_name=?',
                (nid, current_user['full_name'])
            ).fetchone()
            if not row:
                conn.close()
                return jsonify({'ok': False, 'error': 'not_found'}), 404
            conn.execute(
                'UPDATE notifications SET is_read=1 WHERE id=? AND user_name=?',
                (nid, current_user['full_name'])
            )
            # خواندن Push فقط اعلان را خوانده‌شده می‌کند؛ درخواست از قبل مستقیم در کارتابل است.
            conn.commit()
            from core.push import get_unread_count
            n = get_unread_count(conn, current_user['full_name'])
            conn.close()
            return jsonify({'ok': True, 'count': n})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/push/mark-all-read', methods=['POST'])
    def api_push_mark_all_read():
        current_user = get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'auth'}), 401
        try:
            conn = get_db()
            conn.execute(
                'UPDATE notifications SET is_read=1 WHERE user_name=?',
                (current_user['full_name'],)
            )
            conn.commit()
            conn.close()
            return jsonify({'ok': True, 'count': 0})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @app.route('/api/push/status')
    def api_push_status():
        """وضعیت پشتیبانی و subscription فعلی کاربر."""
        current_user = get_current_user()
        if not current_user:
            return jsonify({'ok': False, 'error': 'auth'}), 401
        try:
            from core.push import get_user_subscriptions, ensure_vapid_keys, get_vapid_public_key
            ensure_vapid_keys()
            conn = get_db()
            subs = get_user_subscriptions(conn, current_user['full_name'])
            conn.close()
            return jsonify({
                'ok': True,
                'vapid_ready': bool(get_vapid_public_key()),
                'subscriptions': len(subs),
                'devices': [
                    {
                        'id': s['id'],
                        'user_agent': (s.get('user_agent') or '')[:80],
                        'created_at': s.get('created_at'),
                        'last_used_at': s.get('last_used_at'),
                    }
                    for s in subs
                ],
            })
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500


