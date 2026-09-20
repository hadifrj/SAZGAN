# -*- coding: utf-8 -*-
"""SAZGAN thin client with a first-run multi-step setup wizard.

This variant forces the 'mshtml' GUI backend: pywebview renders the window
using the Trident/IE engine that ships with Windows itself (Windows 7 SP1+),
instead of bundling a full Chromium engine (CEF) or requiring the WebView2
runtime (which does not exist on Windows 7). Result: a real standalone
window (not the user's default browser), with a much smaller executable
and no extra runtime to install - at the cost of an older HTML/CSS/JS
rendering engine (roughly IE11-level).
"""
from __future__ import annotations
import os, sys, json, webbrowser
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import webview

APP_TITLE = "Sazgan"
CONFIG_FILENAME = "sazgan_client.json"
GUI_BACKEND = "mshtml"

def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _config_path() -> str:
    # Store user settings in AppData so Program Files is not required to be writable.
    appdata = os.environ.get("APPDATA")
    if appdata:
        p = os.path.join(appdata, "Sazgan")
        os.makedirs(p, exist_ok=True)
        return os.path.join(p, CONFIG_FILENAME)
    return os.path.join(_base_dir(), CONFIG_FILENAME)

def _load_config():
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_config(data):
    with open(_config_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _normalize_url(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.startswith("http://") and not raw.startswith("https://"):
        raw = "http://" + raw
    return raw.rstrip("/")

def _check_server(url: str):
    try:
        req = Request(url, headers={"User-Agent": "SazganClient/1.0"})
        with urlopen(req, timeout=6) as resp:
            return (resp.status < 500, "" if resp.status < 500 else f"کد پاسخ {resp.status}")
    except HTTPError as e:
        return (e.code < 500, "" if e.code < 500 else f"سرور خطا داد (کد {e.code}).")
    except URLError:
        return False, "اتصال برقرار نشد. آدرس، شبکه و پورت را بررسی کنید."
    except Exception as e:
        return False, "خطای غیرمنتظره در بررسی سرور."

WIZARD_HTML = r'''
<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;background:#f6f8fb;color:#18212b;font-family:"Segoe UI",Tahoma,sans-serif}
.shell{width:560px;max-width:94vw;margin:28px auto;background:#fff;border:1px solid #e3e8ef;border-radius:18px;box-shadow:0 14px 40px rgba(20,40,70,.10);overflow:hidden}
.top{padding:22px 26px;border-bottom:1px solid #edf0f4}.brand{font-size:20px;font-weight:800}.sub{font-size:12px;color:#718096;margin-top:4px}.steps{display:flex;gap:8px;margin-top:18px}.dot{height:6px;flex:1;border-radius:99px;background:#e6ebf1}.dot.on{background:#2aabee}
.body{padding:28px 30px;min-height:270px}.page{display:none}.page.on{display:block}h2{font-size:18px;margin:0 0 9px}p{font-size:13px;line-height:1.9;color:#64748b;margin:0 0 18px}.box{background:#f7f9fc;border:1px solid #e6ebf1;border-radius:12px;padding:14px;margin:10px 0}.ok{color:#15803d}.err{display:none;color:#b91c1c;background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:9px;font-size:12px;margin-top:12px}.status{font-size:13px;line-height:2}.progress{height:8px;background:#e9eef4;border-radius:99px;overflow:hidden}.bar{height:100%;width:0;background:#2aabee;transition:.2s}input{width:100%;padding:12px;border:1px solid #d7dee8;border-radius:10px;font-size:14px;direction:ltr;text-align:left;outline:none}input:focus{border-color:#2aabee}label{font-size:12px;font-weight:700;display:block;margin-bottom:7px}.foot{padding:16px 24px;border-top:1px solid #edf0f4;display:flex;gap:9px}.btn{border:0;border-radius:10px;padding:11px 18px;font-weight:700;cursor:pointer}.primary{background:#2aabee;color:#fff}.secondary{background:#eef2f6;color:#334155}.grow{flex:1}.hidden{display:none}
</style></head><body><div class="shell"><div class="top"><div class="brand">راه‌اندازی Sazgan Client</div><div class="sub">اتصال امن و مرحله‌ای به سرور مرکزی</div><div class="steps"><i class="dot on"></i><i class="dot"></i><i class="dot"></i><i class="dot"></i></div></div>
<div class="body"><section class="page on" data-p="0"><h2>خوش آمدید</h2><p>این برنامه فقط کلاینت است و دیتابیس یا سرور محلی ندارد. در چند مرحله آدرس سرور را ثبت و اتصال را بررسی می‌کنیم.</p><div class="box">✓ بدون نصب Python<br>✓ بدون دیتابیس محلی<br>✓ ذخیره تنظیمات برای دفعات بعد</div></section>
<section class="page" data-p="1"><h2>آدرس سرور</h2><p>آدرس سرور Sazgan را وارد کنید.</p><label>آدرس سرور</label><input id="url" placeholder="http://192.168.1.39:5000"><div id="err" class="err"></div></section>
<section class="page" data-p="2"><h2>بررسی اتصال</h2><p>اتصال به سرور بررسی می‌شود. اگر موفق باشد، نسخه سرور نیز نمایش داده می‌شود.</p><div class="box status" id="status">آماده بررسی...</div></section>
<section class="page" data-p="3"><h2>پایان راه‌اندازی</h2><p class="ok">✓ تنظیمات با موفقیت ذخیره شد.</p><div class="box">از این به بعد برنامه مستقیماً به سرور متصل می‌شود. برای تغییر سرور، برنامه را با <b>--setup</b> اجرا کنید.</div></section></div>
<div class="foot"><button class="btn secondary" id="back">قبلی</button><div class="grow"></div><button class="btn primary" id="next">بعدی</button></div></div>
<script>
let step=0, url=''; const pages=[...document.querySelectorAll('.page')],dots=[...document.querySelectorAll('.dot')],back=document.getElementById('back'),next=document.getElementById('next');
function render(){pages.forEach((x,i)=>x.classList.toggle('on',i===step));dots.forEach((x,i)=>x.classList.toggle('on',i<=step));back.style.visibility=step===0?'hidden':'visible';next.textContent=step===3?'اجرای Sazgan':(step===2?'بررسی اتصال':'بعدی');}
function err(t){let e=document.getElementById('err');e.textContent=t;e.style.display=t?'block':'none'}
async function go(){
 if(step===1){url=document.getElementById('url').value.trim();if(!url){err('آدرس سرور را وارد کنید.');return}err('');step=2;render();document.getElementById('status').textContent='در حال بررسی اتصال...';let r=await pywebview.api.check(url);if(!r.ok){document.getElementById('status').innerHTML='<span style="color:#b91c1c">✗ '+r.error+'</span>';return}document.getElementById('status').innerHTML='<span class="ok">✓ اتصال موفق است</span><br>سرور: '+r.url+(r.version?'\nنسخه: '+r.version:'');return;}
 if(step===2){let r=await pywebview.api.check(url);if(!r.ok){document.getElementById('status').innerHTML='<span style="color:#b91c1c">✗ '+r.error+'</span>';return}let s=await pywebview.api.save(url);if(!s.ok){document.getElementById('status').textContent=s.error;return}step=3;render();return;}
 if(step===3){pywebview.api.open();return} step++;render(); if(step===1){let c=await pywebview.api.get_config();document.getElementById('url').value=c.url||'';}}
back.onclick=()=>{if(step>0){step--;render()}};next.onclick=go;render();
</script></body></html>'''

class Api:
    def __init__(self): self.window=None
    def get_config(self): return _load_config()
    def check(self, raw_url):
        url=_normalize_url(raw_url)
        if not url:return {"ok":False,"error":"آدرس سرور را وارد کنید."}
        ok,msg=_check_server(url)
        if not ok:return {"ok":False,"error":msg}
        version=""
        try:
            req=Request(url+"/api/health",headers={"User-Agent":"SazganClient/1.0"})
            with urlopen(req,timeout=4) as r:
                data=json.loads(r.read().decode("utf-8")); version=str(data.get("version") or data.get("app_version") or "")
        except Exception: pass
        return {"ok":True,"url":url,"version":version}
    def save(self, raw_url):
        url=_normalize_url(raw_url); ok,msg=_check_server(url)
        if not ok:return {"ok":False,"error":msg}
        _save_config({"url":url}); return {"ok":True}
    def open(self):
        cfg=_load_config(); url=cfg.get("url")
        if self.window and url:self.window.load_url(url)

def main():
    force="--setup" in sys.argv[1:]
    cfg=_load_config(); saved=cfg.get("url") if not force else None
    api=Api()
    if saved:
        ok,_=_check_server(saved)
        if ok:
            w=webview.create_window(APP_TITLE,url=saved,width=1440,height=900,min_size=(1000,700),resizable=True,js_api=api)
        else:
            w=webview.create_window("راه‌اندازی Sazgan Client",html=WIZARD_HTML,width=650,height=560,resizable=False,js_api=api)
    else:
        w=webview.create_window("راه‌اندازی Sazgan Client",html=WIZARD_HTML,width=650,height=560,resizable=False,js_api=api)
    api.window=w; webview.start(gui=GUI_BACKEND)
if __name__=="__main__": main()
