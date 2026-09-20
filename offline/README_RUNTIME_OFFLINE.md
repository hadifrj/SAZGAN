# Python Runtime - Offline

برای نصب کاملاً آفلاین سرور، فایل رسمی CPython 3.11.9 x64 را در مسیر زیر قرار دهید:

`runtime\python-3.11.9-amd64.exe`

اگر فایل وجود داشته باشد، Wizard آن را بدون اینترنت و به‌صورت silent نصب می‌کند. اگر Python 3.11 از قبل نصب باشد، دوباره نصب نمی‌شود.

برای ساخت بسته Runtime روی یک سیستم متصل به اینترنت:

`scripts\prepare_runtime.bat`

سپس کل پوشه `runtime` را همراه Release به سرور آفلاین منتقل کنید.
