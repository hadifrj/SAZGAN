# -*- coding: utf-8 -*-
"""Command line database migration tool for Sazgan Desktop."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.db import get_db, init_db
from core.migration_engine import migrate, verify_history


def main():
    parser = argparse.ArgumentParser(description="Sazgan database migrations")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show pending migrations without changing the DB")
    parser.add_argument("--no-backup", action="store_true",
                        help="Do not create a pre-migration backup")
    parser.add_argument("--status", action="store_true",
                        help="Show migration status/history")
    args = parser.parse_args()

    # Ensure the legacy 2.10.10 compatibility schema exists before baseline.
    init_db()
    conn = get_db()
    try:
        if args.status:
            print(json.dumps(verify_history(conn), ensure_ascii=False, indent=2))
            return 0

        result = migrate(
            conn,
            dry_run=args.dry_run,
            backup=not args.no_backup,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"[sazgan] migration failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
