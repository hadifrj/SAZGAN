# -*- coding: utf-8 -*-
"""Backward-compatible import surface for routes.features."""
from routes.features import *  # noqa: F401,F403
from routes.features import (  # noqa: F401
    ensure_features_schema,
    register_feature_routes,
    log_status_change,
    allowed_next_statuses,
)
