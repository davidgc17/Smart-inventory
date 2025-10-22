import uuid
import traceback
from datetime import date, datetime
from django.urls import path, include
from django.conf import settings
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.filters import OrderingFilter, SearchFilter


from .models import Batch, Product, Location, Movement
from .serializers import ProductSerializer, LocationSerializer, MovementSerializer

DEFAULT_TENANT = uuid.UUID(getattr(settings, "DEFAULT_TENANT", "00000000-0000-0000-0000-000000000001"))


class TenantScopedMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(tenant_id=DEFAULT_TENANT)

    def perform_create(self, serializer):
        serializer.save(tenant_id=DEFAULT_TENANT)


# -------------------------------------------------------------------
#  Routers para vistas estándar (admin / API REST)
# -------------------------------------------------------------------
router = DefaultRouter()


class BaseViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

# 👇 Hijos SIN el mixin
class ProductViewSet(BaseViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class LocationViewSet(BaseViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer

class MovementViewSet(BaseViewSet):
    queryset = Movement.objects.all()
    serializer_class = MovementSerializer

router.register(r"products", ProductViewSet)
router.register(r"locations", LocationViewSet)
router.register(r"movements", MovementViewSet)


# -------------------------------------------------------------------
#  ENDPOINT PRINCIPAL DE ESCANEO
# -------------------------------------------------------------------
@method_decorator(csrf_exempt, name='dispatch')
class ScanEndpoint(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        payload = (request.data.get("payload") or "").strip()
        # cantidad segura
        try:
            qty = int(request.data.get("quantity") or 1)
        except ValueError:
            return Response({"detail": "Cantidad inválida"}, status=400)

        loc_name = (request.data.get("location") or "").strip()

        # Normalización del tipo (acepta español o código)
        mtype_raw = (request.data.get("movement_type") or request.data.get("type") or "OUT").strip().upper()
        TYPE_MAP = {
            "ENTRADA": "IN", "IN": "IN",
            "SALIDA": "OUT", "OUT": "OUT",
            "AUDITORIA": "AUD", "AUDITORÍA": "AUD", "AUD": "AUD",
            "AUDTOTAL": "AUDTOTAL", "TOTAL": "AUDTOTAL"
        }
        mtype = TYPE_MAP.get(mtype_raw, mtype_raw)

        # -------------------------------------------------------
        # Buscar ubicación (opcional) + queryset base
        # -------------------------------------------------------
        location = None
        location_qs = Location.objects.none()
        if loc_name:
            location = Location.objects.filter(name=loc_name, tenant_id=DEFAULT_TENANT).first()
            if not location:
                return Response({"detail": "Ubicación no encontrada"}, status=status.HTTP_404_NOT_FOUND)
            # Si tu modelo tiene jerarquía y quieres incluir sububicaciones,
            # reemplaza esta línea por una que obtenga descendientes.
            # Por ahora: solo la ubicación exacta.
            location_qs = Location.objects.filter(id=location.id, tenant_id=DEFAULT_TENANT)

        # -------------------------------------------------------
        # Helper: extraer UUID del payload "PRD:<uuid>"
        # -------------------------------------------------------
        def parse_uuid_from_payload(p):
            if not p.startswith("PRD:"):
                return None
            return p.split(":", 1)[1].strip()

        incoming_uuid = parse_uuid_from_payload(payload)

        # -------------------------------------------------------
        # ENTRADA
        # -------------------------------------------------------
        if mtype == "IN":
            new_data = request.data.get("new_product", {}) or {}
            name = new_data.get("name", "").strip()
            unit = new_data.get("unit", "").strip()
            category = new_data.get("category", "").strip()

            if not name:
                return Response({"detail": "El nombre del producto es obligatorio"}, status=400)
            if not unit:
                return Response({"detail": "La unidad es obligatoria"}, status=400)

            product, created = Product.objects.get_or_create(
                name=name,
                location=location,
                tenant_id=DEFAULT_TENANT,
                defaults={
                    "category": category,
                    "unit": unit,
                    "min_stock": int(new_data.get("min_stock") or 0),
                    "notes": new_data.get("notes", ""),
                    "expiration_date": new_data.get("expiration_date") or None,
                },
            )

            batch = Batch.objects.create(
                product=product,
                quantity=abs(qty),
                expiration_date=new_data.get("expiration_date") or None,
                notes=new_data.get("notes", ""),
                tenant_id=DEFAULT_TENANT,
            )

            Movement.objects.create(
                product=product,
                location=location,
                quantity=abs(qty),
                movement_type="IN",
                metadata={"batch_id": batch.id, "entry_date": str(batch.entry_date)},
                tenant_id=DEFAULT_TENANT,
            )

            return Response({
                "ok": True,
                "payload": f"PRD:{product.uuid}",
                "detail": f"Entrada registrada (lote {batch.id})"
            })

        # -------------------------------------------------------
        # SALIDA
        # -------------------------------------------------------
        elif mtype == "OUT":
            if not incoming_uuid:
                return Response({"detail": "Payload inválido (se espera PRD:<uuid>)"}, status=400)

            product = Product.objects.filter(uuid=incoming_uuid, tenant_id=DEFAULT_TENANT).first()
            if not product:
                return Response({"detail": "Producto no encontrado"}, status=404)

            Movement.objects.create(
                product=product,
                location=location,
                quantity=-abs(qty),
                movement_type="OUT",
                tenant_id=DEFAULT_TENANT,           # <- faltaba
            )

            return Response({"ok": True, "payload": f"PRD:{product.uuid}"}, status=200)

        # -------------------------------------------------------
        # AUDITORÍA POR UBICACIÓN
        # -------------------------------------------------------
        elif mtype == "AUD":
            if not location:
                return Response({"detail": "Debes indicar una ubicación"}, status=400)

            products = (
                Product.objects
                .filter(location__in=location_qs, tenant_id=DEFAULT_TENANT)
                .select_related("location")
                .prefetch_related("batches")
            )

            data = []
            for p in products:
                batches = list(
                    p.batches.values("id", "quantity", "expiration_date").order_by("expiration_date")
                )
                total_qty = sum(int(b.get("quantity") or 0) for b in batches)
                nearest_exp = min(
                    (b["expiration_date"] for b in batches if b.get("expiration_date")),
                    default=None
                )
                data.append({
                    "product": p.name,
                    "total_quantity": total_qty,
                    "nearest_expiration": nearest_exp,
                    "batches": batches,
                })

            return Response({
                "ok": True,
                "location": location.full_path() if hasattr(location, "full_path") else location.name,
                "total_products": len(data),
                "items": data,
            }, status=200)

        # -------------------------------------------------------
        # AUDITORÍA TOTAL (INVENTARIO COMPLETO)
        # -------------------------------------------------------
        elif mtype == "AUDTOTAL":
            all_locations = Location.objects.filter(tenant_id=DEFAULT_TENANT).order_by("name")
            inventory = []

            for loc in all_locations:
                products = (
                    Product.objects
                    .filter(location=loc, tenant_id=DEFAULT_TENANT)
                    .prefetch_related("batches")
                )
                if not products.exists():
                    continue

                items = []
                for p in products:
                    batches = list(
                        p.batches.values("id", "quantity", "expiration_date").order_by("expiration_date")
                    )
                    total_qty = sum(int(b.get("quantity") or 0) for b in batches)
                    nearest_exp = min(
                        (b["expiration_date"] for b in batches if b.get("expiration_date")),
                        default=None
                    )
                    items.append({
                        "product": p.name,
                        "total_quantity": total_qty,
                        "nearest_expiration": nearest_exp,
                        "batches": batches,
                    })

                inventory.append({
                    "location": loc.full_path() if hasattr(loc, "full_path") else loc.name,
                    "total_products": len(items),
                    "items": items,
                })

            return Response({"ok": True, "total_locations": len(inventory), "inventory": inventory}, status=200)

        # -------------------------------------------------------
        # ERROR
        # -------------------------------------------------------
        else:
            return Response({"detail": f"Tipo de movimiento no soportado: {mtype}"}, status=400)



# -------------------------------------------------------------------
#  URLS DEL MÓDULO
# -------------------------------------------------------------------
urlpatterns = [
    path("", include(router.urls)),
    path("scan/", ScanEndpoint.as_view()),
]
