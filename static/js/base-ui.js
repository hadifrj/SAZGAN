/* base-ui.js — فاز ۲ (تفکیک JS، بخش ۲): این فایل دیگر تمام منطق رو نداره.
 * ۱۰ ماژول واقعی به static/js/modules/ منتقل شدن (۹ ماژول نام‌برده در سند فاز ۲
 * + یک فایل جدا برای table-utils که به هیچ‌کدوم از اون ۹ مسئولیت تعلق نداشت).
 * اینجا فقط چیزی می‌مونه که به هیچ ماژولی تعلق نداره (کلاس iframe، تزریق CSRF).
 * base.html این فایل + ۱۰ ماژول رو به‌ترتیب با <script defer> لود می‌کنه.
 */

(function injectCsrf() {
            var meta = document.querySelector('meta[name="csrf-token"]');
            var token = meta ? meta.getAttribute('content') : '';
            if (!token) return;
            document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(function(f) {
                if (!f.querySelector('input[name="csrf_token"]')) {
                    var i = document.createElement('input');
                    i.type = 'hidden';
                    i.name = 'csrf_token';
                    i.value = token;
                    f.appendChild(i);
                }
            });
        })();
