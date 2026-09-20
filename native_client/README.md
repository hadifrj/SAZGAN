# Sazgan Native Client (PyQt5)

کلاینت بومی PyQt5 برای جریان‌های کارمندی سامانه سازگان. این نسخه مبنای فاز نهایی هم‌ترازی Native با وب است؛ منطق Login/Backend نسخه سالم حفظ شده و تغییرات این فاز روی UI، پوشش جریان‌ها و رفتار Native اعمال شده‌اند.

## وضعیت فاز نهایی — اجرای Gap Prompt 2026-08-20

| ماژول | وضعیت | توضیح |
|---|---|---|
| ورود و اتصال | ✅ | Session/Cookie + CSRF و Backend واقعی |
| RTL / Vazirmatn / Design System | ✅ | مبتنی بر `theme.py` و design tokens |
| Responsive Desktop | ✅ | سایدبار خودکار جمع می‌شود و Header در عرض‌های کم فشرده می‌شود |
| امور مشتریان و خدمات | ✅ | ۶ نوع خدمت، فهرست، فرم New و Detail |
| Detail خدمات | ✅ | وضعیت، تاریخچه، قطعات، گزارش تکنسین/QC، پیوست و اکشن‌های نقش |
| ویرایش اطلاعات پرونده | ✅ | هر ۶ نوع خدمت؛ فیلدها از `save_fields` وب، ذخیره از API واقعی، کنترل نقش و گزینه‌های server-backed برای شهر/مدل/تکنسین |
| کارتابل / وظایف | ✅ | داشبورد، جستجو، وضعیت، نوع خدمت، تأخیر، استان، مسئول، مرتب‌سازی و Detail Native |
| جستجوی سراسری | ✅ | نتایج خدمات تا حد امکان مستقیم به Detail Native می‌روند؛ مقصدهای عمومی/غیرNative در مرورگر باز می‌شوند |
| اعلان‌ها | ✅ | شمارنده، خواندن تکی/همه و مقصد |
| پشتیبانی | ✅ | Inbox و Thread |
| مالی | ✅ | تسویه، رسید، فاکتور، دستمزد و پرونده مالی |
| گزارش‌ها | ✅ | داشبورد، مدیریتی، تأخیر مراحل و ماتریس تأخیر |
| نمایندگان و Permission | ✅ | CRUD/آرشیو و ماتریس دسترسی |
| تنظیمات پایه | ✅ | کاربران، مشتریان، محصولات، تقویم، شرکت، لیست‌ها، جغرافیا، راهنما و پرونده دستگاه |
| پیوست‌ها | ✅ | آپلود/حذف در Detailهای دارای قابلیت سرور |
| چاپ سنگین | 🌐 وب | دکمه/مسیر مرورگر؛ بازسازی موتور چاپ Native انجام نمی‌شود |
| صفحات عمومی بدون Login | 🌐 وب | عمداً خارج از Native |

## ماتریس صفحات وب ↔ Native

| جریان وب | مقصد Native |
|---|---|
| کارتابل | `HomePage` |
| جستجو | `SearchPage` |
| گفتگوی مشتری | `SupportPage` |
| اعلان‌ها | `NotificationsPage` |
| امور مشتریان | `HubPage` + `CustomersPage` / `ContactsPage` / `AnnouncementsPage` / `SurveysPage` |
| تعمیر داخلی | `ServicePage` + `InternalRepairDetailDialog` |
| تعمیر خارجی | `ServicePage` + `ExternalRepairDetailDialog` |
| درخواست نصب | `ServicePage` + `InstallationRequestDetailDialog` |
| ثبت نصب | `ServicePage` + `InstallationRegisterDetailDialog` |
| درخواست/گزارش بازدید | `ServicePage` + `InspectionDetailDialog` |
| انبار | `WarehousePage` |
| مالی | `FinancePage` |
| گزارش‌ها | `ReportsPage` |
| تنظیمات | `SettingsPage` |
| حساب کاربری | `AccountPage` |
| Export/Import | `DataHubPage` |
| گزارش/مدیریت دستمزد | `ImprovementsPage` |
| چاپ سنگین | مرورگر |
| صفحات عمومی مشتری | مرورگر |

## قواعد اجرایی فاز نهایی

