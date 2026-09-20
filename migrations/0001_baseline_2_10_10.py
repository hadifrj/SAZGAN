# -*- coding: utf-8 -*-
"""Baseline marker for the schema shipped with Sazgan 2.10.10."""

def upgrade(conn):
    # The legacy init_db() function creates/migrates the 2.10.10 schema.
    # This migration intentionally has no SQL; it establishes version 1.
    return None
