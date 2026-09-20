# SAZGAN Offline Server Installation

هدف این بسته: نصب و به‌روزرسانی SAZGAN بدون دسترسی اینترنت در زمان نصب.

## پیش‌نیازهای سرور

- Windows 10/11 x64 یا Windows Server x64 سازگار
- دسترسی Administrator
- Python 3.11 x64 (برای نسخه فعلی سورس) روی سرور
- فایل Release کامل SAZGAN
- بسته‌های Wheel مخصوص Windows/Python 3.11 داخل `offline_packages\`
- دسترسی LAN برای اتصال Clientها به سرور

SQLite نیاز به نصب جداگانه ندارد.

## ساخت بسته آفلاین

روی یک Windows PC که یک بار اینترنت دارد اجرا کنید:

```bat
scripts\prepare_offline_bundle.bat
```

این اسکریپت Wheelهای وابستگی‌های `requirements.txt` را برای Windows x64 / CPython 3.11 دانلود و در `offline_packages\` قرار می‌دهد.

سپس کل پروژه/Release را با `offline_packages\` بسته‌بندی کنید و به سرور آفلاین منتقل کنید.

## رفتار Installer

اگر `offline_packages\` حاوی Wheel باشد، Wizard از این دستور استفاده می‌کند:

```text
pip install --no-index --find-links offline_packages -r requirements.txt
```

بنابراین در مرحله Dependency هیچ اتصال اینترنتی انجام نمی‌شود.

اگر بسته آفلاین وجود نداشته باشد، Wizard به حالت عادی آنلاین برمی‌گردد.

## نکته مهم Runtime

فایل Wheel جای Python Runtime را نمی‌گیرد. اگر سرور Python 3.11 نداشته باشد، باید Python 3.11 x64 Offline Installer نیز در پکیج تحویل قرار گیرد و قبل از اجرای Wizard نصب شود. در مرحله بعد می‌توان Runtime را هم داخل یک `SazganServerSetup.exe` واحد Bundle کرد.

## حالت آنلاین

Wizard اکنون سه حالت دارد: خودکار، آنلاین و آفلاین. در حالت آنلاین پیش‌نیازها با pip از PyPI دریافت می‌شوند و اینترنت لازم است. در حالت خودکار، اگر Wheelهای آفلاین موجود باشند از آن‌ها استفاده می‌شود؛ در غیر این صورت اتصال به PyPI بررسی می‌شود.
