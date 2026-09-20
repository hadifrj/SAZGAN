/* اعتبارسنجی فرم‌های سازگان — پیام‌های فارسی، تاریخ شمسی واقعی */
(function () {
  'use strict';

  function toEnglishDigits(s) {
    return String(s || '')
      .replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 1728); })
      .replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 1632); });
  }

  var JAL_BREAKS = [-61,9,38,199,426,686,756,818,1111,1181,1210,1635,2060,2097,2192,2262,2324,2394,2456,3178];
  function isLeapJalali(jy) {
    var bl = JAL_BREAKS.length, leapJ = -14, jp = JAL_BREAKS[0], jump = 0;
    for (var i = 1; i < bl; i++) {
      var jm = JAL_BREAKS[i];
      jump = jm - jp;
      if (jy < jm) break;
      leapJ = leapJ + Math.floor(jump / 33) * 8 + Math.floor((jump % 33) / 4);
      jp = jm;
    }
    var n = jy - jp;
    if (jump - n < 6) n = n - jump + Math.floor((jump + 4) / 33) * 33;
    var leap = (((n + 1) % 33) - 1) % 4;
    if (leap === -1) leap = 4;
    return leap === 0;
  }

  function daysInJalaliMonth(jy, jm) {
    if (jm >= 1 && jm <= 6) return 31;
    if (jm >= 7 && jm <= 11) return 30;
    return isLeapJalali(jy) ? 30 : 29;
  }

  /** اعتبار تاریخ شمسی واقعی (نه فقط الگوی رشته) */
  function parseJalaliDate(str) {
    var s = toEnglishDigits(str).trim().replace(/-/g, '/');
    var m = s.match(/^(\d{3,4})\/(\d{1,2})\/(\d{1,2})$/);
    if (!m) return null;
    var y = +m[1], mo = +m[2], d = +m[3];
    if (y < 1300 || y > 1500) return null;
    if (mo < 1 || mo > 12) return null;
    var dim = daysInJalaliMonth(y, mo);
    if (d < 1 || d > dim) return null;
    return { y: y, m: mo, d: d };
  }

  function isValidJalaliDate(str) {
    if (!str || !String(str).trim()) return true; // خالی = اختیاری مگر required
    return !!parseJalaliDate(str);
  }

  function labelText(el) {
    var id = el.getAttribute('id');
    var lab = null;
    if (id) lab = document.querySelector('label[for="' + id + '"]');
    if (!lab) {
      var p = el.closest('div, .field, .filter-field, td, label');
      if (p) lab = p.querySelector('label');
    }
    if (lab) {
      return (lab.textContent || '')
        .replace(/\*/g, '')
        .replace(/\(.*?\)/g, '')
        .replace(/\s+/g, ' ')
        .trim();
    }
    return el.getAttribute('name') || 'این مورد';
  }

  function clearErrors(form) {
    form.querySelectorAll('.field-error-msg').forEach(function (n) { n.remove(); });
    form.querySelectorAll('.field-invalid').forEach(function (n) {
      n.classList.remove('field-invalid');
    });
    var ban = form.querySelector('.form-error-banner');
    if (ban) ban.remove();
  }

  function markInvalid(el, msg) {
    el.classList.add('field-invalid');
    var wrap = el.closest('.ss-wrap');
    if (wrap) wrap.classList.add('field-invalid');
    var host = el.closest('div, .field, .filter-field') || el.parentElement;
    if (!host) return;
    if (host.querySelector('.field-error-msg')) return;
    var span = document.createElement('span');
    span.className = 'field-error-msg';
    span.textContent = msg;
    host.appendChild(span);
  }

  function isEmpty(el) {
    if (el.type === 'checkbox' || el.type === 'radio') {
      if (el.type === 'radio') {
        var name = el.name;
        var group = el.form ? el.form.querySelectorAll('input[type=radio][name="' + name + '"]') : [];
        return !Array.prototype.some.call(group, function (r) { return r.checked; });
      }
      return !el.checked;
    }
    return !(el.value || '').toString().trim();
  }

  function validatePhone(v) {
    var s = toEnglishDigits(v).replace(/[\s\-()]/g, '');
    if (!s) return true;
    return /^(0|\+98|98)?9\d{9}$/.test(s) || /^0\d{8,11}$/.test(s);
  }

  function isDateField(el) {
    if (el.classList && el.classList.contains('jalali-date')) return true;
    if (el.getAttribute('data-jalali') != null) return true;
    var n = ((el.name || '') + ' ' + (el.id || '')).toLowerCase();
    if (!/date|تاریخ|jalali/.test(n)) return false;
    if (/time|ساعت|datetime|updated|created/.test(n)) return false;
    return el.tagName === 'INPUT';
  }

  function validateForm(form) {
    clearErrors(form);
    var firstBad = null;
    var missing = [];

    form.querySelectorAll('[required]').forEach(function (el) {
      if (el.disabled) return;
      if (isEmpty(el)) {
        var name = labelText(el);
        markInvalid(el, name + ' را وارد کنید');
        missing.push(name);
        if (!firstBad) firstBad = el;
      }
    });

    form.querySelectorAll('input[type="tel"], input[name*="phone"], input[name*="mobile"], input[inputmode="tel"]').forEach(function (el) {
      if (el.disabled) return;
      var v = (el.value || '').trim();
      if (v && !validatePhone(v)) {
        markInvalid(el, 'شماره تماس را بررسی کنید');
        if (!firstBad) firstBad = el;
      }
    });

    form.querySelectorAll('input').forEach(function (el) {
      if (el.disabled || el.readOnly) return;
      if (!isDateField(el)) return;
      var v = (el.value || '').trim();
      if (!v) return;
      if (!isValidJalaliDate(v)) {
        markInvalid(el, 'تاریخ شمسی معتبر نیست (مثال: ۱۴۰۵/۰۱/۱۵)');
        if (!firstBad) firstBad = el;
      }
    });

    if (firstBad) {
      var ban = document.createElement('div');
      ban.className = 'form-error-banner';
      ban.setAttribute('role', 'alert');
      ban.textContent = missing.length
        ? 'چند مورد نیاز به تکمیل دارد: ' + missing.slice(0, 4).join('، ') + (missing.length > 4 ? '…' : '')
        : 'لطفاً موارد مشخص‌شده را اصلاح کنید';
      form.insertBefore(ban, form.firstChild);
      try { firstBad.focus({ preventScroll: false }); } catch (e) { firstBad.focus(); }
      try { firstBad.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e2) {}
      return false;
    }
    return true;
  }

  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (!form || form.tagName !== 'FORM') return;
    if (form.getAttribute('data-no-validate') === '1') return;
    if (form.method && form.method.toLowerCase() === 'get' && !form.querySelector('[required]')) return;
    if (!validateForm(form)) {
      ev.preventDefault();
      ev.stopPropagation();
    }
  }, true);

  document.addEventListener('input', function (ev) {
    var el = ev.target;
    if (!el || !el.classList) return;
    if (el.classList.contains('field-invalid')) {
      el.classList.remove('field-invalid');
      var wrap = el.closest('.ss-wrap');
      if (wrap) wrap.classList.remove('field-invalid');
      var host = el.closest('div, .field, .filter-field');
      if (host) {
        var msg = host.querySelector('.field-error-msg');
        if (msg) msg.remove();
      }
    }
  }, true);

  window.SazganValidate = {
    validateForm: validateForm,
    clearErrors: clearErrors,
    isValidJalaliDate: isValidJalaliDate,
    parseJalaliDate: parseJalaliDate
  };
})();
