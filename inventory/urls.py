from django.urls import path, include
from .views import scan_view, scan_qr_view, scan_action_view, locations_manager, home_view, register, logout_view, qr_list_view
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", home_view, name="home"),
    path("scan/", scan_view, name="scan"),
    path("scan/qr/", scan_qr_view, name="scan-qr"),
    path("qrcodes/", qr_list_view, name="qr_list"),
    path("scan/<uuid:batch_id>/action/", scan_action_view, name="scan_action"),
    path("ubicaciones/", locations_manager, name="locations-manager"),
    path("api/", include("inventory.api")),
    path("login/",auth_views.LoginView.as_view(template_name="inventory/login.html"),name="login",),
    path("logout/", logout_view, name="logout"),
    path("register/", register, name="register"),
]
