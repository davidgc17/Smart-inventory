from django.urls import path, include
from .views import scan_view, scan_qr_view, scan_action_view
from inventory.views import locations_manager

urlpatterns = [
    # Página principal de escaneo (la que ya tenías)
    path("scan/", scan_view, name="scan"),

    # Procesar un QR concreto (?qr=PRD:...)
    path("scan/qr/", scan_qr_view, name="scan-qr"),

    # Acción sobre un lote concreto (POST desde la pantalla de decisión)
    path("scan/<uuid:batch_id>/action/", scan_action_view, name="scan_action"),

    # Manager de ubicaciones
    path("ubicaciones/", locations_manager, name="locations-manager"),

    # API REST
    path("api/", include("inventory.api")),
]
