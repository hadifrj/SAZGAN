import sqlite3

import pytest

from core.migrations import _ensure_v16_workflow_integrity
from core.workflow import WorkflowError, transition_request


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            role TEXT,
            province TEXT,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE requests (
            id INTEGER PRIMARY KEY,
            customer_name TEXT,
            device_type TEXT,
            problem_desc TEXT,
            service_type TEXT,
            province TEXT,
            request_category TEXT,
            status TEXT,
            assigned_technician TEXT,
            assigned_technician_id INTEGER,
            status_changed_at TEXT,
            closed_at TEXT,
            proforma_confirmed INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0
        );
        CREATE TABLE request_parts (
            id INTEGER PRIMARY KEY,
            request_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            is_void INTEGER DEFAULT 0,
            serial_good TEXT,
            serial_defective TEXT,
            serial_healthy TEXT,
            serial_faulty TEXT,
            stage TEXT,
            notes TEXT
        );
        CREATE TABLE status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            from_status TEXT,
            to_status TEXT,
            changed_by TEXT,
            changed_at TEXT,
            note TEXT
        );
        CREATE TABLE case_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            event_type TEXT,
            title TEXT,
            body TEXT,
            actor_type TEXT,
            actor_name TEXT,
            created_at TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO users(id,full_name,role,province,is_active) VALUES(?,?,?,?,?)",
        [
            (1, "Manager", "مدیر سیستم", "تهران", 1),
            (2, "Factory Tech", "تکنسین کارخانه", "تهران", 1),
            (3, "Province Tech", "تکنسین استانی", "اصفهان", 1),
            (4, "Inactive Tech", "تکنسین استانی", "اصفهان", 0),
        ],
    )
    conn.execute(
        """INSERT INTO requests
        (id,customer_name,device_type,problem_desc,service_type,province,request_category,status)
        VALUES(?,?,?,?,?,?,?,?)""",
        (1, "C", "D", "P", "کارخانه", "تهران", "تعمیر", "پذیرش دستگاه انجام شد"),
    )
    conn.execute(
        """INSERT INTO requests
        (id,customer_name,device_type,problem_desc,service_type,province,request_category,status)
        VALUES(?,?,?,?,?,?,?,?)""",
        (2, "C", "D", "P", "در محل", "اصفهان", "تعمیر", "در انتظار بررسی پذیرش"),
    )
    _ensure_v16_workflow_integrity(conn)
    return conn


def test_legal_transition_is_atomic_and_audited():
    conn = db()
    transition_request(
        conn,
        1,
        "در انتظار تست اولیه است",
        actor_name="Manager",
        expected_status="پذیرش دستگاه انجام شد",
    )
    assert conn.execute("SELECT status FROM requests WHERE id=1").fetchone()[0] == "در انتظار تست اولیه است"
    assert conn.execute("SELECT COUNT(*) FROM status_history WHERE request_id=1").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM case_timeline WHERE request_id=1").fetchone()[0] == 1


def test_illegal_transition_is_blocked_in_domain_and_db():
    conn = db()
    transition_request(conn, 1, "در انتظار تست اولیه است", actor_name="Manager")
    with pytest.raises(WorkflowError):
        transition_request(conn, 1, "پایان تعمیرات", actor_name="Manager")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE requests SET status='پایان تعمیرات' WHERE id=1")


def test_part_quantity_and_serial_integrity():
    conn = db()
    conn.execute("INSERT INTO request_parts(id,request_id,quantity) VALUES(1,1,1)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO request_parts(id,request_id,quantity) VALUES(2,1,0)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE request_parts SET quantity=-2 WHERE id=1")
    conn.execute("UPDATE request_parts SET serial_good='SG-1', serial_defective='SD-1' WHERE id=1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO request_parts(id,request_id,quantity,serial_healthy) VALUES(3,1,1,'SG-1')")
    conn.execute("UPDATE request_parts SET is_void=1 WHERE id=1")
    conn.execute("INSERT INTO request_parts(id,request_id,quantity,serial_good) VALUES(3,1,1,'SG-1')")


def test_technician_assignment_integrity():
    conn = db()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE requests SET assigned_technician_id=3 WHERE id=1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE requests SET assigned_technician_id=4 WHERE id=2")
    conn.execute("UPDATE requests SET assigned_technician_id=2 WHERE id=1")
    conn.execute("UPDATE requests SET assigned_technician_id=3 WHERE id=2")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE requests SET province='تهران' WHERE id=2")


def test_reopen_uses_only_workflow_targets():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE users(id INTEGER PRIMARY KEY, full_name TEXT, role TEXT, province TEXT, is_active INTEGER DEFAULT 1);
        CREATE TABLE requests(id INTEGER PRIMARY KEY, request_category TEXT, service_type TEXT, province TEXT, status TEXT, assigned_technician_id INTEGER, status_changed_at TEXT, closed_at TEXT);
        CREATE TABLE request_parts(id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL, quantity INTEGER NOT NULL DEFAULT 1, is_void INTEGER DEFAULT 0, serial_good TEXT, serial_defective TEXT, serial_healthy TEXT, serial_faulty TEXT);
        CREATE TABLE status_history(id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER, from_status TEXT, to_status TEXT, changed_by TEXT, changed_at TEXT, note TEXT);
        CREATE TABLE case_timeline(id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER, event_type TEXT, title TEXT, body TEXT, actor_type TEXT, actor_name TEXT, created_at TEXT);
    """)
    conn.execute("INSERT INTO users VALUES(1,'Manager','مدیر سیستم','تهران',1)")
    conn.execute("INSERT INTO requests VALUES(1,'تعمیر','کارخانه','تهران','پایان تعمیرات',NULL,NULL,NULL)")
    conn.execute("INSERT INTO requests VALUES(2,'تعمیر','در محل','اصفهان','پیش‌فاکتور رد شد — درخواست لغو شد',NULL,NULL,NULL)")
    _ensure_v16_workflow_integrity(conn)
    transition_request(conn, 1, 'پذیرش دستگاه انجام شد', actor_name='Manager', allow_reopen=True)
    transition_request(conn, 2, 'پذیرش انجام شد', actor_name='Manager', allow_reopen=True)
    with pytest.raises(WorkflowError):
        transition_request(conn, 1, 'در انتظار تست اولیه است', actor_name='Manager', allow_reopen=True)


def test_repair_conversion_from_non_repair_is_allowed_once():
    conn = db()
    conn.execute(
        """INSERT INTO requests
        (id,customer_name,device_type,problem_desc,service_type,province,request_category,status)
        VALUES(?,?,?,?,?,?,?,?)""",
        (10, "C", "D", "P", "در محل", "اصفهان", "اعلام خرابی", "در انتظار بررسی"),
    )
    conn.execute(
        "UPDATE requests SET request_category='تعمیر', status='پذیرش انجام شد' WHERE id=10"
    )
    transition_request(conn, 2, "پذیرش انجام شد", actor_name="Manager", expected_status="در انتظار بررسی پذیرش")
