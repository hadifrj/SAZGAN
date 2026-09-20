/* این فایل بخشی از تفکیک base-ui.js (فاز ۲، بخش ۲) است — کد بدون تغییر منطق از static/js/base-ui.js منتقل شده. */

(function(){
  try {
    var ver = document.body && document.body.getAttribute('data-app-version');
    if (!ver || !('serviceWorker' in navigator)) return;
    var KEY = 'sazgan-app-version-seen';
    var seen = localStorage.getItem(KEY);
    if (seen === ver) return;
    localStorage.setItem(KEY, ver);
    if (!seen) return; // اولین بار نصب؛ unregister لازم نیست
    navigator.serviceWorker.getRegistrations().then(function(regs){
      return Promise.all(regs.map(function(r){ return r.unregister(); }));
    }).then(function(){
      if (window.caches && caches.keys) {
        return caches.keys().then(function(keys){
          return Promise.all(keys.map(function(k){ return caches.delete(k); }));
        });
      }
    }).then(function(){
      // یک رفرش سخت تا فایل‌های جدید بیایند
      window.location.reload(true);
    }).catch(function(){});
  } catch (e) {}
})();

/* PWA: Service Worker + دکمه نصب (Install app) */
(function(){
  var deferredPrompt = null;

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js?v=' + (document.body && document.body.getAttribute('data-app-version') || '1'), { scope: '/' })
        .then(function (reg) {
          try { reg.update(); } catch (e) {}
        })
        .catch(function (err) {
          console.warn('SW register failed', err);
        });
    });
  }

  try {
    var standalone = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches)
      || window.navigator.standalone === true
      || (window.matchMedia && window.matchMedia('(display-mode: minimal-ui)').matches);
    if (standalone) document.documentElement.classList.add('pwa-standalone');
    // Desktop browser / installed Chrome app (not phone)
    var isDesktop = (window.innerWidth || 0) >= 901
      || (window.matchMedia && window.matchMedia('(pointer: fine)').matches && !/Mobi|Android/i.test(navigator.userAgent || ''));
    if (isDesktop) document.documentElement.classList.add('pwa-desktop');
  } catch (e) {}

  /* ---- Desktop / installed PWA: lock max window size (1008×630), allow smaller ---- */
  (function () {
    var MAX_W = 1280;
    var MAX_H = 720;
    var clamping = false;

    function isDesktopLike() {
      try {
        if (window.matchMedia && window.matchMedia('(max-width: 900px)').matches) return false;
      } catch (e) {}
      var ua = navigator.userAgent || '';
      if (/Mobi|Android|iPhone|iPod/i.test(ua)) return false;
      return true;
    }

    function isStandalone() {
      try {
        return (window.matchMedia && (
          window.matchMedia('(display-mode: standalone)').matches ||
          window.matchMedia('(display-mode: minimal-ui)').matches
        )) || window.navigator.standalone === true;
      } catch (e) {
        return false;
      }
    }

    function clampWindow() {
      if (!isDesktopLike()) return;
      if (clamping) return;
      var ow = window.outerWidth || 0;
      var oh = window.outerHeight || 0;
      if (!ow || !oh) return;
      var nw = Math.min(ow, MAX_W);
      var nh = Math.min(oh, MAX_H);
      // Only shrink when larger than cap — never force larger
      if (nw < ow || nh < oh) {
        clamping = true;
        try {
          // Works for many installed Chromium PWAs / app windows
          if (typeof window.resizeTo === 'function') {
            window.resizeTo(nw, nh);
          }
        } catch (e) {}
        setTimeout(function () { clamping = false; }, 120);
      }
    }

    // Initial clamp (standalone / desktop)
    function boot() {
      if (!isDesktopLike()) return;
      clampWindow();
      // Re-clamp if user tries to enlarge past the cap
      var t = null;
      window.addEventListener('resize', function () {
        if (t) clearTimeout(t);
        t = setTimeout(clampWindow, 80);
      });
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', boot);
    } else {
      boot();
    }
    // Extra pass after PWA chrome settles
    setTimeout(clampWindow, 400);
    setTimeout(clampWindow, 1200);
  })();

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    var btn = document.getElementById('btn-pwa-install');
    var bar = document.getElementById('install-pwa-bar');
    if (btn) btn.style.display = 'inline-flex';
    if (bar && !localStorage.getItem('pwa-install-dismiss')) bar.style.display = 'block';
  });

  window.addEventListener('appinstalled', function () {
    deferredPrompt = null;
    var bar = document.getElementById('install-pwa-bar');
    if (bar) bar.style.display = 'none';
    localStorage.setItem('pwa-install-dismiss', '1');
  });

  document.addEventListener('click', function (ev) {
    var t = ev.target;
    if (!t) return;
    if (t.id === 'btn-pwa-install' || (t.closest && t.closest('#btn-pwa-install'))) {
      ev.preventDefault();
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(function () { deferredPrompt = null; });
    }
    if (t.id === 'btn-pwa-dismiss' || (t.closest && t.closest('#btn-pwa-dismiss'))) {
      var bar = document.getElementById('install-pwa-bar');
      if (bar) bar.style.display = 'none';
      localStorage.setItem('pwa-install-dismiss', '1');
    }
  });
})();
