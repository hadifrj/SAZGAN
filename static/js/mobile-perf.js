/**
 * Sazgan mobile performance helpers
 * - Instant navigation feedback (loading bar)
 * - Prefetch on touch/hover for common links
 * - Preserve scroll position lightly
 * - Reduce work when tab hidden
 */
(function () {
  'use strict';

  var bar = null;
  function getBar() {
    if (!bar) bar = document.getElementById('page-loading-bar');
    return bar;
  }

  function startProgress() {
    var el = getBar();
    if (!el) return;
    el.classList.add('active');
    el.style.width = '18%';
    requestAnimationFrame(function () {
      el.style.width = '55%';
    });
    setTimeout(function () {
      if (el.classList.contains('active')) el.style.width = '78%';
    }, 400);
  }

  function endProgress() {
    var el = getBar();
    if (!el) return;
    el.style.width = '100%';
    setTimeout(function () {
      el.classList.remove('active');
      el.style.width = '0%';
    }, 180);
  }

  // Show bar on internal navigations
  document.addEventListener(
    'click',
    function (e) {
      var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
      if (!a) return;
      var href = a.getAttribute('href') || '';
      if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0) return;
      if (a.target === '_blank' || a.hasAttribute('download')) return;
      if (href.indexOf('http') === 0 && href.indexOf(location.origin) !== 0) return;
      // same-page anchors
      if (href.charAt(0) === '/' || href.indexOf(location.origin) === 0) {
        startProgress();
      }
    },
    true
  );

  window.addEventListener('pageshow', function () {
    endProgress();
  });
  document.addEventListener('DOMContentLoaded', function () {
    endProgress();
  });

  // Prefetch common destinations
  var seen = Object.create(null);
  function prefetch(href) {
    if (!href || href.charAt(0) !== '/') return;
    if (seen[href]) return;
    seen[href] = 1;
    try {
      var l = document.createElement('link');
      l.rel = 'prefetch';
      l.href = href;
      l.as = 'document';
      document.head.appendChild(l);
    } catch (e) {}
  }

  var PREFETCH_SELECTORS =
    'a.sidebar-link, a.sidebar-sublink, a.bn-item, a.settings-tab, a.ca-tab, a.ui-tab, .list-header-actions a, .card-action';

  document.addEventListener(
    'pointerdown',
    function (e) {
      var a = e.target && e.target.closest ? e.target.closest(PREFETCH_SELECTORS) : null;
      if (a && a.getAttribute) prefetch(a.getAttribute('href') || a.pathname);
    },
    { passive: true, capture: true }
  );

  // Idle prefetch of primary destinations
  function idlePrefetch() {
    ['/cartable', '/dashboard', '/notifications', '/search', '/customer-affairs/open-list'].forEach(
      function (h) {
        prefetch(h);
      }
    );
  }
  if ('requestIdleCallback' in window) {
    requestIdleCallback(idlePrefetch, { timeout: 2500 });
  } else {
    setTimeout(idlePrefetch, 1800);
  }

  // Pause non-critical intervals when hidden (hook for other scripts)
  document.addEventListener('visibilitychange', function () {
    document.documentElement.classList.toggle('tab-hidden', document.hidden);
  });

  // Mark touch devices for CSS
  try {
    if (window.matchMedia('(hover: none) and (pointer: coarse)').matches) {
      document.documentElement.classList.add('is-touch');
    }
  } catch (e) {}
})();
