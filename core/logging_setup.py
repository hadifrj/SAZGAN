# -*- coding: utf-8 -*-
"""Centralized structured logging for Sazgan.

The application uses one ``sazgan`` logger so Flask routes, core services and
native-client helpers can write consistently formatted operational logs.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from core.constants import BASE_DIR

LOGGER_NAME = "sazgan"
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "sazgan.log")
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the application logger.

    Configuration is idempotent so repeated imports/startup hooks do not add
    duplicate file handlers.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    os.makedirs(LOG_DIR, exist_ok=True)

    handler_exists = any(
        isinstance(handler, RotatingFileHandler)
        and os.path.abspath(getattr(handler, "baseFilename", "")) == os.path.abspath(LOG_FILE)
        for handler in logger.handlers
    )
    if not handler_exists:
        handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(module)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)

    return logger
