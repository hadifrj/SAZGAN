/*! Sazgan Jalali Datepicker — lightweight, no dependency */
(function (global) {
  'use strict';
  var MONTHS = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
  var WEEK = ['ش','ی','د','س','چ','پ','ج']; // Sat..Fri (هفته از شنبه)
  function holidayMap(){
    try { return (global.SAZGAN_HOLIDAYS && typeof global.SAZGAN_HOLIDAYS === 'object') ? global.SAZGAN_HOLIDAYS : {}; }
    catch(e){ return {}; }
  }
  function dateKey(y,m,d){
    function p2(n){ n=String(n); return n.length<2 ? ('0'+n) : n; }
    return y + '/' + p2(m) + '/' + p2(d);
  }

  var ICONS = {
    cal: '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    chevL: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>',
    chevR: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>'
  };

  function div(a,b){ return Math.floor(a/b); }
  function toJalaali(gy,gm,gd){
    var g_d_m=[0,31,59,90,120,151,181,212,243,273,304,334];
    var gy2=(gm>2)?(gy+1):gy;
    var days=355666+365*gy+div(gy2+3,4)-div(gy2+99,100)+div(gy2+399,400)+gd+g_d_m[gm-1];
    var jy= -1595+33*div(days,12053); days%=12053;
    jy+=4*div(days,1461); days%=1461;
    if(days>365){ jy+=div(days-1,365); days=(days-1)%365; }
    var jm; for(jm=1;jm<13&&days>=[0,31,62,93,124,155,186,216,246,276,306,336][jm];jm++);
    var jd=days-([0,31,62,93,124,155,186,216,246,276,306,336][jm-1]||0)+1;
    return {jy:jy,jm:jm,jd:jd};
  }
  function toGregorian(jy,jm,jd){
    var gy,gm,gd,days;
    jy+=1595; days=-355668+365*jy+div(jy,33)*8+div((jy%33)+3,4)+jd+((jm<7)?(jm-1)*31:((jm-7)*30+186));
    gy=400*div(days,146097); days%=146097;
    if(days>36524){ gy+=100*div(--days,36524); days%=36524; if(days>=365)days++; }
    gy+=4*div(days,1461); days%=1461;
    if(days>365){ gy+=div(days-1,365); days=(days-1)%365; }
    gd=days+1;
    var sal_a=[0,31,(gy%4===0&&gy%100!==0)||gy%400===0?29:28,31,30,31,30,31,31,30,31,30,31];
    for(gm=1;gm<13&&gd>sal_a[gm];gm++) gd-=sal_a[gm];
    return {gy:gy,gm:gm,gd:gd};
  }
  function jMonthLength(jy,jm){
    if(jm<=6) return 31;
    if(jm<=11) return 30;
    // Esfand: leap?
    var a=jy-979, b=div(a,33), c=a%33;
    return (c<0?((c+33)%33):c) < 0 ? 29 : (((c+1)%33)-1)%4===0?30:29;
  }
    /* کبیسه جلالی — الگوریتم کامل jalaali-js (با جدول breaks)
     isLeap وقتی leap===0؛ نمونه: 1391، 1395، 1399، 1403، 1408 */
  var JAL_BREAKS = [-61,9,38,199,426,686,756,818,1111,1181,1210,1635,2060,2097,2192,2262,2324,2394,2456,3178];
  function isLeapJalali(jy){
    var bl = JAL_BREAKS.length;
    var leapJ = -14;
    var jp = JAL_BREAKS[0];
    var jump = 0;
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
  function daysInMonth(jy,jm){
    if(jm>=1&&jm<=6) return 31;
    if(jm>=7&&jm<=11) return 30;
    return isLeapJalali(jy)?30:29;
  }
  function pad(n){ return (n<10?'0':'')+n; }
  function format(jy,jm,jd){ return jy+'/'+pad(jm)+'/'+pad(jd); }
  function toEnDigits(s){
    return String(s||'').replace(/[۰-۹]/g,function(d){return String(d.charCodeAt(0)-1728);})
      .replace(/[٠-٩]/g,function(d){return String(d.charCodeAt(0)-1632);});
  }
  function parse(str){
    if(!str) return null;
    var m=toEnDigits(str).trim().match(/^(\d{3,4})[\/\-](\d{1,2})[\/\-](\d{1,2})$/);
    if(!m) return null;
    var jy=+m[1], jm=+m[2], jd=+m[3];
    if(jm<1||jm>12) return null;
    if(jd<1||jd>daysInMonth(jy,jm)) return null;
    return {jy:jy,jm:jm,jd:jd};
  }
  function todayJ(){
    var d=new Date();
    return toJalaali(d.getFullYear(), d.getMonth()+1, d.getDate());
  }

  var openPicker=null;

  function buildPicker(input){
    var wrap=document.createElement('div');
    wrap.className='sg-jdp';
    wrap.dir='rtl';
    var state = parse(input.value) || todayJ();
    if(state.jm<1||state.jm>12) state=todayJ();

    function render(){
      var y=state.jy, m=state.jm;
      var dim=daysInMonth(y,m);
      // weekday of 1st: convert to gregorian then getDay (0=Sun)
      var g=toGregorian(y,m,1);
      var wd=new Date(g.gy,g.gm-1,g.gd).getDay(); // 0 Sun
      // Jalali week starts Saturday: map Sun=1 ... Fri=6, Sat=0
      var start=(wd+1)%7; // Sat=0

      var html='<div class="sg-jdp-head">'+
        '<button type="button" class="sg-jdp-nav" data-nav="-1" aria-label="ماه قبل">'+ICONS.chevL+'</button>'+
        '<div class="sg-jdp-title">'+MONTHS[m-1]+' '+y+'</div>'+
        '<button type="button" class="sg-jdp-nav" data-nav="1" aria-label="ماه بعد">'+ICONS.chevR+'</button>'+
        '</div>';
      html+='<div class="sg-jdp-week">';
      for(var i=0;i<7;i++) html+='<span'+(i===6?' class="is-friday-head"':'')+'>'+WEEK[i]+'</span>';
      html+='</div><div class="sg-jdp-grid">';
      for(var e=0;e<start;e++) html+='<span class="sg-jdp-empty"></span>';
      var t=todayJ();
      var hol=holidayMap(); // object ref از window — سبک
      for(var d=1;d<=dim;d++){
        var cls='sg-jdp-day';
        // weekday in grid: 0=شنبه ... 6=جمعه
        var jwd=(start + d - 1) % 7;
        if(jwd===6) cls+=' is-friday';
        var key=dateKey(y,m,d);
        var htitle=hol[key]||'';
        if(htitle) cls+=' is-holiday';
        if(t.jy===y&&t.jm===m&&t.jd===d) cls+=' is-today';
        var cur=parse(input.value);
        if(cur&&cur.jy===y&&cur.jm===m&&cur.jd===d) cls+=' is-selected';
        html+='<button type="button" class="'+cls+'" data-day="'+d+'"'+(htitle?(' title="'+String(htitle).replace(/"/g,'&quot;')+'"'):'')+'>'+d+'</button>';
      }
      html+='</div>';
      html+='<div class="sg-jdp-foot"><button type="button" class="sg-jdp-today">امروز</button>'+
        '<button type="button" class="sg-jdp-clear">پاک کردن</button></div>';
      wrap.innerHTML=html;

      wrap.querySelector('[data-nav="-1"]').onclick=function(ev){
        ev.preventDefault(); ev.stopPropagation();
        state.jm--; if(state.jm<1){state.jm=12;state.jy--;} render();
      };
      wrap.querySelector('[data-nav="1"]').onclick=function(ev){
        ev.preventDefault(); ev.stopPropagation();
        state.jm++; if(state.jm>12){state.jm=1;state.jy++;} render();
      };
      wrap.querySelectorAll('.sg-jdp-day').forEach(function(btn){
        btn.onclick=function(ev){
          ev.preventDefault(); ev.stopPropagation();
          var day=+btn.getAttribute('data-day');
          input.value=format(state.jy,state.jm,day);
          input.dispatchEvent(new Event('change',{bubbles:true}));
          input.dispatchEvent(new Event('input',{bubbles:true}));
          // sync linked year/month/day selects if present
          syncSelects(input, state.jy, state.jm, day);
          close();
        };
      });
      wrap.querySelector('.sg-jdp-today').onclick=function(ev){
        ev.preventDefault(); ev.stopPropagation();
        var tj=todayJ();
        input.value=format(tj.jy,tj.jm,tj.jd);
        input.dispatchEvent(new Event('change',{bubbles:true}));
        syncSelects(input, tj.jy, tj.jm, tj.jd);
        close();
      };
      wrap.querySelector('.sg-jdp-clear').onclick=function(ev){
        ev.preventDefault(); ev.stopPropagation();
        input.value='';
        input.dispatchEvent(new Event('change',{bubbles:true}));
        close();
      };
    }

    function place(){
      var r=input.getBoundingClientRect();
      wrap.style.position='fixed';
      wrap.style.zIndex='99999';
      var top=r.bottom+6;
      var left=Math.min(r.left, window.innerWidth-300);
      if(top+320>window.innerHeight) top=Math.max(8, r.top-320);
      wrap.style.top=top+'px';
      wrap.style.left=Math.max(8,left)+'px';
    }
    function close(){
      if(wrap.parentNode) wrap.parentNode.removeChild(wrap);
      if(openPicker===wrap) openPicker=null;
      document.removeEventListener('click', onDoc, true);
    }
    function onDoc(e){
      if(!wrap.contains(e.target) && e.target!==input && !input.contains(e.target))
        close();
    }
    render();
    place();
    document.body.appendChild(wrap);
    openPicker=wrap;
    setTimeout(function(){ document.addEventListener('click', onDoc, true); },0);
    return {close:close, wrap:wrap};
  }

  function syncSelects(input, y, m, d){
    var root=input.closest('.jalali-date-wrap')||input.closest('.form-grid')||input.closest('form')||document;
    var ys=root.querySelector('select[name*="year"],select[name$="_y"],select.jalali-year');
    var ms=root.querySelector('select[name*="month"],select[name$="_m"],select.jalali-month');
    var ds=root.querySelector('select[name*="day"],select[name$="_d"],select.jalali-day');
    // also sibling jalali-row
    var row=input.closest('.field-full,.form-section-date')||input.parentElement;
    if(row){
      var selects=row.querySelectorAll('.jalali-row select');
      if(selects.length>=3){ ys=selects[0]; ms=selects[1]; ds=selects[2]; }
    }
    if(ys){ ys.value=String(y); ys.dispatchEvent(new Event('change',{bubbles:true})); }
    if(ms){ ms.value=String(m); ms.dispatchEvent(new Event('change',{bubbles:true})); }
    if(ds){ ds.value=String(d); ds.dispatchEvent(new Event('change',{bubbles:true})); }
  }

  function enhanceInput(input){
    if(!input || input.dataset.jdp==='1') return;
    input.dataset.jdp='1';
    input.setAttribute('autocomplete','off');
    if(!input.placeholder) input.setAttribute('placeholder', '۱۴۰۵/۰۱/۱۵');
    input.classList.add('sg-jdp-input');
    input.addEventListener('focus', function(){
      if(openPicker) try{ openPicker.remove(); }catch(e){}
      buildPicker(input);
    });
    input.addEventListener('click', function(){
      if(openPicker) return;
      buildPicker(input);
    });
  }

  function enhanceJalaliRow(row){
    if(row.dataset.jdp==='1') return;
    row.dataset.jdp='1';
    var btn=document.createElement('button');
    btn.type='button';
    btn.className='sg-jdp-trigger';
    btn.title='انتخاب از تقویم';
    btn.innerHTML=ICONS.cal;
    btn.classList.add('sg-jdp-trigger-svg');
    row.appendChild(btn);
    // hidden proxy input for picker value
    var proxy=document.createElement('input');
    proxy.type='text';
    proxy.className='sg-jdp-proxy';
    proxy.style.position='absolute';
    proxy.style.opacity='0';
    proxy.style.width='1px';
    proxy.style.height='1px';
    row.style.position='relative';
    row.appendChild(proxy);

    function readFromSelects(){
      var sels=row.querySelectorAll('select');
      if(sels.length<3) return null;
      var y=+sels[0].value, m=+sels[1].value, d=+sels[2].value;
      if(!y||!m||!d) return null;
      return {jy:y,jm:m,jd:d};
    }
    btn.addEventListener('click', function(e){
      e.preventDefault(); e.stopPropagation();
      var cur=readFromSelects()||todayJ();
      proxy.value=format(cur.jy,cur.jm,cur.jd);
      // monkey: on change of proxy update selects
      var once=function(){
        var p=parse(proxy.value);
        if(p){
          var sels=row.querySelectorAll('select');
          if(sels[0]) sels[0].value=String(p.jy);
          if(sels[1]) sels[1].value=String(p.jm);
          if(sels[2]) sels[2].value=String(p.jd);
          sels.forEach(function(s){ s.dispatchEvent(new Event('change',{bubbles:true})); });
        }
        proxy.removeEventListener('change', once);
      };
      proxy.addEventListener('change', once);
      if(openPicker) try{ openPicker.remove(); }catch(ex){}
      buildPicker(proxy);
    });
  }

  function scan(root){
    root=root||document;
    if(!root.querySelectorAll) return;
    root.querySelectorAll('input.jalali-date, input[data-jalali], input.sg-jalali').forEach(enhanceInput);
    // فقط فیلدهایی که نام/شناسهٔ تاریخ دارند — نه همهٔ inputهای متنی
    root.querySelectorAll('input[type="text"][name*="date"], input[type="text"][id*="date"], input[type="text"][name*="تاریخ"]').forEach(function(inp){
      var n=(inp.name||'')+(inp.id||'');
      if(/time|ساعت|datetime/i.test(n)) return;
      enhanceInput(inp);
    });
    root.querySelectorAll('.jalali-row').forEach(enhanceJalaliRow);
  }

  function injectCss(){
    var s=document.getElementById('sg-jdp-css');
    if(!s){ s=document.createElement('style'); s.id='sg-jdp-css'; document.head.appendChild(s); }
    s.textContent=
      '.sg-jdp{width:280px;background:#fff;border:1px solid #e2e8f0;border-radius:14px;'+
      'box-shadow:0 16px 40px rgba(15,23,42,.18);padding:12px;font-family:Tahoma,Vazirmatn,sans-serif;color:#0f172a}'+
      '.sg-jdp-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}'+
      '.sg-jdp-title{font-weight:700;font-size:14px}'+
      '.sg-jdp-nav{border:1px solid #e2e8f0;background:#f8fafc;width:32px;height:32px;border-radius:8px;cursor:pointer;font-size:16px}'+
      '.sg-jdp-nav:hover{background:#E2231A;color:#fff;border-color:#E2231A}'+
      '.sg-jdp-week{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center;font-size:11px;color:#94a3b8;font-weight:700;margin-bottom:4px}'+
      '.sg-jdp-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}'+
      '.sg-jdp-day{border:0;background:transparent;height:34px;border-radius:8px;cursor:pointer;font-size:13px;font-family:inherit;color:#0f172a}'+
      '.sg-jdp-day:hover{background:#fee2e2;color:#E2231A}'+
      '.sg-jdp-day.is-today{box-shadow:inset 0 0 0 1px #E2231A;font-weight:700}'+
      '.sg-jdp-day.is-selected{background:#E2231A;color:#fff !important;font-weight:700}'+
      '.sg-jdp-week span.is-friday-head{color:#dc2626 !important;font-weight:800}'+
      '.sg-jdp-day.is-friday{color:#dc2626 !important;font-weight:700}'+
      '.sg-jdp-day.is-holiday{color:#dc2626 !important;font-weight:700;background:rgba(220,38,38,.08)}'+
      '.sg-jdp-day.is-friday.is-selected,.sg-jdp-day.is-holiday.is-selected{background:#dc2626 !important;color:#fff !important}'+
      '[data-theme="dark"] .sg-jdp{background:#1a2436;border-color:#2b3a52;color:#e5e9f0;box-shadow:0 12px 40px rgba(0,0,0,.45)}'+
      '[data-theme="dark"] .sg-jdp-day{color:#e5e9f0}'+
      '[data-theme="dark"] .sg-jdp-day.is-friday,[data-theme="dark"] .sg-jdp-week span.is-friday-head{color:#f87171 !important}'+
      '.sg-jdp-empty{height:34px}'+
      '.sg-jdp-foot{display:flex;gap:8px;margin-top:10px;justify-content:center}'+
      '.sg-jdp-today,.sg-jdp-clear{border:1px solid #e2e8f0;background:#fff;border-radius:8px;padding:6px 12px;cursor:pointer;font-family:inherit;font-size:12px;font-weight:600}'+
      '.sg-jdp-today{background:#E2231A;color:#fff;border-color:#E2231A}'+
      '.sg-jdp-clear:hover{background:#f1f5f9}'+
      '.sg-jdp-input{background:#fff !important}'+
      '.sg-jdp-trigger{border:1px solid #cbd5e1;background:#fff;border-radius:8px;width:36px;height:34px;cursor:pointer;flex-shrink:0;margin-right:4px;display:inline-flex;align-items:center;justify-content:center;color:#64748b;padding:0}'+
      '.sg-jdp-trigger svg{display:block;width:18px;height:18px}'+
      '.sg-jdp-nav{display:inline-flex;align-items:center;justify-content:center}'+
      '.sg-jdp-nav svg{display:block}'+
      '.sg-jdp-trigger:hover{border-color:#E2231A;background:#fff5f5}'+
      '.jalali-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap}';
  }

  function init(){
    injectCss();
    scan(document);
    // observe dynamic forms / modals
    try{
      var scanTimer=null;
      var pending=[];
      function flushScan(){
        scanTimer=null;
        var nodes=pending; pending=[];
        nodes.forEach(function(n){ if(n && n.nodeType===1) scan(n); });
      }
      var mo=new MutationObserver(function(muts){
        for(var i=0;i<muts.length;i++){
          var m=muts[i];
          if(!m.addedNodes) continue;
          for(var j=0;j<m.addedNodes.length;j++){
            var n=m.addedNodes[j];
            if(n.nodeType===1) pending.push(n);
          }
        }
        if(pending.length && !scanTimer){
          scanTimer=setTimeout(flushScan, 80);
        }
      });
      mo.observe(document.body,{childList:true,subtree:true});
    }catch(e){}
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  global.SazganJalali={
    scan:scan, format:format, parse:parse, today:todayJ,
    daysInMonth:daysInMonth, isLeap:isLeapJalali,
    isValid:function(str){
      var p=parse(str); if(!p) return false;
      if(p.jm<1||p.jm>12) return false;
      return p.jd>=1 && p.jd<=daysInMonth(p.jy,p.jm);
    }
  };
})(window);
