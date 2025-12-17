import os
import sys
import webbrowser
import threading
from pathlib import Path

from django.db import connections
from django.db.migrations.executor import MigrationExecutor


# ============================================================
# CONFIGURACIÓN BASE
# ============================================================

APP_NAME = "SmartInventory"

# --- Carpeta de datos persistentes (Roaming) ---
if sys.platform == "win32":
    APP_DATA_DIR = Path(os.environ["APPDATA"]) / APP_NAME
else:
    APP_DATA_DIR = Path.home() / f".{APP_NAME.lower()}"

DB_DIR = APP_DATA_DIR / "db"
MEDIA_DIR = APP_DATA_DIR / "media"
QR_DIR = MEDIA_DIR / "qr"
LOGS_DIR = APP_DATA_DIR / "logs"
BACKUP_DIR = APP_DATA_DIR / "backups"

for d in (DB_DIR, MEDIA_DIR, QR_DIR, LOGS_DIR, BACKUP_DIR):
    d.mkdir(parents=True, exist_ok=True)
os.environ["SMARTINV_LOG_DIR"] = str(LOGS_DIR)

os.environ["SMARTINV_MEDIA_DIR"] = str(MEDIA_DIR)

os.environ["DEBUG"] = "true"



# --- Forzar base de datos SQLite en Roaming ---
os.environ["DATABASE_URL"] = f"sqlite:///{DB_DIR / 'db.sqlite3'}"

# --- Silenciar stdout/stderr en modo exe ---
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# --- Directorio del código ---
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).resolve().parent

MANAGE_PY = ROOT_DIR / "manage.py"


# ============================================================
# FUNCIONES DJANGO
# ============================================================

def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_inventory.settings")
    import django
    django.setup()


def has_superuser():
    setup_django()
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.filter(is_superuser=True).exists()


def has_pending_migrations():
    setup_django()
    connection = connections["default"]
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    plan = executor.migration_plan(targets)
    return bool(plan)


def django_cmd(args):
    setup_django()
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py"] + args)


# ============================================================
# MAIN
# ============================================================

def main():
    # 1️⃣ Migraciones (con backup previo)
    if has_pending_migrations():
        try:
            from backup_db import backup_sqlite_db
            backup_sqlite_db(reason="pre_migrate", backup_dir=BACKUP_DIR)
        except Exception:
            pass

        django_cmd(["migrate", "--noinput"])

    # 2️⃣ Crear superusuario si no existe
    try:
        if not has_superuser():
            resp = input(
                "\nNo existe ningún administrador.\n"
                "¿Quieres crear uno ahora? (s/N): "
            ).strip().lower()

            if resp == "s":
                django_cmd(["createsuperuser"])
    except Exception:
        pass

    # 3️⃣ Arrancar servidor + abrir navegador
    threading.Timer(
        1.0,
        lambda: webbrowser.open("http://127.0.0.1:8000")
    ).start()

    django_cmd(["runserver", "0.0.0.0:8000", "--noreload", "--insecure"])


if __name__ == "__main__":
    main()
