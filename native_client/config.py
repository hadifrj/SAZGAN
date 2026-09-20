# -*- coding: utf-8 -*-
"""Persistent configuration for the Sazgan Native Client."""
from __future__ import annotations
import json
import os
from pathlib import Path

CONFIG_FILENAME = "sazgan_native_client.json"
DEFAULT_SERVER_URL = "http://127.0.0.1:5000"


def config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        folder = Path(appdata) / "Sazgan"
    else:
        folder = Path.home() / ".sazgan"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / CONFIG_FILENAME


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/")


def load_config() -> dict:
    try:
        with config_path().open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(data: dict) -> None:
    current = load_config()
    current.update(data or {})
    with config_path().open("w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)


def get_server_url() -> str:
    return normalize_url(load_config().get("url", ""))
