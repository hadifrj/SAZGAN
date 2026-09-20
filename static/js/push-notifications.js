/**
 * Sazgan Web Push client
 * - Permission request at appropriate time
 * - Subscribe / unsubscribe
 * - Badge sync
 * - Notification center helpers
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'sazgan-push-prompted';
  var SUB_KEY = 'sazgan-push-subscribed';

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var rawData = window.atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  function isSupported() {
    return (
      'serviceWorker' in navigator &&
      'PushManager' in window &&
      'Notification' in window
    );
  }

  function getPermission() {
    if (!('Notification' in window)) return 'unsupported';
    return Notification.permission; // 'granted' | 'denied' | 'default'
  }

  function fetchJson(url, opts) {
    opts = opts || {};
    opts.credentials = opts.credentials || 'include';
    opts.headers = opts.headers || {};
    var csrf = document.querySelector('meta[name="csrf-token"]');
    if (csrf && csrf.content && /^(POST|PUT|PATCH|DELETE)$/i.test(opts.method || 'GET')) {
      opts.headers['X-CSRF-Token'] = csrf.content;
    }
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    return fetch(url, opts).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  function getRegistration() {
    return navigator.serviceWorker.ready;
  }

  function getVapidKey() {
    return fetchJson('/api/push/vapid-public-key').then(function (d) {
      if (!d || !d.key) throw new Error('no vapid key');
      return d.key;
    });
  }

  function subscribe() {
    if (!isSupported()) return Promise.reject(new Error('unsupported'));
    return getRegistration()
      .then(function (reg) {
        return getVapidKey().then(function (key) {
          return reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(key)
          });
        });
      })
      .then(function (sub) {
        var json = sub.toJSON();
        return fetchJson('/api/push/subscribe', {
          method: 'POST',
          body: {
            endpoint: json.endpoint,
            keys: json.keys,
            user_agent: navigator.userAgent || ''
          }
        }).then(function () {
          try { localStorage.setItem(SUB_KEY, '1'); } catch (e) {}
          return sub;
        });
      });
  }

  function unsubscribe() {
    if (!isSupported()) return Promise.resolve(false);
    return getRegistration()
      .then(function (reg) {
        return reg.pushManager.getSubscription();
      })
      .then(function (sub) {
        if (!sub) return false;
        var endpoint = sub.endpoint;
        return sub.unsubscribe().then(function () {
          return fetchJson('/api/push/unsubscribe', {
            method: 'POST',
            body: { endpoint: endpoint }
          }).catch(function () {}).then(function () {
            try { localStorage.removeItem(SUB_KEY); } catch (e) {}
            return true;
          });
        });
      });
  }

  function ensureSubscribed() {
    if (!isSupported()) return Promise.resolve(false);
    if (getPermission() !== 'granted') return Promise.resolve(false);
    return getRegistration()
      .then(function (reg) {
        return reg.pushManager.getSubscription();
      })
      .then(function (sub) {
        if (sub) {
          // re-sync with server
          var json = sub.toJSON();
          return fetchJson('/api/push/subscribe', {
            method: 'POST',
            body: {
              endpoint: json.endpoint,
              keys: json.keys,
              user_agent: navigator.userAgent || ''
            }
          }).then(function () { return true; }).catch(function () { return true; });
        }
        return subscribe().then(function () { return true; });
      })
      .catch(function () { return false; });
  }

  function requestPermissionAndSubscribe() {
    if (!isSupported()) {
      return Promise.resolve({ ok: false, reason: 'unsupported' });
    }
    var perm = getPermission();
    if (perm === 'denied') {
      return Promise.resolve({ ok: false, reason: 'denied' });
    }
    if (perm === 'granted') {
      return ensureSubscribed().then(function (ok) {
        return { ok: !!ok, reason: ok ? 'subscribed' : 'subscribe_failed' };
      });
    }
    // default — ask
    return Notification.requestPermission().then(function (result) {
      try { localStorage.setItem(STORAGE_KEY, '1'); } catch (e) {}
      if (result === 'granted') {
        return subscribe()
          .then(function () { return { ok: true, reason: 'subscribed' }; })
          .catch(function () { return { ok: false, reason: 'subscribe_failed' }; });
      }
      return { ok: false, reason: result };
    });
  }

  /* Badge helpers */
  function setBadge(count) {
    count = Number(count) || 0;
    try {
      if (navigator.setAppBadge) {
        if (count > 0) navigator.setAppBadge(count);
        else navigator.clearAppBadge();
      }
    } catch (e) {}
    // also tell SW
    try {
      if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({
          type: 'UPDATE_BADGE',
          count: count
        });
      }
    } catch (e) {}
    // update nav badge in UI
    updateNavBadge(count);
  }

  function updateNavBadge(count) {
    count = Number(count) || 0;
    var selectors = [
      'a[href="/notifications"]',
      'a.sidebar-link[href="/notifications"]',
      '#nav-notifications',
      '[data-nav="notifications"]'
    ];
    var link = null;
    for (var i = 0; i < selectors.length; i++) {
      link = document.querySelector(selectors[i]);
      if (link) break;
    }
    if (!link) return;

    var old = link.querySelector('.nav-badge, .push-badge');
    if (old) old.remove();
    if (count <= 0) return;

    var b = document.createElement('span');
    b.className = 'nav-badge push-badge';
    b.textContent = count > 99 ? '99+' : String(count);
    b.style.cssText =
      'margin-right:6px;background:#ef4444;color:#fff;border-radius:999px;' +
      'font-size:10px;padding:1px 6px;font-weight:700;line-height:1.4;';
    var text = link.querySelector('.sidebar-link-text');
    if (text) text.appendChild(b);
    else link.appendChild(b);
  }

  function refreshUnreadCount() {
    return fetchJson('/api/push/unread-count')
      .then(function (d) {
        var n = (d && d.count) ? Number(d.count) : 0;
        setBadge(n);
        return n;
      })
      .catch(function () { return 0; });
  }

  /* Soft prompt UI (not on first paint) */
  function maybeShowSoftPrompt() {
    if (!isSupported()) return;
    if (getPermission() !== 'default') return;
    // در صفحه گفتگوی دوستونی (تلگرام‌مانند)، این بنر پایین صفحه با پنل چت/کادر نوشتن پیام تداخل دارد — نمایش داده نشود
    if (document.querySelector('.sc-chat-pane')) return;
    try {
      if (localStorage.getItem(STORAGE_KEY) === '1') return;
    } catch (e) {}

    // Wait until user has interacted a bit (not immediate on load)
    var shown = false;
    function show() {
      if (shown) return;
      shown = true;
      var bar = document.getElementById('push-permission-bar');
      if (bar) {
        bar.style.display = 'block';
        return;
      }
      // create soft prompt
      var el = document.createElement('div');
      el.id = 'push-permission-bar';
      el.setAttribute('dir', 'rtl');
      el.style.cssText =
        'position:fixed;bottom:16px;left:16px;right:16px;z-index:9999;' +
        'max-width:420px;margin:0 auto;background:#0f172a;color:#f8fafc;' +
        'border-radius:12px;padding:14px 16px;box-shadow:0 8px 30px rgba(0,0,0,.35);' +
        'font-family:inherit;font-size:13px;line-height:1.6;display:flex;' +
        'flex-direction:column;gap:10px;';
      el.innerHTML =
        '<div style="font-weight:600">فعال‌سازی اعلان‌ها</div>' +
        '<div style="opacity:.85">برای دریافت اعلان حتی وقتی برنامه بسته است، مجوز اعلان را فعال کنید.</div>' +
        '<div style="display:flex;gap:8px;justify-content:flex-end">' +
        '<button type="button" id="push-prompt-later" style="background:transparent;border:1px solid rgba(255,255,255,.25);color:#fff;border-radius:8px;padding:6px 12px;cursor:pointer">بعداً</button>' +
        '<button type="button" id="push-prompt-enable" style="background:#0284c7;border:none;color:#fff;border-radius:8px;padding:6px 14px;cursor:pointer;font-weight:600">فعال‌سازی</button>' +
        '</div>';
      document.body.appendChild(el);
      document.getElementById('push-prompt-later').onclick = function () {
        try { localStorage.setItem(STORAGE_KEY, '1'); } catch (e) {}
        el.remove();
      };
      document.getElementById('push-prompt-enable').onclick = function () {
        requestPermissionAndSubscribe().then(function () {
          el.remove();
        });
      };
    }

    // Show after ~8s of presence, or after first meaningful click
    setTimeout(show, 8000);
    document.addEventListener(
      'click',
      function once() {
        setTimeout(show, 1500);
        document.removeEventListener('click', once, true);
      },
      true
    );
  }

  /* Handle notification-click messages from SW */
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', function (event) {
      if (event.data && event.data.type === 'notification-click' && event.data.url) {
        try {
          if (window.location.pathname + window.location.search !== event.data.url) {
            window.location.href = event.data.url;
          }
        } catch (e) {}
      }
    });
  }

  /* Public API */
  window.SazganPush = {
    isSupported: isSupported,
    getPermission: getPermission,
    subscribe: subscribe,
    unsubscribe: unsubscribe,
    ensureSubscribed: ensureSubscribed,
    requestPermissionAndSubscribe: requestPermissionAndSubscribe,
    refreshUnreadCount: refreshUnreadCount,
    setBadge: setBadge,
    updateNavBadge: updateNavBadge
  };

  /* Auto-init after load */
  function init() {
    if (!isSupported()) return;

    // If already granted, ensure subscription is synced
    if (getPermission() === 'granted') {
      ensureSubscribed().then(function () {
        refreshUnreadCount();
      });
    } else {
      // soft prompt later
      maybeShowSoftPrompt();
      // still refresh in-app badge from server
      refreshUnreadCount();
    }

    // Refresh count periodically when page visible
    setInterval(function () {
      if (!document.hidden) refreshUnreadCount();
    }, 60000);

    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) refreshUnreadCount();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      setTimeout(init, 400);
    });
  } else {
    setTimeout(init, 400);
  }
})();
