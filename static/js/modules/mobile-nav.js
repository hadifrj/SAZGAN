/* این فایل بخشی از تفکیک base-ui.js (فاز ۲، بخش ۲) است — کد بدون تغییر منطق از static/js/base-ui.js منتقل شده. */

/* --- block 2 --- */
if(window.self!==window.top){document.documentElement.classList.add('in-iframe');}

(function(){
      function showMobileBottomNav(){
        var nav = document.getElementById('mobile-bottom-nav');
        if (!nav) return;
        var desktop = (window.innerWidth || 0) >= 901;
        nav.style.display = desktop ? 'none' : 'flex';
        document.body.classList.toggle('has-mobile-bottom-nav', !desktop);
        if (desktop) {
          // ensure collapsed on desktop
          var sheet = document.getElementById('bn-sheet');
          if (sheet) {
            sheet.classList.remove('bn-expanded', 'bn-dragging');
            sheet.style.setProperty('--bn-drag', '0px');
            document.body.classList.remove('bn-nav-expanded');
          }
        }
      }
      showMobileBottomNav();
      window.addEventListener('resize', showMobileBottomNav);
      window.addEventListener('orientationchange', function(){ setTimeout(showMobileBottomNav, 120); });
    })();

(function(){
      var sheet = document.getElementById('bn-sheet');
      var nav = document.getElementById('mobile-bottom-nav');
      var handle = document.getElementById('bn-handle');
      var extra = document.getElementById('bn-extra-row');
      var centerBtn = document.getElementById('bn-center-drag');
      var mainRow = sheet ? sheet.querySelector('.bn-main-row') : null;
      if (!sheet || !nav || !handle || !extra) return;

      var EXTRA_H = 64;
      var THRESHOLD = 28;
      var VELOCITY_THRESHOLD = 0.35;
      var MOVE_SLOP = 5;      // px قبل از شروع رسمی درگ
      var CLICK_SLOP = 6;     // px قبل از سرکوب کلیک زیرین
      var VEL_SAMPLES = 4;    // تعداد نمونه برای محاسبه سرعت (نرم‌تر و دقیق‌تر از آخرین نمونه تنها)

      var expanded = false;
      var dragging = false;
      var startY = 0, startX = 0;
      var dragY = 0;
      var startDragY = 0;
      var suppressClick = false;
      var activePointerId = null;

      // نمونه‌های اخیر { t, y } برای محاسبه سرعت روان (به‌جای فقط دو نقطهٔ آخر)
      var samples = [];

      // بچ کردن نوشتن استایل روی requestAnimationFrame تا از layout/paint تکراری
      // به‌ازای هر رویداد pointermove (که می‌تونه خیلی پرتکرار باشه) جلوگیری شود.
      var pendingY = null;
      var rafId = null;
      function flushDrag() {
        rafId = null;
        if (pendingY === null) return;
        var y = pendingY;
        pendingY = null;
        y = Math.max(0, Math.min(EXTRA_H, y));
        dragY = y;
        sheet.style.setProperty('--bn-drag', y + 'px');
        var fully = y >= EXTRA_H - 1;
        sheet.classList.toggle('bn-expanded', fully);
        extra.style.pointerEvents = fully ? 'auto' : 'none';
      }
      function scheduleDrag(y) {
        pendingY = y;
        if (rafId === null) rafId = requestAnimationFrame(flushDrag);
      }

      function isDesktop() {
        return (window.innerWidth || 0) >= 901;
      }

      function setExpanded(on) {
        expanded = !!on;
        sheet.classList.remove('bn-dragging');
        pendingY = null;
        if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null; }
        dragY = expanded ? EXTRA_H : 0;
        sheet.style.setProperty('--bn-drag', dragY + 'px');
        sheet.classList.toggle('bn-expanded', expanded);
        handle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        extra.setAttribute('aria-hidden', expanded ? 'false' : 'true');
        document.body.classList.toggle('bn-nav-expanded', expanded);
        extra.style.pointerEvents = expanded ? 'auto' : 'none';
        if (centerBtn) {
          centerBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        }
      }

      function currentVelocity() {
        if (samples.length < 2) return 0;
        var first = samples[0];
        var last = samples[samples.length - 1];
        var dt = last.t - first.t;
        if (dt <= 0) return 0;
        // مثبت یعنی رو به بالا (سرعت باز شدن)
        return (first.y - last.y) / dt;
      }

      function onStart(clientX, clientY, pointerId) {
        if (isDesktop()) return;
        dragging = true;
        suppressClick = false;
        activePointerId = pointerId;
        startY = clientY;
        startX = clientX;
        samples = [{ t: performance.now(), y: clientY }];
        startDragY = expanded ? EXTRA_H : 0;
        dragY = startDragY;
        sheet.classList.add('bn-dragging');
      }

      function onMove(clientX, clientY) {
        if (!dragging) return;
        var dy = startY - clientY; // بالا = مثبت
        var dx = clientX - startX;
        if (Math.abs(dy) < MOVE_SLOP && Math.abs(dx) < MOVE_SLOP) return;
        // اگر حرکت اصلی افقیه، یعنی درگ عمودی نیست؛ رها کن تا اسکرول/تپ افقی طبیعی بمونه
        if (Math.abs(dx) > Math.abs(dy) * 1.35 && Math.abs(dx) > 14) {
          dragging = false;
          sheet.classList.remove('bn-dragging');
          setExpanded(expanded);
          return;
        }
        if (Math.abs(dy) > CLICK_SLOP) suppressClick = true;
        scheduleDrag(startDragY + dy);
        samples.push({ t: performance.now(), y: clientY });
        if (samples.length > VEL_SAMPLES) samples.shift();
      }

      function onEnd() {
        if (!dragging) return;
        dragging = false;
        activePointerId = null;
        sheet.classList.remove('bn-dragging');
        var velocity = currentVelocity();
        var shouldExpand;
        if (Math.abs(velocity) > VELOCITY_THRESHOLD) {
          shouldExpand = velocity > 0;
        } else {
          shouldExpand = dragY >= THRESHOLD;
        }
        setExpanded(shouldExpand);
        setTimeout(function(){ suppressClick = false; }, 90);
      }

      function bindPointer(el) {
        if (!el) return;
        el.addEventListener('pointerdown', function(e){
          if (e.pointerType === 'mouse' && e.button !== 0) return;
          onStart(e.clientX, e.clientY, e.pointerId);
          try { el.setPointerCapture(e.pointerId); } catch (_) {}
        }, { passive: true });
        el.addEventListener('pointermove', function(e){
          if (!dragging || (activePointerId !== null && e.pointerId !== activePointerId)) return;
          onMove(e.clientX, e.clientY);
        }, { passive: true });
        function end(e){
          if (activePointerId !== null && e.pointerId !== activePointerId) return;
          onEnd();
        }
        el.addEventListener('pointerup', end, { passive: true });
        el.addEventListener('pointercancel', end, { passive: true });
      }

      // سطح درگ = کل نوار (نه فقط دستگیرهٔ باریک)، تا سوایپ از هر نقطه‌ای روی
      // نوار پایین کار کنه. تپ ساده روی آیکن‌ها با آستانهٔ CLICK_SLOP و suppressClick
      // (پایین‌تر) از درگ تفکیک می‌شه، پس ناوبری آیکن‌ها دست‌نخورده می‌مونه.
      bindPointer(sheet);

      // Block accidental navigation while swiping
      sheet.addEventListener('click', function(e){
        if (suppressClick) {
          e.preventDefault();
          e.stopPropagation();
        }
      }, true);

      // Tap handle to toggle
      handle.addEventListener('click', function(e){
        if (suppressClick) return;
        e.preventDefault();
        e.stopPropagation();
        setExpanded(!expanded);
      });
      handle.addEventListener('keydown', function(e){
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          setExpanded(!expanded);
        }
      });

      // Collapse after choosing an extra item
      extra.addEventListener('click', function(e){
        if (e.target.closest('a.bn-item') && expanded) {
          setTimeout(function(){ setExpanded(false); }, 140);
        }
      });

      // Outside tap collapses
      document.addEventListener('pointerdown', function(e){
        if (!expanded || dragging) return;
        if (nav.contains(e.target)) return;
        setExpanded(false);
      }, { passive: true });

      window.addEventListener('resize', function(){
        if (isDesktop() && expanded) setExpanded(false);
      });
    })();

(function(){
      var nav = document.getElementById('mobile-bottom-nav');
      if (!nav) return;
      nav.addEventListener('click', function(e){
        var a = e.target && e.target.closest ? e.target.closest('a.bn-item') : null;
        if (!a || !a.href) return;
        // اگر drag مانع شده، خودمان برو
        if (e.defaultPrevented) {
          window.location.href = a.href;
        }
      }, true);
    })();
