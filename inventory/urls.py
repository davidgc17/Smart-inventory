from django.urls import path, include
from .views import scan_view
from inventory.views import locations_manager

urlpatterns = [
    path("scan/", scan_view, name="scan"),  # HTML
    path("ubicaciones/", locations_manager, name="locations-manager"),
    path("api/", include("inventory.api")),
]