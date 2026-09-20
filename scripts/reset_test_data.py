#!/usr/bin/env python3
"""Create/reset a dedicated empty Sazgan test database."""
import argparse, sqlite3
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("--db",default="data/sazgan-test.db")
p.add_argument("--force",action="store_true")
a=p.parse_args()
db=Path(a.db)
if db.exists() and not a.force:
    raise SystemExit(f"{db} exists. Use --force to replace it.")
db.parent.mkdir(parents=True,exist_ok=True)
if db.exists(): db.unlink()
con=sqlite3.connect(db)
con.execute("CREATE TABLE sazgan_runtime(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
con.execute("INSERT INTO sazgan_runtime VALUES('environment','test')")
con.commit(); con.close()
print(f"Empty test database created: {db}")
