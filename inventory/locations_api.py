# inventory/locations_api.py

from django.conf import settings
from django.db import models
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Location, Product
import uuid

DEFAULT_TENANT = uuid.UUID(
    getattr(settings, "DEFAULT_TENANT", "00000000-0000-0000-0000-000000000001")
)


class LocationTreeView(APIView):
    """
    GET /api/locations/tree/
    Devuelve el árbol completo de ubicaciones del tenant.
    """

    def get(self, request):
        qs = (
            Location.objects.filter(tenant_id=DEFAULT_TENANT)
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

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        parent_id = request.data.get("parent_id")

        if not name:
            return Response(
                {"ok": False, "detail": "El nombre es obligatorio"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent = None
        if parent_id:
            try:
                parent = Location.objects.get(
                    id=parent_id, tenant_id=DEFAULT_TENANT
                )
            except Location.DoesNotExist:
                return Response(
                    {"ok": False, "detail": "Ubicación padre no encontrada"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        loc = Location.objects.create(
            name=name,
            parent=parent,
            tenant_id=DEFAULT_TENANT,
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

    def post(self, request, loc_id):
        try:
            loc = Location.objects.get(id=loc_id, tenant_id=DEFAULT_TENANT)
        except Location.DoesNotExist:
            return Response(
                {"ok": False, "detail": "Ubicación no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_name = request.data.get("name")
        new_parent_id = request.data.get("parent_id")

        if new_name is not None and new_name.strip():
            loc.name = new_name.strip()

        if new_parent_id is not None:
            if new_parent_id == "":
                loc.parent = None
            else:
                try:
                    parent = Location.objects.get(
                        id=new_parent_id, tenant_id=DEFAULT_TENANT
                    )
                except Location.DoesNotExist:
                    return Response(
                        {"ok": False, "detail": "Nuevo padre no encontrado"},
                        status=status.HTTP_404_NOT_FOUND,
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

                loc.parent = parent

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

    def post(self, request, loc_id):
        try:
            loc = Location.objects.get(id=loc_id, tenant_id=DEFAULT_TENANT)
        except Location.DoesNotExist:
            return Response(
                {"ok": False, "detail": "Ubicación no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        has_children = Location.objects.filter(
            parent=loc, tenant_id=DEFAULT_TENANT
        ).exists()
        has_products = Product.objects.filter(
            location=loc, tenant_id=DEFAULT_TENANT
        ).exists()

        if has_children or has_products:
            return Response(
                {
                    "ok": False,
                    "detail": "No se puede eliminar: tiene sub-ubicaciones o productos asociados",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        loc.delete()
        return Response({"ok": True, "detail": "Ubicación eliminada"}, status=200)
