from __future__ import annotations
from flask import Blueprint, jsonify, request
from core.data_entry import validate_customer, validate_equipment, validate_service

data_entry_api=Blueprint("data_entry_api",__name__,url_prefix="/api/data-entry")

@data_entry_api.post("/validate/customer")
def customer():
    return jsonify(validate_customer(request.get_json(silent=True) or {}))

@data_entry_api.post("/validate/equipment")
def equipment():
    return jsonify(validate_equipment(request.get_json(silent=True) or {}))

@data_entry_api.post("/validate/service")
def service():
    return jsonify(validate_service(request.get_json(silent=True) or {}))
