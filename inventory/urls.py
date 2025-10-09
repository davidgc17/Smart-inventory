from django.urls import path
from .views import scan_view

urlpatterns = [
    path("scan/", scan_view, name="scan_view"),
]
