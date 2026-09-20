from __future__ import annotations
from flask import Blueprint, jsonify, request, current_app
from pathlib import Path
from core.excel_engine import preview, mapping_suggestions
from core.helpers import get_current_user

excel_api=Blueprint("excel_engine_api",__name__,url_prefix="/api/excel")

MAX_EXCEL_UPLOAD = 10 * 1024 * 1024
MAX_EXCEL_PREVIEW_ROWS = 5000

def _login_required():
    if not get_current_user():
        return jsonify({"ok":False,"error":"auth"}),401
    return None


def _db():
    for k in ("DATABASE_PATH","DB_PATH","DATABASE"):
        if current_app.config.get(k): return current_app.config[k]
    return str(Path(current_app.root_path)/"data"/"sazgan.db")

@excel_api.post("/preview")
def preview_api():
    denied = _login_required()
    if denied: return denied
    if request.content_length and request.content_length > MAX_EXCEL_UPLOAD:
        return jsonify({"ok":False,"error":"file_too_large","max_bytes":MAX_EXCEL_UPLOAD}),413
    if "file" not in request.files:
        return jsonify({"ok":False,"error":"file is required"}),400
    f=request.files["file"]
    if not f.filename.lower().endswith((".xlsx",".xlsm")):
        return jsonify({"ok":False,"error":"only .xlsx/.xlsm are supported"}),400
    upload=Path(current_app.root_path)/"data"/"imports"
    upload.mkdir(parents=True,exist_ok=True)
    safe=Path(f.filename).name
    path=upload/safe
    f.save(path)
    try:
        result = preview(path, request.form.get("sheet") or None)
        if isinstance(result, dict) and isinstance(result.get('rows'), list):
            result['rows'] = result['rows'][:MAX_EXCEL_PREVIEW_ROWS]
        return jsonify(result)
    finally:
        path.unlink(missing_ok=True)

@excel_api.post("/mapping")
def mapping_api():
    denied = _login_required()
    if denied: return denied
    body=request.get_json(silent=True) or {}
    return jsonify({"ok":True,"mapping":mapping_suggestions(body.get("headers",[]),body.get("target_fields",[]))})
