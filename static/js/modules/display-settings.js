/* این فایل بخشی از تفکیک base-ui.js (فاز ۲، بخش ۲) است — کد بدون تغییر منطق از static/js/base-ui.js منتقل شده. */

        function applyThemeUI() {
            var theme = document.documentElement.getAttribute('data-theme') || 'light';
            var icons = { light: '<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>', dark: '<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="4.5"/><line x1="12" y1="19.5" x2="12" y2="22"/><line x1="2" y1="12" x2="4.5" y2="12"/><line x1="19.5" y1="12" x2="22" y2="12"/><line x1="4.9" y1="4.9" x2="6.6" y2="6.6"/><line x1="17.4" y1="17.4" x2="19.1" y2="19.1"/><line x1="4.9" y1="19.1" x2="6.6" y2="17.4"/><line x1="17.4" y1="6.6" x2="19.1" y2="4.9"/></svg>' };
            var labels = { light: 'حالت شب', dark: 'حالت روز' };
            var ic = document.getElementById('theme-toggle-icon');
            var lb = document.getElementById('theme-toggle-label');
            if (ic) ic.innerHTML = icons[theme] || '<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>';
            if (lb) lb.textContent = labels[theme] || 'حالت تاریک';
        }
        function toggleTheme() {
            var order = ['light', 'dark'];
            var current = document.documentElement.getAttribute('data-theme') || 'light';
            if (order.indexOf(current) < 0) current = 'light';
            var next = order[(order.indexOf(current) + 1) % order.length];
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('sazgan-theme', next);
            try {
              var cfg = (window.SazganDisplay && window.SazganDisplay.load) ? window.SazganDisplay.load() : {};
              cfg.theme = next;
              if (window.SazganDisplay) window.SazganDisplay.apply(cfg);
            } catch (e) {}
            applyThemeUI();
        }
        applyThemeUI();

(function(){
  try {
    fetch('/static/design-tokens.json',{cache:'force-cache'}).then(function(r){return r.ok?r.json():null;}).then(function(t){
      if(!t||!t.colors) return;
      var c=t.colors, root=document.documentElement;
      root.style.setProperty('--ds-bg',c.bg); root.style.setProperty('--ds-card',c.card); root.style.setProperty('--ds-text',c.text);
      root.style.setProperty('--ds-muted',c.muted); root.style.setProperty('--ds-border',c.border); root.style.setProperty('--ds-accent',c.accent);
      root.style.setProperty('--ds-sidebar',c.sidebar); root.style.setProperty('--ds-sidebar-active',c.sidebarActive);
    }).catch(function(){});
  } catch(e){}
})();
