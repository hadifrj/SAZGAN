/**
 * نقشه تعاملی ایران — SVG از IranMap v1.1.0 (MohammadReza Pourmohammad)
 * کلیک روی استان → انتخاب شهر
 */
(function () {
  'use strict';

  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'className') n.className = attrs[k];
        else if (k === 'text') n.textContent = attrs[k];
        else if (k.indexOf('on') === 0) n.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
        else n.setAttribute(k, attrs[k]);
      });
    }
    (children || []).forEach(function (c) {
      if (c == null) return;
      n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return n;
  }

  function ensureCityModal() {
    var m = document.getElementById('iran-city-modal');
    if (m) return m;
    m = el('div', { id: 'iran-city-modal', className: 'iran-city-modal' });
    m.innerHTML =
      '<div class="iran-city-dialog" role="dialog" aria-modal="true">' +
      '  <div class="iran-city-header"><span class="iran-city-title"></span></div>' +
      '  <div class="iran-city-body"><div class="iran-city-list"></div></div>' +
      '  <div class="iran-city-footer">' +
      '    <button type="button" class="btn iran-city-confirm">تأیید</button>' +
      '    <button type="button" class="btn-cancel iran-city-back">بازگشت</button>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(m);
    m.addEventListener('click', function (e) {
      if (e.target === m) closeCityModal();
    });
    m.querySelector('.iran-city-back').addEventListener('click', closeCityModal);
    return m;
  }

  var selectedCities = [];
  var currentProvince = null;

  function closeCityModal() {
    var m = document.getElementById('iran-city-modal');
    if (m) m.classList.remove('open');
    document.body.style.overflow = '';
  }

  function openCityModal(province) {
    currentProvince = province;
    selectedCities = [];
    var m = ensureCityModal();
    m.querySelector('.iran-city-title').textContent = 'انتخاب شهر در ' + province.name;
    var list = m.querySelector('.iran-city-list');
    list.innerHTML = '';
    (province.cities || []).forEach(function (city) {
      var row = el('label', { className: 'iran-city-row' }, [
        el('input', { type: 'checkbox', value: city }),
        el('span', { text: city })
      ]);
      row.querySelector('input').addEventListener('change', function () {
        var v = this.value;
        if (this.checked) {
          if (selectedCities.indexOf(v) < 0) selectedCities.push(v);
        } else {
          selectedCities = selectedCities.filter(function (c) { return c !== v; });
        }
      });
      list.appendChild(row);
    });
    if (!(province.cities || []).length) {
      list.appendChild(el('div', { className: 'iran-city-empty', text: 'شهری برای این استان تعریف نشده است.' }));
    }
    m.querySelector('.iran-city-confirm').onclick = function () {
      var info = document.getElementById('iran-map-selection');
      if (info) {
        info.innerHTML =
          '<strong>' + province.name + '</strong>' +
          (selectedCities.length ? ' — ' + selectedCities.join('، ') : ' (شهری انتخاب نشد)');
      }
      try {
        document.dispatchEvent(new CustomEvent('iran-map-select', {
          detail: { province: province.name, cities: selectedCities.slice() }
        }));
      } catch (e) {}
      closeCityModal();
    };
    m.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function mount(root, data) {
    root.innerHTML = '';
    var provinces = data.provinces || [];
    var app = el('div', { className: 'iran-map-app' });
    var svgWrap = el('div', { className: 'iran-map-svg-wrap' });
    var tip = el('div', { className: 'iran-map-tip', text: '' });
    tip.style.display = 'none';

    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', data.viewBox || '20 0 970 960');
    svg.setAttribute('class', 'iran-map-svg');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'نقشه ایران');

    function addPath(d, className, fill, stroke, strokeWidth, interactive) {
      if (!d) return null;
      var path = document.createElementNS(ns, 'path');
      path.setAttribute('d', d);
      if (className) path.setAttribute('class', className);
      path.style.fill = fill;
      path.style.stroke = stroke || 'none';
      path.style.strokeWidth = strokeWidth || '0';
      if (!interactive) path.style.pointerEvents = 'none';
      svg.appendChild(path);
      return path;
    }

    // seas
    (data.seas || []).forEach(function (s) {
      addPath(s.d, 'iran-sea ' + (s.class || ''), '#5dade2', 'none', 0, false);
    });
    // lakes
    (data.lakes || []).forEach(function (s) {
      addPath(s.d, 'iran-lake ' + (s.class || ''), '#7ec8e3', 'none', 0, false);
    });
    // islands (non-interactive)
    (data.islands || []).forEach(function (s) {
      addPath(s.d, 'iran-island ' + (s.class || ''), '#94a3b8', '#fff', 0.4, false);
    });

    var selectedId = null;
    var pathById = {};

    provinces.forEach(function (p) {
      var path = addPath(p.d, 'iran-prov-path', '#9ca3af', '#ffffff', 1.1, true);
      if (!path) return;
      path.setAttribute('data-id', String(p.id));
      path.setAttribute('data-name', p.name);
      path.style.cursor = 'pointer';
      path.style.transition = 'fill 0.15s ease';
      pathById[p.id] = path;

      path.addEventListener('mouseenter', function (ev) {
        if (String(p.id) !== String(selectedId)) path.style.fill = '#60a5fa';
        tip.textContent = p.name;
        tip.style.display = 'block';
        moveTip(ev);
      });
      path.addEventListener('mousemove', moveTip);
      path.addEventListener('mouseleave', function () {
        if (String(p.id) !== String(selectedId)) path.style.fill = '#9ca3af';
        tip.style.display = 'none';
      });
      path.addEventListener('click', function () {
        selectedId = p.id;
        Object.keys(pathById).forEach(function (id) {
          pathById[id].style.fill = '#9ca3af';
        });
        path.style.fill = '#2563eb';
        openCityModal(p);
      });
    });

    function moveTip(ev) {
      var rect = svgWrap.getBoundingClientRect();
      var x = (ev.clientX - rect.left) + 12;
      var y = (ev.clientY - rect.top) + 12;
      tip.style.left = x + 'px';
      tip.style.top = y + 'px';
    }

    svgWrap.appendChild(svg);
    svgWrap.appendChild(tip);
    svgWrap.style.position = 'relative';

    var side = el('div', { className: 'iran-map-side' }, [
      el('div', { className: 'iran-map-info' }, [
        el('div', { className: 'iran-map-info-title', text: 'انتخاب فعلی' }),
        el('div', { id: 'iran-map-selection', className: 'iran-map-info-name', text: '— روی نقشه کلیک کنید —' })
      ]),
      el('div', { className: 'iran-map-list' })
    ]);
    var list = side.querySelector('.iran-map-list');
    provinces.slice().sort(function (a, b) {
      return (a.name || '').localeCompare(b.name || '', 'fa');
    }).forEach(function (p) {
      var btn = el('button', {
        type: 'button',
        className: 'iran-map-chip',
        text: p.name,
        onClick: function () {
          selectedId = p.id;
          Object.keys(pathById).forEach(function (id) {
            pathById[id].style.fill = (String(id) === String(p.id)) ? '#2563eb' : '#9ca3af';
          });
          openCityModal(p);
        }
      });
      list.appendChild(btn);
    });

    app.appendChild(svgWrap);
    app.appendChild(side);
    root.innerHTML = '';
    root.appendChild(app);
  }

  var MAP_CACHE_KEY = 'sazgan-iran-map-v2';

  function applyMapData(root, data) {
    if (data && data.provinces) mount(root, data);
    else if (Array.isArray(data)) mount(root, { viewBox: '20 0 970 960', provinces: data });
    else mount(root, { viewBox: '20 0 970 960', provinces: (data && data.provinces) || [] });
  }

  function init() {
    var root = document.getElementById('iran-map-root');
    if (!root) return;
    root.innerHTML = '<div class="iran-map-loading">در حال بارگذاری نقشه…</div>';

    // 1) instant paint from localStorage cache if available
    try {
      var cached = localStorage.getItem(MAP_CACHE_KEY);
      if (cached) {
        applyMapData(root, JSON.parse(cached));
      }
    } catch (e) {}

    // 2) network fetch (cache-first; update in background)
    var url = '/static/data/iran-map.json';
    fetch(url, { credentials: 'same-origin', cache: 'force-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('map');
        return r.json();
      })
      .then(function (data) {
        try { localStorage.setItem(MAP_CACHE_KEY, JSON.stringify(data)); } catch (e) {}
        // remount only if not already mounted from cache, or always refresh for correctness
        applyMapData(root, data);
      })
      .catch(function () {
        if (root.querySelector('.iran-map-app')) return; // already have cache
        fetch('/static/data/iran-provinces.json', { cache: 'force-cache' })
          .then(function (r) { return r.json(); })
          .then(function (provinces) {
            applyMapData(root, { viewBox: '20 0 970 960', provinces: provinces });
          })
          .catch(function () {
            root.innerHTML = '<div class="iran-map-loading">بارگذاری نقشه ناموفق بود.</div>';
          });
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
