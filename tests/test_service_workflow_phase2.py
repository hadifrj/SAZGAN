import sqlite3

import pytest

from core.migrations import _ensure_v17_service_workflow_integrity
from core.workflow import WorkflowError, can_view_request, transition_request


def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE users(id INTEGER PRIMARY KEY, full_name TEXT, role TEXT, province TEXT, is_active INTEGER DEFAULT 1);
    CREATE TABLE requests(
        id INTEGER PRIMARY KEY, request_category TEXT, request_subtype TEXT, service_type TEXT,
        province TEXT, status TEXT, assigned_technician_id INTEGER, status_changed_at TEXT, closed_at TEXT
    );
    CREATE TABLE status_history(id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER, from_status TEXT, to_status TEXT, changed_by TEXT, changed_at TEXT, note TEXT);
    CREATE TABLE case_timeline(id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER, event_type TEXT, title TEXT, body TEXT, actor_type TEXT, actor_name TEXT, created_at TEXT);
    """)
    _ensure_v17_service_workflow_integrity(c)
    return c


def test_installation_transition_and_db_guard():
    c = conn()
    c.execute("INSERT INTO requests VALUES(1,'نصب و آموزش','درخواست نصب','در محل','تهران','درخواست ثبت شد',NULL,NULL,NULL)")
    transition_request(c,1,'در انتظار انجام نصب',actor_name='Manager',expected_status='درخواست ثبت شد')
    transition_request(c,1,'نصب انجام شد',actor_name='Manager',expected_status='در انتظار انجام نصب')
    with pytest.raises(WorkflowError):
        transition_request(c,1,'درخواست ثبت شد',actor_name='Manager')
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("UPDATE requests SET status='درخواست ثبت شد' WHERE id=1")


def test_inspection_paid_flow_and_direct_jump_block():
    c = conn()
    c.execute("INSERT INTO requests VALUES(2,'بررسی و بازدید','درخواست بازدید','در محل','اصفهان','در انتظار ارسال پیش‌فاکتور است',NULL,NULL,NULL)")
    transition_request(c,2,'در انتظار دریافت تاییدیه پیش‌فاکتور است',actor_name='Manager')
    transition_request(c,2,'در انتظار انجام بازدید',actor_name='Manager')
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("UPDATE requests SET status='در انتظار ارسال پیش‌فاکتور است' WHERE id=2")
    transition_request(c,2,'در انتظار گزارش بازدید',actor_name='Manager')
    transition_request(c,2,'بازدید انجام شد',actor_name='Manager')


def test_assigned_technician_can_only_view_own_active_step():
    c = conn()
    c.execute("INSERT INTO users VALUES(2,'Tech','تکنسین استانی','تهران',1)")
    c.execute("INSERT INTO requests VALUES(3,'نصب و آموزش','درخواست نصب','در محل','تهران','در انتظار انجام نصب',2,NULL,NULL)")
    row=c.execute("SELECT * FROM requests WHERE id=3").fetchone()
    assert can_view_request({'id':2,'role':'تکنسین استانی'},row) is True
    c.execute("UPDATE requests SET status='نصب انجام شد' WHERE id=3")
    row=c.execute("SELECT * FROM requests WHERE id=3").fetchone()
    assert can_view_request({'id':2,'role':'تکنسین استانی'},row) is False


def test_finance_can_view_inspection_without_name_error_and_actions_use_visit_statuses():
    c = conn()
    c.execute("INSERT INTO requests VALUES(4,'بررسی و بازدید','درخواست بازدید','در محل','تهران','در انتظار ارسال پیش‌فاکتور است',NULL,NULL,NULL)")
    row = c.execute("SELECT * FROM requests WHERE id=4").fetchone()
    finance = {'id': 10, 'role': 'امور مالی'}
    assert can_view_request(finance, row) is True
    # در مرحله ارسال پیش‌فاکتور، مالی فقط پرونده را می‌بیند؛ تصمیم تایید/رد در مرحله بعد مجاز است.
    assert __import__('core.workflow', fromlist=['can_act_on_request']).can_act_on_request(finance, row, 'proforma_decision') is False
    c.execute("UPDATE requests SET status='در انتظار دریافت تاییدیه پیش‌فاکتور است' WHERE id=4")
    row = c.execute("SELECT * FROM requests WHERE id=4").fetchone()
    wf = __import__('core.workflow', fromlist=['can_act_on_request'])
    assert wf.can_view_request(finance, row) is True
    assert wf.can_act_on_request(finance, row, 'proforma_decision') is True
