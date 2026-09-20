# -*- coding: utf-8 -*-
"""Unit tests for critical Sazgan core logic using temporary SQLite databases."""
from __future__ import annotations

import sqlite3

import pytest

from core.access import enforce_path_access, is_system_admin, user_has_access
from core.distance import calculate_distance, haversine_km, seed_coordinates_from_json
from core.wages import compute_repair_wage, ensure_wage_schema, seed_default_wage_rates


def sqlite_memory():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_haversine_known_distance():
    distance = haversine_km(0, 0, 0, 1)
    assert distance == pytest.approx(111.195, rel=1e-4)


def test_road_factor_is_applied_to_haversine_distance():
    conn = sqlite_memory()
    conn.execute("""
        CREATE TABLE geo_provinces (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
        )
    """)
    conn.execute("""
        CREATE TABLE geo_counties (
            id INTEGER PRIMARY KEY, province_id INTEGER NOT NULL, name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE geo_cities (
            id INTEGER PRIMARY KEY, province_id INTEGER NOT NULL,
            county_id INTEGER NOT NULL, name TEXT, lat REAL, lng REAL
        )
    """)
    conn.execute("INSERT INTO geo_provinces(id, name) VALUES (1, 'تهران')")
    conn.execute("INSERT INTO geo_counties(id, province_id, name) VALUES (1, 1, 'تهران')")
    conn.execute("INSERT INTO geo_cities(id, province_id, county_id, name, lat, lng) VALUES (1,1,1,'مبدأ',0,0)")
    conn.execute("INSERT INTO geo_cities(id, province_id, county_id, name, lat, lng) VALUES (2,1,1,'مقصد',0,1)")
    conn.commit()

    result = calculate_distance(conn, 'مبدأ', 'مقصد', 'تهران', 'تهران', road_factor=1.5)
    assert result['ok'] is True
    assert result['road_km'] == pytest.approx(result['air_km'] * 1.5, abs=0.2)
    assert result['round_trip_km'] == pytest.approx(result['road_km'] * 2, abs=0.2)


def test_seed_coordinates_from_json_updates_matching_city():
    conn = sqlite_memory()
    conn.execute("CREATE TABLE geo_provinces (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
    conn.execute("CREATE TABLE geo_counties (id INTEGER PRIMARY KEY, province_id INTEGER NOT NULL, name TEXT)")
    conn.execute("CREATE TABLE geo_cities (id INTEGER PRIMARY KEY, province_id INTEGER NOT NULL, county_id INTEGER NOT NULL, name TEXT, lat REAL, lng REAL)")
    conn.execute("INSERT INTO geo_provinces(id, name) VALUES (1, 'تهران')")
    conn.execute("INSERT INTO geo_counties(id, province_id, name) VALUES (1, 1, 'تهران')")
    conn.execute("INSERT INTO geo_cities(id, province_id, county_id, name) VALUES (1,1,1,'تهران')")
    conn.commit()

    updated, skipped, message = seed_coordinates_from_json(
        conn,
        [{"name": "تهران", "cities": [{"name": "تهران", "latitude": 35.6892, "longitude": 51.3890}]}],
    )
    row = conn.execute("SELECT lat, lng FROM geo_cities WHERE id=1").fetchone()
    assert (updated, skipped, message) == (1, 0, None)
    assert row['lat'] == pytest.approx(35.6892)
    assert row['lng'] == pytest.approx(51.3890)


def test_repair_wage_calculation_uses_default_rates_and_local_travel():
    conn = sqlite_memory()
    conn.execute("""
        CREATE TABLE representatives (
            id INTEGER PRIMARY KEY, rep_type TEXT, company_name TEXT,
            first_name TEXT, last_name TEXT, city TEXT, province TEXT, county TEXT
        )
    """)
    conn.execute(
        "INSERT INTO representatives VALUES (1, 'حقیقی', NULL, 'علی', 'رضایی', 'تهران', 'تهران', '')"
    )
    ensure_wage_schema(conn)
    seed_default_wage_rates(conn)

    result = compute_repair_wage(
        conn,
        representative_id=1,
        customer_city='تهران',
        customer_province='تهران',
        device_count=2,
        include_travel=True,
    )

    assert result['ok'] is True
    assert result['is_local'] is True
    assert result['service_amount'] == 11_000_000
    assert result['travel_amount'] == 2_500_000
    assert result['total'] == 13_500_000


def test_role_access_and_system_admin_rules():
    finance = {'role': 'امور مالی', 'username': 'finance1'}
    technician = {'role': 'تکنسین استانی', 'username': 'tech1'}
    admin = {'role': 'کاربر عادی', 'username': 'admin'}

    assert user_has_access(finance, 'finance') is True
    assert user_has_access(finance, 'system') is False
    assert user_has_access(technician, 'finance') is False
    assert is_system_admin(admin) is True
    assert enforce_path_access(technician, '/finance/') is False
    assert enforce_path_access(technician, '/login') is True
