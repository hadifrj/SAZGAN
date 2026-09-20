# -*- coding: utf-8 -*-
"""متن‌های راهنمای فرم‌ها (آیکون i کنار سربرگ‌ها).

هر آیتم یک کلید، یک برچسب برای صفحه تنظیمات، و متن پیش‌فرض دارد.
مقدار «فعلی» هر کلید در app_settings با پیشوند help_tip_ ذخیره می‌شود؛
اگر ذخیره نشده باشد، متن پیش‌فرض همین‌جا استفاده می‌شود.
"""
from __future__ import annotations

HELP_TIP_CATALOG = {
    "quick_report_upload": {
        "label": "آپلود سریع گزارش نماینده — سربرگ فرم",
        "default": "با انتخاب فایل، گوشی خودش گزینهٔ «دوربین» یا «گالری/فایل‌ها» رو نشون می‌ده.",
    },
    "account_photo": {
        "label": "حساب کاربری — عکس پروفایل",
        "default": "انتخاب عکس → تنظیم کادر → تأیید برش → ذخیره عکس",
    },
    "account_finance": {
        "label": "حساب کاربری — اطلاعات مالی نماینده",
        "default": "شماره کارت و شبا برای تسویه دستمزد نماینده",
    },
    "account_profile_photo": {
        "label": "ویرایش کاربر (ادمین) — تغییر عکس پروفایل",
        "default": "عکس را انتخاب کنید → کادر را تنظیم کنید → تأیید برش → ذخیره عکس",
    },
    "edit_user_photo": {
        "label": "ویرایش کاربر — فرمت عکس",
        "default": "فرمت‌های مجاز: jpg, jpeg, png",
    },
    "backups_intro": {
        "label": "پشتیبان‌گیری — سربرگ صفحه",
        "default": "بکاپ شامل <strong>دیتابیس</strong> و <strong>پیوست‌ها</strong> است و فایل <code>.zip</code> هم ساخته می‌شود.",
    },
    "backup_network_path": {
        "label": "پشتیبان‌گیری — مسیر شبکه/محلی",
        "default": "اگر مسیر پر باشد، بعد از هر بکاپ یک کپی هم آنجا ذخیره می‌شود.",
    },
    "bale_test": {
        "label": "اتصال بله — ارسال پیام آزمایشی",
        "default": "نمونه chat_id عددی است (مثل 1931422408). قبل از تست Token را ذخیره و در صورت نیاز ربات را روشن کنید. پیام تست: «تست اعلان سازگان»",
    },
    "company_logo": {
        "label": "تنظیمات شرکت — لوگو",
        "default": "این لوگو کنار دکمه منو در بالای صفحات نمایش داده می‌شود. ترجیحاً تصویر مربعی استفاده کنید.",
    },
    "company_info": {
        "label": "تنظیمات شرکت — اطلاعات تماس",
        "default": "نام، آدرس، کد پستی و تلفن شرکت برای چاپ بیجک (فرستنده) استفاده می‌شود. موبایل پشتیبانی در صفحه ورود نمایش داده می‌شود.",
    },
    "wage_manual": {
        "label": "دستمزد — ثبت دستی (موارد غیرپذیرش)",
        "default": (
            "برای <strong>آموزش، تحویل کالا، سوکت‌زنی</strong> و سایر آیتم‌هایی که پرونده پذیرش ندارند. "
            "پرونده‌های تعمیر/بازدید/نصب پس از مختومه شدن <strong>خودکار</strong> در دستمزد ماهانه ثبت می‌شوند."
        ),
    },
    "wage_no_rep": {
        "label": "دستمزد — پیام نبود نماینده",
        "default": "هنوز نماینده فعالی ثبت نشده. از تنظیمات → نمایندگی‌ها اضافه کنید.",
    },
    "wages_table": {
        "label": "جدول دستمزد — سربرگ صفحه",
        "default": (
            "نرخ‌ها سالانه قابل ویرایش‌اند. تعمیر: مبلغ محل نمایندگی و خارج محل جداست. "
            "ایاب داخل شهر مبلغ ثابت؛ بین‌شهری = کیلومتر رفت‌وبرگشت × نرخ هر کیلومتر. "
            "شهر نماینده از اطلاعات نمایندگی و شهر مشتری از طرف‌حساب خوانده می‌شود."
        ),
    },
    "activation_help": {
        "label": "فعال‌سازی نرم‌افزار — سربرگ صفحه",
        "default": "کلید فعال‌سازی را از پشتیبانی سازگان دریافت کنید. پس از ثبت موفق، وضعیت در همین صفحه نمایش داده می‌شود.",
    },
    "finance_cartable_intro": {
        "label": "کارتابل امور مالی — سربرگ صفحه",
        "default": "فقط پرونده‌هایی که در مراحل مالی هستند نمایش داده می‌شوند. اطلاعات تعمیر از همان فرم پرونده خوانده می‌شود.",
    },
    "distance_intro": {
        "label": "محاسبه مسافت — سربرگ صفحه",
        "default": (
            "محاسبه <strong>مسافت تقریبی جاده‌ای</strong> و <strong>رفت‌وبرگشت</strong> بین شهر نماینده و شهر مشتری. "
            "روش: فاصله هوایی × ضریب جاده (پیش‌فرض ۱٫۳۰). از تب نقشه هم می‌توان شهر مقصد را انتخاب کرد."
        ),
    },
    "geo_intro": {
        "label": "استان / شهر و مسافت — سربرگ صفحه",
        "default": (
            "نقشه تعاملی ایران: روی استان کلیک کنید تا لیست شهرها باز شود. "
            "تب <strong>مسافت</strong> فاصله تقریبی جاده‌ای و رفت‌وبرگشت را حساب می‌کند. "
            "ورود اکسل فقط از <a href=\"/settings/data-hub\"><strong>Export / Import</strong></a>."
        ),
    },
    "warehouse_external_intro": {
        "label": "کنترل قطعات نمایندگان — سربرگ صفحه",
        "default": "فقط جدول کنترلی برای رهگیری قطعات نزد نمایندگان. موجودی انبار مدیریت نمی‌شود. هر قطعه با شماره پذیرش و سریال ورودی/داغی قابل رهگیری است.",
    },
    "warehouse_internal_intro": {
        "label": "کنترل قطعات تعمیرات داخلی — سربرگ صفحه",
        "default": "این بخش انبار نیست. فقط سوابق مصرف و رهگیری قطعات روی شماره پذیرش ثبت می‌شود. سریال قطعه ورودی و سریال داغی الزامی است و هر قطعه به شماره پذیرش مرتبط می‌شود.",
    },
    "customer_picker": {
        "label": "انتخاب مشتری — فیلد نام مشتری",
        "default": (
            "نام مشتری فقط از <strong>طرف‌حساب‌های ثبت‌شده</strong> انتخاب می‌شود؛ تایپ نام دلخواه مجاز نیست. "
            "با دکمه «نام مشتری» پنجره باز می‌شود: فیلتر استان و شهر + جستجوی نام. "
            "پس از انتخاب، استان و آدرس خودکار پر می‌شوند."
        ),
    },
    "ca_new_request": {
        "label": "امور مشتریان — درخواست جدید",
        "default": (
            "برای ثبت درخواست، ابتدا مشتری را از لیست طرف‌حساب انتخاب کنید. "
            "اگر مشتری در لیست نیست، اول در تنظیمات → طرف‌حساب‌ها ثبتش کنید."
        ),
    },
    "activate_warranty_calc": {
        "label": "فعال‌سازی گارانتی — نحوه محاسبه",
        "default": "تاریخ اتمام گارانتی به‌صورت خودکار از تاریخ نصب + مدت محاسبه می‌شود و وضعیت «فعال» می‌شود.",
    },
}

