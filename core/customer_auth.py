# -*- coding: utf-8 -*-
"""احراز هویت مشتری — بدون رمز عبور.

مشتری با «شماره موبایل» + «کد پیگیری» وارد می‌شود؛ کد می‌تواند ``tracking_code`` برای اعلام خرابیِ هنوز پذیرش‌نشده یا ``reception_no`` برای پروندهٔ پذیرش‌شده باشد. هیچ رمز عبوری ذخیره/بررسی نمی‌شود؛ دانستن
هر دو مقدار با هم (که فقط در برگه تحویل/پیامک به مشتری داده می‌شود) برای
ورود کافی است.
"""
from __future__ import annotations

import re
from typing import Optional


def normalize_phone(phone: str) -> str:
    """اعداد فارسی/عربی و کاراکترهای غیرعددی را حذف و فرمت را یکدست می‌کند."""
    if not phone:
        return ""
    # ارقام فارسی/عربی → لاتین
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    table = {}
    for i, d in enumerate(persian_digits):
        table[d] = str(i)
    for i, d in enumerate(arabic_digits):
        table[d] = str(i)
    phone = "".join(table.get(ch, ch) for ch in phone)

    digits = re.sub(r"[^0-9]", "", phone)
    if digits.startswith("0098"):
        digits = digits[4:]
    if digits.startswith("98") and len(digits) > 10:
        digits = digits[2:]
    if digits and not digits.startswith("0") and len(digits) == 10:
        digits = "0" + digits
    return digits


def normalize_code(code: str) -> str:
    return (code or "").strip().upper().replace(" ", "")


def find_request_by_phone_and_code(conn, phone: str, code: str):
    """پرونده‌ای که هم شماره موبایل و هم کد پیگیری با آن مطابقت دارد را برمی‌گرداند."""
    phone_n = normalize_phone(phone)
    code_n = normalize_code(code)
    if not phone_n or not code_n:
        return None

    row = conn.execute(
        "SELECT * FROM requests WHERE customer_phone=? AND (reception_no=? OR tracking_code=?)",
        (phone_n, code_n, code_n),
    ).fetchone()
    if row:
        return row

    # مقایسهٔ انعطاف‌پذیر برای شماره‌های ذخیره‌شده بدون صفر ابتدایی
    alt = phone_n[1:] if phone_n.startswith("0") else ("0" + phone_n)
    row = conn.execute(
        "SELECT * FROM requests WHERE customer_phone=? AND (reception_no=? OR tracking_code=?)",
        (alt, code_n, code_n),
    ).fetchone()
    return row


def get_verified_request(conn, request_id: int, phone: str) -> Optional[dict]:
    """برای بارگذاری مجدد جزئیات یک پرونده که قبلاً در سشن تأیید شده است."""
    phone_n = normalize_phone(phone)
    row = conn.execute(
        "SELECT * FROM requests WHERE id=? AND customer_phone=?",
        (request_id, phone_n),
    ).fetchone()
    if row:
        return row
    alt = phone_n[1:] if phone_n.startswith("0") else ("0" + phone_n)
    row = conn.execute(
        "SELECT * FROM requests WHERE id=? AND customer_phone=?",
        (request_id, alt),
    ).fetchone()
    return row