1. منطق Login/Backend سالم نسخه مبنا دست‌نخورده می‌ماند.
2. منطق کسب‌وکار در UI کپی نمی‌شود؛ Native از API و `view_functions` موجود استفاده می‌کند.
3. قابلیت جدید باید مسیر `routes/native_api.py` → `api_client.py` → Native UI داشته باشد.
4. UI کاملاً RTL و مبتنی بر `theme.py` است.
5. در مسیرهای کارمندی نباید stub، `_not_native_yet` یا پیام «به‌زودی» باقی بماند.
6. چاپ سنگین و صفحات عمومی عمداً وب می‌مانند.
7. Permission باید روی منو و اکشن اثر واقعی داشته باشد.

## ترتیب ادامه فاز

### موج ۱ — اجرا شد
- Edit Native هر ۶ نوع خدمت بر اساس فیلدهای واقعی `save_fields` وب
- گزینه‌های server-backed برای شهر/مدل/تکنسین بدون کپی‌کردن منطق کسب‌وکار در UI
- فیلترهای کارتابل: وضعیت، نوع خدمت، تأخیر، استان، مسئول و جستجو
- دابل‌کلیک ردیف به Detail Native درست

### موج ۲ — اجرا شد
- مالی، اعلان، جستجو، حساب، Session و permissionهای API موجود بررسی و حفظ شدند
- کنترل دسترسی Edit بر اساس پاسخ سرور یکسان شد

### موج ۳ — اجرا شد در سطح سورس
- تنظیمات CRUD، پشتیبانی/پیوست و گزارش‌های موجود بررسی شدند
- پیام موقت «به‌زودی» در scope مسیرهای Native/routes حذف شد
- اسناد با وضعیت واقعی و محدودیت تست runtime هماهنگ شدند

## معیار پذیرش نهایی

- [x] هیچ جریان کارمندی لاگین‌شده در محدوده تعریف‌شده بدون مقصد Native باقی نماند.
- [x] Login و Backend واقعی حفظ شده‌اند.
- [x] RTL / Vazirmatn / Design System اعمال شده است.
- [x] Responsive Desktop اعمال شده است.
- [x] Detail و New برای جریان‌های اصلی موجود است.
- [x] Edit هر ۶ نوع خدمت اصلی با Native UI، API واقعی و کنترل دسترسی تکمیل شده است.
- [x] مالی، گزارش‌ها، تنظیمات، جستجو و اعلان‌ها دارای API/صفحه Native هستند.
- [x] چاپ سنگین و صفحات عمومی تنها موارد وب‌مانده تعریف‌شده‌اند.

## اجرا

```text
pip install -r requirements-native.txt
python main.py
```

## Wave 1 status — 2026-08-20

| Wave 1 item | Native status |
|---|---|
| Service Detail for internal/external repair | Complete + Edit tab |
| Installation request Detail | Complete + Edit tab |
| Installation register Detail | Complete + Edit tab |
| Inspection Detail | Complete + Edit tab |
| New internal repair form | Expanded with web-aligned reception fields |
| New external repair form | Expanded with probable-parts forwarding |
| Cartable / My Tasks | Search + status/type + delayed filters + Native Detail navigation |
| Login / Backend baseline | Preserved |

## Wave 2 – Finance / Permissions / Account / Notifications
- Finance tabs now include month/year filtering for representative settlement work, settlement detail and receipt inspection, searchable wage history, invoices, wage rates and finance files.
- Representative settlement uses the real native settlement/detail/receipt APIs and respects the finance permission.
- Account profile now exposes province and bank details returned by the server; bank details can be saved through the native account API.
- Permission matrix and representative CRUD remain backed by the existing native JSON endpoints and access checks.
- Notifications keep unread count, read-one/read-all and destination handling.
- Search and notification behavior remains Native-first for supported service destinations.

## Wave 3 status — 2026-08-20

| Wave 3 item | Native status |
|---|---|
| گزارش‌های اجرایی | Complete — داشبورد اجرایی با استان/وضعیت |
| گزارش ممیزی عملیات | Complete — فیلتر کاربر/عملیات/جزئیات |
| محصولات CRUD | Complete — دستگاه، قطعه و شناسنامه کالا: افزودن/ویرایش/حذف |
| تقویم CRUD | Complete — افزودن/ویرایش/حذف تعطیلی |
| لیست‌های نرم‌افزار | Complete — افزودن/ویرایش/غیرفعال‌سازی؛ موارد سیستمی محافظت می‌شوند |
| شرکت | Complete — ویرایش اطلاعات اصلی |
| راهنماهای فرم | Complete — ویرایش دسته‌جمعی |
| پرونده دستگاه‌ها | Complete — جستجو و سابقه مرتبط |
| پشتیبانی و پیوست | Complete — ارسال فایل در Thread و نمایش پیوست |
| نقش و permission | Preserved — APIهای مدیریتی همچنان access check دارند |
| پاکسازی/تست Syntax | Complete — `native_client` / `routes` / `core` compile شدند |

