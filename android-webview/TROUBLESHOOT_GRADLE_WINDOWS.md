# خطای «Could not initialize native services» / gradle-fileevents.dll

## چرا این خطا می‌افته
این خطا از **کد این پروژه نمی‌آد** — سرویس بومی پایش فایل (native file-watch) گریدل
روی ویندوزتونه که فایلش (`gradle-fileevents.dll`) یا خراب دانلود شده، یا با یه
نسخه‌ی دیگه‌ی گریدل قاطی شده، یا آنتی‌ویروس دست‌کاریش کرده.

نکته‌ی مهم دیگه: این پروژه فایل `gradle-wrapper` نداشت، یعنی هر بار با هر نسخه‌ی
گریدلی که رو سیستم شما نصب/کش شده (این‌جا `9.3.0`) اجرا می‌شد. `com.android.application 8.2.0`
رسماً برای گریدل `8.2` تست شده، نه `9.3.0` — پس حتی بعد از رفع این خطا ممکنه به
مشکل سازگاری بعدی بخورید.

## کاری که همین الان تو پروژه انجام شد
تو `android-webview/gradle.properties` این خط اضافه شد:
```
org.gradle.vfs.watch=false
```
این سرویس پایش فایل (همونی که کرش می‌کنه) رو کلاً خاموش می‌کنه. برای بیلد
یک‌باره/APK گرفتن هیچ افتی نداره؛ فقط auto-rebuild زنده (که این‌جا استفاده نمی‌شه)
غیرفعال می‌مونه.

## قدم‌هایی که باید رو ویندوز خودتون بزنید

### ۱. کش خراب رو پاک کنید (مهم‌ترین قدم)
همه‌ی پنجره‌های Android Studio رو ببندید، بعد تو PowerShell:
```powershell
Get-Process | Where-Object {$_.ProcessName -like "*java*" -or $_.ProcessName -like "*gradle*"} | Stop-Process -Force
Remove-Item -Recurse -Force "$env:USERPROFILE\.gradle\native"
Remove-Item -Recurse -Force "$env:USERPROFILE\.gradle\daemon"
```
بعد Android Studio رو باز کنید و دوباره Sync/Build بگیرید — گریدل خودش دوباره
دانلودش می‌کنه.

### ۲. اگه هنوز خطا داد: آنتی‌ویروس رو چک کنید
پوشه‌ی `%USERPROFILE%\.gradle` رو به Exclusion لیست Windows Defender (یا آنتی‌ویروس
دیگه‌تون) اضافه کنید، بعد دوباره قدم ۱ رو تکرار کنید.

### ۳. برای جلوگیری از این مشکل در آینده: نسخه‌ی گریدل رو تو خودِ پروژه قفل کنید
یه بار این دستور رو تو پوشه‌ی `android-webview` اجرا کنید (با همون گریدل نصب‌شده‌تون؛
فرقی نداره چه نسخه‌ای نصبه، فقط برای ساختن wrapper استفاده می‌شه):
```powershell
cd android-webview
gradle wrapper --gradle-version 8.2 --distribution-type all
```
این کار یه پوشه‌ی `gradle/wrapper/` و فایل‌های `gradlew.bat`/`gradlew` می‌سازه که
نسخه‌ی گریدل رو دقیقاً رو `8.2` (نسخه‌ی سازگار با `com.android.application 8.2.0`)
قفل می‌کنه. از این به بعد Android Studio همیشه از همین نسخه استفاده می‌کنه، صرف‌نظر
از این‌که رو سیستم چی نصبه — و این‌جور مشکلات سازگاری نسخه دیگه پیش نمیاد.
بعد از این دستور، فایل‌های ساخته‌شده (`gradlew`, `gradlew.bat`, پوشه‌ی
`gradle/wrapper/`) رو نگه دارید و همراه پروژه commit/ذخیره کنید.
