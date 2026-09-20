/**
 * Customer picker — یکپارچه، اجباری از طرف‌حساب‌های ثبت‌شده
 * فیلتر استان → شهر + جستجو
 */
(function () {
  'use strict';

  function ensureOverlay() {
    var ov = document.getElementById('cp-overlay');
    if (ov) return ov;
    ov = document.createElement('div');
    ov.id = 'cp-overlay';
    ov.className = 'sg-modal-overlay cp-overlay';
    ov.innerHTML =
      '<div class="sg-modal cp-modal" role="dialog" aria-modal="true" aria-label="انتخاب مشتری">' +
      '  <div class="sg-modal-header cp-modal-header">' +
      '    <div class="sg-modal-header-text">' +
      '      <span class="sg-modal-title cp-modal-title">انتخاب مشتری</span>' +
      '      <span class="sg-modal-subtitle">فقط از طرف‌حساب‌های ثبت‌شده — ثبت نام دلخواه مجاز نیست</span>' +
      '    </div>' +
      '    <button type="button" class="sg-modal-close cp-modal-close" aria-label="بستن">×</button>' +
      '  </div>' +
      '  <div class="sg-modal-toolbar">' +
      '    <div class="sg-filter-row">' +
      '      <select class="cp-filter-province field-select" aria-label="فیلتر استان">' +
      '        <option value="">همه استان‌ها</option>' +
      '      </select>' +
      '      <select class="cp-filter-city field-select" aria-label="فیلتر شهر" disabled>' +
      '        <option value="">همه شهرها</option>' +
      '      </select>' +
      '    </div>' +
      '    <input type="search" class="cp-search sg-modal-search" placeholder="جستجوی نام مشتری…" autocomplete="off">' +
      '  </div>' +
      '  <div class="sg-modal-body cp-modal-body">' +
      '    <ul class="cp-list sg-modal-list" role="listbox"></ul>' +
      '  </div>' +
      '  <div class="sg-modal-footer cp-meta">' +
      '    <span class="cp-meta-text"></span>' +
      '    <span class="sg-modal-hint">با انتخاب مشتری، استان و آدرس خودکار پر می‌شود</span>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(ov);

    ov.addEventListener('click', function (e) {
      if (e.target === ov) closeOverlay();
    });
    ov.querySelector('.cp-modal-close').addEventListener('click', closeOverlay);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && ov.classList.contains('open')) closeOverlay();
    });
    return ov;
  }

  var activeCtx = null;

  function closeOverlay() {
    var ov = document.getElementById('cp-overlay');
    if (ov) {
      ov.classList.remove('open');
      document.body.style.overflow = '';
    }
    activeCtx = null;
  }

  function optionProvince(opt) {
    return (opt.getAttribute('data-province') || '').trim();
  }
  function optionCity(opt) {
    var c = (opt.getAttribute('data-city') || '').trim();
    if (c) return c;
    // fallback: از متن «نام — استان / شهر»
    var t = (opt.textContent || '');
    var m = t.match(/\/\s*([^\s—]+(?:\s+[^\s—]+)*)\s*$/);
    return m ? m[1].trim() : '';
  }
  function optionName(opt) {
    var n = (opt.getAttribute('data-name') || '').trim();
    if (n) return n;
    return (opt.textContent || '').split(' — ')[0].trim();
  }

  function openOverlay(ctx) {
    var ov = ensureOverlay();
    activeCtx = ctx;
    var search = ov.querySelector('.cp-search');
    var list = ov.querySelector('.cp-list');
    var meta = ov.querySelector('.cp-meta-text');
    var provSel = ov.querySelector('.cp-filter-province');
    var citySel = ov.querySelector('.cp-filter-city');
    var activeIdx = -1;
    var visibleLis = [];
    var options = Array.prototype.slice.call(ctx.sel.options || []).filter(function (o) {
      return !!o.value;
    });

    // ساخت لیست استان‌ها
    var provinces = {};
    options.forEach(function (opt) {
      var p = optionProvince(opt);
      if (p) provinces[p] = 1;
    });
    var provList = Object.keys(provinces).sort(function (a, b) {
      return a.localeCompare(b, 'fa');
    });
    provSel.innerHTML = '<option value="">همه استان‌ها</option>';
    provList.forEach(function (p) {
      var o = document.createElement('option');
      o.value = p;
      o.textContent = p;
      provSel.appendChild(o);
    });
    citySel.innerHTML = '<option value="">همه شهرها</option>';
    citySel.disabled = true;

    function rebuildCities() {
      var prov = (provSel.value || '').trim();
      var cities = {};
      options.forEach(function (opt) {
        if (prov && optionProvince(opt) !== prov) return;
        var c = optionCity(opt);
        if (c) cities[c] = 1;
      });
      var cityList = Object.keys(cities).sort(function (a, b) {
        return a.localeCompare(b, 'fa');
      });
      var keep = citySel.value;
      citySel.innerHTML = '<option value="">همه شهرها</option>';
      cityList.forEach(function (c) {
        var o = document.createElement('option');
        o.value = c;
        o.textContent = c;
        citySel.appendChild(o);
      });
      citySel.disabled = !prov;
      if (keep && cities[keep]) citySel.value = keep;
      else citySel.value = '';
    }

    function setActive(i) {
      visibleLis.forEach(function (li) { li.classList.remove('cp-active'); });
      activeIdx = i;
      if (i >= 0 && i < visibleLis.length) {
        visibleLis[i].classList.add('cp-active');
        try { visibleLis[i].scrollIntoView({ block: 'nearest' }); } catch (e) {}
      }
    }

    function buildList() {
      list.innerHTML = '';
      visibleLis = [];
      activeIdx = -1;
      var q = (search.value || '').trim().toLowerCase();
      var prov = (provSel.value || '').trim();
      var city = (citySel.value || '').trim();
      var total = 0;

      options.forEach(function (opt, idx) {
        if (opt.hidden || opt.disabled) return;
        if (opt.style && opt.style.display === 'none') return;
        var p = optionProvince(opt);
        var c = optionCity(opt);
        var name = optionName(opt);
        var label = (opt.textContent || '').trim();
        if (prov && p !== prov) return;
        if (city && c !== city) return;
        if (q && name.toLowerCase().indexOf(q) === -1 && label.toLowerCase().indexOf(q) === -1) return;

        total++;
        var li = document.createElement('li');
        li.className = 'sg-modal-item';
        li.setAttribute('role', 'option');
        li.dataset.index = String(idx);

        var title = document.createElement('div');
        title.className = 'sg-item-title';
        title.textContent = name;

        var sub = document.createElement('div');
        sub.className = 'sg-item-sub';
        var bits = [];
        if (p) bits.push(p);
        if (c) bits.push(c);
        sub.textContent = bits.length ? bits.join(' / ') : '—';

        li.appendChild(title);
        li.appendChild(sub);

        if (String(opt.value) === String(ctx.sel.value)) li.classList.add('cp-selected');
        li.addEventListener('mousedown', function (e) {
          e.preventDefault();
          pick(idx);
        });
        li.addEventListener('mouseenter', function () {
          setActive(visibleLis.indexOf(li));
        });
        list.appendChild(li);
        visibleLis.push(li);
      });

      if (total === 0) {
        var empty = document.createElement('li');
        empty.className = 'sg-modal-empty';
        empty.innerHTML = '<div class="sg-empty-icon">🔍</div><div>مشتری‌ای با این فیلتر یافت نشد</div><div class="sg-empty-hint">استان یا شهر را عوض کنید یا ابتدا طرف‌حساب را در تنظیمات ثبت کنید</div>';
        list.appendChild(empty);
      }
      meta.textContent = total ? (total + ' طرف‌حساب') : 'بدون نتیجه';
      if (visibleLis.length) setActive(0);
    }

    function pick(idx) {
      var opt = options[idx];
      if (!opt || !opt.value) return;
      // find real index in select
      var realIdx = -1;
      for (var i = 0; i < ctx.sel.options.length; i++) {
        if (ctx.sel.options[i] === opt) { realIdx = i; break; }
      }
      if (realIdx < 0) {
        ctx.sel.value = opt.value;
      } else {
        ctx.sel.selectedIndex = realIdx;
      }
      ctx.nameInput.value = optionName(opt);
      ctx.nameInput.readOnly = true;
      if (ctx.btn) {
        var btnText = ctx.btn.querySelector('.cp-label-text');
        if (btnText) btnText.textContent = optionName(opt);
      }
      closeOverlay();
      try {
        ctx.sel.dispatchEvent(new Event('change', { bubbles: true }));
      } catch (e) {}
      if (typeof window.fillCustomer === 'function' && ctx.sel.id === 'customer_id') {
        try { window.fillCustomer(); } catch (e) {}
      }
      if (typeof window.fillCaCustomer === 'function' && ctx.sel.id === 'ca_customer_id') {
        try { window.fillCaCustomer(); } catch (e) {}
      }
      try { ctx.nameInput.focus(); } catch (e) {}
    }

    provSel.onchange = function () {
      rebuildCities();
      buildList();
    };
    citySel.onchange = function () { buildList(); };
    search.oninput = function () { buildList(); };
    search.onkeydown = function (e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeOverlay();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (visibleLis.length) setActive(Math.min(activeIdx + 1, visibleLis.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (visibleLis.length) setActive(Math.max(activeIdx - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (activeIdx >= 0 && visibleLis[activeIdx]) {
          pick(parseInt(visibleLis[activeIdx].dataset.index, 10));
        }
      }
    };

    search.value = '';
    rebuildCities();
    buildList();
    ov.classList.add('open');
    document.body.style.overflow = 'hidden';
    setTimeout(function () { search.focus(); }, 40);
  }

  function buildPicker(root) {
    if (!root || root.dataset.cpReady === '1') return;
    var sel = root.querySelector('select.cp-source');
    var nameInput = root.querySelector('input.cp-name, input[name="customer_name"], #customer_name, #ca_customer_name');
    if (!sel || !nameInput) return;
    root.dataset.cpReady = '1';

    sel.classList.add('cp-source-hidden');
    sel.tabIndex = -1;
    sel.setAttribute('aria-hidden', 'true');

    // نام مشتری فقط از لیست — تایپ آزاد مجاز نیست
    nameInput.readOnly = true;
    nameInput.placeholder = 'از دکمه «نام مشتری» انتخاب کنید';
    nameInput.classList.add('cp-name-locked');
    var oldCtrl = root.querySelector('.cp-control');
    if (oldCtrl) {
      if (oldCtrl.contains(nameInput)) root.insertBefore(nameInput, oldCtrl);
      if (oldCtrl.contains(sel)) root.insertBefore(sel, oldCtrl);
      oldCtrl.remove();
    }

    var existingBtn = root.querySelector('.cp-label-btn');
    if (!existingBtn) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cp-label-btn rtp-btn btn-cancel';
      btn.innerHTML =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-left:4px;flex-shrink:0;"><path d="M12 5v14M5 12h14"/></svg>' +
        '<span class="cp-label-text">نام مشتری</span>';
      var lab = root.querySelector('label');
      if (lab && !lab.classList.contains('field-hint-check')) {
        lab.classList.add('cp-label-small');
        var labText = (lab.textContent || '').trim() || 'نام مشتری';
        btn.querySelector('.cp-label-text').textContent = labText;
        if (lab.nextSibling) lab.parentNode.insertBefore(btn, lab.nextSibling);
        else lab.parentNode.appendChild(btn);
      } else {
        root.insertBefore(btn, root.firstChild);
      }
      existingBtn = btn;
    }
    // اگر مقدار از قبل پر بود (مثلاً بازکردن مجدد فرم)، متن دکمه را همان نام کن
    if (nameInput.value) {
      var t0 = existingBtn.querySelector('.cp-label-text');
      if (t0) t0.textContent = nameInput.value;
    }

    // غنی‌سازی data-city از متن option اگر نبود
    Array.prototype.forEach.call(sel.options, function (opt) {
      if (!opt.value) return;
      if (!opt.getAttribute('data-city')) {
        var t = opt.textContent || '';
        var m = t.match(/\/\s*([^—]+)\s*$/);
        if (m) opt.setAttribute('data-city', m[1].trim());
      }
    });

    var ctx = { sel: sel, nameInput: nameInput, root: root, btn: existingBtn };
    existingBtn.addEventListener('click', function (e) {
      e.preventDefault();
      openOverlay(ctx);
    });
    nameInput.addEventListener('click', function (e) {
      e.preventDefault();
      openOverlay(ctx);
    });

    sel.addEventListener('change', function () {
      var opt = sel.options[sel.selectedIndex];
      if (opt && opt.value) {
        nameInput.value = optionName(opt);
        var t = existingBtn.querySelector('.cp-label-text');
        if (t) t.textContent = optionName(opt);
      }
    });
  }

  function enhanceAll(root) {
    (root || document).querySelectorAll('.customer-field-block, .cp-root').forEach(buildPicker);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { enhanceAll(document); });
  } else {
    enhanceAll(document);
  }

  window.enhanceCustomerPickers = enhanceAll;
  window.closeCustomerPicker = closeOverlay;
})();