### موارد عمداً وب‌مانده
- چاپ/PDF صفحه‌آرایی‌شده و موتور چاپ کامل وب
- صفحات عمومی بدون Login
- `/settings/display` — تم/رنگ/فونت؛ کاملاً در `localStorage` مرورگر ذخیره می‌شود (شخصی‌سازی per-device، نه یک workflow کاری، پس مفهوم «هم‌ترازی» اصلاً برایش صادق نیست)؛ Native سیستم طراحی مستقل خودش را دارد (`theme.py`)

### موتور فاصله، سیستم، درباره/تاریخچه و فعال‌سازی — اکنون در Native
این چهار مورد قبلاً وب‌مانده بودند؛ همه اکنون در Native پیاده‌سازی شده‌اند، هرکدام با همان access check معادل وب:

- **موتور فاصله** (`/settings/distance`) — عملیاتی‌ترین مورد، روی تخصیص تکنسین/نماینده اثر می‌گذارد:
  - `GET /api/native/settings/distance`, `POST .../factor`, `POST .../method`, `POST .../seed`
  - تب «استان / شهر و مسافت» (`GeoTab`)
- **اطلاعات سیستم** (`/settings/system`) — نمایشی صرف (مسیر دیتابیس، آدرس host):
  - `GET /api/native/settings/system` — تب «اطلاعات سیستم» (`SystemInfoTab`)
- **درباره / تاریخچه تغییرات** (`/settings/about`, `/settings/changelog`) — نمایشی صرف:
  - `GET /api/native/settings/about` (دسترسی `system`), `GET /api/native/settings/changelog` (فقط لاگین)
  - تب «درباره / تاریخچه تغییرات» (`AboutTab`)
- **فعال‌سازی نرم‌افزار** (`/settings/activation`) — فقط یک‌بار در زمان نصب استفاده می‌شود؛ به‌دلیل هزینه کم پیاده‌سازی، به Native اضافه شد تا نصاب مجبور به مراجعه به مرورگر نباشد:
  - `GET /api/native/settings/activation`, `POST /api/native/settings/activation/activate`
  - تب «فعال‌سازی نرم‌افزار» (`ActivationTab`)

همه‌ی endpointهای بالا دقیقاً همان منطق فایل `routes/settings.py` را با همان access check (`_native_manage_allowed(u,'system')`) بازتولید می‌کنند.


## Final Acceptance — 2026-08-20

> وضعیت: Source-level Done. Runtime acceptance روی محیط هدف هنوز باید اجرا شود.

- Source-level acceptance review completed after the current implementation set.
- `native_client`, `routes`, `core` and `scripts` pass Python syntax compilation.
- Stub/temporary-marker scan found no `_not_native_yet`, TODO/FIXME or “coming soon” markers in the Native/routes scope.
- Web↔Native matrix and intentionally web-only scope are documented above.
- Full runtime acceptance requires the target environment with Flask/PyQt5 and the project's test database; the build container does not provide those dependencies.
- Detailed acceptance evidence and the target-environment checklist are in `docs/development.md`.

## UI behavior verification — 2026-08-21

| UX item | Status | Implementation |
|---|---|---|
| Shared busy state | ✅ | `ui_common.busy` disables the active action and shows wait cursor during synchronous API calls |
| Loading/empty table state | ✅ | shared `fill_table` now shows an explicit empty-state row |
| Notification polling | ✅ | 60-second `QTimer` uses `/api/native/notifications`; focus also triggers an immediate refresh |
| Notification badge | ✅ | unread count is shown on the header bell |
| Session expiry | ✅ | HTTP 401 raises `SessionExpiredError`; MainWindow routes the user back to Login with the web-equivalent message |
| Network errors | ✅ | connection/timeout errors have clear user-facing messages |
| CSV export | ✅ | CSV export controls added to the main Finance/Reports tables and export uses the visible filtered table |
| Search Enter behavior | Preserved | Existing `returnPressed` handlers remain in the Native search/filter pages |
| Table sorting | Preserved | Shared `fill_table/style_table` enables sorting where the Native table is backed by that helper |

Runtime side-by-side web/native timing and role acceptance still require the target environment and real test database.
