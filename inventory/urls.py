from django.urls import path, include
from .views import scan_view, scan_qr_view, scan_action_view, locations_manager, home_view

urlpatterns = [
    path("", home_view, name="home"),
    path("scan/", scan_view, name="scan"),
    path("scan/qr/", scan_qr_view, name="scan-qr"),
    path("scan/<uuid:batch_id>/action/", scan_action_view, name="scan_action"),
    path("ubicaciones/", locations_manager, name="locations-manager"),
    path("api/", include("inventory.api")),
]
