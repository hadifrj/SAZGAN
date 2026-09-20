#!/usr/bin/env python3
"""Sazgan data safety CLI."""
import argparse
from pathlib import Path
from core.data_safety import integrity_check, backup_database, restore_database

p=argparse.ArgumentParser()
p.add_argument("action",choices=["check","backup","restore"])
p.add_argument("--db",default="data/sazgan.db")
p.add_argument("--backup-dir",default="data/backups")
p.add_argument("--backup")
a=p.parse_args()
db=Path(a.db)
if a.action=="check": print(integrity_check(db))
elif a.action=="backup": print(backup_database(db,a.backup_dir))
else:
    if not a.backup: p.error("--backup is required")
    print(restore_database(a.backup,db,True))
