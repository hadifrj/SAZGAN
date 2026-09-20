/* این فایل بخشی از تفکیک base-ui.js (فاز ۲، بخش ۲) است — کد بدون تغییر منطق از static/js/base-ui.js منتقل شده. */

        function openModal(id) {
            var el = document.getElementById(id);
            if (el) el.classList.add('open');
            document.body.style.overflow = 'hidden';
        }
        function closeModal(id) {
            var el = document.getElementById(id);
            if (el) el.classList.remove('open');
            document.body.style.overflow = '';
        }

function openQuickNew(url, title) {
            var modal = document.getElementById('quick-new-modal');
            var frame = document.getElementById('quick-new-frame');
            var t = document.getElementById('quick-new-title');
            var loading = document.getElementById('quick-new-loading');
            var full = document.getElementById('quick-new-full');
            if (t) t.textContent = title || 'ثبت درخواست جدید';
            if (full) full.href = url;
            if (loading) loading.classList.remove('hidden');
            if (frame) {
                var sep = url.indexOf('?') >= 0 ? '&' : '?';
                var src = url + sep + 'embed=1&_=' + Date.now();
                frame.onload = function() {
                    if (loading) loading.classList.add('hidden');
                };
                // اگر onload گیر کرد، بعد از ۳ ثانیه لودینگ را بردار
                setTimeout(function() {
                    if (loading) loading.classList.add('hidden');
                }, 3000);
                frame.src = src;
            }
            if (modal) modal.classList.add('open');
            document.body.style.overflow = 'hidden';
        }
        function closeQuickNew() {
            var modal = document.getElementById('quick-new-modal');
            var frame = document.getElementById('quick-new-frame');
            var loading = document.getElementById('quick-new-loading');
            if (modal) modal.classList.remove('open');
            if (frame) { frame.onload = null; frame.src = 'about:blank'; }
            if (loading) loading.classList.add('hidden');
            document.body.style.overflow = '';
        }
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeQuickNew();
        });

(function(){
  function closeAll(except){
    document.querySelectorAll('.sg-help-tip.open').forEach(function(el){
      if(el!==except) el.classList.remove('open');
    });
  }
  document.addEventListener('click', function(e){
    var btn = e.target.closest('.sg-help-btn');
    if(btn){
      e.preventDefault();
      e.stopPropagation();
      var tip = btn.closest('.sg-help-tip');
      var open = tip.classList.contains('open');
      closeAll();
      if(!open) tip.classList.add('open');
      return;
    }
    if(!e.target.closest('.sg-help-tip')) closeAll();
  });
  document.addEventListener('keydown', function(e){
    if(e.key==='Escape') closeAll();
  });
})();

(function(){
  var modal=document.getElementById('sg-form-modal'), frame=document.getElementById('sg-form-modal-frame');
  if(!modal||!frame)return;
  var title=document.getElementById('sg-form-modal-title'), close=modal.querySelector('.sg-form-modal-close');
  var formPaths=[
    '/customer-affairs/new-request',
    '/customer-affairs/new-request/quick',
    '/service/internal-repair/new','/service/external-repair/new',
    '/service/installation/request-new','/service/installation/register-new',
    '/service/inspection/request-new','/service/inspection/report-new',
    '/service/demo/new',
    '/settings/customers/edit/','/settings/representatives/edit/',
    '/settings/users/edit/','/settings/warranty/edit/','/settings/warranty/activate/',
    '/service/internal-repair/view/','/service/external-repair/view/',
    '/service/pending-request/','/service/cartable-preview/','/service/inspection/view/',
    '/service/installation/request-view/'
  ];
  function isFormPath(path){
    path=(path||'').split('?')[0].split('#')[0];
    return formPaths.some(function(p){return p[p.length-1]==='/' ? path.indexOf(p)===0 : path===p;});
  }
  function closeModal(){
    modal.classList.remove('open'); modal.setAttribute('aria-hidden','true'); document.body.classList.remove('sg-modal-open');
    frame.src='about:blank';
  }
  var prefetched={};
  function normalizedModalUrl(url){
    var u=new URL(url,window.location.origin);
    u.searchParams.set('embed','1'); u.searchParams.set('_modal','1');
    return u.toString();
  }
  function prefetchModal(url){
    try{
      var key=normalizedModalUrl(url);
      if(prefetched[key]) return;
      prefetched[key]=true;
      if(window.fetch) fetch(key,{credentials:'same-origin',cache:'force-cache',headers:{'X-Sazgan-Prefetch':'1'}}).catch(function(){});
    }catch(e){}
  }
  function setModalLoading(on){
    modal.classList.toggle('is-loading',!!on);
    frame.setAttribute('aria-busy', on ? 'true' : 'false');
  }
  function openModal(url, label){
    modal.classList.add('open'); modal.setAttribute('aria-hidden','false'); document.body.classList.add('sg-modal-open');
    title.textContent=label||'فرم';
    var u=normalizedModalUrl(url);
    setModalLoading(true);
    frame.src=u;
  }
  close.addEventListener('click',closeModal);
  modal.addEventListener('click',function(e){if(e.target===modal)closeModal();});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&modal.classList.contains('open'))closeModal();});
  document.addEventListener('pointerover',function(e){
    var a=e.target&&e.target.closest?e.target.closest('a[href]'):null;
    if(!a || a.target==='_blank') return;
    try{
      var u=new URL(a.href,location.href);
      if(u.origin===location.origin && isFormPath(u.pathname)) prefetchModal(u.toString());
    }catch(_){}
  },{passive:true});
  document.addEventListener('focusin',function(e){
    var a=e.target&&e.target.closest?e.target.closest('a[href]'):null;
    if(!a) return;
    try{
      var u=new URL(a.href,location.href);
      if(u.origin===location.origin && isFormPath(u.pathname)) prefetchModal(u.toString());
    }catch(_){}
  });
  document.addEventListener('click',function(e){
    var a=e.target&&e.target.closest?e.target.closest('a[href]'):null;
    if(!a||a.target==='_blank'||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;
    var u;
    try{u=new URL(a.href,location.href);}catch(_){return;}
    if(u.origin!==location.origin||!isFormPath(u.pathname))return;
    e.preventDefault(); e.stopPropagation();
    openModal(u.toString(),a.getAttribute('title')||a.textContent.trim()||'فرم');
  },true);
  frame.addEventListener('load',function(){
    setModalLoading(false);
    if(!modal.classList.contains('open'))return;
    try{
      var doc=frame.contentDocument, path=frame.contentWindow.location.pathname;
      // فرم‌های موفق معمولاً پس از POST به فهرست برمی‌گردند؛ خطای اعتبارسنجی همان URL فرم را نگه می‌دارد.
      if(!isFormPath(path) && path!=='/login'){
        closeModal();
        if(window.location.reload) window.location.reload();
        return;
      }
      // لینک «بازگشت» داخل فرم، مودال را نبندد و به صفحه قبلی اصلی برگردد.
      doc.addEventListener('click',function(ev){
        var a=ev.target&&ev.target.closest?ev.target.closest('a[href]'):null;
        if(!a)return;
        var u; try{u=new URL(a.href,location.href);}catch(_){return;}
        if(u.origin===location.origin && !isFormPath(u.pathname)){
          ev.preventDefault(); closeModal(); window.location.href=u.toString();
        }
      },true);
    }catch(_){}
  });
  window.sgOpenFormModal=openModal;
  window.sgCloseFormModal=closeModal;
})();
