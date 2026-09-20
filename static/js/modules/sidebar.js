/* این فایل بخشی از تفکیک base-ui.js (فاز ۲، بخش ۲) است — کد بدون تغییر منطق از static/js/base-ui.js منتقل شده. */

function updateClock() {
            var now = new Date();
            var h = String(now.getHours()).padStart(2, '0');
            var m = String(now.getMinutes()).padStart(2, '0');
            var s = String(now.getSeconds()).padStart(2, '0');
            var el = document.getElementById('live-clock');
            if (el) el.textContent = h + ':' + m + ':' + s;
        }
        updateClock();
        setInterval(updateClock, 1000);

        function isMobileNav() {
            return window.matchMedia('(max-width: 900px)').matches;
        }

        // ---- قفل اسکرول پس‌زمینه (سازگار با iOS — overflow:hidden به‌تنهایی روی iOS کافی نیست) ----
        var _sazganScrollLockY = 0;
        function lockBodyScroll() {
            if (document.body.classList.contains('sidebar-scroll-locked')) return;
            _sazganScrollLockY = window.scrollY || document.documentElement.scrollTop || 0;
            document.body.style.top = (-_sazganScrollLockY) + 'px';
            document.body.classList.add('sidebar-scroll-locked');
        }
        function unlockBodyScroll() {
            if (!document.body.classList.contains('sidebar-scroll-locked')) return;
            document.body.classList.remove('sidebar-scroll-locked');
            document.body.style.top = '';
            window.scrollTo(0, _sazganScrollLockY);
        }

        function closeMobileSidebar() {
            var sidebar = document.getElementById('sidebar');
            var overlay = document.getElementById('sidebar-overlay');
            if (sidebar) sidebar.classList.remove('mobile-open');
            if (overlay) overlay.classList.remove('visible');
            unlockBodyScroll();
        }
        function openMobileSidebar() {
            var sidebar = document.getElementById('sidebar');
            var overlay = document.getElementById('sidebar-overlay');
            if (sidebar) sidebar.classList.add('mobile-open');
            if (overlay) overlay.classList.add('visible');
            lockBodyScroll();
        }

        // ---- سواپ چپ/راست برای باز و بسته کردن ساید‌بار (موبایل) ----
        // ساید‌بار در سمت راست صفحه است: سواپ از لبه‌ی راست به چپ = باز شدن، سواپ به راست روی ساید‌بار باز = بسته شدن
        (function(){
            var EDGE = 24;       // فاصله از لبه‌ی راست برای شروع ژست «باز کردن»
            var THRESHOLD = 48;  // حداقل جابه‌جایی افقی برای شمارش به‌عنوان سواپ
            var startX = 0, startY = 0, tracking = false, fromEdge = false;

            function onTouchStart(e) {
                if (!isMobileNav()) { tracking = false; return; }
                var t = e.touches[0];
                startX = t.clientX;
                startY = t.clientY;
                var sidebar = document.getElementById('sidebar');
                var isOpen = sidebar && sidebar.classList.contains('mobile-open');
                fromEdge = !isOpen && (window.innerWidth - startX) <= EDGE;
                tracking = isOpen || fromEdge;
            }
            function onTouchEnd(e) {
                if (!tracking) return;
                tracking = false;
                var t = e.changedTouches[0];
                var dx = t.clientX - startX;
                var dy = t.clientY - startY;
                if (Math.abs(dx) < THRESHOLD || Math.abs(dx) < Math.abs(dy) * 1.2) return;
                var sidebar = document.getElementById('sidebar');
                var isOpen = sidebar && sidebar.classList.contains('mobile-open');
                if (fromEdge && dx < 0) openMobileSidebar();
                else if (isOpen && dx > 0) closeMobileSidebar();
            }
            document.addEventListener('touchstart', onTouchStart, { passive: true });
            document.addEventListener('touchend', onTouchEnd, { passive: true });
        })();

        (function(){
            var bar = document.getElementById('page-loading-bar');
            if (!bar) return;
            function show() {
                bar.classList.add('active');
                bar.style.width = '30%';
                setTimeout(function(){ bar.style.width = '75%'; }, 120);
            }
            function reset() {
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
                show();
            });
            document.addEventListener('submit', function(e){
                var form = e.target;
                if (!form || form.tagName !== 'FORM') return;
                if (e.defaultPrevented) return;
                show();
            });
            window.addEventListener('pageshow', function(e){
                if (e.persisted) reset();
            });
        })();

        function syncSidebarCollapsedClass() {
            var sidebar = document.getElementById('sidebar');
            var collapsed = !!(sidebar && sidebar.classList.contains('collapsed'));
            // فقط وقتی سایدبار واقعاً جمع است نام را در هدر نشان بده
            if (document.body) {
              if (collapsed) document.body.classList.add('show-header-brand');
              else document.body.classList.remove('show-header-brand');
            }
            document.documentElement.classList.toggle('sidebar-is-collapsed', collapsed);
            if (document.body) document.body.classList.toggle('sidebar-is-collapsed', collapsed);
        }
        function toggleSidebar() {
            var sidebar = document.getElementById('sidebar');
            if (!sidebar) return;
            if (isMobileNav()) {
                if (sidebar.classList.contains('mobile-open')) closeMobileSidebar();
                else openMobileSidebar();
            } else {
                sidebar.classList.toggle('collapsed');
                localStorage.setItem('sazgan-sidebar-collapsed', sidebar.classList.contains('collapsed') ? '1' : '0');
                syncSidebarCollapsedClass();
                document.querySelectorAll('.sidebar-group.is-flyout-open').forEach(function(x){
                  x.classList.remove('is-flyout-open');
                  x.removeAttribute('open');
                });
            }
        }

        // =====================================================================
        // ژست لمسی منوی موبایل: کشیدن با انگشت برای باز/بسته کردن
        // - سوایپ از لبه‌ی صفحه به‌سمت مرکز → باز شدن
        // - کشیدن منو به‌سمت لبه → بسته شدن
        // - دنبال‌کردن لحظه‌ای انگشت، آستانه‌ی قابل‌تنظیم، و رهاسازی با تکانه (momentum)
        // =====================================================================
        (function(){
            var sidebar = document.getElementById('sidebar');
            var overlay = document.getElementById('sidebar-overlay');
            if (!sidebar || !overlay) return;

            // ---- تنظیمات قابل‌تغییر ----
            var EDGE_ZONE_PX = 24;          // فاصله از لبه‌ی راست صفحه برای شروع ژست «باز شدن»
            var OPEN_THRESHOLD = 0.35;      // این‌قدر از عرض منو رد شود → باز شدن قطعی می‌شود
            var CLOSE_THRESHOLD = 0.30;     // این‌قدر از عرض منو رد شود → بسته شدن قطعی می‌شود
            var VELOCITY_COMMIT = 0.55;     // px/ms — رهاسازی سریع (تند کشیدن) حتی قبل از رسیدن به آستانه هم قطعی می‌شود
            var AXIS_LOCK_RATIO = 1.15;     // برای تشخیص کشش افقی در برابر اسکرول عمودی
            var MOVE_INTENT_PX = 10;        // حداقل جابه‌جایی برای تشخیص قصد کشیدن

            var g = null; // وضعیت ژست جاری

            function sidebarWidth() { return sidebar.offsetWidth || 300; }
            function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
            function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }

            function setDragState(on) {
                sidebar.classList.toggle('sidebar-dragging', on);
                overlay.classList.toggle('sidebar-dragging', on);
            }
            function clearInlineStyles() {
                sidebar.style.transform = '';
                sidebar.style.transition = '';
                overlay.style.opacity = '';
                overlay.style.transition = '';
            }
            function applyPreview(px, w) {
                // px: ۰ = کاملاً باز، w = کاملاً بسته
                sidebar.style.transform = 'translateX(' + px + 'px)';
                overlay.style.opacity = String(1 - clamp(px / w, 0, 1));
            }

            // انیمیشن نهایی یکپارچه برای هر ۴ حالت: تکمیل باز/بسته یا بازگشت فنری به حالت قبل
            function animateSidebar(open, fromPx) {
                var w = sidebarWidth();
                var maxPx = w + 40;
                var targetPx = open ? 0 : maxPx;
                var dist = Math.abs(targetPx - fromPx);
                var ratio = clamp(maxPx > 0 ? dist / maxPx : 1, 0.18, 1);
                var duration = Math.round(90 + 190 * ratio); // مسافت کمتر ⇒ زمان کوتاه‌تر (حس فنری/طبیعی)

                sidebar.style.transition = 'transform ' + duration + 'ms cubic-bezier(.22,.61,.36,1)';
                overlay.style.transition = 'opacity ' + duration + 'ms ease';
                // اطمینان از این‌که مرورگر مقدار فعلی را قبل از تغییر transition ثبت کرده باشد
                void sidebar.offsetWidth;
                sidebar.style.transform = 'translateX(' + targetPx + 'px)';
                overlay.style.opacity = open ? '1' : '0';

                var done = false;
                function finish() {
                    if (done) return;
                    done = true;
                    sidebar.removeEventListener('transitionend', onTransEnd);
                    clearTimeout(safety);
                    setDragState(false);
                    if (open) {
                        sidebar.classList.add('mobile-open');
                        overlay.classList.add('visible');
                        clearInlineStyles();
                        lockBodyScroll();
                    } else {
                        sidebar.classList.remove('mobile-open');
                        overlay.classList.remove('visible');
                        clearInlineStyles();
                        unlockBodyScroll();
                    }
                }
                function onTransEnd(ev) {
                    if (ev && ev.target !== sidebar) return;
                    if (ev && ev.propertyName && ev.propertyName !== 'transform') return;
                    finish();
                }
                sidebar.addEventListener('transitionend', onTransEnd);
                var safety = setTimeout(finish, duration + 90); // شبکه‌ی ایمنی اگر transitionend نیاید
            }

            function onTouchStart(e) {
                if (!isMobileNav()) return;
                if (g || e.touches.length !== 1) return;
                var t = e.touches[0];
                var isOpen = sidebar.classList.contains('mobile-open');
                var startedOnSidebar = sidebar.contains(e.target);
                var fromEdge = (window.innerWidth - t.clientX) <= EDGE_ZONE_PX;

                if (isOpen && !startedOnSidebar) return;   // بستن فقط با کشیدن خودِ منو
                if (!isOpen && !fromEdge) return;           // باز شدن فقط با سوایپ از لبه

                g = {
                    mode: isOpen ? 'close' : 'open',
                    startX: t.clientX,
                    startY: t.clientY,
                    lastX: t.clientX,
                    lastT: now(),
                    velocity: 0,
                    dragging: false,
                    width: sidebarWidth(),
                };
            }

            function onTouchMove(e) {
                if (!g || e.touches.length !== 1) return;
                var t = e.touches[0];
                var dx = t.clientX - g.startX;
                var dy = t.clientY - g.startY;

                if (!g.dragging) {
                    if (Math.abs(dx) < MOVE_INTENT_PX && Math.abs(dy) < MOVE_INTENT_PX) return;
                    var isHorizontal = Math.abs(dx) > Math.abs(dy) * AXIS_LOCK_RATIO;
                    if (!isHorizontal) { g = null; return; } // قصد اسکرول عمودی → دخالت نکن
                    if (g.mode === 'open' && dx >= 0) { g = null; return; }  // باید به‌سمت مرکز (چپ) بکشد
                    if (g.mode === 'close' && dx <= 0) { g = null; return; } // باید به‌سمت لبه (راست) بکشد
                    g.dragging = true;
                    setDragState(true);
                    if (!overlay.classList.contains('visible')) overlay.classList.add('visible');
                }

                e.preventDefault(); // از اسکرول صفحه‌ی پشت و ژست بازگشت مرورگر جلوگیری می‌کند

                var dt = now() - g.lastT;
                if (dt > 0) g.velocity = (t.clientX - g.lastX) / dt; // px/ms، با علامت
                g.lastX = t.clientX;
                g.lastT = now();

                var w = g.width, maxPx = w + 40, px;
                if (g.mode === 'open') px = clamp(w + dx, 0, maxPx);
                else px = clamp(dx, 0, maxPx);
                applyPreview(px, w);
            }

            function currentPx(s) {
                var maxPx = s.width + 40;
                return s.mode === 'open'
                    ? clamp(s.width + (s.lastX - s.startX), 0, maxPx)
                    : clamp(s.lastX - s.startX, 0, maxPx);
            }

            function onTouchEnd(e) {
                if (!g) return;
                var s = g; g = null;
                if (!s.dragging) return;
                e.preventDefault();

                var px = currentPx(s);
                var openProgress = 1 - clamp(px / s.width, 0, 1); // ۱=کاملاً باز، ۰=کاملاً بسته
                var flickOpen = s.velocity < -VELOCITY_COMMIT;
                var flickClose = s.velocity > VELOCITY_COMMIT;

                var goOpen;
                if (s.mode === 'open') {
                    goOpen = !flickClose && (flickOpen || openProgress >= OPEN_THRESHOLD);
                } else {
                    goOpen = flickOpen || (!flickClose && openProgress > (1 - CLOSE_THRESHOLD));
                }
                animateSidebar(goOpen, px);
            }

            function onTouchCancel() {
                if (!g) return;
                var s = g; g = null;
                if (!s.dragging) return;
                animateSidebar(s.mode === 'close', currentPx(s)); // بازگشت به وضعیت قبل از ژست
            }

            document.addEventListener('touchstart', onTouchStart, {passive: true});
            document.addEventListener('touchmove', onTouchMove, {passive: false});
            document.addEventListener('touchend', onTouchEnd, {passive: false});
            document.addEventListener('touchcancel', onTouchCancel, {passive: true});
        })();

        function toggleMobileKebab() {
            var panel = document.getElementById('mobile-topbar-kebab-panel');
            if (panel) panel.classList.toggle('open');
        }
        document.addEventListener('click', function(e) {
            var panel = document.getElementById('mobile-topbar-kebab-panel');
            var btn = document.getElementById('mobile-topbar-kebab-btn');
            if (!panel || !panel.classList.contains('open')) return;
            if (panel.contains(e.target) || (btn && btn.contains(e.target))) return;
            panel.classList.remove('open');
        });

        function toggleAhUserMenu() {
            var dd = document.getElementById('ah-dropdown');
            var btn = document.getElementById('ah-user-toggle-btn');
            if (!dd) return;
            var open = !dd.hidden;
            dd.hidden = open;
            if (btn) btn.setAttribute('aria-expanded', open ? 'false' : 'true');
        }
        document.addEventListener('click', function(e) {
            var dd = document.getElementById('ah-dropdown');
            var menu = document.getElementById('ah-user-menu');
            if (!dd || dd.hidden) return;
            if (menu && menu.contains(e.target)) return;
            dd.hidden = true;
            var btn = document.getElementById('ah-user-toggle-btn');
            if (btn) btn.setAttribute('aria-expanded', 'false');
        });
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                var dd = document.getElementById('ah-dropdown');
                if (dd) dd.hidden = true;
            }
        });
        (function() {
            if (!isMobileNav() && localStorage.getItem('sazgan-sidebar-collapsed') === '1') {
                var sb = document.getElementById('sidebar');
                if (sb) sb.classList.add('collapsed');
                // Keep the pre-paint and live DOM states identical.
                document.documentElement.classList.add('sidebar-is-collapsed');
                if (document.body) document.body.classList.add('sidebar-is-collapsed');
            }
            if (typeof syncSidebarCollapsedClass === 'function') syncSidebarCollapsedClass();
            document.querySelectorAll('.sidebar a').forEach(function(a) {
                a.addEventListener('click', function() {
                    if (isMobileNav()) closeMobileSidebar();
                });
            });
            window.addEventListener('resize', function() {
                if (!isMobileNav()) closeMobileSidebar();
            });

            function isCollapsedDesktop() {
                var sb = document.getElementById('sidebar');
                return !!(sb && sb.classList.contains('collapsed') && !isMobileNav());
            }
            // -----------------------------------------------------------------
            // Drill-down navigation:
            // Main sidebar -> click a parent -> main sidebar is replaced by a
            // dedicated child sidebar. Back returns to the exact main menu.
            // -----------------------------------------------------------------
            (function initDrillDownSidebar() {
                var sidebar = document.getElementById('sidebar');
                if (!sidebar) return;

                var mainNavs = Array.prototype.slice.call(
                    sidebar.querySelectorAll('.sidebar-nav.is-main-sidebar')
                );
                if (!mainNavs.length) return;

                var activeMainNav = mainNavs.find(function(nav) {
                    return getComputedStyle(nav).display !== 'none';
                }) || mainNavs[0];

                // Remove any native <details> state so submenu items can never
                // stack into the main sidebar.
                sidebar.querySelectorAll('.sidebar-group').forEach(function(group) {
                    group.removeAttribute('open');
                    group.classList.remove('is-flyout-open');
                });

                var panel = sidebar.querySelector('.sidebar-subnav-panel');
                if (!panel) {
                    panel = document.createElement('div');
                    panel.className = 'sidebar-subnav-panel';
                    panel.setAttribute('aria-hidden', 'true');
                    sidebar.appendChild(panel);
                }

                function iconClone(summary) {
                    var icon = summary && summary.querySelector('.sidebar-link-icon');
                    return icon ? icon.cloneNode(true) : null;
                }

                function textOf(summary) {
                    var text = summary && summary.querySelector('.sidebar-link-text');
                    return text ? text.textContent.trim() : summary.textContent.trim();
                }

                function closePanel() {
                    sidebar.classList.remove('sidebar-subnav-open', 'sidebar-subnav-overlay');
                    panel.setAttribute('aria-hidden', 'true');
                    panel.innerHTML = '';
                    activeMainNav = mainNavs.find(function(nav) {
                        return getComputedStyle(nav).display !== 'none';
                    }) || mainNavs[0];

                    if (activeMainNav) activeMainNav.removeAttribute('aria-hidden');
                }

                function openPanel(group) {
                    // Opening a child menu must never mutate the persisted collapsed state.
                    // In collapsed desktop mode the child panel is rendered as an overlay;
                    // the 72px rail remains collapsed and navigation state stays independent.
                    var wasCollapsed = isCollapsedDesktop();
                    var summary = group.querySelector(':scope > summary.sidebar-link');
                    var submenu = group.querySelector(':scope > .sidebar-submenu');
                    if (!summary || !submenu) return;

                    activeMainNav = mainNavs.find(function(nav) {
                        return nav.contains(group) && getComputedStyle(nav).display !== 'none';
                    }) || mainNavs[0];

                    if (activeMainNav) activeMainNav.setAttribute('aria-hidden', 'true');

                    panel.innerHTML = '';

                    var head = document.createElement('div');
                    head.className = 'sazgan-subnav-head';

                    var back = document.createElement('button');
                    back.type = 'button';
                    back.className = 'sazgan-subnav-back';
                    back.setAttribute('aria-label', 'بازگشت');
                    back.title = 'بازگشت';
                    back.innerHTML =
                        '<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
                        '<path d="m12 5 7 7-7 7"/><path d="M19 12H5"/></svg>';
                    back.addEventListener('click', closePanel);

                    var title = document.createElement('div');
                    title.className = 'sazgan-subnav-title';
                    var ico = iconClone(summary);
                    if (ico) title.appendChild(ico);
                    var label = document.createElement('span');
                    label.textContent = textOf(summary);
                    title.appendChild(label);

                    head.appendChild(back);
                    head.appendChild(title);

                    var body = document.createElement('div');
                    body.className = 'sazgan-subnav-body';

                    // Clone instead of moving the original DOM so templates remain
                    // untouched and active links keep their server-rendered state.
                    var cloned = submenu.cloneNode(true);
                    body.appendChild(cloned);

                    panel.appendChild(head);
                    panel.appendChild(body);

                    sidebar.classList.add('sidebar-subnav-open');
                    if (wasCollapsed) sidebar.classList.add('sidebar-subnav-overlay');
                    else sidebar.classList.remove('sidebar-subnav-overlay');
                    panel.setAttribute('aria-hidden', 'false');
                    syncSidebarCollapsedClass();

                    var first = body.querySelector('.sidebar-sublink');
                    if (first) {
                        setTimeout(function() { first.focus({preventScroll:true}); }, 40);
                    }
                }

                sidebar.querySelectorAll('.sidebar-group > summary.sidebar-link').forEach(function(sum) {
                    sum.addEventListener('click', function(ev) {
                        ev.preventDefault();
                        ev.stopPropagation();
                        openPanel(sum.parentElement);
                    });
                });

                document.addEventListener('keydown', function(ev) {
                    if (ev.key === 'Escape' && sidebar.classList.contains('sidebar-subnav-open')) {
                        closePanel();
                    }
                });

                window.addEventListener('resize', function() {
                    // Keep the drill-down model consistent across breakpoints.
                    if (sidebar.classList.contains('sidebar-subnav-open')) {
                        panel.scrollTop = 0;
                    }
                });

                // Expose a tiny API for other UI controls.
                window.SazganSidebar = {
                    openSubmenu: openPanel,
                    closeSubmenu: closePanel
                };
            })();

            document.querySelectorAll('.sidebar-group.is-flyout-open').forEach(function(x) {
                x.classList.remove('is-flyout-open');
            });
        })();

/* --- block 17 --- */
/* همگام‌سازی اولیه نام هدر با وضعیت سایدبار */
(function(){
  function bootBrand(){
    try {
      if (typeof syncSidebarCollapsedClass === 'function') syncSidebarCollapsedClass();
      else if (document.body) document.body.classList.remove('show-header-brand');
    } catch(e) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bootBrand);
  else bootBrand();
  window.addEventListener('pageshow', bootBrand);
})();

