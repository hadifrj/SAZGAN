/* این فایل بخشی از تفکیک base-ui.js (فاز ۲، بخش ۲) است — کد بدون تغییر منطق از static/js/base-ui.js منتقل شده. */

(function(){
  function loadBadge(){
    fetch('/api/cartable-badge').then(function(r){return r.json()}).then(function(d){
      if(!d || !d.count) return;
      document.querySelectorAll('a[href="/cartable"] .sidebar-link-text').forEach(function(el){
        el.textContent = 'کارتابل (' + d.count + ')';
      });
    }).catch(function(){});
  }
  if('requestIdleCallback' in window) requestIdleCallback(loadBadge, {timeout:2500});
  else setTimeout(loadBadge, 1200);
})();

(function(){
  function paintOne(link, n){
    var old = link.querySelector('.nav-badge, .ah-badge');
    if(old) old.remove();
    if(!n) return;
    var label = n > 99 ? '99+' : String(n);
    if(link.classList.contains('ah-icon-btn')){
      var b = document.createElement('span');
      b.className = 'ah-badge';
      b.textContent = label;
      link.appendChild(b);
      return;
    }
    var text = link.querySelector('.sidebar-link-text') || link.querySelector('span:last-child');
    var b2 = document.createElement('span');
    b2.className = 'nav-badge';
    b2.textContent = label;
    b2.style.cssText = 'margin-right:6px;background:#ef4444;color:#fff;border-radius:999px;font-size:10px;padding:1px 6px;font-weight:700;';
    if(text) text.appendChild(b2); else link.appendChild(b2);
  }
  function paint(n){
    document.querySelectorAll('a[href="/support/inbox"]').forEach(function(link){ paintOne(link, n); });
    window.dispatchEvent(new CustomEvent('sazgan:support-unread',{detail:{count:n}}));
  }
  function tick(){
    if (document.hidden) return;
    fetch('/api/support/unread-count',{cache:'no-store'}).then(function(r){return r.json()}).then(function(d){
      paint(d.count||0);
    }).catch(function(){});
  }
  tick();
  setInterval(tick, 12000);
  document.addEventListener('visibilitychange', function(){
    if (!document.hidden) tick();
  });
  window.SazganSupportUnread = {refresh: tick};
})();
