#!/usr/bin/env bash
# ساخت گواهی self-signed برای سرور داخلی سازگان
# استفاده:
#   ./generate_self_signed_cert.sh 192.168.10.50
#   ./generate_self_signed_cert.sh sazgan.local
#
# خروجی دو فایل توی همین پوشه می‌سازه: sazgan.crt و sazgan.key
# این‌ها رو بعداً به nginx-sazgan.conf وصل می‌کنیم.

set -e

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo "استفاده: $0 <IP یا هاست‌نیم سرور داخلی>"
  echo "مثال:   $0 192.168.10.50"
  exit 1
fi

DAYS=730   # اعتبار ۲ ساله؛ هر ۲ سال باید دوباره بسازیش
OUT_DIR="$(cd "$(dirname "$0")" && pwd)"
CRT="$OUT_DIR/sazgan.crt"
KEY="$OUT_DIR/sazgan.key"

# تشخیص IP یا هاست‌نیم برای SAN (گواهی‌های مدرن به SAN نیاز دارن، CN تنها کافی نیست)
if [[ "$TARGET" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN="IP:$TARGET,IP:127.0.0.1"
else
  SAN="DNS:$TARGET,DNS:localhost,IP:127.0.0.1"
fi

openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$KEY" -out "$CRT" \
  -days "$DAYS" \
  -subj "/C=IR/O=Sazgan/CN=$TARGET" \
  -addext "subjectAltName=$SAN"

chmod 600 "$KEY"
chmod 644 "$CRT"

echo ""
echo "ساخته شد:"
echo "  گواهی: $CRT"
echo "  کلید:  $KEY"
echo ""
echo "این گواهی self-signed هست، یعنی مرورگرها بهش هشدار «غیرقابل‌اعتماد» می‌دن."
echo "برای رفع هشدار روی دستگاه‌های داخل شرکت، فایل sazgan.crt رو روی هر کلاینت"
echo "به‌عنوان گواهی مورد اعتماد (Trusted Root) نصب کنید."
