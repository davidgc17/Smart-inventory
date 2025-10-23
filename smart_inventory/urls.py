from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# smart_inventory/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("inventory.urls")),         # vistas HTML (incluye /scan/)
    path("api/", include("inventory.api")),      # API REST (incluye /api/scan/)
]
