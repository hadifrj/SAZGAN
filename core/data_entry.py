"""
Sazgan V2.5 Data Entry helpers.
Validation and test-database bootstrap for manual data entry.
"""
from __future__ import annotations
import re, sqlite3
from pathlib import Path
from typing import Any, Dict

PHONE_RE=re.compile(r"^[0-9+\-\s()]{7,20}$")
MOBILE_RE=re.compile(r"^(?:\+98|0098|98|0)?9\d{9}$")
POSTAL_RE=re.compile(r"^\d{10}$")

def validate_customer(data: Dict[str,Any]) -> Dict[str,Any]:
    errors={}
    name=str(data.get("name") or "").strip()
    if not name: errors["name"]="نام مشتری الزامی است"
    if data.get("phone") and not PHONE_RE.match(str(data["phone"]).strip()):
        errors["phone"]="فرمت تلفن صحیح نیست"
    if data.get("mobile"):
        m=re.sub(r"[\s\-]","",str(data["mobile"]))
        if not MOBILE_RE.match(m): errors["mobile"]="فرمت موبایل صحیح نیست"
    if data.get("postal_code") and not POSTAL_RE.match(re.sub(r"\s","",str(data["postal_code"]))):
        errors["postal_code"]="کد پستی باید ۱۰ رقم باشد"
    ctype=str(data.get("customer_type") or "").strip()
    if ctype and ctype not in ("شخص","شرکت"):
        errors["customer_type"]="نوع مشتری باید شخص یا شرکت باشد"
    return {"ok":not errors,"errors":errors}

def validate_equipment(data: Dict[str,Any]) -> Dict[str,Any]:
    errors={}
    if not str(data.get("name") or "").strip(): errors["name"]="نام تجهیز الزامی است"
    if not str(data.get("serial") or "").strip(): errors["serial"]="سریال الزامی است"
    return {"ok":not errors,"errors":errors}

def validate_service(data: Dict[str,Any]) -> Dict[str,Any]:
    errors={}
    if not str(data.get("service_type") or "").strip(): errors["service_type"]="نوع سرویس الزامی است"
    if not str(data.get("date") or "").strip(): errors["date"]="تاریخ سرویس الزامی است"
    return {"ok":not errors,"errors":errors}