# سازگاری با کد قدیمی‌تر که مستقیم DEFAULT_HELP_TIPS را می‌خواند
DEFAULT_HELP_TIPS = {k: v["default"] for k, v in HELP_TIP_CATALOG.items()}

_SETTING_PREFIX = "help_tip_"

# --- Sanitization -----------------------------------------------------
# متن راهنما در قالب با فیلتر |safe رندر می‌شود (چون بعضی پیش‌فرض‌ها عمداً
# از تگ‌های ساده مثل <strong> و <code> استفاده می‌کنند). برای اینکه یک
# کاربر با دسترسی ویرایش راهنماها نتواند XSS ذخیره‌شده تزریق کند (که در
# مرورگر هر کاربر لاگین‌شده‌ای، از جمله مدیر سیستم، اجرا می‌شود)، هر متنی
# که ذخیره می‌شود از یک فیلتر مجاز (allowlist) عبور می‌کند: فقط چند تگ
# فرمت‌دهی ساده و بدون هیچ attribute مجازند؛ هر تگ دیگر (script, iframe,
# on*=، href با javascript: و ...) کامل حذف می‌شود.
import re as _re_sanitize

_ALLOWED_TAGS = {"strong", "b", "em", "i", "code", "br", "ul", "ol", "li", "small", "u"}
_TAG_RE = _re_sanitize.compile(r"</?\s*([a-zA-Z0-9]+)([^>]*)>")


def _sanitize_help_html(text: str) -> str:
    if not text:
        return ""

    def _replace(match: "_re_sanitize.Match[str]") -> str:
        tag = match.group(1).lower()
        if tag not in _ALLOWED_TAGS:
            return ""
        is_closing = match.group(0).startswith("</")
        if tag == "br":
            return "<br>"
        return f"</{tag}>" if is_closing else f"<{tag}>"

    return _TAG_RE.sub(_replace, text)


def get_help_tip(conn, key: str, default: str | None = None) -> str:
    """خواندن متن راهنما؛ اگر در تنظیمات ذخیره شده باشد همان برمی‌گردد."""
    if not key:
        return default or ""
    try:
        from core.db import get_setting
        raw = get_setting(conn, _SETTING_PREFIX + key, "") or ""
        if raw.strip():
            return _sanitize_help_html(raw.strip())
    except Exception:
        pass
    if default:
        return default
    return HELP_TIP_CATALOG.get(key, {}).get("default", "")


def set_help_tip(conn, key: str, text: str) -> None:
    """ذخیره متن راهنمای سفارشی؛ متن خالی یعنی بازگشت به پیش‌فرض (حذف override).
    متن قبل از ذخیره پاکسازی می‌شود تا امکان XSS ذخیره‌شده وجود نداشته باشد."""
    from core.db import set_setting
    clean = _sanitize_help_html((text or "").strip())
    set_setting(conn, _SETTING_PREFIX + key, clean)


def list_help_tips(conn):
    """فهرست همه راهنماها به‌همراه متن فعلی (سفارشی یا پیش‌فرض) برای صفحه تنظیمات."""
    from core.db import get_setting
    items = []
    for key, meta in HELP_TIP_CATALOG.items():
        custom = (get_setting(conn, _SETTING_PREFIX + key, "") or "").strip()
        items.append({
            "key": key,
            "label": meta["label"],
            "default": meta["default"],
            "current": custom or meta["default"],
            "is_custom": bool(custom),
        })
    items.sort(key=lambda x: x["label"])
    return items
