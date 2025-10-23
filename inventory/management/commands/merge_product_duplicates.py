from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import Product, Batch, Movement

class Command(BaseCommand):
    help = (
        "Fusiona productos duplicados por (tenant_id, location_id, name_normalized). "
        "Mueve Batches y Movements al producto canónico y elimina el resto."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra lo que haría sin modificar nada."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Construir mapa de duplicados
        dupes = defaultdict(list)
        for p in Product.objects.all().values("id", "tenant_id", "location_id", "name", "name_normalized"):
            key = (p["tenant_id"], p["location_id"], p["name_normalized"])
            dupes[key].append(p)

        to_merge = {k: v for k, v in dupes.items() if len(v) > 1}
        total_groups = len(to_merge)
        self.stdout.write(self.style.WARNING(f"Grupos duplicados: {total_groups}"))

        if total_groups == 0:
            self.stdout.write(self.style.SUCCESS("No hay duplicados. Nada que hacer."))
            return

        for key, rows in to_merge.items():
            # Canónico = el de id menor (más antiguo)
            rows_sorted = sorted(rows, key=lambda r: str(r["id"]))
            canonical_id = rows_sorted[0]["id"]
            losers = [r["id"] for r in rows_sorted[1:]]

            self.stdout.write(f" Mantengo: {canonical_id}  |  Borro: {losers}")

            if dry_run:
                # Solo mostrar
                continue

            with transaction.atomic():
                # Reasignar lotes y movimientos
                Batch.objects.filter(product_id__in=losers).update(product_id=canonical_id)
                Movement.objects.filter(product_id__in=losers).update(product_id=canonical_id)
                # Eliminar productos duplicados
                Product.objects.filter(id__in=losers).delete()

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run completado. No se ha modificado la BD."))
        else:
            self.stdout.write(self.style.SUCCESS("Fusión de duplicados completada."))