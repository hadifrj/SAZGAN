/* این فایل بخشی از تفکیک base-ui.js (فاز ۲، بخش ۲) است — کد بدون تغییر منطق از static/js/base-ui.js منتقل شده. */
/* فاز ۲ بخش ۴ (Navigation/Prefetch واقعی): نمایش نوار لودینگ ۱۵۰-۲۰۰ میلی‌ثانیه به تعویق افتاد —
   اگر ناوبری زودتر از این تموم بشه (صفحه unload بشه)، تایمر هیچ‌وقت اجرا نمی‌شه و نوار اصلاً دیده
   نمی‌شه (چون کل کانتکست جاوااسکریپت با unload از بین می‌ره) — دقیقاً همون رفتاری که سند خواسته. */

        (function(){
            var bar = document.getElementById('page-loading-bar');
            if (!bar) return;
            var LOADING_DELAY_MS = 180;
            var pendingTimer = null;
            function show() {
                bar.classList.add('active');
                bar.style.width = '30%';
                setTimeout(function(){ bar.style.width = '75%'; }, 120);
            }
            function scheduleShow() {
                if (pendingTimer) clearTimeout(pendingTimer);
                pendingTimer = setTimeout(show, LOADING_DELAY_MS);
            }
            function reset() {
                if (pendingTimer) { clearTimeout(pendingTimer); pendingTimer = null; }
                bar.classList.remove('active');
                bar.style.width = '0%';
            }
            document.addEventListener('click', function(e){
                var a = e.target.closest && e.target.closest('a[href]');
                if (!a) return;
                if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
                if (a.target === '_blank' || a.hasAttribute('download')) return;
                var href = a.getAttribute('href') || '';
                if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0) return;
                try {
                    var url = new URL(href, window.location.href);
                    if (url.origin !== window.location.origin) return;
                } catch (err) { return; }
                scheduleShow();
            });
            document.addEventListener('submit', function(e){
                var form = e.target;
                if (!form || form.tagName !== 'FORM') return;
                if (e.defaultPrevented) return;
                scheduleShow();
            });
            window.addEventListener('pageshow', function(e){
                if (e.persisted) reset();
            });
        })();
