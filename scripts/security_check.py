from pathlib import Path
root=Path(__file__).resolve().parents[1]
issues=[]
for p in root.rglob('*.py'):
    t=p.read_text(errors='ignore').lower()
    if 'password =' in t or 'secret_key =' in t: issues.append(str(p))
print('Security issues:', issues or 'none')
