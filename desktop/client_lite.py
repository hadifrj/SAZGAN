# -*- coding: utf-8 -*-
"""SAZGAN lightweight client — no webview / no CEF / no WebView2.

Asks for the server address once (via a small Tkinter dialog — part of the
Python standard library, so no extra dependency and no embedded browser
engine), saves it, then opens the address in the user's normal default
web browser (Chrome / Firefox / Edge / IE). Works on Windows 7 and up.
"""
from __future__ import annotations
import os, sys, json, webbrowser, tkinter as tk
from tkinter import messagebox
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

APP_TITLE = "Sazgan Client"
CONFIG_FILENAME = "sazgan_client.json"


def _config_path() -> str:
    appdata = os.environ.get("APPDATA")
    if appdata:
        p = os.path.join(appdata, "Sazgan")
        os.makedirs(p, exist_ok=True)
        return os.path.join(p, CONFIG_FILENAME)
    return os.path.join(os.path.abspath("."), CONFIG_FILENAME)


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
    except Exception:
        return False, "خطای غیرمنتظره در بررسی سرور."


class SetupDialog(tk.Tk):
    """A tiny, native (non-webview) dialog to collect and verify the server URL."""

    def __init__(self, initial_url=""):
        super().__init__()
        self.title("راه‌اندازی Sazgan Client")
        self.geometry("420x220")
        self.resizable(False, False)
        self.result_url = None

        tk.Label(self, text="آدرس سرور Sazgan را وارد کنید:", font=("Segoe UI", 11)).pack(pady=(20, 6))
        self.entry = tk.Entry(self, width=38, justify="left", font=("Segoe UI", 10))
        self.entry.insert(0, initial_url)
        self.entry.pack(pady=4)
        self.entry.focus()

        self.status = tk.Label(self, text="", fg="#b91c1c", wraplength=380, font=("Segoe UI", 9))
        self.status.pack(pady=8)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="بررسی و اتصال", command=self._check_and_close, width=16).pack(side="right", padx=6)
        tk.Button(btn_frame, text="انصراف", command=self.destroy, width=10).pack(side="right")

        self.bind("<Return>", lambda e: self._check_and_close())

    def _check_and_close(self):
        url = _normalize_url(self.entry.get())
        if not url:
            self.status.config(text="آدرس سرور را وارد کنید.")
            return
        self.status.config(text="در حال بررسی اتصال...", fg="#334155")
        self.update()
        ok, msg = _check_server(url)
        if not ok:
            self.status.config(text=msg or "اتصال برقرار نشد.", fg="#b91c1c")
            return
        self.result_url = url
        self.destroy()


def run_setup(initial_url=""):
    dlg = SetupDialog(initial_url)
    dlg.mainloop()
    return dlg.result_url


def main():
    force = "--setup" in sys.argv[1:]
    cfg = _load_config()
    saved = cfg.get("url") if not force else None

    if saved:
        ok, _ = _check_server(saved)
        if ok:
            webbrowser.open(saved)
            return
        # Saved server is unreachable - fall through to ask again.

    url = run_setup(initial_url=cfg.get("url", ""))
    if not url:
        return  # user cancelled
    _save_config({"url": url})
    webbrowser.open(url)


if __name__ == "__main__":
    main()
