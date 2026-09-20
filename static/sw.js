/* Sazgan service worker — PWA + Web Push + سرعت بارگذاری استاتیک */
const CACHE = 'sazgan-shell-v2.10.50';
const SHELL = [
  '/offline',
  '/static/manifest.webmanifest',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon-192-maskable.png',
  '/static/icons/icon-512-maskable.png',
  '/static/icons/icon-96.png',
  '/static/fonts/Vazirmatn-Regular.woff2',
  '/static/fonts/Vazirmatn-Bold.woff2',
  '/static/css/style.min.css',
  '/static/css/design-system.min.css',
  '/static/css/scrollbars.css',
  '/static/css/searchable-select.css',
  '/static/css/neutral-white-theme.css',
  '/static/css/responsive-global-a1.css'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;

  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req).catch(() =>
        caches.match('/offline').then((r) => r || caches.match(req))
      )
    );
    return;
  }

  const url = new URL(req.url);
  if (url.origin === self.location.origin && url.pathname.startsWith('/static/')) {
    /* cache-first برای CSS/JS/فونت/آیکن — سریع‌تر در بازدیدهای بعدی */
    const isVersioned = url.searchParams.has('v');
    e.respondWith(
      caches.match(req).then((cached) => {
        const network = fetch(req).then((resp) => {
          if (resp && resp.ok) {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
          }
          return resp;
        }).catch(() => cached);
        /* اگر نسخه در URL هست و کش داریم، همان را فوری برگردان */
        if (cached && (isVersioned || url.pathname.match(/\.(woff2|png|ico|css|js)$/))) {
          return cached;
        }
        return network;
      })
    );
    return;
  }

  e.respondWith(fetch(req).catch(() => caches.match(req)));
});

/* Web Push */
self.addEventListener('push', (event) => {
  let payload = {
    title: 'سازگان',
    body: '',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-96.png',
    tag: 'sazgan',
    url: '/',
    dir: 'rtl',
    lang: 'fa',
    data: {}
  };

  try {
    if (event.data) {
      const raw = event.data.json ? event.data.json() : JSON.parse(event.data.text());
      payload = Object.assign(payload, raw || {});
    }
  } catch (err) {
    try {
      payload.body = event.data ? event.data.text() : '';
    } catch (e2) {}
  }

  const options = {
    body: payload.body || '',
    icon: payload.icon || '/static/icons/icon-192.png',
    badge: payload.badge || '/static/icons/icon-96.png',
    tag: payload.tag || 'sazgan',
    dir: payload.dir || 'rtl',
    lang: payload.lang || 'fa',
    renotify: true,
    requireInteraction: false,
    data: {
      url: payload.url || '/',
      notification_id: payload.notification_id || null,
      extra: payload.data || {}
    },
    actions: payload.actions || [
      { action: 'open', title: 'مشاهده' },
      { action: 'dismiss', title: 'بستن' }
    ]
  };

  if (payload.timestamp) {
    options.timestamp = payload.timestamp;
  }

  event.waitUntil(
    self.registration.showNotification(payload.title || 'سازگان', options)
      .then(() => updateBadgeFromServer())
      .catch(() => {})
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const action = event.action;
  if (action === 'dismiss') {
    return;
  }

  const data = event.notification.data || {};
  let targetUrl = data.url || '/';
  if (targetUrl && !targetUrl.startsWith('http') && !targetUrl.startsWith('/')) {
    targetUrl = '/' + targetUrl;
  }

  const nid = data.notification_id;
  const markRead = nid
    ? fetch('/api/push/mark-read/' + nid, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' }
      }).catch(() => {})
    : Promise.resolve();

  event.waitUntil(
    Promise.all([
      markRead,
      clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
        for (const client of clientList) {
          if ('focus' in client) {
            return client.focus().then((c) => {
              if (c && 'navigate' in c && targetUrl) {
                try { return c.navigate(targetUrl); } catch (e) {}
              }
              try {
                c.postMessage({ type: 'notification-click', url: targetUrl });
              } catch (e) {}
              return c;
            });
          }
        }
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      })
    ]).then(() => updateBadgeFromServer()).catch(() => {})
  );
});

self.addEventListener('notificationclose', (event) => {});

function updateBadgeFromServer() {
  return fetch('/api/push/unread-count', { credentials: 'include' })
    .then((r) => (r.ok ? r.json() : { count: 0 }))
    .then((d) => {
      const n = (d && d.count) ? Number(d.count) : 0;
      if (self.navigator && self.navigator.setAppBadge) {
        if (n > 0) return self.navigator.setAppBadge(n);
        return self.navigator.clearAppBadge();
      }
      if (self.registration && self.registration.setAppBadge) {
        if (n > 0) return self.registration.setAppBadge(n);
        return self.registration.clearAppBadge();
      }
    })
    .catch(() => {});
}

self.addEventListener('message', (event) => {
  if (!event.data) return;
  if (event.data.type === 'UPDATE_BADGE') {
    const n = Number(event.data.count) || 0;
    try {
      if (self.navigator && self.navigator.setAppBadge) {
        if (n > 0) self.navigator.setAppBadge(n);
        else self.navigator.clearAppBadge();
      }
    } catch (e) {}
  }
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
