/**
 * یکسان‌سازی انتخاب فایل — شبیه «آپلود سریع»
 * هر input[type=file] (بدون data-fp="off") به دکمه خط‌چین تبدیل می‌شود.
 * ورودی‌هایی که از قبل UI سفارشی دارند (مخفی / داخل جعبه پروفایل / برچسب دکمه) رد می‌شوند
 * تا دکمهٔ اضافه روی کنترل آپلود ظاهر نشود.
 */
(function () {
  'use strict';

  function isAlreadyCustomUI(input) {
    if (!input) return true;
    if (input.dataset.fp === 'off') return true;
    if (input.closest('.fp-wrap')) return true;
    if (input.closest('.profile-upload-box')) return true;
    if (input.closest('.avatar-crop') || input.closest('[data-avatar-crop]')) return true;

    // مخفی بودن با style یا کلاس
    var style = window.getComputedStyle ? window.getComputedStyle(input) : null;
    if (input.style && (input.style.display === 'none' || input.style.visibility === 'hidden')) return true;
    if (style && (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0')) return true;
    if (input.classList && (input.classList.contains('sr-only') || input.classList.contains('visually-hidden'))) return true;

    // اگر label[for] به صورت دکمه استایل شده، UI سفارشی است
    if (input.id) {
      var lab = document.querySelector('label[for="' + input.id + '"]');
      if (lab) {
        var lc = (lab.className || '').toString();
        if (/\bbtn\b|\bbtn-primary\b|\bbtn-secondary\b|profile-upload-btn|upload-btn/i.test(lc)) return true;
      }
    }
    return false;
  }

  function enhance(input) {
    if (!input || input.dataset.fpReady === '1') return;
    if (isAlreadyCustomUI(input)) {
      input.dataset.fpReady = '1';
      return;
    }
    input.dataset.fpReady = '1';

    var wrap = document.createElement('div');
    wrap.className = 'fp-wrap';

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'fp-btn';
    btn.innerHTML =
      '<svg class="fp-icon" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>' +
      '<span class="fp-label">انتخاب فایل</span>';

    var nameSpan = document.createElement('div');
    nameSpan.className = 'fp-name';
    nameSpan.hidden = true;

    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(btn);
    wrap.appendChild(nameSpan);
    wrap.appendChild(input);
    input.classList.add('fp-native');

    function sync() {
      var files = input.files;
      if (files && files.length) {
        var names = [];
        for (var i = 0; i < files.length; i++) names.push(files[i].name);
        nameSpan.textContent = names.join('، ');
        nameSpan.hidden = false;
        btn.querySelector('.fp-label').textContent = files.length > 1 ? (files.length + ' فایل انتخاب شد') : 'تغییر فایل';
        wrap.classList.add('has-file');
      } else {
        nameSpan.hidden = true;
        nameSpan.textContent = '';
        btn.querySelector('.fp-label').textContent = 'انتخاب فایل';
        wrap.classList.remove('has-file');
      }
    }

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      input.click();
    });
    input.addEventListener('change', sync);
    sync();
  }

  function enhanceAll(root) {
    (root || document).querySelectorAll('input[type="file"]').forEach(enhance);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { enhanceAll(document); });
  } else {
    enhanceAll(document);
  }

  window.enhanceFilePickers = enhanceAll;
})();
