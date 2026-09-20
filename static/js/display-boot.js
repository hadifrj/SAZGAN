(function(){
  var KEY='sazgan-display';
  var FONTS={
    vazirmatn:"'Vazirmatn', Tahoma, system-ui, sans-serif",
    iransans:"'IRANSans', Tahoma, sans-serif",
    iransansx:"'IRANSansX', 'IRANSans', Tahoma, sans-serif",
    iranyekan:"'IRANYekan', 'IranYekan', Tahoma, sans-serif",
    bnazanin:"'B Nazanin', 'BNazanin', Nazanin, Tahoma, serif",
    yekanbakh:"'Yekan Bakh', 'YekanBakh', Tahoma, sans-serif",
    tahoma:"Tahoma, 'Segoe UI', sans-serif",
    system:"system-ui, -apple-system, 'Segoe UI', Tahoma, sans-serif",
    iran:"'IRANSans', Tahoma, sans-serif"
  };
  var SIZES={sm:'13px',md:'14.5px',lg:'16.5px',xl:'18px'};
  var RADII={soft:{r:'12px',rs:'8px'},round:{r:'16px',rs:'12px'},sharp:{r:'6px',rs:'4px'}};
  /* نام‌های قدیمی → hex (مهاجرت) */
  var ACCENT_LEGACY={
    blue:'#2563eb',indigo:'#4f46e5',teal:'#0d9488',green:'#16a34a',
    orange:'#ea580c',rose:'#C00000',gold:'#D4A017',slate:'#475569'
  };
  var BG_LEGACY={
    softgray:'#f1f5f9',coolblue:'#e8f1fb',sky:'#dff3fb',ice:'#eef7ff',
    mint:'#e8f6f1',sage:'#eef5e9',teal:'#e6f7f5',lavender:'#f0eefc',
    lilac:'#f5eef8',warm:'#faf3eb',sand:'#f7f1e6',peach:'#fff0e8',
    blush:'#fceef2',rose:'#fde8ec',slate:'#e2e8f0',graphite:'#e8eaed',
    paper:'#f7f5f0',ocean:'#e4eef6',brandwarm:'#FDF6F5',brandsoft:'#FFF8F7'
  };

  function isHex(v){ return typeof v==='string' && /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(v.trim()); }
  function normHex(v){
    v=(v||'').trim();
    if(!isHex(v)) return null;
    if(v.length===4) v='#'+v[1]+v[1]+v[2]+v[2]+v[3]+v[3];
    return v.toLowerCase();
  }
  function hexToRgb(hex){
    hex=normHex(hex)||'#2563eb';
    return {
      r:parseInt(hex.slice(1,3),16),
      g:parseInt(hex.slice(3,5),16),
      b:parseInt(hex.slice(5,7),16)
    };
  }
  function isLightHex(hex){
    hex=(hex||'').replace('#','');
    if(hex.length===3) hex=hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
    if(hex.length!==6) return false;
    var r=parseInt(hex.slice(0,2),16), g=parseInt(hex.slice(2,4),16), b=parseInt(hex.slice(4,6),16);
    // relative luminance
    var L=(0.299*r+0.587*g+0.114*b)/255;
    return L>0.62;
  }
  function darken(hex, factor){
    var c=hexToRgb(hex);
    var f=Math.max(0, Math.min(1, factor));
    function ch(n){ return ('0'+Math.round(n*(1-f)).toString(16)).slice(-2); }
    return '#'+ch(c.r)+ch(c.g)+ch(c.b);
  }
  function softRgba(hex, a){
    var c=hexToRgb(hex);
    return 'rgba('+c.r+','+c.g+','+c.b+','+(a==null?0.14:a)+')';
  }
  function resolveAccent(v){
    if(isHex(v)) return normHex(v);
    if(ACCENT_LEGACY[v]) return ACCENT_LEGACY[v];
    return '#2563eb';
  }
  function resolveBg(v){
    if(isHex(v)) return normHex(v);
    if(BG_LEGACY[v]) return BG_LEGACY[v];
    return '#e8f1fb';
  }
  function normalizeTheme(t){
    if(t==='dark') return 'dark';
    if(t==='system') return 'system';
    return 'light'; /* sazgan و سایر → روشن */
  }
  function systemPrefersDark(){
    try{ return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches; }
    catch(e){ return false; }
  }
  function resolveEffectiveTheme(storedTheme){
    return storedTheme==='system' ? (systemPrefersDark()?'dark':'light') : (storedTheme||'light');
  }

  var UI_THEMES={
    light_modern_indigo:{label:'Light Modern Indigo',theme:'light',accent:'#4f46e5',bg:'#f8fafc',sidebar:'#ffffff',cardTheme:'default',colorThemeId:'light-modern-indigo'},
    dark_modern_indigo:{label:'Dark Modern Indigo',theme:'dark',accent:'#6366f1',bg:'#0f172a',sidebar:'#111827',cardTheme:'default',colorThemeId:'dark-modern-indigo'},
    minimal_premium:{label:'Minimal Premium',theme:'light',accent:'#111827',bg:'#f8fafc',sidebar:'#ffffff',cardTheme:'mono',colorThemeId:'minimal-premium'}
  };
  function normalizeUiTheme(v){ return UI_THEMES[v]?v:'minimal_premium'; }
  function applyUiThemePreset(d){
    d.uiTheme=normalizeUiTheme(d.uiTheme);
    var p=UI_THEMES[d.uiTheme];
    d.theme=p.theme; d.accent=p.accent; d.bg=p.bg; d.sidebar=p.sidebar; d.cardTheme=p.cardTheme; d.colorThemeId=p.colorThemeId;
    return d;
  }

  function load(){
    try{
      var d=JSON.parse(localStorage.getItem(KEY)||'{}')||{};
      if(!d.theme) d.theme=localStorage.getItem('sazgan-theme')||'light';
      d.theme=normalizeTheme(d.theme);
      if(!d.font) d.font='vazirmatn';
      if(!d.accent) d.accent='#374151';
      else d.accent=resolveAccent(d.accent);
      if(!d.size) d.size='md';
      if(!d.density) d.density='comfortable';
      if(!d.radius) d.radius='soft';
      if(!d.uiTheme){
        // migrate old installations: monochrome -> Minimal Premium, others -> modern light
        d.uiTheme='minimal_premium';
      }
      d.uiTheme=normalizeUiTheme(d.uiTheme);
      applyUiThemePreset(d);
      if(['default','module','mono'].indexOf(d.cardTheme)<0) d.cardTheme='default';
      if(!d.printFont) d.printFont=d.font||'vazirmatn';
      if(!d.printSize) d.printSize='12pt';
      if(!d.bg) d.bg='#f8fafc';
      else d.bg=resolveBg(d.bg);
      if(!d.sidebar) d.sidebar='#ffffff';
      else d.sidebar=resolveAccent(d.sidebar);
      d.reduceMotion=!!d.reduceMotion;
      d.increaseContrast=!!d.increaseContrast;
      d.amoled=!!d.amoled;
      /* مهاجرت تم: نسخه‌های قدیمی ممکن است Ocean/blue را در localStorage نگه داشته باشند.
         نسخه جدید پیش‌فرض Neutral White است؛ Dark Mode همچنان از theme='dark' استفاده می‌کند. */
      (function(){
        var blue = {
          '#0284c7':1,'#0c4a6e':1,'#075985':1,'#0369a1':1,'#2563eb':1,
          '#1d4ed8':1,'#3b82f6':1,'#60a5fa':1,'#0ea5e9':1,'#1976d2':1,
          '#2196f3':1,'#1565c0':1
        };
        var ac=(d.accent||'').toLowerCase();
        var sb=(d.sidebar||'').toLowerCase();
        var tid=(d.colorThemeId||'').toLowerCase();
        if(blue[ac] || blue[sb] || tid==='ocean' || tid==='classic-blue'){
          d.accent='#374151';
          d.sidebar='#ffffff';
          d.bg='#f8fafc';
          d.colorThemeId='neutral';
          try{ localStorage.setItem('sazganDisplayConfig', JSON.stringify(d)); }catch(e){}
        }
      })();
      return d;
    }catch(e){
      return {uiTheme:'minimal_premium',theme:'light',font:'vazirmatn',accent:'#111827',size:'md',density:'comfortable',radius:'soft',cardTheme:'mono',bg:'#f8fafc',sidebar:'#ffffff',colorThemeId:'minimal-premium'};
    }
  }
  function ensureStyleEl(){
    var el=document.getElementById('sazgan-display-overrides');
    if(!el){
      el=document.createElement('style');
      el.id='sazgan-display-overrides';
      (document.head||document.documentElement).appendChild(el);
    }
    return el;
  }
  function apply(cfg){
    cfg=cfg||load();
    cfg.uiTheme=normalizeUiTheme(cfg.uiTheme);
    applyUiThemePreset(cfg);
    cfg.theme=normalizeTheme(cfg.theme);
    cfg.accent=resolveAccent(cfg.accent);
    cfg.bg=resolveBg(cfg.bg);
    cfg.sidebar=resolveAccent(cfg.sidebar||'#0c4a6e');
    if(['default','module','mono'].indexOf(cfg.cardTheme)<0) cfg.cardTheme='mono';
    try{ localStorage.setItem(KEY, JSON.stringify(cfg)); }catch(e){}
    var storedTheme=cfg.theme||'light';
    var theme=resolveEffectiveTheme(storedTheme);
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-theme-pref', storedTheme);
    document.documentElement.setAttribute('data-ui-theme', cfg.uiTheme);
    try{ localStorage.setItem('sazgan-theme', theme); }catch(e){}

    var accentHex=cfg.accent;
    var ac={
      accent: accentHex,
      hover: darken(accentHex, 0.18),
      soft: softRgba(accentHex, 0.14)
    };
    var font=FONTS[cfg.font]||FONTS.vazirmatn;
    var size=SIZES[cfg.size]||SIZES.md;
    var printFont=FONTS[cfg.printFont]||font;
    var printSize=cfg.printSize||'12pt';
    var rad=RADII[cfg.radius]||RADII.soft;
    document.documentElement.setAttribute('data-density', cfg.density||'comfortable');
    document.documentElement.setAttribute('data-font', cfg.font||'vazirmatn');
    document.documentElement.setAttribute('data-card-theme', cfg.cardTheme);

    var pageBg, cardBg, textCol, mutedCol, borderCol, inputBg, inputText, topbarBg;
    if(theme==='dark'){
      if(cfg.amoled){
        pageBg='#000000'; cardBg='#0a0a0a'; textCol='#f1f5f9'; mutedCol='#a1a1aa';
        borderCol='#232323'; inputBg='#050505'; inputText='#f1f5f9'; topbarBg='#000000';
      } else {
        pageBg='#0f172a'; cardBg='#1a2436'; textCol='#e5e9f0'; mutedCol='#94a3b8';
        borderCol='#2b3a52'; inputBg='#131c2c'; inputText='#e5e9f0'; topbarBg='#1a2436';
      }
    } else {
      pageBg=cfg.bg; cardBg='#ffffff'; textCol='#0f172a'; mutedCol='#64748b';
      borderCol='#e2e8f0'; inputBg='#ffffff'; inputText='#0f172a'; topbarBg='#ffffff';
    }
    if(cfg.increaseContrast){
      textCol = theme==='dark' ? '#ffffff' : '#000000';
      borderCol = theme==='dark' ? '#5b6b85' : '#94a3b8';
      mutedCol = theme==='dark' ? '#cbd5e1' : '#334155';
    }

    var css =
      'html,html:root,:root{'+
        '--accent:'+ac.accent+' !important;--accent-hover:'+ac.hover+' !important;--accent-soft:'+ac.soft+' !important;'+
        '--app-font:'+font+' !important;--app-font-size:'+size+' !important;'+'--print-font:'+printFont+' !important;--print-font-size:'+printSize+' !important;'+
        '--radius:'+rad.r+' !important;--radius-sm:'+rad.rs+' !important;'+
        '--bg:'+pageBg+' !important;--card:'+cardBg+' !important;'+
        '--text:'+textCol+' !important;--text-muted:'+mutedCol+' !important;--border:'+borderCol+' !important;'+
        '--navy:'+cfg.sidebar+' !important;--navy-light:'+darken(cfg.sidebar,0.12)+' !important;'+'--brand:'+ac.accent+' !important;--brand-dark:'+cfg.sidebar+' !important;'+
      '}'+
      'html,body{font-family:'+font+' !important;font-size:'+size+' !important;}'+'body,body *{font-family:inherit !important;}'+'html,body{'+
        'background:'+pageBg+' !important;color:'+textCol+' !important;}'+
      '.main-content,.container{background:transparent !important;}'+
      '.card,.login-box{background:'+cardBg+' !important;color:'+textCol+' !important;border-color:'+borderCol+' !important;}'+
      '.topbar{background:'+topbarBg+' !important;border-color:'+borderCol+' !important;color:'+textCol+' !important;}'+
      '.card-header{border-color:'+borderCol+' !important;}'+
      'th{background:'+(theme==='dark'?'#16202f':pageBg)+' !important;color:'+mutedCol+' !important;border-color:'+borderCol+' !important;}'+
      'td{border-color:'+borderCol+' !important;color:'+textCol+' !important;}'+
      'input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=color]):not([type=range]),textarea,select,select.field-select{'+
        'background:'+inputBg+' !important;color:'+inputText+' !important;'+
        '-webkit-text-fill-color:'+inputText+' !important;border-color:'+(theme==='dark'?'#475569':'#94a3b8')+' !important;}'+
      '.btn,.btn-quick-new,.btn-complete,.sidebar-link.active,.ca-tab.active,.settings-tab.active,.brand-mark{'+
        'background:'+ac.accent+' !important;border-color:'+ac.accent+' !important;}'+
      '.btn:hover,.btn-quick-new:hover,.sidebar-link.active:hover{background:'+ac.hover+' !important;}'+
      (function(){
        var sb=cfg.sidebar||'#ffffff';
        var light=isLightHex(sb);
        var sb2=light ? sb : darken(sb,0.14);
        var linkC=light?'#1e293b':'#cbd5e1';
        var linkH=light?'#0f172a':'#ffffff';
        var muted=light?'#64748b':'#94a3b8';
        var border=light?'rgba(15,23,42,.12)':'rgba(255,255,255,.08)';
        return '.sidebar{background:linear-gradient(180deg,'+sb+' 0%,'+sb2+' 100%) !important;color:'+(light?'#0f172a':'#fff')+' !important;}'+
          '.sidebar-link{color:'+linkC+' !important;}'+
          '.sidebar-link:hover{color:'+linkH+' !important;background:'+(light?'rgba(15,23,42,.06)':'rgba(255,255,255,.08)')+' !important;}'+
          '.sidebar-sublink{color:'+linkC+' !important;}'+
          '.sidebar-brand-text,.brand-name{color:'+(light?'#0f172a':'#fff')+' !important;}'+
          '.brand-sub,.sidebar-footer-version{color:'+muted+' !important;}'+
          '.sidebar-profile-name{color:'+(light?'#0f172a':'#f8fafc')+' !important;}'+
          '.sidebar-toggle{color:'+(light?'#0f172a':'#fff')+' !important;background:'+(light?'rgba(15,23,42,.08)':'rgba(255,255,255,.12)')+' !important;}'+
          '.sidebar-brand,.sidebar-profile,.sidebar-footer{border-color:'+border+' !important;}'+(theme==='light'?'.sidebar{background:#ffffff !important;color:#111827 !important;} .sidebar-link{color:#374151 !important;} .sidebar-link.active{background:#f3f4f6 !important;color:#111827 !important;box-shadow:inset -3px 0 0 #374151 !important;}':'');
      })();

    /* تم کارت‌ها: پیش‌فرض = ظاهر مینیمال قبلی، رنگی = Accent ماژول، mono = سیاه/سفید */
    if(cfg.cardTheme==='module'){
      css += ':root{--module-customers:#2563eb;--module-inventory:#ea580c;--module-finance:#16a34a;--module-reports:#7c3aed;--module-settings:#64748b;}'+
        '[data-card-theme="module"] .hub-card[data-module="customers"],[data-card-theme="module"] .module-card[data-module="customers"]{--card-accent:var(--module-customers);}'+
        '[data-card-theme="module"] .hub-card[data-module="inventory"],[data-card-theme="module"] .module-card[data-module="inventory"]{--card-accent:var(--module-inventory);}'+
        '[data-card-theme="module"] .hub-card[data-module="finance"],[data-card-theme="module"] .module-card[data-module="finance"]{--card-accent:var(--module-finance);}'+
        '[data-card-theme="module"] .hub-card[data-module="reports"],[data-card-theme="module"] .module-card[data-module="reports"]{--card-accent:var(--module-reports);}'+
        '[data-card-theme="module"] .hub-card[data-module="settings"],[data-card-theme="module"] .module-card[data-module="settings"]{--card-accent:var(--module-settings);}'+
        '[data-card-theme="module"] .hub-card,[data-card-theme="module"] .module-card,[data-card-theme="module"] .sys-tile{border-inline-start:3px solid var(--card-accent,var(--accent)) !important;}'+
        '[data-card-theme="module"] .hub-card .ui-icon,[data-card-theme="module"] .module-card .ui-icon,[data-card-theme="module"] .sys-tile .ui-icon{color:var(--card-accent,var(--accent)) !important;}';
    } else if(cfg.cardTheme==='mono'){
      /* Minimal Premium: Hub cards must be truly neutral.  The global card system
         defines module accent variables and pseudo-elements, so neutralize every
         accent-bearing surface here instead of only changing the border. */
      css += '[data-card-theme="mono"] .hub-card,[data-card-theme="mono"] .module-card,[data-card-theme="mono"] .sys-tile{--sg-module-accent:var(--text) !important;--sg-module-soft:transparent !important;--sg-module-line:var(--border) !important;border-color:var(--border) !important;border-inline-start:1px solid var(--border) !important;box-shadow:none !important;background:var(--card) !important;}'+
        '[data-card-theme="mono"] .hub-card::before,[data-card-theme="mono"] .module-card::before,[data-card-theme="mono"] .sys-tile::before{display:none !important;background:none !important;}'+
        '[data-card-theme="mono"] .hub-card::after,[data-card-theme="mono"] .module-card::after,[data-card-theme="mono"] .sys-tile::after{color:var(--text) !important;border-color:var(--border) !important;}'+
        '[data-card-theme="mono"] .hub-card .ui-icon,[data-card-theme="mono"] .module-card .ui-icon,[data-card-theme="mono"] .sys-tile .ui-icon,[data-card-theme="mono"] .sys-tile-icon{color:var(--text) !important;background:transparent !important;}'+
        '[data-card-theme="mono"] .hub-card .ic{background:#111827 !important;color:#fff !important;}'+
        '[data-card-theme="mono"] .stg-acc-item[data-color] .stg-card{border-color:var(--border) !important;border-inline-start:1px solid var(--border) !important;background:var(--card) !important;box-shadow:none !important;}'+
        '[data-card-theme="mono"] .stg-acc-item[data-color] .stg-card::before,[data-card-theme="mono"] .stg-acc-item[data-color] .stg-card::after{display:none !important;content:none !important;}'+
        '[data-card-theme="mono"] .stg-acc-item[data-color] .stg-card .stg-card-ic{color:var(--text) !important;background:transparent !important;}'+
        '[data-card-theme="mono"] .hub-card:hover,[data-card-theme="mono"] .module-card:hover,[data-card-theme="mono"] .sys-tile:hover{border-color:var(--text) !important;box-shadow:0 6px 18px rgba(15,23,42,.06) !important;}';
    } else {
      css += '[data-card-theme="default"] .hub-card,[data-card-theme="default"] .module-card,[data-card-theme="default"] .sys-tile{border-inline-start:1px solid var(--border) !important;}';
    }

    /* تراکم و گوشه — محسوس */
    (function(){
      var dens = cfg.density || 'comfortable';
      var densCss = '';
      if(dens === 'compact'){
        densCss =
          'html[data-density="compact"] .card-body{padding:8px 10px !important;}'+
          'html[data-density="compact"] .card-header{padding:8px 10px !important;}'+
          'html[data-density="compact"] .sidebar-link{padding:7px 10px !important;font-size:12.5px !important;}'+
          'html[data-density="compact"] .container{padding:12px 12px 28px !important;}'+
          'html[data-density="compact"] .btn,.btn-edit,.btn-export,.btn-cancel,.btn-complete,.btn-quick-new{min-height:32px !important;padding:5px 10px !important;font-size:12.5px !important;}'+
          'html[data-density="compact"] table th,html[data-density="compact"] table td{padding:6px 8px !important;font-size:12.5px !important;}'+
          'html[data-density="compact"] .form-grid{gap:8px 10px !important;}'+
          'html[data-density="compact"] .filter-bar{padding:10px !important;gap:8px !important;}'+
          'html[data-density="compact"] label{margin-bottom:3px !important;font-size:12px !important;}';
      } else if(dens === 'spacious'){
        densCss =
          'html[data-density="spacious"] .card-body{padding:22px 24px !important;}'+
          'html[data-density="spacious"] .card-header{padding:16px 20px !important;}'+
          'html[data-density="spacious"] .sidebar-link{padding:14px 16px !important;font-size:14px !important;}'+
          'html[data-density="spacious"] .container{padding:28px 28px 56px !important;}'+
          'html[data-density="spacious"] .btn,.btn-edit,.btn-export,.btn-cancel,.btn-complete,.btn-quick-new{min-height:44px !important;padding:10px 18px !important;font-size:14.5px !important;}'+
          'html[data-density="spacious"] table th,html[data-density="spacious"] table td{padding:14px 16px !important;}'+
          'html[data-density="spacious"] .form-grid{gap:18px 20px !important;}'+
          'html[data-density="spacious"] .filter-bar{padding:18px !important;gap:14px !important;}';
      } else {
        densCss =
          'html[data-density="comfortable"] .card-body{padding:16px 18px !important;}'+
          'html[data-density="comfortable"] .card-header{padding:12px 16px !important;}'+
          'html[data-density="comfortable"] .sidebar-link{padding:11px 14px !important;}'+
          'html[data-density="comfortable"] .btn,.btn-edit,.btn-export,.btn-cancel{min-height:38px !important;padding:8px 14px !important;}';
      }
      var r = rad.r, rs = rad.rs;
      densCss +=
        '.card,.login-box,.stat-card,.ds-section{border-radius:'+r+' !important;}'+
        '.btn,.btn-edit,.btn-export,.btn-cancel,.btn-complete,.btn-quick-new,.btn-delete,'+
        'input,textarea,select,select.field-select,.sidebar-link{border-radius:'+rs+' !important;}'+
        '.search-box,.ds-chip,.ds-mode{border-radius:calc('+rs+' + 4px) !important;}';
      css += densCss;
    })();
    if(cfg.reduceMotion){
      css += '*,*::before,*::after{animation-duration:0.001ms !important;animation-iteration-count:1 !important;transition-duration:0.001ms !important;scroll-behavior:auto !important;}';
    }
    if(cfg.increaseContrast){
      css += 'a,button,.btn,.sidebar-link,input,select,textarea{outline-offset:2px !important;} :focus-visible{outline:2.5px solid '+ac.accent+' !important;}';
    }
    ensureStyleEl().textContent=css;
    document.documentElement.style.setProperty('--navy', cfg.sidebar||'#ffffff');
    document.documentElement.style.setProperty('--navy-light', darken(cfg.sidebar||'#ffffff', 0.04));
    document.documentElement.style.setProperty('--accent', ac.accent);
    var sbEl=document.getElementById('sidebar')||document.querySelector('.sidebar');
    if(sbEl){
      var sb=cfg.sidebar||'#ffffff';
      var sb2=isLightHex(sb)?sb:darken(sb,0.14);
      sbEl.style.setProperty('background', 'linear-gradient(180deg,'+sb+' 0%,'+sb2+' 100%)', 'important');
    }
    document.querySelectorAll('.btn:not(.btn-cancel):not(.btn-edit):not(.btn-export):not(.btn-delete), .btn-quick-new, .btn-complete').forEach(function(b){
      b.style.setProperty('background', ac.accent, 'important');
      b.style.setProperty('background-color', ac.accent, 'important');
      b.style.setProperty('border-color', ac.accent, 'important');
      b.style.setProperty('color', '#fff', 'important');
    });
    document.querySelectorAll('.sidebar-link.active').forEach(function(b){
      b.style.setProperty('background', ac.accent, 'important');
    });
    document.querySelectorAll('.brand-mark').forEach(function(b){
      b.style.setProperty('background', ac.accent, 'important');
    });
    if(document.body){
      document.body.style.setProperty('font-family', font, 'important');
      document.body.style.setProperty('font-size', size, 'important');
      document.documentElement.style.setProperty('font-size', size, 'important');
      document.documentElement.style.setProperty('font-family', font, 'important');
      document.body.style.setProperty('background', pageBg, 'important');
      document.body.style.setProperty('color', textCol, 'important');
    }
  }
  function bootTheme(){
    try { apply(load()); } catch(e) { console.warn('theme apply', e); }
  }
  bootTheme();
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded', bootTheme);
  } else {
    setTimeout(bootTheme, 0);
  }
  window.addEventListener('pageshow', function(){ bootTheme(); });
  try{
    var _mq=window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
    if(_mq && _mq.addEventListener){
      _mq.addEventListener('change', function(){
        var cur=load();
        if(cur.theme==='system') bootTheme();
      });
    }
  }catch(e){}
  window.SazganDisplay={
    apply:apply, load:load, save:function(cfg){ try{ localStorage.setItem(KEY, JSON.stringify(cfg)); }catch(e){} }, KEY:KEY,
    resolveAccent:resolveAccent, resolveBg:resolveBg,
    darken:darken, softRgba:softRgba, normHex:normHex,
    syncFromServer:function(){
      if(!document.body || !document.body.hasAttribute('data-user-logged-in')) return;
      try{
        fetch('/api/display-prefs', {credentials:'same-origin'})
          .then(function(r){ return r.ok ? r.json() : null; })
          .then(function(res){
            if(res && res.ok && res.prefs && typeof res.prefs==='object' && Object.keys(res.prefs).length){
              var merged=Object.assign({}, load(), res.prefs);
              apply(merged);
            }
          })
          .catch(function(){});
      }catch(e){}
    },
    saveToServer:function(cfg){
      if(!document.body || !document.body.hasAttribute('data-user-logged-in')) return;
      try{
        var meta=document.querySelector('meta[name="csrf-token"]');
        fetch('/api/display-prefs', {
          method:'POST', credentials:'same-origin',
          headers:{'Content-Type':'application/json', 'X-CSRF-Token': meta?meta.content:''},
          body: JSON.stringify({prefs: cfg})
        }).catch(function(){});
      }catch(e){}
    }
  };
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded', function(){ window.SazganDisplay.syncFromServer(); });
  } else {
    setTimeout(function(){ window.SazganDisplay.syncFromServer(); }, 0);
  }
})();

/* Mark display initialization complete after tokens are applied, preventing transient sidebar/settings flashes. */
try {
  document.documentElement.classList.add('display-ready');
  window.requestAnimationFrame(function(){ document.documentElement.classList.add('display-painted'); });
} catch(e){}
