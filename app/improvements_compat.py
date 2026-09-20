# -*- coding: utf-8 -*-
"""Backward-compatible import surface for routes.improvements."""
from routes.improvements import *  # noqa: F401,F403
from routes.improvements import (  # noqa: F401
    ensure_improvements_schema,
    register_improvements,
    migrate_statuses,
    normalize_status,
    checklist_complete,
    try_auto_warehouse,
)
