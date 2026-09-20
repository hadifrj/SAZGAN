# -*- coding: utf-8 -*-
"""SAZGAN Windows server installation/update wizard with online/offline dependency modes."""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile, zipfile, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
APP_NAME="SAZGAN Server Setup"
RUNTIME_VERSION="3.11.9"
RUNTIME_URL="https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
ROOT=Path(__file__).resolve().parent.parent

def find_python():
    candidates = [["py", "-3.11"], ["py", "-3"], ["python"]]
    for cmd in candidates:
        try:
            p=subprocess.run(cmd+["--version"],capture_output=True,text=True)
            if p.returncode==0 and "3.11" in (p.stdout+p.stderr): return cmd
        except Exception: pass
    return None

def runtime_installer(root):
    for p in [ROOT/"runtime"/f"python-{RUNTIME_VERSION}-amd64.exe", root/"runtime"/f"python-{RUNTIME_VERSION}-amd64.exe"]:
        if p.is_file(): return p
    return None

def download_runtime(dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    # PowerShell is built into supported Windows versions and avoids requiring curl.
    cmd=["powershell","-NoProfile","-ExecutionPolicy","Bypass","-Command",
         f"$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Uri '{RUNTIME_URL}' -OutFile '{dest}'"]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
    if p.returncode!=0 or not dest.exists() or dest.stat().st_size < 10000000:
        raise RuntimeError("دریافت Python Runtime ناموفق بود. اتصال اینترنت را بررسی کنید.")
    return dest

def install_runtime():
    global ROOT
    py=find_python()
    if py: return py, "existing"
    installer=runtime_installer(ROOT)
    if installer is None:
        installer=download_runtime(ROOT/"runtime"/f"python-{RUNTIME_VERSION}-amd64.exe")
    # Per-machine install; the wizard itself should be run as Administrator.
    args=[str(installer),"/quiet","InstallAllUsers=1","PrependPath=0","Include_test=0","Include_pip=1","Include_launcher=1","SimpleInstall=1"]
    p=subprocess.run(args,capture_output=True,text=True,timeout=600)
    if p.returncode not in (0,3010):
        raise RuntimeError(f"نصب Python Runtime شکست خورد. کد: {p.returncode}")
    py=find_python()
    if not py:
        raise RuntimeError("Python Runtime نصب شد اما Python 3.11 قابل شناسایی نیست.")
    return py, "installed"

def read_version(root):
    try:return (root/"VERSION").read_text(encoding="utf-8").splitlines()[0].strip().lstrip("vV")
    except Exception:return "0.0.0"

def ver(v):
    try:return tuple(int(x) for x in v.split(".")[:3])
    except:return (0,0,0)

def runtime_dirs(root):
    for rel in ["backups/updates","data","config","logs","static/uploads"]:
        (root/rel).mkdir(parents=True,exist_ok=True)

def offline_package_dir(root):
    for p in [root/"offline_packages", root/"offline"/"packages"]:
        if p.is_dir() and any(p.glob("*.whl")): return p
    return None

def internet_available():
    try:
        p=subprocess.run(["powershell","-NoProfile","-Command","try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 https://pypi.org/simple/).StatusCode } catch { exit 1 }"],capture_output=True,text=True,timeout=8)
        return p.returncode==0 and "200" in p.stdout
    except Exception:return False

def install_dependencies(py_cmd, root, mode):
    req=root/"requirements.txt"
    if not req.exists(): return subprocess.CompletedProcess([],0,"requirements.txt not found; skipped\n","")
    wheels=offline_package_dir(root)
    if mode=="offline":
        if not wheels: raise RuntimeError("حالت آفلاین انتخاب شده اما offline_packages/*.whl موجود نیست.")
        return subprocess.run(py_cmd+["-m","pip","install","--no-index","--find-links",str(wheels),"-r",str(req)],cwd=str(root),text=True,capture_output=True)
    # online mode intentionally uses the configured pip index; no --no-index.
    return subprocess.run(py_cmd+["-m","pip","install","-r",str(req)],cwd=str(root),text=True,capture_output=True)

class Wizard(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(APP_NAME); self.geometry("760x560"); self.resizable(False,False); self.configure(bg="#f6f8fb")
        self.mode=tk.StringVar(value="new"); self.dep_mode=tk.StringVar(value="auto"); self.package=tk.StringVar(); self.target=tk.StringVar(value=str(Path(os.environ.get("PROGRAMDATA",Path.home()))/"Sazgan")); self.service=tk.BooleanVar(value=True); self.status=tk.StringVar(value="آماده"); self.step=0; self.py=find_python(); self.runtime_file=runtime_installer(ROOT); self.offline_ready=offline_package_dir(ROOT) is not None; self.pages=[]; self._build(); self.show(0)
    def _build(self):
        top=tk.Frame(self,bg="#ffffff",height=92);top.pack(fill="x"); tk.Label(top,text="S A Z G A N",font=("Segoe UI",20,"bold"),bg="#fff",fg="#17212b").pack(anchor="e",padx=30,pady=(18,0)); tk.Label(top,text="راه‌اندازی و به‌روزرسانی سرور",font=("Segoe UI",10),bg="#fff",fg="#64748b").pack(anchor="e",padx=30)
        self.body=tk.Frame(self,bg="#f6f8fb");self.body.pack(fill="both",expand=True,padx=30,pady=20)
        self._page_welcome();self._page_mode();self._page_dep();self._page_target();self._page_install();self._page_done()
        foot=tk.Frame(self,bg="#fff");foot.pack(fill="x",side="bottom");self.back=tk.Button(foot,text="قبلی",command=self.prev);self.back.pack(side="left",padx=15,pady=12);self.next=tk.Button(foot,text="بعدی",bg="#2aabee",fg="white",relief="flat",command=self.next_step);self.next.pack(side="right",padx=15,pady=12)
    def page(self): f=tk.Frame(self.body,bg="#f6f8fb");self.pages.append(f);return f
    def _page_welcome(self):
        f=self.page();tk.Label(f,text="به نصب‌کننده SAZGAN خوش آمدید",font=("Segoe UI",18,"bold"),bg="#f6f8fb",fg="#17212b").pack(anchor="e",pady=15);tk.Label(f,text="نصب جدید یا به‌روزرسانی را مرحله‌به‌مرحله انجام می‌دهد. قبل از Migration پشتیبان‌گیری می‌شود.",justify="right",font=("Segoe UI",11),bg="#f6f8fb",fg="#64748b").pack(anchor="e",fill="x",pady=8);self.welcome_info=tk.Label(f,text="",justify="right",bg="#fff",fg="#334155",padx=15,pady=15);self.welcome_info.pack(fill="x",pady=15)
    def _page_mode(self):
        f=self.page();tk.Label(f,text="نوع عملیات",font=("Segoe UI",18,"bold"),bg="#f6f8fb").pack(anchor="e",pady=15);tk.Radiobutton(f,text="نصب جدید روی سرور",variable=self.mode,value="new",bg="#f6f8fb",font=("Segoe UI",11),anchor="e").pack(fill="x",pady=8);tk.Radiobutton(f,text="به‌روزرسانی نصب موجود",variable=self.mode,value="update",bg="#f6f8fb",font=("Segoe UI",11),anchor="e").pack(fill="x",pady=8)
    def _page_dep(self):
        f=self.page();tk.Label(f,text="روش نصب پیش‌نیازها",font=("Segoe UI",18,"bold"),bg="#f6f8fb").pack(anchor="e",pady=15);tk.Radiobutton(f,text="خودکار — اگر بسته آفلاین موجود باشد از آن استفاده می‌شود، در غیر این صورت آنلاین",variable=self.dep_mode,value="auto",bg="#f6f8fb",font=("Segoe UI",11),anchor="e",justify="right").pack(fill="x",pady=8);tk.Radiobutton(f,text="آنلاین — دریافت پیش‌نیازها از PyPI (اینترنت لازم است)",variable=self.dep_mode,value="online",bg="#f6f8fb",font=("Segoe UI",11),anchor="e",justify="right").pack(fill="x",pady=8);tk.Radiobutton(f,text="آفلاین — فقط از offline_packages استفاده شود (اینترنت لازم نیست)",variable=self.dep_mode,value="offline",bg="#f6f8fb",font=("Segoe UI",11),anchor="e",justify="right").pack(fill="x",pady=8);self.dep_info=tk.Label(f,text="",justify="right",bg="#fff",fg="#334155",padx=15,pady=15);self.dep_info.pack(fill="x",pady=20)
    def _page_target(self):
        f=self.page();tk.Label(f,text="مسیر و بسته نصب",font=("Segoe UI",18,"bold"),bg="#f6f8fb").pack(anchor="e",pady=15);row=tk.Frame(f,bg="#f6f8fb");row.pack(fill="x",pady=8);tk.Label(row,text="مسیر نصب:",bg="#f6f8fb").pack(side="right");tk.Entry(row,textvariable=self.target,width=55).pack(side="right",padx=8);tk.Button(row,text="انتخاب",command=self.pick_target).pack(side="left");row2=tk.Frame(f,bg="#f6f8fb");row2.pack(fill="x",pady=8);tk.Label(row2,text="ZIP نسخه:",bg="#f6f8fb").pack(side="right");tk.Entry(row2,textvariable=self.package,width=55).pack(side="right",padx=8);tk.Button(row2,text="انتخاب فایل",command=self.pick_zip).pack(side="left");tk.Checkbutton(f,text="نصب/فعال‌سازی سرویس Windows پس از نصب",variable=self.service,bg="#f6f8fb").pack(anchor="e",pady=15)
    def _page_install(self):
        f=self.page();tk.Label(f,text="در حال انجام عملیات",font=("Segoe UI",18,"bold"),bg="#f6f8fb").pack(anchor="e",pady=15);self.progress=ttk.Progressbar(f,mode="determinate",maximum=100);self.progress.pack(fill="x",pady=20);tk.Label(f,textvariable=self.status,justify="right",bg="#fff",anchor="e",padx=15,pady=15).pack(fill="both",expand=True)
    def _page_done(self):
        f=self.page();tk.Label(f,text="عملیات با موفقیت انجام شد",font=("Segoe UI",18,"bold"),bg="#f6f8fb",fg="#15803d").pack(anchor="e",pady=30);self.done=tk.Label(f,text="",justify="right",bg="#fff",padx=18,pady=18);self.done.pack(fill="x")
    def pick_zip(self): self.package.set(filedialog.askopenfilename(filetypes=[("SAZGAN Release","*.zip"),("All files","*.*")]))
    def pick_target(self):
        p=filedialog.askdirectory();
        if p:self.target.set(p)
    def show(self,n):
        self.step=n
        for p in self.pages:p.pack_forget()
        self.pages[n].pack(fill="both",expand=True);self.back.config(state="normal" if n>0 else "disabled");self.next.config(text="نصب" if n==4 else ("پایان" if n==5 else "بعدی"),state="normal")
        if n==0:self.welcome_info.config(text=f"Python: {'✓ پیدا شد' if self.py else '✗ پیدا نشد'}\nبسته آفلاین: {'✓ آماده' if self.offline_ready else '✗ موجود نیست'}\nروش پیش‌فرض پیش‌نیازها: خودکار\nPython Runtime: {"✓ نصب است" if self.py else ("✓ بسته آماده است" if self.runtime_file else "⚠ نیاز به دریافت آنلاین")}\nمسیر پیشنهادی: {self.target.get()}")
        if n==2:self.dep_info.config(text=f"وضعیت بسته آفلاین: {'✓ موجود' if self.offline_ready else '✗ موجود نیست'}\nدر حالت آنلاین، pip از PyPI استفاده می‌کند و اینترنت لازم است.\nدر حالت آفلاین، هیچ اتصال اینترنتی برای Dependency انجام نمی‌شود.")
    def prev(self):
        if self.step>0:self.show(self.step-1)
    def next_step(self):
        if self.step==0:self.show(1);return
        if self.step==1:self.show(2);return
        if self.step==2:
            if self.dep_mode.get()=="offline" and not self.offline_ready:messagebox.showerror(APP_NAME,"حالت آفلاین انتخاب شده اما بسته‌های offline_packages موجود نیست.");return
            self.show(3);return
        if self.step==3:
            if not self.package.get():messagebox.showerror(APP_NAME,"لطفاً فایل Release ZIP را انتخاب کنید.");return
            if not Path(self.package.get()).exists():messagebox.showerror(APP_NAME,"فایل ZIP پیدا نشد.");return
            self.show(4);self.after(100,self.run_install);return
        if self.step==4:return
        self.destroy()
    def run_install(self):
        try:
            mode=self.dep_mode.get(); wheels=offline_package_dir(ROOT)
            if not self.py:
                if mode=="offline" and self.runtime_file is None:
                    raise RuntimeError("حالت آفلاین انتخاب شده اما Python Runtime آفلاین داخل بسته وجود ندارد.")
                self.status.set("در حال نصب Python Runtime 3.11 x64..."); self.update()
                self.py, runtime_state = install_runtime()
            else:
                runtime_state = "existing"
            if mode=="auto": mode="offline" if wheels else "online"
            if mode=="online" and not internet_available(): raise RuntimeError("حالت آنلاین انتخاب شده اما اتصال به اینترنت/PyPI در دسترس نیست.")
            if mode=="offline" and not wheels: raise RuntimeError("حالت آفلاین انتخاب شده اما offline_packages موجود نیست.")
            pkg=Path(self.package.get()).resolve();target=Path(self.target.get()).resolve();target.mkdir(parents=True,exist_ok=True);runtime_dirs(target)
            self.progress['value']=10;self.status.set("بررسی Release ZIP...");self.update()
            with zipfile.ZipFile(pkg) as z:
                if z.testzip(): raise RuntimeError("ZIP آسیب‌دیده است.")
                extract=Path(tempfile.mkdtemp(prefix="sazgan_setup_"));z.extractall(extract)
            candidates=[p for p in [extract,extract/"sazgan-app"] if (p/"VERSION").exists()]
            if not candidates: raise RuntimeError("ZIP معتبر SAZGAN نیست.")
            source=candidates[0];newv=read_version(source);oldv=read_version(target)
            self.progress['value']=25;self.status.set(f"نسخه نصب: {oldv}\nنسخه جدید: {newv}\nPython Runtime: {runtime_state}\nروش پیش‌نیازها: {'آنلاین' if mode=='online' else 'آفلاین'}");self.update()
            if self.mode.get()=="update" and ver(newv)<=ver(oldv):raise RuntimeError(f"نسخه {newv} جدیدتر از {oldv} نیست.")
            self.progress['value']=40;self.status.set("پشتیبان‌گیری و آماده‌سازی...");self.update()
            # Copy first for a fresh install. Existing updater remains responsible for production updates.
            if self.mode.get()=="update" and (target/"scripts"/"update.py").exists():
                p=subprocess.run(self.py+[str(target/"scripts"/"update.py"),"--package",str(pkg)],cwd=target,capture_output=True,text=True)
                if p.returncode!=0:raise RuntimeError(p.stdout[-1800:]+p.stderr[-1800:])
            else:
                preserve={"sazgan.db",".secret_key","backups","static/uploads","dist","build",".venv","venv","env","logs"}
                for item in source.iterdir():
                    if item.name in preserve:continue
                    dest=target/item.name
                    if item.is_dir():shutil.copytree(item,dest,dirs_exist_ok=True)
                    else:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(item,dest)
                runtime_dirs(target)
                self.progress['value']=60;self.status.set(f"نصب پیش‌نیازها به روش {'آنلاین (PyPI)' if mode=='online' else 'آفلاین'}...");self.update()
                p=install_dependencies(self.py,target,mode)
                if p.returncode!=0:raise RuntimeError((p.stdout or "")[-1200:]+(p.stderr or "")[-2000:])
                self.progress['value']=78;self.status.set("اجرای Migration دیتابیس...");self.update()
                mig=target/"scripts"/"migrate_db.py"
                if mig.exists():
                    p=subprocess.run(self.py+[str(mig)],cwd=target,capture_output=True,text=True)
                    if p.returncode!=0:raise RuntimeError((p.stdout or "")[-1000:]+(p.stderr or "")[-1000:])
            self.progress['value']=90;self.status.set("بررسی نهایی و آماده‌سازی سرویس...");self.update()
            if self.service.get():
                svc=target/"scripts"/"install_service.bat"
                if svc.exists():subprocess.run(["cmd","/c",str(svc)],cwd=target)
            self.progress['value']=100;self.status.set("✓ نصب و Migration با موفقیت انجام شد.");self.done.config(text=f"نسخه {newv} نصب شد.\nمسیر: {target}\nروش پیش‌نیازها: {'آنلاین' if mode=='online' else 'آفلاین'}\nدیتابیس موجود حفظ شد و Migration اجرا شد.");self.show(5)
        except Exception as e:
            self.status.set("✗ عملیات متوقف شد:\n"+str(e));messagebox.showerror(APP_NAME,str(e));self.next.config(state="disabled")
if __name__=="__main__": Wizard().mainloop()
