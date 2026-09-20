(function () {
  function $(id) { return document.getElementById(id); }
  var input = $('photo-input');
  var panel = $('crop-panel');
  var img = $('crop-image');
  var box = $('crop-box');
  var hidden = $('photo_cropped');
  var status = $('crop-status');
  var btnOk = $('crop-confirm');
  var btnCancel = $('crop-cancel');
  var btnReset = $('crop-reset');
  var photoInfo = $('photo-info');
  var preview = $('avatar-preview-current');
  if (!input || !panel || !img || !box || !hidden) return;

  var state = { x: 20, y: 20, s: 120, dragging: null, startX: 0, startY: 0, ox: 0, oy: 0, os: 0 };

  function resetCrop(){
    var side = Math.min(img.clientWidth, img.clientHeight) * 0.7;
    if (!side || side < 40) side = 120;
    state.s = side;
    state.x = Math.max(0, (img.clientWidth - side) / 2);
    state.y = Math.max(0, (img.clientHeight - side) / 2);
    clamp(); applyBox(); hidden.value=''; if(status) status.textContent='';
  }

  function applyBox() {
    box.style.left = state.x + 'px';
    box.style.top = state.y + 'px';
    box.style.width = state.s + 'px';
    box.style.height = state.s + 'px';
  }

  function clamp() {
    var rw = img.clientWidth || 1;
    var rh = img.clientHeight || 1;
    state.s = Math.max(40, Math.min(state.s, rw, rh));
    state.x = Math.max(0, Math.min(state.x, rw - state.s));
    state.y = Math.max(0, Math.min(state.y, rh - state.s));
  }

  input.addEventListener('change', function () {
    var f = input.files && input.files[0];
    if (!f) return;
    if (photoInfo) photoInfo.textContent = 'حجم: ' + Math.round(f.size/1024) + 'KB | نوع: ' + (f.type || 'نامشخص');
    if (f.size > 5 * 1024 * 1024) { if(status) status.textContent='حجم تصویر باید کمتر از ۵ مگابایت باشد.'; input.value=''; return; }
    if (!/^image\//.test(f.type || '')) {
      if (status) status.textContent = 'فقط فایل تصویر انتخاب کنید.';
      return;
    }
    var url = URL.createObjectURL(f);
    img.onload = function () {
      panel.style.display = 'block';
      hidden.value = '';
      if (status) status.textContent = 'کادر را تنظیم کنید، سپس «تأیید برش» را بزنید.';
      setTimeout(function () {
        var side = Math.min(img.clientWidth, img.clientHeight) * 0.7;
        if (!side || side < 40) side = 120;
        state.s = side;
        state.x = Math.max(0, (img.clientWidth - side) / 2);
        state.y = Math.max(0, (img.clientHeight - side) / 2);
        applyBox();
      }, 30);
    };
    img.onerror = function () {
      if (status) status.textContent = 'بارگذاری تصویر ناموفق بود.';
    };
    img.src = url;
  });

  function pointerDown(e, mode) {
    e.preventDefault();
    e.stopPropagation();
    var pt = e.touches ? e.touches[0] : e;
    state.dragging = mode;
    state.startX = pt.clientX;
    state.startY = pt.clientY;
    state.ox = state.x;
    state.oy = state.y;
    state.os = state.s;
  }

  box.addEventListener('mousedown', function (e) {
    if (e.target.getAttribute('data-h')) return;
    pointerDown(e, 'move');
  });
  box.addEventListener('touchstart', function (e) {
    if (e.target.getAttribute('data-h')) return;
    pointerDown(e, 'move');
  }, { passive: false });

  box.querySelectorAll('[data-h]').forEach(function (h) {
    h.addEventListener('mousedown', function (e) { pointerDown(e, h.getAttribute('data-h')); });
    h.addEventListener('touchstart', function (e) { pointerDown(e, h.getAttribute('data-h')); }, { passive: false });
  });

  function pointerMove(e) {
    if (!state.dragging) return;
    e.preventDefault();
    var pt = e.touches ? e.touches[0] : e;
    var dx = pt.clientX - state.startX;
    var dy = pt.clientY - state.startY;
    if (state.dragging === 'move') {
      state.x = state.ox + dx;
      state.y = state.oy + dy;
    } else {
      var mode = state.dragging;
      var ns = state.os;
      if (mode === 'se') ns = state.os + Math.max(dx, dy);
      if (mode === 'nw') {
        ns = state.os - Math.max(dx, dy);
        state.x = state.ox + (state.os - ns);
        state.y = state.oy + (state.os - ns);
      }
      if (mode === 'ne') {
        ns = state.os + Math.max(dx, -dy);
        state.y = state.oy + (state.os - ns);
      }
      if (mode === 'sw') {
        ns = state.os + Math.max(-dx, dy);
        state.x = state.ox + (state.os - ns);
      }
      state.s = ns;
    }
    clamp();
    applyBox();
  }
  function pointerUp() { state.dragging = null; }
  window.addEventListener('mousemove', pointerMove);
  window.addEventListener('mouseup', pointerUp);
  window.addEventListener('touchmove', pointerMove, { passive: false });
  window.addEventListener('touchend', pointerUp);

  if (btnReset) { btnReset.addEventListener('click', function(e){ e.preventDefault(); resetCrop(); }); }

  function zoomBy(delta) {
    var cx = state.x + state.s / 2;
    var cy = state.y + state.s / 2;
    state.s += delta;
    state.x = cx - state.s / 2;
    state.y = cy - state.s / 2;
    clamp();
    applyBox();
  }
  var btnZoomIn = $('crop-zoom-in');
  var btnZoomOut = $('crop-zoom-out');
  if (btnZoomIn) { btnZoomIn.addEventListener('click', function(e){ e.preventDefault(); zoomBy(-20); }); }
  if (btnZoomOut) { btnZoomOut.addEventListener('click', function(e){ e.preventDefault(); zoomBy(20); }); }

  if (btnCancel) {
    btnCancel.addEventListener('click', function (e) {
      e.preventDefault();
      panel.style.display = 'none';
      try { input.value = ''; } catch (err) {}
      hidden.value = '';
      if (status) status.textContent = '';
    });
  }

  if (btnOk) {
    btnOk.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (!img.naturalWidth) {
        if (status) status.textContent = 'تصویر هنوز آماده نیست.';
        return;
      }
      try {
        var scaleX = img.naturalWidth / (img.clientWidth || 1);
        var scaleY = img.naturalHeight / (img.clientHeight || 1);
        var sx = Math.round(state.x * scaleX);
        var sy = Math.round(state.y * scaleY);
        var ss = Math.round(state.s * scaleX);
        ss = Math.max(1, Math.min(ss, img.naturalWidth - sx, img.naturalHeight - sy));
        var canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 512;
        var ctx = canvas.getContext('2d');
        ctx.fillStyle = '#fff';
        ctx.fillRect(0, 0, 512, 512);
        ctx.drawImage(img, sx, sy, ss, ss, 0, 0, 512, 512);
        var dataUrl = canvas.toDataURL('image/jpeg', 0.92);
        hidden.value = dataUrl;
        if (preview) {
          if (preview.tagName === 'IMG') {
            preview.src = dataUrl;
          } else {
            var im = document.createElement('img');
            im.id = 'avatar-preview-current';
            im.src = dataUrl;
            im.alt = '';
            im.style.cssText = 'width:140px;height:140px;border-radius:50%;object-fit:cover;border:1px solid var(--border);';
            preview.parentNode.replaceChild(im, preview);
            preview = im;
          }
        }
        if (status) {
          status.textContent = 'برش تأیید شد. روی «ذخیره عکس» بزنید.';
          status.style.color = '#059669';
        }
        panel.style.display = 'none';
        // clear file input so server uses cropped data
        try { input.value = ''; } catch (err) {}
      } catch (err) {
        if (status) status.textContent = 'خطا در برش: ' + (err.message || err);
      }
    });
  }
})();
