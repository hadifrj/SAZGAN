# -*- coding: utf-8 -*-
"""محاسبه مسافت بین شهرها

روش ۱ — haversine (پیش‌فرض، کاملاً آفلاین/رایگان):
  فاصله هوایی (Haversine) × ضریب جاده → تخمین جاده‌ای + رفت‌وبرگشت

روش ۲ — osrm (رایگان متن‌باز، OpenStreetMap):
  مسیر رانندگی واقعی از سرور OSRM؛ در صورت قطعی، به روش ۱ برمی‌گردد.

انتخاب روش از تنظیمات: distance_method = haversine | osrm
"""
from __future__ import annotations

import logging

import math
import re
from typing import Optional, Tuple

logger = logging.getLogger("sazgan")

# ضریب تقریبی مسیر جاده‌ای نسبت به خط مستقیم در ایران
DEFAULT_ROAD_FACTOR = 1.30


def _normalize_name(name: str) -> str:
    if not name:
        return ''
    s = str(name).strip()
    # ی/ک عربی → فارسی
    s = s.replace('ي', 'ی').replace('ك', 'ک')
    s = s.replace('آ', 'ا').replace('أ', 'ا').replace('إ', 'ا')
    s = re.sub(r'\s+', ' ', s)
    return s


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """فاصله هوایی بین دو نقطه (کیلومتر)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def ensure_distance_schema(conn):
    """افزودن lat/lng به geo_cities + تنظیمات ضریب جاده."""
    try:
        cols = {r[1] for r in conn.execute('PRAGMA table_info(geo_cities)').fetchall()}
        if 'lat' not in cols:
            conn.execute('ALTER TABLE geo_cities ADD COLUMN lat REAL')
        if 'lng' not in cols:
            conn.execute('ALTER TABLE geo_cities ADD COLUMN lng REAL')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_geo_cities_name ON geo_cities(name)')
    except Exception as e:
        logger.exception("Silent exception in core/distance.py")
    conn.commit()


def _fix_coords(lat: float, lng: float) -> Tuple[float, float]:
    """اگر lat/lng جابه‌جا باشد (خارج از محدوده ایران) جابه‌جا کن."""
    # ایران تقریبی: lat 24–40 ، lng 44–64
    if 24 <= lat <= 40 and 44 <= lng <= 64:
        return lat, lng
    if 24 <= lng <= 40 and 44 <= lat <= 64:
        return lng, lat
    return lat, lng


def find_city_coords(conn, city: str, province: str = '', county: str = '') -> Optional[Tuple[float, float, str]]:
    """
    پیدا کردن مختصات شهر.
    برمی‌گرداند: (lat, lng, matched_name) یا None
    """
    city_n = _normalize_name(city)
    if not city_n:
        return None
    province_n = _normalize_name(province)
    county_n = _normalize_name(county)

    # exact match with province
    if province_n:
        row = conn.execute(
            '''SELECT ci.name, ci.lat, ci.lng FROM geo_cities ci
               JOIN geo_provinces p ON p.id = ci.province_id
               WHERE ci.name = ? AND p.name = ? AND ci.lat IS NOT NULL AND ci.lng IS NOT NULL
               LIMIT 1''',
            (city, province),
        ).fetchone()
        if not row:
            # normalized scan for province
            rows = conn.execute(
                '''SELECT ci.name, ci.lat, ci.lng, p.name AS pname FROM geo_cities ci
                   JOIN geo_provinces p ON p.id = ci.province_id
                   WHERE ci.lat IS NOT NULL AND ci.lng IS NOT NULL'''
            ).fetchall()
            for r in rows:
                if _normalize_name(r['name']) == city_n and _normalize_name(r['pname']) == province_n:
                    row = r
                    break
        if row and row['lat'] is not None:
            lat, lng = _fix_coords(float(row['lat']), float(row['lng']))
            return lat, lng, row['name']

    # by name only
    row = conn.execute(
        '''SELECT name, lat, lng FROM geo_cities
           WHERE name = ? AND lat IS NOT NULL AND lng IS NOT NULL LIMIT 1''',
        (city,),
    ).fetchone()
    if row:
        lat, lng = _fix_coords(float(row['lat']), float(row['lng']))
        return lat, lng, row['name']

    # fuzzy contains
    rows = conn.execute(
        '''SELECT name, lat, lng FROM geo_cities
           WHERE lat IS NOT NULL AND lng IS NOT NULL'''
    ).fetchall()
    for r in rows:
        rn = _normalize_name(r['name'])
        if rn == city_n or city_n in rn or rn in city_n:
            lat, lng = _fix_coords(float(r['lat']), float(r['lng']))
            return lat, lng, r['name']
    return None


def get_road_factor(conn) -> float:
    try:
        from core.db import get_setting
        val = get_setting(conn, 'distance_road_factor', str(DEFAULT_ROAD_FACTOR))
        f = float(val)
        if 1.0 <= f <= 2.5:
            return f
    except Exception as e:
        logger.exception("Silent exception in core/distance.py")
    return DEFAULT_ROAD_FACTOR


# روش‌های محاسبه: haversine (۱) | osrm (۲)
METHOD_HAVERSINE = 'haversine'
METHOD_OSRM = 'osrm'
DEFAULT_METHOD = METHOD_HAVERSINE
DEFAULT_OSRM_URL = 'https://router.project-osrm.org'


def get_distance_method(conn) -> str:
    try:
        from core.db import get_setting
        val = (get_setting(conn, 'distance_method', DEFAULT_METHOD) or DEFAULT_METHOD).strip().lower()
        if val in (METHOD_HAVERSINE, METHOD_OSRM, '1', '2'):
            if val == '1':
                return METHOD_HAVERSINE
            if val == '2':
                return METHOD_OSRM
            return val
    except Exception as e:
        logger.exception("Silent exception in core/distance.py")
    return DEFAULT_METHOD


def get_osrm_base_url(conn) -> str:
    try:
        from core.db import get_setting
        val = (get_setting(conn, 'distance_osrm_url', DEFAULT_OSRM_URL) or DEFAULT_OSRM_URL).strip().rstrip('/')
        if val.startswith('http'):
            return val
    except Exception as e:
        logger.exception("Silent exception in core/distance.py")
    return DEFAULT_OSRM_URL


def osrm_route_km(lat1: float, lng1: float, lat2: float, lng2: float, base_url: str = None) -> dict:
    """
    مسافت جاده‌ای واقعی از OSRM (OpenStreetMap).
    خروجی: {ok, road_km, duration_min, error}
    """
    import json
    import urllib.request
    import urllib.error

    base = (base_url or DEFAULT_OSRM_URL).rstrip('/')
    # OSRM expects lon,lat
    path = f"{base}/route/v1/driving/{lng1},{lat1};{lng2},{lat2}?overview=false&alternatives=false"
    out = {'ok': False, 'road_km': None, 'duration_min': None, 'error': None}
    try:
        req = urllib.request.Request(path, headers={'User-Agent': 'SazganDistance/1.0'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if data.get('code') != 'Ok' or not data.get('routes'):
            out['error'] = data.get('message') or data.get('code') or 'مسیر OSRM یافت نشد'
            return out
        route = data['routes'][0]
        meters = float(route.get('distance') or 0)
        seconds = float(route.get('duration') or 0)
        out.update({
            'ok': True,
            'road_km': round(meters / 1000.0, 1),
            'duration_min': round(seconds / 60.0, 0),
            'error': None,
        })
        return out
    except urllib.error.HTTPError as e:
        out['error'] = f'خطای OSRM HTTP {e.code}'
        return out
    except Exception as e:
        out['error'] = f'ارتباط با OSRM برقرار نشد: {e}'
        return out


def calculate_distance(
    conn,
    from_city: str,
    to_city: str,
    from_province: str = '',
    to_province: str = '',
    from_county: str = '',
    to_county: str = '',
    road_factor: float = None,
) -> dict:
    """
    محاسبه مسافت یک‌طرفه و رفت‌وبرگشت.

    خروجی:
      {
        ok, air_km, road_km, round_trip_km,
        from_matched, to_matched, road_factor, error
      }
    """
    method = get_distance_method(conn)
    factor = road_factor if road_factor is not None else get_road_factor(conn)
    result = {
        'ok': False,
        'air_km': None,
        'road_km': None,
        'round_trip_km': None,
        'duration_min': None,
        'from_matched': None,
        'to_matched': None,
        'road_factor': factor,
        'method': method,
        'method_label': 'تقریبی (هوایی × ضریب)' if method == METHOD_HAVERSINE else 'مسیر جاده‌ای (OSRM / OpenStreetMap)',
        'error': None,
        'fallback': False,
    }
    if not from_city or not to_city:
        result['error'] = 'شهر مبدأ و مقصد الزامی است'
        return result

    a = find_city_coords(conn, from_city, from_province, from_county)
    b = find_city_coords(conn, to_city, to_province, to_county)
    if not a:
        result['error'] = f'مختصات شهر مبدأ «{from_city}» پیدا نشد'
        return result
    if not b:
        result['error'] = f'مختصات شهر مقصد «{to_city}» پیدا نشد'
        return result

    lat1, lng1, name1 = a
    lat2, lng2, name2 = b
    air = haversine_km(lat1, lng1, lat2, lng2)
    result['air_km'] = round(air, 1)
    result['from_matched'] = name1
    result['to_matched'] = name2
    result['from_coords'] = {'lat': lat1, 'lng': lng1}
    result['to_coords'] = {'lat': lat2, 'lng': lng2}

    if method == METHOD_OSRM:
        osrm = osrm_route_km(lat1, lng1, lat2, lng2, get_osrm_base_url(conn))
        if osrm.get('ok') and osrm.get('road_km') is not None:
            road = float(osrm['road_km'])
            result.update({
                'ok': True,
                'road_km': round(road, 1),
                'round_trip_km': round(road * 2, 1),
                'duration_min': osrm.get('duration_min'),
                'error': None,
            })
            return result
        # fallback to haversine if OSRM fails
        road = air * factor
        result.update({
            'ok': True,
            'road_km': round(road, 1),
            'round_trip_km': round(road * 2, 1),
            'method': METHOD_HAVERSINE,
            'method_label': 'تقریبی (پشتیبان — OSRM در دسترس نبود)',
            'fallback': True,
            'error': None,
            'osrm_error': osrm.get('error'),
        })
        return result

    # default: haversine × factor
    road = air * factor
    result.update({
        'ok': True,
        'road_km': round(road, 1),
        'round_trip_km': round(road * 2, 1),
        'error': None,
    })
    return result


def distance_for_request(conn, req, rep_user=None) -> dict:
    """
    مسافت رفت‌وبرگشت نماینده تا شهر مشتری برای یک پرونده.
    مبدأ: شهر/استان نماینده (یا کاربر تکنسین)
    مقصد: شهر/استان پرونده
    """
    to_city = ''
    to_province = ''
    to_county = ''
    if req:
        if hasattr(req, 'keys'):
            to_city = (req['city'] if 'city' in req.keys() else '') or ''
            to_province = (req['province'] if 'province' in req.keys() else '') or ''
            to_county = (req['county'] if 'county' in req.keys() else '') or ''
        elif isinstance(req, dict):
            to_city = req.get('city') or ''
            to_province = req.get('province') or ''
            to_county = req.get('county') or ''

    from_city = ''
    from_province = ''
    from_county = ''

    # از نماینده متصل به کاربر
    if rep_user:
        uid = rep_user['id'] if hasattr(rep_user, 'keys') and 'id' in rep_user.keys() else (rep_user.get('id') if isinstance(rep_user, dict) else None)
        rep_id = None
        if hasattr(rep_user, 'keys'):
            from_province = (rep_user['province'] if 'province' in rep_user.keys() else '') or ''
            rep_id = rep_user['representative_id'] if 'representative_id' in rep_user.keys() else None
        elif isinstance(rep_user, dict):
            from_province = rep_user.get('province') or ''
            rep_id = rep_user.get('representative_id')

        if rep_id:
            rep = conn.execute('SELECT * FROM representatives WHERE id = ?', (rep_id,)).fetchone()
            if rep:
                from_city = (rep['city'] if 'city' in rep.keys() else '') or ''
                from_county = (rep['county'] if 'county' in rep.keys() else '') or ''
                from_province = (rep['province'] if 'province' in rep.keys() else '') or from_province

        # اگر شهر نماینده خالی بود، از مرکز استان استفاده کن (نام استان به‌عنوان شهر)
        if not from_city and from_province:
            from_city = from_province

    if not to_city and to_province:
        to_city = to_province

    return calculate_distance(
        conn,
        from_city=from_city,
        to_city=to_city,
        from_province=from_province,
        to_province=to_province,
        from_county=from_county,
        to_county=to_county,
    )


def seed_coordinates_from_json(conn, data: list) -> tuple:
    """
    data: [{name: استان, cities: [{name, latitude, longitude}, ...]}, ...]
    برمی‌گرداند: (updated, skipped, message)
    """
    ensure_distance_schema(conn)
    updated = 0
    skipped = 0

    # map province names normalized
    prov_rows = conn.execute('SELECT id, name FROM geo_provinces').fetchall()
    prov_map = {_normalize_name(r['name']): r for r in prov_rows}

    for prov in data:
        pname = _normalize_name(prov.get('name') or '')
        prow = prov_map.get(pname)
        if not prow:
            # try partial
            for k, v in prov_map.items():
                if pname in k or k in pname:
                    prow = v
                    break
        if not prow:
            skipped += len(prov.get('cities') or [])
            continue

        for city in prov.get('cities') or []:
            cname = (city.get('name') or '').strip()
            if not cname:
                continue
            try:
                lat = float(city.get('latitude') or city.get('lat') or 0)
                lng = float(city.get('longitude') or city.get('lng') or 0)
                lat, lng = _fix_coords(lat, lng)
            except (TypeError, ValueError):
                skipped += 1
                continue
            if not (24 <= lat <= 40 and 44 <= lng <= 64):
                skipped += 1
                continue

            # match city in this province
            row = conn.execute(
                '''SELECT id, name FROM geo_cities WHERE province_id = ?''',
                (prow['id'],),
            ).fetchall()
            matched = None
            cn = _normalize_name(cname)
            for r in row:
                if _normalize_name(r['name']) == cn:
                    matched = r
                    break
            if not matched:
                for r in row:
                    rn = _normalize_name(r['name'])
                    if cn in rn or rn in cn:
                        matched = r
                        break
            if matched:
                conn.execute(
                    'UPDATE geo_cities SET lat = ?, lng = ? WHERE id = ?',
                    (lat, lng, matched['id']),
                )
                updated += 1
            else:
                skipped += 1

    conn.commit()
    return updated, skipped, None


def coords_stats(conn) -> dict:
    try:
        total = conn.execute('SELECT COUNT(*) AS c FROM geo_cities').fetchone()['c']
        with_coords = conn.execute(
            'SELECT COUNT(*) AS c FROM geo_cities WHERE lat IS NOT NULL AND lng IS NOT NULL'
        ).fetchone()['c']
        return {'total_cities': total, 'with_coords': with_coords}
    except Exception:
        return {'total_cities': 0, 'with_coords': 0}
