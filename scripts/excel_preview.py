#!/usr/bin/env python3
import argparse, json
from core.excel_engine import preview
p=argparse.ArgumentParser()
p.add_argument("file")
p.add_argument("--sheet")
p.add_argument("--limit",type=int,default=100)
a=p.parse_args()
print(json.dumps(preview(a.file,a.sheet,limit=a.limit),ensure_ascii=False,indent=2))
