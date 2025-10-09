import traceback
from datetime import date, datetime
from django.urls import path, include
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import Batch, Product, Location, Movement
from .serializers import ProductSerializer, LocationSerializer, MovementSerializer


# -------------------------------------------------------------------
#  Routers para vistas estándar (admin / API REST)
# -------------------------------------------------------------------
router = DefaultRouter()


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]


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
        import uuid
        from datetime import date, datetime

        payload = (request.data.get("payload") or "").strip()
        qty = int(request.data.get("quantity") or 1)
        loc_name = (request.data.get("location") or "").strip()
        mtype = (request.data.get("movement_type") or "OUT").upper()

        # -------------------------------------------------------
        # Buscar ubicación (solo si se ha enviado)
        # -------------------------------------------------------
        location = None
        if loc_name:
            location = Location.objects.filter(name=loc_name).first()
            if not location:
                return Response({"detail": "Ubicación no encontrada"}, status=status.HTTP_404_NOT_FOUND)

        # -------------------------------------------------------
        # Helper: extraer UUID del payload "PRD:<uuid>"
        # -------------------------------------------------------
        def parse_uuid_from_payload(p):
            if not p.startswith("PRD:"):
                return None
            return p.split(":", 1)[1].strip()

        incoming_uuid = parse_uuid_from_payload(payload)
        product = None

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

            # Buscar producto existente (por nombre y ubicación)
            product, created = Product.objects.get_or_create(
                name=name,
                location=location,
                defaults={
                    "category": category,
                    "unit": unit,
                    "min_stock": int(new_data.get("min_stock") or 0),
                    "notes": new_data.get("notes", ""),
                    "expiration_date": new_data.get("expiration_date") or None,
                }
            )

            # Crear lote vinculado
            batch = Batch.objects.create(
                product=product,
                quantity=abs(qty),
                expiration_date=new_data.get("expiration_date") or None,
                notes=new_data.get("notes", "")
            )

            # Registrar movimiento vinculado al lote
            Movement.objects.create(
                product=product,
                location=location,
                quantity=abs(qty),
                movement_type="IN",
                metadata={"batch_id": batch.id, "entry_date": str(batch.entry_date)},
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

            product = Product.objects.filter(uuid=incoming_uuid).first()
            if not product:
                return Response({"detail": "Producto no encontrado"}, status=404)

            Movement.objects.create(
                product=product,
                location=location,
                quantity=-abs(qty),
                movement_type="OUT",
            )

            return Response({
                "ok": True,
                "payload": f"PRD:{product.uuid}",
            }, status=200)

        # -------------------------------------------------------
        # AUDITORÍA POR UBICACIÓN
        # -------------------------------------------------------
        elif mtype == "AUD":
            if not location:
                return Response({"detail": "Debes indicar una ubicación"}, status=400)

            products = Product.objects.filter(location=location)
            data = []

            for p in products:
                batches = list(p.batches.values("id", "quantity", "expiration_date").order_by("expiration_date"))
                total_qty = sum(b["quantity"] for b in batches)
                nearest_exp = min(
                    (b["expiration_date"] for b in batches if b["expiration_date"]),
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
                "location": location.full_path(),
                "total_products": len(data),
                "items": data,
            }, status=200)

        # -------------------------------------------------------
        # AUDITORÍA TOTAL (INVENTARIO COMPLETO)
        # -------------------------------------------------------
        elif mtype == "AUDTOTAL":
            all_locations = Location.objects.all().order_by("name")
            inventory = []

            for loc in all_locations:
                products = Product.objects.filter(location=loc)
                if not products.exists():
                    continue

                items = []
                for p in products:
                    batches = list(p.batches.values("id", "quantity", "expiration_date").order_by("expiration_date"))
                    total_qty = sum(b["quantity"] for b in batches)
                    nearest_exp = min(
                        (b["expiration_date"] for b in batches if b["expiration_date"]),
                        default=None
                    )
                    items.append({
                        "product": p.name,
                        "total_quantity": total_qty,
                        "nearest_expiration": nearest_exp,
                        "batches": batches,
                    })

                inventory.append({
                    "location": loc.full_path(),
                    "total_products": len(items),
                    "items": items,
                })

            return Response({
                "ok": True,
                "total_locations": len(inventory),
                "inventory": inventory,
            }, status=200)

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
