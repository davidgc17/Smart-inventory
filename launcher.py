import sys
import webbrowser
from pathlib import Path
import os
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from pathlib import Path
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).resolve().parent

MANAGE_PY = ROOT_DIR / "manage.py"




def has_superuser():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_inventory.settings")
    import django
    django.setup()

    from django.contrib.auth import get_user_model
    User = get_user_model()

    return User.objects.filter(is_superuser=True).exists()


def has_pending_migrations():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_inventory.settings")
    import django
    django.setup()


    connection = connections["default"]
    executor = MigrationExecutor(connection)

    targets = executor.loader.graph.leaf_nodes()
    plan = executor.migration_plan(targets)

    return bool(plan)

def django_cmd(args):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_inventory.settings")
    import django
    django.setup()
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py"] + args)




def main():
    # 1) Migraciones
    if has_pending_migrations():
        print(">> Migraciones pendientes detectadas")
        from backup_db import backup_sqlite_db
        backup_sqlite_db(reason="pre_migrate")
        django_cmd(["migrate", "--noinput"])
    else:
        print(">> No hay migraciones pendientes")

    # 2) Admin
    try:
        if not has_superuser():
            resp = input(
                "\nNo existe ningún administrador.\n"
                "¿Quieres crear uno ahora? (s/N): "
            ).strip().lower()

            if resp == "s":
                django_cmd(["createsuperuser"])
    except Exception as e:
        print("Aviso admin:", e)

    # 3) Servidor + navegador
    print("\n>> Iniciando servidor Django")
    import threading
    threading.Timer(
        1.0,
        lambda: webbrowser.open("http://127.0.0.1:8000")
    ).start()

    django_cmd(["runserver", "0.0.0.0:8000", "--noreload", "--insecure"])




if __name__ == "__main__":
    main()
