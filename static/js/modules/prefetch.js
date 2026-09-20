/* این فایل بخشی از تفکیک base-ui.js (فاز ۲، بخش ۲) است — کد بدون تغییر منطق از static/js/base-ui.js منتقل شده. */

(function(){
  function loadSS(){
    var s=document.createElement('script');
    s.src='/static/js/searchable-select.js?v=' + (document.body.getAttribute('data-app-version')||'1');
    s.defer=true;
    document.body.appendChild(s);
  }
  function loadCP(){
    var s=document.createElement('script');
    s.src='/static/js/customer-picker.js?v=' + (document.body.getAttribute('data-app-version')||'1');
    s.defer=true;
    document.body.appendChild(s);
  }
  function loadFP(){
    var s=document.createElement('script');
    s.src='/static/js/file-picker.js?v=' + (document.body.getAttribute('data-app-version')||'1');
    s.defer=true;
    document.body.appendChild(s);
  }
  if('requestIdleCallback' in window) {
    requestIdleCallback(loadSS,{timeout:2000});
    requestIdleCallback(loadCP,{timeout:1500});
    requestIdleCallback(loadFP,{timeout:1500});
  } else {
    setTimeout(loadSS, 400);
    setTimeout(loadCP, 200);
    setTimeout(loadFP, 250);
  }
})();

  (function(){
    var seen = {};
    function warm(href){
      if(!href || href.charAt(0)!=='/' || href.indexOf('#')===0) return;
      if(seen[href]) return;
      seen[href]=1;
      try{
        var l=document.createElement('link');
        l.rel='prefetch';
        l.href=href;
        l.as='document';
        document.head.appendChild(l);
      }catch(e){}
    }
    document.addEventListener('mouseover', function(e){
      var a = e.target && e.target.closest ? e.target.closest('a.sidebar-link, a.sidebar-sublink, a.settings-tab, a.ca-tab, a.ui-tab') : null;
      if(a && a.href) warm(a.getAttribute('href')||a.pathname);
    }, {passive:true, capture:true});
    document.addEventListener('touchstart', function(e){
      var a = e.target && e.target.closest ? e.target.closest('a.sidebar-link, a.sidebar-sublink, a.settings-tab, a.ca-tab, a.ui-tab') : null;
      if(a && a.href) warm(a.getAttribute('href')||a.pathname);
    }, {passive:true, capture:true});
  })();
