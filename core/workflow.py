# -*- coding: utf-8 -*-
"""مرکز واحد کنترل گردش‌کار پرونده‌های تعمیر.

هیچ route نباید برای تعمیر داخلی/خارجی مستقیماً status را تغییر دهد.
این ماژول تنها نقطه تصمیم‌گیری Transition است و update را به‌صورت
compare-and-swap انجام می‌دهد تا race condition باعث ثبت تاریخچه‌ی جعلی نشود.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.constants import (
    CLOSED_STATUSES,
    EXTERNAL_REPAIR_STATUSES,
    INTERNAL_REPAIR_STATUSES,
    FINANCE_EXTERNAL_STATUSES,
    FINANCE_INTERNAL_STATUSES,
    FINANCE_VISIT_STATUSES,
    REOPEN_ROLES,
)


class WorkflowError(ValueError):
    """خطای کسب‌وکار در Transition یا دسترسی پرونده."""


class WorkflowConflict(WorkflowError):
    """وضعیت پرونده بین خواندن و update تغییر کرده است."""


@dataclass(frozen=True)
class TransitionResult:
    request_id: int
    from_status: str
    to_status: str


def _service_key(req) -> Optional[str]:
    category = (req["request_category"] or "") if "request_category" in req.keys() else ""
    service_type = (req["service_type"] or "") if "service_type" in req.keys() else ""
    if category == "تعمیر" and service_type == "کارخانه":
        return "internal-repair"
    if category == "تعمیر" and service_type == "در محل":
        return "external-repair"
    if category == "نصب و آموزش":
        return "installation"
    if category == "بررسی و بازدید":
        return "inspection"
    return None


def _normalize_status(status: str) -> str:
    from core.constants import INTERNAL_REPAIR_LEGACY_STATUS_ALIASES
    return INTERNAL_REPAIR_LEGACY_STATUS_ALIASES.get((status or "").strip(), (status or "").strip())


# Transitionهای واقعی و مجاز. وضعیت‌های شاخه‌ای عمداً در اینجا صریح‌اند؛
# «پریدن» به یک وضعیت دلخواه مجاز نیست.
INTERNAL_TRANSITIONS = {
    "پذیرش دستگاه انجام شد": {"در انتظار تست اولیه است"},
    "در انتظار تست اولیه است": {
        "در انتظار ارسال گزارش فنی است",
        "در انتظار ارسال حواله تعمیر اولیه است",
    },
    "در انتظار ارسال حواله تعمیر اولیه است": {"در انتظار دریافت قطعه تعمیر اولیه است"},
    "در انتظار دریافت قطعه تعمیر اولیه است": {"در انتظار تعمیر اولیه است"},
    "در انتظار تعمیر اولیه است": {"در انتظار تست اولیه است"},
    "در انتظار ارسال گزارش فنی است": {"در انتظار ارسال پیش‌فاکتور است"},
    "در انتظار ارسال پیش‌فاکتور است": {"در انتظار دریافت تاییدیه پیش‌فاکتور است"},
    "در انتظار دریافت تاییدیه پیش‌فاکتور است": {
        "در انتظار ارسال حواله تعمیر نهایی است",
        "پیش‌فاکتور رد شد — ارسال به مشتری",
    },
    "در انتظار ارسال حواله تعمیر نهایی است": {"در انتظار دریافت قطعه تعمیر نهایی است"},
    "در انتظار دریافت قطعه تعمیر نهایی است": {"در انتظار گزارش نهایی است"},
    "در انتظار گزارش نهایی است": {"در انتظار تست نهایی و تحویل است"},
    "در انتظار تست نهایی و تحویل است": {
        "در انتظار خروج از کارخانه است",
        "در انتظار گزارش نهایی است",
    },
    "در انتظار خروج از کارخانه است": {"در انتظار صدور فاکتور است"},
    "در انتظار صدور فاکتور است": {"پایان تعمیرات"},
}

EXTERNAL_TRANSITIONS = {
    "در انتظار بررسی پذیرش": {"پذیرش انجام شد"},
    "پذیرش انجام شد": {"در انتظار ارسال پیش‌فاکتور است"},
    "در انتظار ارسال پیش‌فاکتور است": {"در انتظار دریافت تاییدیه پیش‌فاکتور است"},
    "در انتظار دریافت تاییدیه پیش‌فاکتور است": {
        "در انتظار ارسال حواله است",
        "پیش‌فاکتور رد شد — درخواست لغو شد",
    },
    "در انتظار ارسال حواله است": {"در انتظار دریافت قطعه در انبار استان است"},
    "در انتظار دریافت قطعه در انبار استان است": {"ماموریت در جریان (کارتابل نماینده)"},
    "ماموریت در جریان (کارتابل نماینده)": {"در انتظار بررسی گزارش توسط پذیرش است"},
    "در انتظار بررسی گزارش توسط پذیرش است": {"در انتظار ثبت شماره فاکتور است"},
    "در انتظار ثبت شماره فاکتور است": {"پایان تعمیرات"},
}

# نصب و بازدید نیز باید State Machine داشته باشند؛ فرم و Native API حق پرش
# مستقیم بین وضعیت‌ها را ندارند. برای خدمت بازدید، پرونده رایگان از مرحله انجام بازدید شروع می‌شود.
INSTALLATION_TRANSITIONS = {
    "درخواست ثبت شد": {"در انتظار انجام نصب"},
    "در انتظار انجام نصب": {"نصب انجام شد"},
    "نصب انجام شد": {"بسته شد"},
}

INSPECTION_TRANSITIONS = {
    "در انتظار ارسال پیش‌فاکتور است": {"در انتظار دریافت تاییدیه پیش‌فاکتور است"},
    "در انتظار دریافت تاییدیه پیش‌فاکتور است": {"در انتظار انجام بازدید"},
    "در انتظار انجام بازدید": {"در انتظار گزارش بازدید", "بازدید انجام شد"},
    "در انتظار گزارش بازدید": {"بازدید انجام شد"},
    "بازدید انجام شد": {"بسته شد"},
}

# وضعیت‌های read-only هر نقش در تعمیر داخلی/خارجی
INTERNAL_QC_VIEW = {
    "در انتظار تست اولیه است",
    "در انتظار تست نهایی و تحویل است",
}
INTERNAL_TECH_VIEW = {
    "در انتظار ارسال حواله تعمیر اولیه است",
    "در انتظار دریافت قطعه تعمیر اولیه است",
    "در انتظار تعمیر اولیه است",
    "در انتظار ارسال گزارش فنی است",
    "در انتظار گزارش نهایی است",
}
EXTERNAL_TECH_VIEW = {
    "ماموریت در جریان (کارتابل نماینده)",
    "در انتظار بررسی گزارش توسط پذیرش است",
}


def _row_value(row, key, default=None):
    try:
        if key in row.keys():
            return row[key]
    except Exception:
        pass
    return default


def can_view_request(user, req) -> bool:
    """کنترل object-level برای پرونده‌های تعمیر."""
    if not user or not req:
        return False
    role = user.get("role") if isinstance(user, dict) else user["role"]
    if role in ("مدیر سیستم", "مدیر", "مسئول پذیرش"):
        return True

    key = _service_key(req)
    status = _normalize_status(_row_value(req, "status", ""))
    if key == "internal-repair":
        if role == "امور مالی":
            return status in FINANCE_INTERNAL_STATUSES
        if role == "کنترل کیفیت":
            return status in INTERNAL_QC_VIEW
        if role == "تکنسین کارخانه":
            assigned_id = _row_value(req, "assigned_technician_id")
            return bool(assigned_id and int(assigned_id) == int(user.get("id") or -1) and status in INTERNAL_TECH_VIEW)
        return False

    if key == "external-repair":
        if role == "امور مالی":
            return status in FINANCE_EXTERNAL_STATUSES
        if role == "تکنسین استانی":
            assigned_id = _row_value(req, "assigned_technician_id")
            same_id = bool(assigned_id and int(assigned_id) == int(user.get("id") or -1))
            return same_id and status in EXTERNAL_TECH_VIEW
        return False
    if key == "installation":
        if role == "تکنسین استانی":
            assigned_id = _row_value(req, "assigned_technician_id")
            return bool(assigned_id and int(assigned_id) == int(user.get("id") or -1) and status == "در انتظار انجام نصب")
        return False
    if key == "inspection":
        if role == "امور مالی":
            return status in FINANCE_VISIT_STATUSES
        if role == "تکنسین استانی":
            assigned_id = _row_value(req, "assigned_technician_id")
            return bool(assigned_id and int(assigned_id) == int(user.get("id") or -1) and status in {"در انتظار انجام بازدید", "در انتظار گزارش بازدید"})
        return False
    return False


def can_act_on_request(user, req, action: str) -> bool:
    if not can_view_request(user, req):
        return False
    role = user.get("role") if isinstance(user, dict) else user["role"]
    if role in ("مدیر سیستم", "مدیر", "مسئول پذیرش"):
        return True
    key = _service_key(req)
    status = _normalize_status(_row_value(req, "status", ""))
    if role == "امور مالی":
        if key == "inspection":
            if action == "proforma_decision":
                return status == "در انتظار دریافت تاییدیه پیش‌فاکتور است"
            if action == "issue_final_invoice":
                return False
            return status in FINANCE_VISIT_STATUSES
        if action in {"proforma_decision"}:
            return status == "در انتظار دریافت تاییدیه پیش‌فاکتور است"
        if action == "issue_final_invoice":
            return status == "در انتظار صدور فاکتور است"
        return status in (FINANCE_INTERNAL_STATUSES if key == "internal-repair" else FINANCE_EXTERNAL_STATUSES)
    if key == "internal-repair" and role == "کنترل کیفیت":
        return action == "qc_report" and status in INTERNAL_QC_VIEW
    if key == "internal-repair" and role == "تکنسین کارخانه":
        return action in {"tech_report", "add_part", "edit_part", "delete_part", "receive_initial_parts", "receive_final_parts"}
    if key == "external-repair" and role == "تکنسین استانی":
        return action == "tech_report" and status in EXTERNAL_TECH_VIEW
    if key == "installation" and role == "تکنسین استانی":
        return action == "upload_report" and status == "در انتظار انجام نصب"
    if key == "inspection" and role == "تکنسین استانی":
        return action == "upload_report" and status in {"در انتظار انجام بازدید", "در انتظار گزارش بازدید"}
    return False


def allowed_next_statuses(req) -> set[str]:
    key = _service_key(req)
    current = _normalize_status(_row_value(req, "status", ""))
    if key == "internal-repair":
        return set(INTERNAL_TRANSITIONS.get(current, set()))
    if key == "external-repair":
        return set(EXTERNAL_TRANSITIONS.get(current, set()))
    if key == "installation":
        return set(INSTALLATION_TRANSITIONS.get(current, set()))
    if key == "inspection":
        return set(INSPECTION_TRANSITIONS.get(current, set()))
    return set()


def _write_status_history(conn, request_id, from_status, to_status, actor_name, note=None):
    try:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='status_history'"
        ).fetchone()
        if table:
            conn.execute(
                "INSERT INTO status_history(request_id,from_status,to_status,changed_by,changed_at,note) VALUES(?,?,?,?,?,?)",
                (request_id, from_status, to_status, actor_name, datetime.now().isoformat(timespec="seconds"), note),
            )
    except Exception:
        # تاریخچه باید fail-closed باشد؛ خطای آن نباید باعث ثبت Transition بدون history شود.
        raise


def _write_case_timeline(conn, request_id, to_status, actor_name, note=None):
    try:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='case_timeline'"
        ).fetchone()
        if table:
            conn.execute(
                "INSERT INTO case_timeline(request_id,event_type,title,body,actor_type,actor_name,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    request_id,
                    "status",
                    "تغییر وضعیت پرونده",
                    note or f"وضعیت پرونده به «{to_status}» تغییر کرد.",
                    "staff",
                    actor_name,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
    except Exception:
        raise


def transition_request(conn, request_id: int, new_status: str, *, actor_name=None, actor_role=None,
                        note=None, expected_status=None, allow_reopen=False) -> TransitionResult:
    """تغییر وضعیت اتمیک با کنترل مسیر مجاز و optimistic locking."""
    req = conn.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
    if not req:
        raise WorkflowError("پرونده یافت نشد.")

    key = _service_key(req)
    if key not in {"internal-repair", "external-repair", "installation", "inspection"}:
        raise WorkflowError("این نوع پرونده از گردش‌کار مرکزی پشتیبانی نمی‌کند.")

    current = _normalize_status(_row_value(req, "status", ""))
    target = _normalize_status(new_status)
    if not target:
        raise WorkflowError("وضعیت مقصد نامعتبر است.")
    if expected_status is not None and current != _normalize_status(expected_status):
        raise WorkflowConflict("وضعیت پرونده تغییر کرده است؛ عملیات دوباره انجام نشود.")
    if current == target:
        return TransitionResult(request_id, current, target)

    if allow_reopen:
        role = actor_role
        if role is None and actor_name:
            role_row = conn.execute("SELECT role FROM users WHERE full_name=? ORDER BY id LIMIT 1", (actor_name,)).fetchone()
            role = role_row["role"] if role_row else None
        if current not in CLOSED_STATUSES or role not in REOPEN_ROLES:
            raise WorkflowError("بازگشایی پرونده برای این وضعیت/نقش مجاز نیست.")
        # بازگشایی باید به نقطه شروع همان Workflow برگردد.
        if key == "internal-repair":
            reopen_target = INTERNAL_REPAIR_STATUSES[0]
        elif key == "external-repair":
            reopen_target = EXTERNAL_REPAIR_STATUSES[1]
        else:
            raise WorkflowError("بازگشایی برای این نوع خدمت از طریق این API پشتیبانی نمی‌شود.")
        if target != reopen_target:
            raise WorkflowError("وضعیت مقصد بازگشایی نامعتبر است.")
    else:
        allowed = allowed_next_statuses(req)
        if target not in allowed:
            raise WorkflowError(f"انتقال غیرمجاز: «{current}» → «{target}».")

    # Compare-and-swap: تغییر فقط اگر status همان وضعیت خوانده‌شده باشد.
    cur = conn.execute(
        "UPDATE requests SET status=?, status_changed_at=?, closed_at=? WHERE id=? AND status=?",
        (
            target,
            datetime.now().isoformat(timespec="seconds"),
            datetime.now().isoformat(timespec="seconds") if target in CLOSED_STATUSES else None,
            request_id,
            _row_value(req, "status", ""),
        ),
    )
    if cur.rowcount != 1:
        raise WorkflowConflict("وضعیت پرونده همزمان توسط کاربر دیگری تغییر کرده است.")

    _write_status_history(conn, request_id, current, target, actor_name, note)
    _write_case_timeline(conn, request_id, target, actor_name, note)
    return TransitionResult(request_id, current, target)


def validate_positive_quantity(value, field_name="تعداد") -> int:
    try:
        qty = int(value)
    except (TypeError, ValueError):
        raise WorkflowError(f"{field_name} باید عدد صحیح باشد.")
    if qty <= 0:
        raise WorkflowError(f"{field_name} باید بیشتر از صفر باشد.")
    return qty
