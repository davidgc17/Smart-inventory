from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import Location, Product, Batch, Movement
import uuid

DEFAULT_TENANT = uuid.UUID(
    getattr(settings, "DEFAULT_TENANT", "00000000-0000-0000-0000-000000000001")
)


def get_tenant_from_request(request):
    """
    Devuelve el tenant según el usuario autenticado.
    Si no está autenticado o no tiene Organization, usa DEFAULT_TENANT.
    """
    user = getattr(request, "user", None)
    if user and user.is_authenticated and hasattr(user, "organization"):
        return user.organization.id
    return DEFAULT_TENANT


class LocationTreeView(APIView):
    """
    GET /api/locations/tree/
    Devuelve el árbol completo de ubicaciones del tenant.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant_id = get_tenant_from_request(request)

        qs = (
            Location.objects.filter(tenant_id=tenant_id)
            .select_related("parent")
            .order_by("name")
        )

        nodes = {}
        roots = []

        for loc in qs:
            nodes[loc.id] = {
                "id": str(loc.id),
                "name": loc.name,
                "path": loc.full_path() if hasattr(loc, "full_path") else loc.name,
                "parent_id": str(loc.parent_id) if loc.parent_id else None,
                "children": [],
            }

        for loc in qs:
            node = nodes[loc.id]
            if loc.parent_id and loc.parent_id in nodes:
                nodes[loc.parent_id]["children"].append(node)
            else:
                roots.append(node)

        return Response({"ok": True, "tree": roots}, status=status.HTTP_200_OK)


class LocationCreateView(APIView):
    """
    POST /api/locations/create/
    body: { "name": "...", "parent_id": "uuid" | null }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant_id = get_tenant_from_request(request)

        name = (request.data.get("name") or "").strip()
        parent_id = request.data.get("parent_id")

        if not name:
            return Response(
                {"ok": False, "detail": "El nombre es obligatorio"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent = None
        if parent_id:
            parent = get_object_or_404(
                Location,
                id=parent_id,
                tenant_id=tenant_id,
            )

        # 🔒 Unicidad de nombre dentro del mismo padre
        exists = Location.objects.filter(
            tenant_id=tenant_id,
            parent=parent,
            name__iexact=name,
        ).exists()

        if exists:
            return Response(
                {
                    "ok": False,
                    "error": "duplicate_name",
                    "detail": "Ya existe una ubicación con ese nombre en este nivel.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        loc = Location.objects.create(
            name=name,
            parent=parent,
            tenant_id=tenant_id,
        )

        return Response(
            {
                "ok": True,
                "id": str(loc.id),
                "name": loc.name,
                "path": loc.full_path() if hasattr(loc, "full_path") else loc.name,
            },
            status=status.HTTP_201_CREATED,
        )


class LocationUpdateView(APIView):
    """
    POST /api/locations/update/<uuid:loc_id>/
    body: { "name"?: "...", "parent_id"?: "uuid" }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, loc_id):
        tenant_id = get_tenant_from_request(request)

        loc = get_object_or_404(
            Location,
            id=loc_id,
            tenant_id=tenant_id,
        )

        new_name_raw = request.data.get("name")
        new_parent_id = request.data.get("parent_id")

        # Nombre propuesto (puede ser el actual si no se envía nombre nuevo)
        proposed_name = loc.name
        if new_name_raw is not None and new_name_raw.strip():
            proposed_name = new_name_raw.strip()

        # Padre propuesto (por defecto el actual)
        target_parent = loc.parent

        if new_parent_id is not None:
            if new_parent_id == "":
                # Mover a raíz
                target_parent = None
            else:
                parent = get_object_or_404(
                    Location,
                    id=new_parent_id,
                    tenant_id=tenant_id,
                )

                # Evitar ciclos
                if parent.id == loc.id:
                    return Response(
                        {"ok": False, "detail": "No puedes ser tu propio padre"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                ancestor = parent
                while ancestor is not None:
                    if ancestor.id == loc.id:
                        return Response(
                            {
                                "ok": False,
                                "detail": "No puedes mover la ubicación bajo uno de sus descendientes",
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    ancestor = ancestor.parent

                target_parent = parent

        # 🔒 Unicidad de nombre dentro del padre de destino
        if Location.objects.filter(
            tenant_id=tenant_id,
            parent=target_parent,
            name__iexact=proposed_name,
        ).exclude(id=loc.id).exists():
            return Response(
                {
                    "ok": False,
                    "error": "duplicate_name",
                    "detail": "Ya existe otra ubicación con ese nombre en este nivel.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Aplicar cambios
        loc.name = proposed_name
        loc.parent = target_parent
        loc.save()

        return Response(
            {
                "ok": True,
                "id": str(loc.id),
                "name": loc.name,
                "path": loc.full_path() if hasattr(loc, "full_path") else loc.name,
            },
            status=status.HTTP_200_OK,
        )


class LocationDeleteView(APIView):
    """
    POST /api/locations/delete/<uuid:loc_id>/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, loc_id):
        tenant_id = get_tenant_from_request(request)

        loc = get_object_or_404(
            Location,
            id=loc_id,
            tenant_id=tenant_id,
        )

        # ¿Tiene hijos directos?
        has_children = Location.objects.filter(
            parent=loc, tenant_id=tenant_id
        ).exists()

        # Construir el subárbol completo (incluyendo la propia ubicación)
        to_check = [loc.id]
        queue = [loc.id]

        while queue:
            current = queue.pop(0)
            children_ids = Location.objects.filter(
                parent_id=current, tenant_id=tenant_id
            ).values_list("id", flat=True)
            for child_id in children_ids:
                to_check.append(child_id)
                queue.append(child_id)

        # Productos en cualquier ubicación del subárbol
        has_products = Product.objects.filter(
            location_id__in=to_check, tenant_id=tenant_id
        ).exists()

        # Movimientos asociados a ubicaciones del subárbol
        has_movements = Movement.objects.filter(
            location_id__in=to_check, tenant_id=tenant_id
        ).exists()

        # Lotes asociados a productos en el subárbol
        has_batches = Batch.objects.filter(
            product__location_id__in=to_check, tenant_id=tenant_id
        ).exists()

        if has_children or has_products or has_movements or has_batches:
            return Response(
                {
                    "ok": False,
                    "error": "location_in_use",
                    "detail": "No se puede eliminar: tiene sub-ubicaciones, productos o historial asociado.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        loc.delete()
        return Response(
            {"ok": True, "detail": "Ubicación eliminada"}, status=status.HTTP_200_OK
        )
