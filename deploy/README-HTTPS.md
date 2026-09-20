# راه‌اندازی HTTPS با گواهی Self-Signed

سرور سازگان با `waitress` اجرا میشه که خودش HTTPS رو ساپورت نمی‌کنه؛ برای همین یه
nginx جلوش می‌ذاریم که TLS رو handle کنه و به waitress (روی 127.0.0.1:5000) پاس بده.

## مراحل

1. **ساخت گواهی** (روی خود سرور، با IP ثابت داخلی‌تون):
   ```bash
   cd deploy
   ./generate_self_signed_cert.sh 192.168.10.50   # IP واقعی سرورتون
   ```
   دو فایل `sazgan.crt` و `sazgan.key` ساخته میشه.

2. **نصب nginx** (اگه از قبل نیست):
   ```bash
   sudo apt install nginx
   ```

3. **کپی گواهی‌ها:**
   ```bash
   sudo mkdir -p /etc/nginx/ssl
   sudo cp sazgan.crt sazgan.key /etc/nginx/ssl/
   sudo chmod 600 /etc/nginx/ssl/sazgan.key
   ```

4. **فعال‌سازی کانفیگ:**
   - `nginx-sazgan.conf` رو باز کن و `SAZGAN_SERVER_NAME` رو با IP یا هاست‌نیم واقعی جایگزین کن
   - کپی به `/etc/nginx/sites-available/sazgan` و لینک به `sites-enabled`
   - `sudo nginx -t && sudo systemctl reload nginx`

5. **تنظیم اپ فلسک** — این دو متغیر محیطی رو قبل از اجرای اپ ست کن:
   ```bash
   export SAZGAN_BEHIND_PROXY=1      # فلسک اسکیم HTTPS رو از هدر nginx بخونه
   export SAZGAN_SESSION_SECURE=1    # کوکی نشست فقط روی HTTPS ارسال بشه
   export SAZGAN_HOST=127.0.0.1      # waitress فقط لوکال گوش بده (nginx جلوشه)
   ```
   بعد مثل قبل اجرا کن: `python3 app.py`

## نکات مهم

- چون گواهی **self-signed** هست، اولین بار که هر کاربر با مرورگر وارد میشه یه هشدار
  «اتصال امن نیست» می‌بینه. این طبیعیه. برای رفعش، فایل `sazgan.crt` رو روی هر
  کامپیوتر داخل شرکت به‌عنوان گواهی مورد اعتماد (Trusted Root Certificate) نصب کنید.
- گواهی ۲ سال اعتبار داره؛ بعدش باید دوباره با اسکریپت بسازیدش (تاریخ انقضا رو یادداشت کنید).
- بعد از فعال بودن HTTPS، هدر **HSTS** به‌صورت خودکار فعال میشه (توی `core/security.py`) —
  یعنی از دفعه‌ی دوم به بعد، مرورگر خودش مسیر HTTP رو به HTTPS تبدیل می‌کنه و اجازه‌ی
  داون‌گرید نمی‌ده.
- **Certificate Pinning** عمداً پیاده نشد: امروز مرورگرها از HPKP (نسخه‌ی قدیمی pinning
  توی مرورگر) پشتیبانی نمی‌کنن (Chrome از ۲۰۱۸ حذفش کرده) چون ریسک قفل‌شدن دائمی کاربرها
  از سایت رو داشت. HSTS همون محافظتی که لازم دارید (اجبار HTTPS) رو بدون اون ریسک میده.
  اگه بعداً یه اپ موبایل یا کلاینت اختصاصی برای سازگان ساختید که باید دقیقاً همین گواهی
  رو تشخیص بده، اون‌موقع pinning توی خود اون کلاینت معنی پیدا می‌کنه.
