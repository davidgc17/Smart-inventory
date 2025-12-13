import uuid
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
from rest_framework.permissions import IsAuthenticated

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


def get_tenant_from_request(request):
    """
    Devuelve el tenant a usar en función del usuario.
    - Si el usuario está autenticado y tiene Organization → su UUID.
    - Si no, usa DEFAULT_TENANT como fallback.
    """
    if request is None:
        return DEFAULT_TENANT

    user = getattr(request, "user", None)
    if user and user.is_authenticated and hasattr(user, "organization"):
        return user.organization.id
    return DEFAULT_TENANT


# -------------------------------------------------------------------
#  Aislamiento por tenant en ViewSets
# -------------------------------------------------------------------
class TenantScopedMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        request = getattr(self, "request", None)
        tenant_id = get_tenant_from_request(request)
        return qs.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        request = getattr(self, "request", None)
        tenant_id = get_tenant_from_request(request)
        serializer.save(tenant_id=tenant_id)


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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        if not q:
            return Response({"results": []})

        tenant_id = get_tenant_from_request(request)

        qs = (
            Product.objects.filter(
                tenant_id=tenant_id,
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
    permission_classes = [IsAuthenticated]

    # Mapeo centralizado de tipos de movimiento
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

    # -------------------------
    # Helpers comunes
    # -------------------------
    def _parse_common(self, request):
        data = request.data or {}

        payload = (data.get("payload") or "").strip()

        raw_qty = data.get("quantity") or 1
        try:
            qty = int(raw_qty)
        except (TypeError, ValueError):
            # Lanzamos ValueError genérico que se captura en post()
            raise ValueError("La cantidad debe ser un número entero válido.")

        loc_id_raw = (data.get("location") or "").strip()

        mtype_raw = (
            (data.get("movement_type") or data.get("type") or "OUT")
            .strip()
            .upper()
        )
        mtype = self.TYPE_MAP.get(mtype_raw, mtype_raw)

        mark_open = bool(data.get("mark_open"))
        open_days = data.get("open_days")
        try:
            open_days = int(open_days) if open_days not in ("", None) else None
        except (TypeError, ValueError):
            open_days = None

        return payload, qty, loc_id_raw, mtype, mark_open, open_days

    def _parse_uuid_from_payload(self, payload: str):
        """
        Extrae el UUID de un payload tipo 'PRD:<uuid>'. Si no es válido, devuelve None.
        """
        if not payload or not isinstance(payload, str):
            return None
        if not payload.startswith("PRD:"):
            return None
        return payload.split(":", 1)[1].strip()

    def _error(self, code, detail, status_code=status.HTTP_400_BAD_REQUEST, meta=None):
        """
        Formato uniforme de error, compatible con el frontend actual.
        """
        meta = meta or {}
        data = {
            "ok": False,
            "error": code,
            "detail": detail,
        }
        if meta:
            data["meta"] = meta
            # Compatibilidad con data.available / data.requested
            for key in ("available", "requested"):
                if key in meta:
                    data[key] = meta[key]
        return Response(data, status=status_code)

    # -------------------------
    # Handlers por tipo
    # -------------------------
    def _handle_in(self, request, payload, qty, location, tenant_id):
        """
        Lógica de ENTRADA (IN).

        Regla acordada:
        - Si hay PRD válido → usar Product existente.
        - Si NO hay PRD válido → crear/reutilizar Product usando new_product.
        """
        incoming_uuid = self._parse_uuid_from_payload(payload)
        new_data = request.data.get("new_product", {}) or {}

        if qty is None or qty <= 0:
            return self._error(
                "invalid_quantity",
                "La cantidad debe ser un entero positivo para una entrada.",
            )

        # Campos comunes de lote
        expiration_date = new_data.get("expiration_date") or None
        notes = new_data.get("notes", "")

        # === Caso 1: IN con PRD (producto existente) ===
        if incoming_uuid:
            product = Product.objects.filter(
                id=incoming_uuid,
                tenant_id=tenant_id,
            ).first()
            if not product:
                return self._error(
                    "product_not_found",
                    "Producto no encontrado para el payload indicado.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

            loc_final = location or product.location
            if not loc_final:
                return self._error(
                    "location_required",
                    "Debe indicar una ubicación o el producto debe tener una ubicación asignada.",
                )

            batch = Batch.objects.create(
                product=product,
                quantity=abs(qty),
                expiration_date=expiration_date,
                tenant_id=tenant_id,

                # --- Metadatos específicos del lote ---
                brand=new_data.get("brand"),
                origin=new_data.get("origin"),
                primary_color=new_data.get("primary_color"),
                dimensions=new_data.get("dimensions"),
                estimated_value=new_data.get("estimated_value") or None,
                notes=new_data.get("notes"),
            )

            Movement.objects.create(
                product=product,
                location=loc_final,
                quantity=abs(qty),
                movement_type="IN",
                metadata={"batch_id": batch.id, "entry_date": str(batch.entry_date)},
                tenant_id=tenant_id,
            )

            payload_str = product.qr_payload or f"PRD:{product.id}"
            if not product.qr_payload:
                product.qr_payload = payload_str
                product.save(update_fields=["qr_payload"])

            return Response(
                {
                    "ok": True,
                    "payload": payload_str,
                    "detail": f"Entrada registrada (lote {batch.id})",
                }
            )

        # === Caso 2: IN sin PRD válido → alta o reutilización de Product ===
        name = new_data.get("name", "").strip()
        unit = new_data.get("unit", "").strip()
        category = new_data.get("category", "").strip()

        if not name:
            return self._error(
                "invalid_payload",
                "El nombre del producto es obligatorio para crear una nueva entrada sin PRD.",
            )
        if not unit:
            return self._error(
                "invalid_payload",
                "La unidad es obligatoria para crear una nueva entrada sin PRD.",
            )

        if location is None:
            return self._error(
                "location_required",
                "Debes seleccionar una ubicación para crear un producto nuevo.",
            )

        product, created = Product.objects.get_or_create(
            name=name,
            location=location,
            tenant_id=tenant_id,
            defaults={
                "category": category,
                "unit": unit,
                "min_stock": int(new_data.get("min_stock") or 0),
            },
        )

        batch = Batch.objects.create(
            product=product,
            quantity=abs(qty),
            expiration_date=expiration_date,
            notes=notes,
            tenant_id=tenant_id,
        )

        loc_final = location or product.location
        if not loc_final:
            return self._error(
                "location_required",
                "Debe indicar una ubicación o el producto debe tener una ubicación asignada.",
            )

        Movement.objects.create(
            product=product,
            location=loc_final,
            quantity=abs(qty),
            movement_type="IN",
            metadata={"batch_id": batch.id, "entry_date": str(batch.entry_date)},
            tenant_id=tenant_id,
        )

        payload_str = product.qr_payload or f"PRD:{product.id}"
        if not product.qr_payload:
            product.qr_payload = payload_str
            product.save(update_fields=["qr_payload"])

        return Response(
            {
                "ok": True,
                "payload": payload_str,
                "detail": f"Entrada registrada (lote {batch.id})",
            }
        )

    def _handle_out(self, request, payload, qty, location, mark_open, open_days, tenant_id):
        """
        Lógica de SALIDA (OUT), organizada en fases:
        - consumo de unidad abierta
        - mark_open
        - FIFO estándar
        """
        incoming_uuid = self._parse_uuid_from_payload(payload)
        if not payload or not str(payload).startswith("PRD:"):
            return self._error(
                "missing_prd",
                "Debes seleccionar o escanear un producto para realizar una salida.",
            )

        if not incoming_uuid:
            return self._error(
                "invalid_payload",
                "El formato del producto es inválido (se espera PRD:<uuid>).",
            )

        if qty is None or qty <= 0:
            return self._error(
                "invalid_quantity",
                "La cantidad debe ser un entero positivo para una salida.",
            )

        # Regla acordada: si mark_open → qty debe ser 1
        if mark_open and abs(qty) != 1:
            return self._error(
                "invalid_mark_open",
                "Para marcar como abierto solo se permite cantidad = 1.",
            )

        if mark_open and open_days is not None and open_days <= 0:
            return self._error(
                "invalid_open_days",
                "Los días tras abrir deben ser un entero positivo.",
            )

        # ---------------------------------------------------
        # 1) Si existe una unidad abierta → consumirla primero
        # ---------------------------------------------------
        opened_batch = Batch.objects.filter(
            product_id=incoming_uuid,
            tenant_id=tenant_id,
            opened_units__gt=0,
            quantity__gt=0,
            is_depleted=False,
        ).order_by("open_expires_at", "entry_date").first()

        if opened_batch:
            if mark_open:
                return self._error(
                    "already_open",
                    "Este producto ya tiene una unidad abierta. Debes consumirla primero.",
                )

            prev_qty = opened_batch.quantity
            opened_batch.quantity = prev_qty - 1
            if opened_batch.quantity == 0:
                opened_batch.is_depleted = True
                opened_batch.depleted_at = now()

            opened_batch.opened_units = 0
            opened_batch.opened_at = None
            opened_batch.open_expires_at = None

            opened_batch.save(
                update_fields=[
                    "quantity",
                    "is_depleted",
                    "depleted_at",
                    "opened_units",
                    "opened_at",
                    "open_expires_at",
                ]
            )

            loc_final = location or opened_batch.product.location
            if not loc_final:
                return self._error(
                    "location_required",
                    "Debe indicar una ubicación o el producto debe tener una ubicación asignada.",
                )

            Movement.objects.create(
                product=opened_batch.product,
                location=loc_final,
                quantity=-1,
                movement_type="OUT",
                metadata={"opened_batch": opened_batch.id},
                tenant_id=tenant_id,
            )

            return Response(
                {
                    "ok": True,
                    "detail": "Salida registrada consumiendo la unidad abierta.",
                    "batch_id": opened_batch.id,
                    "remaining_qty": int(opened_batch.quantity),
                }
            )

        # ---------------------------------------------------
        # 2) mark_open = True → abrir lote más cercano
        # ---------------------------------------------------
        if mark_open:
            batch = Batch.objects.filter(
                product_id=incoming_uuid,
                tenant_id=tenant_id,
                is_depleted=False,
                quantity__gt=0,
            ).order_by("expiration_date", "entry_date").first()

            if not batch:
                return self._error("no_stock", "No hay stock para abrir.")

            if batch.opened_units > 0:
                return self._error(
                    "already_open",
                    "Este lote ya tiene una unidad abierta. Debes consumirla primero.",
                )

            if open_days:
                open_expires_at = timezone.now() + timezone.timedelta(days=open_days)
            else:
                open_expires_at = None

            batch.opened_units = 1
            batch.opened_at = timezone.now()
            batch.open_expires_at = open_expires_at
            batch.save()

            return Response(
                {
                    "ok": True,
                    "action": "OPENED",
                    "detail": "Unidad marcada como abierta",
                    "batch_id": batch.id,
                    "open_expires_at": open_expires_at,
                }
            )

        # ---------------------------------------------------
        # 3) Flujo FIFO estándar (sin marcar como abierto)
        # ---------------------------------------------------
        product = Product.objects.filter(
            id=incoming_uuid,
            tenant_id=tenant_id,
        ).first()
        if not product:
            return self._error(
                "product_not_found",
                "Producto no encontrado.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        need = abs(qty)

        batch_total = (
            Batch.objects.filter(product=product, tenant_id=tenant_id).aggregate(
                t=Coalesce(Sum("quantity"), 0)
            )["t"]
            or 0
        )

        if need > int(batch_total):
            return self._error(
                "insufficient_stock",
                f"Stock insuficiente: disponible {int(batch_total)}, solicitado {need}",
                status_code=status.HTTP_400_BAD_REQUEST,
                meta={"available": int(batch_total), "requested": need},
            )

        consumed = []
        with transaction.atomic():
            fifo_batches = (
                Batch.objects.select_for_update()
                .filter(
                    product=product,
                    tenant_id=tenant_id,
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
                b.save(update_fields=["quantity", "is_depleted", "depleted_at"])

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
                return self._error(
                    "concurrency_race",
                    "El stock cambió durante la operación. Intenta de nuevo.",
                    status_code=status.HTTP_409_CONFLICT,
                )

            loc_final = location or product.location
            if not loc_final:
                return self._error(
                    "location_required",
                    "Debe indicar una ubicación o el producto debe tener una ubicación asignada.",
                )

            Movement.objects.create(
                product=product,
                location=loc_final,
                quantity=-need,
                movement_type="OUT",
                metadata={"consumed_batches": consumed},
                tenant_id=tenant_id,
            )

        stock_remaining = (
            Batch.objects.filter(product=product, tenant_id=tenant_id).aggregate(
                t=Coalesce(Sum("quantity"), 0)
            )["t"]
            or 0
        )

        remaining_qs = Batch.objects.filter(
            product=product,
            tenant_id=tenant_id,
            quantity__gt=0,
        ).exclude(expiration_date__isnull=True).order_by("expiration_date")

        exp_dates = list(remaining_qs.values_list("expiration_date", flat=True))
        if exp_dates:
            nearest = exp_dates[0]
            farthest = exp_dates[-1]
        else:
            nearest = None
            farthest = None

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
                "nearest_expiration": nearest.isoformat() if nearest else None,
                "farthest_expiration": farthest.isoformat() if farthest else None,
            },
            status=200,
        )

    def _handle_aud(self, request, location, tenant_id):
        # --- Lectura de filtros opcionales ---
        data_in = request.data or {}
        filters = data_in.get("audit_filters") or {}

        def _s(key):
            v = filters.get(key)
            return (v or "").strip()

        f_name = _s("name")
        f_category = _s("category")
        f_brand = _s("brand")
        f_origin = _s("origin")
        f_color = _s("primary_color")
        f_dimensions = _s("dimensions")

        # --- Regla v0.1: al menos un criterio ---
        has_any_filter = any(
            [location, f_name, f_category, f_brand, f_origin, f_color, f_dimensions]
        )

        if not has_any_filter:
            return self._error(
                "audit_filter_required",
                "Debes indicar una ubicación o al menos un filtro de búsqueda.",
            )

        # --- Base queryset (siempre tenant-scoped) ---
        products = (
            Product.objects.filter(tenant_id=tenant_id)
            .select_related("location")
            .prefetch_related("batches")
        )

        # --- Filtro por ubicación (si existe) ---
        if location:
            descendant_locations = location.descendants_qs(include_self=True)
            products = products.filter(location__in=descendant_locations)

        # --- Filtros combinables (AND) ---
        if f_name:
            products = products.filter(name__icontains=f_name)
        if f_category:
            products = products.filter(category__icontains=f_category)
        if f_brand:
            products = products.filter(brand__icontains=f_brand)
        if f_origin:
            products = products.filter(origin__icontains=f_origin)
        if f_color:
            products = products.filter(primary_color__icontains=f_color)
        if f_dimensions:
            products = products.filter(dimensions__icontains=f_dimensions)

        data = []

        for p in products:
            # --- Lotes (LO QUE YA TENÍAS) ---
            all_batches = list(
                p.batches.values(
                    "id",
                    "quantity",
                    "expiration_date",
                    "opened_units",
                    "opened_at",
                    "open_expires_at",

                    # 🔽 metadatos por LOTE
                    "brand",
                    "origin",
                    "primary_color",
                    "dimensions",
                    "estimated_value",
                    "notes",
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

            # --- Respuesta ampliada ---
            data.append(
                {
                    # Producto (info completa)
                    "id": str(p.id),
                    "sku": p.sku,
                    "product": p.name,
                    "name": p.name,
                    "category": p.category,
                    "unit": p.unit,
                    "min_stock": int(p.min_stock or 0),
                    "notes": p.notes or "",
                    "expiration_date": p.expiration_date.isoformat()
                    if p.expiration_date
                    else None,

                    "brand": p.brand,
                    "origin": p.origin,
                    "primary_color": p.primary_color,
                    "dimensions": p.dimensions,
                    "estimated_value": float(p.estimated_value)
                    if p.estimated_value is not None
                    else None,

                    "location": p.location.full_path()
                    if hasattr(p.location, "full_path")
                    else p.location.name,

                    # Stock / lotes (sin tocar lógica)
                    "total_quantity": total_qty,
                    "nearest_expiration": nearest_exp,
                    "batches": non_empty_batches,
                }
            )

        return Response(
            {
                "ok": True,
                "location": location.full_path()
                if location and hasattr(location, "full_path")
                else location.name if location else None,
                "filters": {
                    "name": f_name or None,
                    "category": f_category or None,
                    "brand": f_brand or None,
                    "origin": f_origin or None,
                    "primary_color": f_color or None,
                    "dimensions": f_dimensions or None,
                },
                "total_products": len(data),
                "items": data,
            },
            status=200,
        )


    def _handle_audtotal(self, request, tenant_id):
        all_locations = Location.objects.filter(
            tenant_id=tenant_id
        ).order_by("name")
        inventory = []

        for loc in all_locations:
            products = (
                Product.objects.filter(location=loc, tenant_id=tenant_id)
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

    # -------------------------
    # POST principal (router)
    # -------------------------
    def post(self, request):
        try:
            tenant_id = get_tenant_from_request(request)

            try:
                (
                    payload,
                    qty,
                    loc_id_raw,
                    mtype,
                    mark_open,
                    open_days,
                ) = self._parse_common(request)
            except ValueError as e:
                # No exponemos mensajes internos; usamos texto genérico
                return self._error(
                    "invalid_quantity",
                    "La cantidad debe ser un número entero válido.",
                )

            # Ubicación (opcional)
            location = None
            if loc_id_raw:
                try:
                    loc_uuid = uuid.UUID(loc_id_raw)
                except ValueError:
                    return self._error(
                        "invalid_location",
                        "Ubicación inválida.",
                    )

                location = Location.objects.filter(
                    public_id=loc_uuid,
                    tenant_id=tenant_id,
                ).first()
                if not location:
                    return self._error(
                        "location_not_found",
                        "Ubicación no encontrada.",
                        status_code=status.HTTP_404_NOT_FOUND,
                    )

            # Enrutado por tipo
            if mtype == "IN":
                return self._handle_in(request, payload, qty, location, tenant_id)

            if mtype == "OUT":
                return self._handle_out(
                    request,
                    payload,
                    qty,
                    location,
                    mark_open,
                    open_days,
                    tenant_id,
                )

            if mtype == "AUD":
                return self._handle_aud(request, location, tenant_id)

            if mtype == "AUDTOTAL":
                return self._handle_audtotal(request, tenant_id)

            return self._error(
                "unknown_type",
                f"Tipo de movimiento no soportado: {mtype}",
            )

        except Exception:
            # Hardening de seguridad:
            # - No devolvemos trazas ni nombres de excepciones al cliente.
            # - Mensaje genérico para el usuario.
            return Response(
                {
                    "ok": False,
                    "error": "server_error",
                    "detail": "Ha ocurrido un error interno. Inténtalo de nuevo más tarde.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
