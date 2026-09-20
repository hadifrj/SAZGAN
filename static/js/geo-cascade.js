/**
 * استان → شهرستان → شهر (cascading select)
 * Depends on API:
 *   GET /api/geo/counties?province=...
 *   GET /api/geo/cities?province=...&county=...
 */
(function () {
  'use strict';

  function fillSelect(sel, items, selected) {
    if (!sel) return;
    var keepFirst = sel.options.length && sel.options[0].value === '';
    var firstLabel = keepFirst ? sel.options[0].text : '— انتخاب —';
    sel.innerHTML = '';
    var opt0 = document.createElement('option');
    opt0.value = '';
    opt0.textContent = firstLabel;
    sel.appendChild(opt0);
    (items || []).forEach(function (name) {
      var o = document.createElement('option');
      o.value = name;
      o.textContent = name;
      if (selected && selected === name) o.selected = true;
      sel.appendChild(o);
    });
  }

  function fetchJson(url) {
    return fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .catch(function () { return { items: [] }; });
  }

  window.onGeoProvinceChange = function (el) {
    var root = el.closest('form') || document;
    var province = el.value || '';
    var countySel = root.querySelector('.geo-county') || root.querySelector('#county');
    var citySel = root.querySelector('.geo-city') || root.querySelector('#city');
    var cityManual = root.querySelector('.geo-city-manual') || root.querySelector('#city_manual');

    fillSelect(countySel, [], '');
    fillSelect(citySel, [], '');
    if (cityManual) cityManual.value = '';

    if (!province) return;

    fetchJson('/api/geo/counties?province=' + encodeURIComponent(province))
      .then(function (data) {
        var items = data.items || data.counties || [];
        var preferred = (countySel && countySel.getAttribute('data-selected')) || '';
        fillSelect(countySel, items, preferred);
        if (countySel) countySel.removeAttribute('data-selected');
        if (preferred) {
          window.onGeoCountyChange(countySel);
        } else if (!items.length && citySel) {
          // no counties — allow free text city
          if (cityManual) {
            cityManual.style.display = '';
            citySel.style.display = 'none';
          }
        }
      });
  };

  window.onGeoCountyChange = function (el) {
    var root = el.closest('form') || document;
    var provinceSel = root.querySelector('.geo-province') || root.querySelector('#province');
    var province = provinceSel ? provinceSel.value : '';
    var county = el.value || '';
    var citySel = root.querySelector('.geo-city') || root.querySelector('#city');
    var cityManual = root.querySelector('.geo-city-manual') || root.querySelector('#city_manual');

    fillSelect(citySel, [], '');

    if (!province) return;

    var url = '/api/geo/cities?province=' + encodeURIComponent(province);
    if (county) url += '&county=' + encodeURIComponent(county);

    fetchJson(url).then(function (data) {
      var items = data.items || data.cities || [];
      var preferred = (citySel && citySel.getAttribute('data-selected')) || '';
      fillSelect(citySel, items, preferred);
      if (citySel) citySel.removeAttribute('data-selected');

      if (!items.length && cityManual) {
        cityManual.style.display = '';
        if (citySel) citySel.style.display = 'none';
        if (preferred) cityManual.value = preferred;
      } else if (cityManual) {
        cityManual.style.display = 'none';
        if (citySel) citySel.style.display = '';
      }
    });
  };

  // On form submit: if city select empty, use city_manual
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || !form.querySelector) return;
    var citySel = form.querySelector('.geo-city') || form.querySelector('#city');
    var cityManual = form.querySelector('.geo-city-manual') || form.querySelector('#city_manual');
    if (citySel && cityManual && !citySel.value && cityManual.value) {
      // inject hidden or set select option
      var opt = document.createElement('option');
      opt.value = cityManual.value;
      opt.selected = true;
      citySel.appendChild(opt);
    }
  }, true);

  // Init on load for edit forms that already have province selected
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.geo-province').forEach(function (el) {
      if (el.value) {
        window.onGeoProvinceChange(el);
      }
    });
  });
})();
