from pathlib import Path
import shutil, datetime

def backup(src='data'):
    out=Path('backup')/str(datetime.date.today())
    out.mkdir(parents=True,exist_ok=True)
    if Path(src).exists(): shutil.copytree(src,out/'data',dirs_exist_ok=True)
    return out
