import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_inventory.settings")
django.setup()

from backup_db import backup_sqlite_db

if __name__ == "__main__":
    path = backup_sqlite_db(reason="pre_migrate")
    print(f"Backup creado en: {path}")
