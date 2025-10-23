from django.urls import path, include
from .views import scan_view 
from .api import ScanEndpoint, ProductQuickSearch
from .api import router

urlpatterns = [
    path("scan/", scan_view, name="scan"),  # HTML
    path("products/search/", ProductQuickSearch.as_view(), name="product_quick_search"),
]