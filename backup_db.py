import os
import shutil
from datetime import datetime
from django.conf import settings

def backup_sqlite_db(reason="manual"):
    db_path = settings.DATABASES["default"]["NAME"]

    if not db_path or not os.path.exists(db_path):
        raise RuntimeError("No se ha encontrado la base de datos SQLite.")

    backups_dir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(backups_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_name = os.path.basename(db_path)

    backup_name = f"{db_name}.{timestamp}.{reason}.bak"
    backup_path = os.path.join(backups_dir, backup_name)

    shutil.copy2(db_path, backup_path)

    return backup_path
