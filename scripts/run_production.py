"""اجرای تولیدی سازگان بدون debug."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, init_db, create_backup
import threading
from app import _backup_scheduler, BACKUP_DIR

if __name__ == '__main__':
    init_db()
    try:
        create_backup('startup')
    except Exception as e:
        print('backup:', e)
    threading.Thread(target=_backup_scheduler, daemon=True).start()
    port = int(os.environ.get('SAZGAN_PORT', '5000'))
    print(f'Sazgan production http://0.0.0.0:{port} backups={BACKUP_DIR}')
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
