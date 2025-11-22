from urllib import request
import uuid
import traceback
from datetime import date, datetime, timedelta
from django.utils import timezone

from django.urls import path, include
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from django.db import transaction, models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.timezone import now

from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.filters import OrderingFilter, SearchFilter

from .utils import available_stock
from .models import Batch, Product, Location, Movement
from .serializers import ProductSerializer, LocationSerializer, MovementSerializer

# 👇 IMPORTAMOS LAS VISTAS DE UBICACIONES
from .locations_api import (
    LocationTreeView,
    LocationCreateView,
    LocationUpdateView,
    LocationDeleteView,
)

DEFAULT_TENANT = uuid.UUID(
    getattr(settings, "DEFAULT_TENANT", "00000000-0000-0000-0000-000000000001")
)


# -------------------------------------------------------------------
#  Aislamiento por tenant en ViewSets
# -------------------------------------------------------------------
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
#  BUSCADOR RÁPIDO
# -------------------------------------------------------------------
class ProductQuickSearch(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        if not q:
            return Response({"results": []})

        qs = (
            Product.objects.filter(
                tenant_id=DEFAULT_TENANT,
                name__icontains=q,
            )
            .select_related("location")
            .order_by("name")[:20]
        )

        data = []
        for p in qs:
            data.append(
                {
                    "id": str(p.id),
                    "name": p.name,
                    "sku": p.sku,
                    "payload": f"PRD:{p.id}",
                    "category": p.category,
                    "location": p.location.full_path() if p.location else None,
                }
            )

        return Response({"results": data})


# -------------------------------------------------------------------
#  ENDPOINT PRINCIPAL DE ESCANEO
# -------------------------------------------------------------------
@method_decorator(csrf_exempt, name="dispatch")
class ScanEndpoint(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            payload = (request.data.get("payload") or "").strip()

            # cantidad segura
            try:
                qty = int(request.data.get("quantity") or 1)
            except ValueError:
                return Response({"detail": "Cantidad inválida"}, status=400)

            # ID de ubicación (UUID) que llega desde el <select>
            loc_id_raw = (request.data.get("location") or "").strip()

            # Normalización del tipo (acepta español o código)
            mtype_raw = (
                (request.data.get("movement_type") or request.data.get("type") or "OUT")
                .strip()
                .upper()
            )

            TYPE_MAP = {
                "ENTRADA": "IN",
                "IN": "IN",
                "SALIDA": "OUT",
                "OUT": "OUT",
                "AUDITORIA": "AUD",
                "AUDITORÍA": "AUD",
                "AUD": "AUD",
                "AUDTOTAL": "AUDTOTAL",
                "TOTAL": "AUDTOTAL",
                "AJUSTE": "ADJ",
                "ADJ": "ADJ",
            }

            
            mtype = TYPE_MAP.get(mtype_raw, mtype_raw)
            # -------------------------------------------------------
            # Buscar ubicación (opcional) + queryset base
            # -------------------------------------------------------
            location = None
            location_qs = Location.objects.none()
            if loc_id_raw:
                try:
                    loc_uuid = uuid.UUID(loc_id_raw)
                except ValueError:
                    return Response(
                        {"detail": "Ubicación inválida"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # 👇 Buscar por public_id (UUID) en vez de por id
                location = Location.objects.filter(
                    public_id=loc_uuid,
                    tenant_id=DEFAULT_TENANT,
                ).first()
                if not location:
                    return Response(
                        {"detail": "Ubicación no encontrada"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Para auditorías seguimos usando id interno
                location_qs = Location.objects.filter(
                    id=location.id,
                    tenant_id=DEFAULT_TENANT,
                )


            # Helper: extraer UUID del payload "PRD:<uuid>"
            def parse_uuid_from_payload(p):
                if not p.startswith("PRD:"):
                    return None
                return p.split(":", 1)[1].strip()

            incoming_uuid = parse_uuid_from_payload(payload)

            mark_open = bool(request.data.get("mark_open"))
            open_days = request.data.get("open_days")
            try:
                open_days = int(open_days) if open_days not in ("", None) else None
            except ValueError:
                open_days = None


            # -------------------------------------------------------
            # ENTRADA
            # -------------------------------------------------------
            if mtype == "IN":
                new_data = request.data.get("new_product", {}) or {}
                name = new_data.get("name", "").strip()
                unit = new_data.get("unit", "").strip()
                category = new_data.get("category", "").strip()

                if not name:
                    return Response(
                        {"detail": "El nombre del producto es obligatorio"}, status=400
                    )
                if not unit:
                    return Response(
                        {"detail": "La unidad es obligatoria"}, status=400
                    )

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

                loc_final = location or product.location
                if not loc_final:
                    return Response(
                        {
                            "detail": "Debe indicar una ubicación o el producto debe tener una ubicación asignada."
                        },
                        status=400,
                    )

                Movement.objects.create(
                    product=product,
                    location=loc_final,
                    quantity=abs(qty),
                    movement_type="IN",
                    metadata={"batch_id": batch.id, "entry_date": str(batch.entry_date)},
                    tenant_id=DEFAULT_TENANT,
                )

                payload_str = f"PRD:{product.id}"
                if not getattr(product, "qr_payload", None):
                    product.qr_payload = payload_str
                    product.save(update_fields=["qr_payload"])

                return Response(
                    {
                        "ok": True,
                        "payload": payload_str,
                        "detail": f"Entrada registrada (lote {batch.id})",
                    }
                )

            # -------------------------------------------------------
            # SALIDA
            # -------------------------------------------------------
            elif mtype == "OUT":

                # ---------------------------------------------------
                # PRIORIDAD: si existe una unidad abierta → consumirla primero
                # ---------------------------------------------------
                opened_batch = Batch.objects.filter(
                    product_id=incoming_uuid,
                    tenant_id=DEFAULT_TENANT,
                    opened_units__gt=0,
                    quantity__gt=0,
                    is_depleted=False,
                ).order_by("open_expires_at", "entry_date").first()

                if opened_batch:
                    # Si el usuario intenta abrir otra → error
                    if mark_open:
                        return Response(
                            {"detail": "Este producto ya tiene una unidad abierta. Debes consumirla primero."},
                            status=400,
                        )

                    # Consumir SOLO 1 unidad del lote abierto
                    prev_qty = opened_batch.quantity
                    opened_batch.quantity = prev_qty - 1
                    if opened_batch.quantity == 0:
                        opened_batch.is_depleted = True
                        opened_batch.depleted_at = now()

                    # Cerrar la unidad abierta tras consumirla
                    opened_batch.opened_units = 0
                    opened_batch.opened_at = None
                    opened_batch.open_expires_at = None

                    opened_batch.save(update_fields=[
                        "quantity", "is_depleted", "depleted_at",
                        "opened_units", "opened_at", "open_expires_at"
                    ])

                    # Registrar movimiento
                    loc_final = location or opened_batch.product.location
                    Movement.objects.create(
                        product=opened_batch.product,
                        location=loc_final,
                        quantity=-1,
                        movement_type="OUT",
                        metadata={"opened_batch": opened_batch.id},
                        tenant_id=DEFAULT_TENANT,
                    )

                    return Response({
                        "ok": True,
                        "detail": "Salida registrada consumiendo la unidad abierta.",
                        "batch_id": opened_batch.id,
                        "remaining_qty": int(opened_batch.quantity),
                    })


                # ---------------------------------------------------
                # 1) Si el usuario ha marcado “abrir”
                # ---------------------------------------------------
                if mark_open:
                    # Localizar el lote más cercano a caducar
                    batch = Batch.objects.filter(
                        product_id=incoming_uuid,
                        tenant_id=DEFAULT_TENANT,
                        is_depleted=False,
                        quantity__gt=0,
                    ).order_by("expiration_date", "entry_date").first()

                    if not batch:
                        return Response({"detail": "No hay stock para abrir."}, status=400)

                    # Si ya tiene una unidad abierta → error
                    if batch.opened_units > 0:
                        return Response(
                            {"detail": "Este lote ya tiene una unidad abierta. Debes consumirla primero."},
                            status=400,
                        )

                    # Calcular caducidad tras abrir
                    if open_days:
                        open_expires_at = timezone.now() + timezone.timedelta(days=open_days)
                    else:
                        open_expires_at = None

                    # Marcar como abierto
                    batch.opened_units = 1
                    batch.opened_at = timezone.now()
                    batch.open_expires_at = open_expires_at
                    batch.save()

                    return Response({
                        "ok": True,
                        "action": "OPENED",
                        "detail": "Unidad marcada como abierta",
                        "batch_id": batch.id,
                        "open_expires_at": open_expires_at,
                    })
                
                # ---------------------------------------------------
                # 2B) Si existe una unidad abierta → consumirla primero
                # ---------------------------------------------------
                open_batch = Batch.objects.filter(
                    product_id=incoming_uuid,
                    tenant_id=DEFAULT_TENANT,
                    opened_units__gt=0,
                    is_depleted=False,
                ).order_by("expiration_date", "entry_date").first()

                if open_batch:
                    # Consumir UNA unidad de la unidad abierta
                    open_batch.opened_units = 0
                    open_batch.opened_at = None
                    open_batch.open_expires_at = None

                    # También restamos 1 unidad del lote
                    if open_batch.quantity > 0:
                        open_batch.quantity -= 1
                        if open_batch.quantity == 0:
                            open_batch.is_depleted = True
                            open_batch.depleted_at = now()

                    open_batch.save()

                    # Registrar movimiento
                    loc_final = location or open_batch.product.location
                    Movement.objects.create(
                        product=open_batch.product,
                        location=loc_final,
                        quantity=-1,
                        movement_type="OUT",
                        metadata={"opened_batch_consumed": open_batch.id},
                        tenant_id=DEFAULT_TENANT,
                    )

                    stock_remaining = Batch.objects.filter(
                        product=open_batch.product, tenant_id=DEFAULT_TENANT
                    ).aggregate(t=Coalesce(Sum("quantity"), 0))["t"] or 0

                    return Response(
                        {
                            "ok": True,
                            "detail": "Unidad abierta consumida",
                            "batch_id": open_batch.id,
                            "requested": 1,
                            "stock_remaining": int(stock_remaining),
                            "payload": open_batch.product.qr_payload,
                        },
                        status=200,
                    )


                # ---------------------------------------------------
                # 2) Si NO se marcó “abrir” → continuar flujo usual
                # ---------------------------------------------------


                if not incoming_uuid:
                    return Response(
                        {"detail": "Payload inválido (se espera PRD:<uuid>)"}, status=400
                    )

                product = Product.objects.filter(
                    id=incoming_uuid, tenant_id=DEFAULT_TENANT
                ).first()
                if not product:
                    return Response(
                        {"detail": "Producto no encontrado"}, status=404
                    )

                need = abs(qty)

                batch_total = Batch.objects.filter(
                    product=product, tenant_id=DEFAULT_TENANT
                ).aggregate(t=Coalesce(Sum("quantity"), 0))["t"] or 0

                if need > int(batch_total):
                    return Response(
                        {
                            "ok": False,
                            "error": "insufficient_stock",
                            "detail": f"Stock insuficiente: disponible {int(batch_total)}, solicitado {need}",
                            "available": int(batch_total),
                            "requested": need,
                        },
                        status=400,
                    )

                consumed = []
                with transaction.atomic():
                    fifo_batches = (
                        Batch.objects.select_for_update()
                        .filter(
                            product=product,
                            tenant_id=DEFAULT_TENANT,
                            quantity__gt=0,
                        )
                        .order_by(
                            models.F("expiration_date").asc(nulls_last=True),
                            "entry_date",
                            "id",
                        )
                    )

                    remaining = need
                    for b in fifo_batches:
                        if remaining <= 0:
                            break

                        prev_qty = int(b.quantity)
                        take = min(prev_qty, remaining)
                        if take <= 0:
                            continue

                        b.quantity = prev_qty - take
                        if b.quantity == 0 and not b.is_depleted:
                            b.is_depleted = True
                            b.depleted_at = now()
                        b.save(
                            update_fields=["quantity", "is_depleted", "depleted_at"]
                        )

                        consumed.append(
                            {
                                "batch_id": b.id,
                                "prev_qty": prev_qty,
                                "taken": take,
                                "new_qty": int(b.quantity),
                                "expiration_date": (
                                    b.expiration_date.isoformat()
                                    if getattr(b, "expiration_date", None)
                                    else None
                                ),
                            }
                        )

                        remaining -= take

                    if remaining > 0:
                        return Response(
                            {
                                "ok": False,
                                "error": "concurrency_race",
                                "detail": "El stock cambió durante la operación. Intenta de nuevo.",
                            },
                            status=409,
                        )

                    loc_final = location or product.location
                    if not loc_final:
                        return Response(
                            {
                                "detail": "Debe indicar una ubicación o el producto debe tener una ubicación asignada."
                            },
                            status=400,
                        )

                    Movement.objects.create(
                        product=product,
                        location=loc_final,
                        quantity=-need,
                        movement_type="OUT",
                        metadata={"consumed_batches": consumed},
                        tenant_id=DEFAULT_TENANT,
                    )

                stock_remaining = Batch.objects.filter(
                    product=product, tenant_id=DEFAULT_TENANT
                ).aggregate(t=Coalesce(Sum("quantity"), 0))["t"] or 0

                return Response(
                    {
                        "ok": True,
                        "product": {
                            "id": str(product.id),
                            "name": product.name,
                            "location": product.location.full_path()
                            if product.location
                            else None,
                        },
                        "requested": need,
                        "stock_remaining": int(stock_remaining),
                        "consumed_batches": consumed,
                        "payload": product.qr_payload,
                        "detail": "Salida registrada correctamente",
                    },
                    status=200,
                )

            # -------------------------------------------------------
            # AUDITORÍA POR UBICACIÓN
            # -------------------------------------------------------
            elif mtype == "AUD":
                if not location:
                    return Response(
                        {"detail": "Debes indicar una ubicación"}, status=400
                    )

                products = (
                    Product.objects.filter(
                        location__in=location_qs, tenant_id=DEFAULT_TENANT
                    )
                    .select_related("location")
                    .prefetch_related("batches")
                )

                data = []
                for p in products:
                    # Recuperamos TODOS los campos que el frontend necesita
                    all_batches = list(
                        p.batches.values(
                            "id",
                            "quantity",
                            "expiration_date",
                            "opened_units",
                            "opened_at",
                            "open_expires_at",
                        ).order_by("expiration_date")
                    )

                    # Solo lotes con cantidad > 0
                    non_empty_batches = [
                        b for b in all_batches if int(b.get("quantity") or 0) > 0
                    ]

                    total_qty = sum(
                        int(b["quantity"]) for b in non_empty_batches
                    )

                    nearest_exp = min(
                        (
                            b["expiration_date"]
                            for b in non_empty_batches
                            if b.get("expiration_date")
                        ),
                        default=None,
                    )

                    data.append(
                        {
                            "product": p.name,
                            "total_quantity": total_qty,
                            "nearest_expiration": nearest_exp,
                            # Mandamos los lotes tal cual los hemos calculado
                            "batches": non_empty_batches,
                        }
                    )

                return Response(
                    {
                        "ok": True,
                        "location": location.full_path()
                        if hasattr(location, "full_path")
                        else location.name,
                        "total_products": len(data),
                        "items": data,
                    },
                    status=200,
                )



            # -------------------------------------------------------
            # AUDITORÍA TOTAL (INVENTARIO COMPLETO)
            # -------------------------------------------------------
            elif mtype == "AUDTOTAL":
                all_locations = Location.objects.filter(
                    tenant_id=DEFAULT_TENANT
                ).order_by("name")
                inventory = []

                for loc in all_locations:
                    products = (
                        Product.objects.filter(location=loc, tenant_id=DEFAULT_TENANT)
                        .select_related("location")
                        .prefetch_related("batches")
                    )
                    if not products.exists():
                        continue

                    items = []
                    for p in products:
                        all_batches = list(
                            p.batches.values(
                                "id",
                                "quantity",
                                "expiration_date",
                                "opened_units",
                                "opened_at",
                                "open_expires_at",
                            ).order_by("expiration_date")
                        )

                        non_empty_batches = [
                            b for b in all_batches if int(b.get("quantity") or 0) > 0
                        ]

                        total_qty = sum(int(b["quantity"]) for b in non_empty_batches)

                        nearest_exp = min(
                            (
                                b["expiration_date"]
                                for b in non_empty_batches
                                if b.get("expiration_date")
                            ),
                            default=None,
                        )

                        items.append(
                            {
                                "product": p.name,
                                "total_quantity": total_qty,
                                "nearest_expiration": nearest_exp,
                                "batches": non_empty_batches,
                            }
                        )

                    inventory.append(
                        {
                            "location": loc.full_path()
                            if hasattr(loc, "full_path")
                            else loc.name,
                            "total_products": len(items),
                            "items": items,
                        }
                    )

                return Response(
                    {"ok": True, "total_locations": len(inventory), "inventory": inventory},
                    status=200,
                )

            # -------------------------------------------------------
            # ERROR
            # -------------------------------------------------------
            else:
                return Response(
                    {"detail": f"Tipo de movimiento no soportado: {mtype}"}, status=400
                )

        except Exception as e:
            tb = traceback.format_exc()
            traceback.print_exc()
            return Response(
                {"detail": "server_error", "error": str(e), "trace": tb}, status=500
            )


# -------------------------------------------------------------------
#  URLS DEL MÓDULO API
# -------------------------------------------------------------------
urlpatterns = [
    # --- Gestión de ubicaciones (árbol) ---
    path("locations/tree/", LocationTreeView.as_view()),
    path("locations/create/", LocationCreateView.as_view()),
    path("locations/update/<int:loc_id>/", LocationUpdateView.as_view()),
    path("locations/delete/<int:loc_id>/", LocationDeleteView.as_view()),

    # --- Scan y buscador rápido ---
    path("scan/", ScanEndpoint.as_view()),
    path("products/search/", ProductQuickSearch.as_view()),

    # --- Resto de endpoints REST estándar ---
    path("", include(router.urls)),
]