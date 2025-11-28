from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Min
from .models import Product, Location, Movement, Batch, Organization

admin.site.register(Organization)

# -------------------------------------------------------------------
#  INLINE: LOTES (BATCHES) DENTRO DE CADA PRODUCTO
# -------------------------------------------------------------------
class BatchInline(admin.TabularInline):
    model = Batch
    extra = 0
    fields = ("quantity", "entry_date", "expiration_date", "notes")
    readonly_fields = ("entry_date",)
    ordering = ("entry_date",)
    show_change_link = True


# -------------------------------------------------------------------
#  LOCATION ADMIN
# -------------------------------------------------------------------
@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("full_path", "parent")
    search_fields = ("name",)
    ordering = ("parent", "name")

    def full_path(self, obj):
        """Muestra la jerarquía completa (ej: Salón / Estantería / Caja Roja)."""
        return obj.full_path()
    full_path.short_description = "Ruta completa"



# -------------------------------------------------------------------
#  PRODUCT ADMIN
# -------------------------------------------------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "unit",
        "location",
        "stock_total",
        "nearest_expiration",
        "status_color",
    )
    list_filter = ("category", "unit", "location")
    search_fields = ("name", "category", "location__name")
    ordering = ("name",)
    readonly_fields = ("qr_payload", "qr_image")
    inlines = [BatchInline]

    fields = (
        "name",
        "category",
        "unit",
        "min_stock",
        "notes",
        "qr_payload",
        "qr_image",
        "nfc_tag_uid",
    )

    # ---- CALCULA EL STOCK TOTAL A PARTIR DE LOS LOTES ----
    def stock_total(self, obj):
        total = obj.batches.aggregate(Sum("quantity"))["quantity__sum"] or 0
        color = "red" if total < (obj.min_stock or 0) else "green"
        return format_html('<b style="color:{};">{}</b>', color, total)
    stock_total.short_description = "Stock total"


    # --- Muestra la ubicación completa ---
    def location_path(self, obj):
        """Muestra la ruta jerárquica completa de la ubicación."""
        if obj.location:
            return obj.location.full_path()
        return "(sin ubicación)"
    location_path.short_description = "Ubicación completa"

    # ---- MUESTRA LA CADUCIDAD MÁS PRÓXIMA ENTRE LOTES ----
    def nearest_expiration(self, obj):
        nearest = obj.batches.aggregate(Min("expiration_date"))["expiration_date__min"]
        if not nearest:
            return "-"
        return nearest.strftime("%d/%m/%Y")
    nearest_expiration.short_description = "Caducidad más próxima"

    # ---- COLOR DE ESTADO SEGÚN STOCK ----
    def status_color(self, obj):
        total = obj.batches.aggregate(Sum("quantity"))["quantity__sum"] or 0
        if total <= 0:
            return format_html('<span style="color:red;">❌ Sin stock</span>')
        elif total < (obj.min_stock or 0):
            return format_html('<span style="color:orange;">⚠ Bajo stock</span>')
        else:
            return format_html('<span style="color:green;">✅ OK</span>')
    status_color.short_description = "Estado"


# -------------------------------------------------------------------
#  MOVEMENT ADMIN (Solo lectura - auditoría)
# -------------------------------------------------------------------
@admin.register(Movement)
class MovementAdmin(admin.ModelAdmin):
    list_display = ("movement_type", "product", "location_path", "quantity", "created_at", "created_by")
    list_filter = ("movement_type", "location", "created_at")
    search_fields = ("product__name", "location__name")
    ordering = ("-created_at",)
    readonly_fields = ("movement_type", "product", "location", "quantity", "created_at", "created_by")

    def location_path(self, obj):
        """Ruta completa de la ubicación."""
        return obj.location.full_path() if obj.location else "(sin ubicación)"
    location_path.short_description = "Ubicación completa"

    # Evita que se edite desde el admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False



# -------------------------------------------------------------------
#  BATCH ADMIN (vista independiente)
# -------------------------------------------------------------------
@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("product", "location_path", "quantity", "entry_date", "expiration_date", "notes")
    list_filter = ("expiration_date",)
    search_fields = ("product__name", "product__location__name")
    ordering = ("-entry_date",)

    def location_path(self, obj):
        """Ruta completa de la ubicación del producto asociado al lote."""
        if obj.product and obj.product.location:
            return obj.product.location.full_path()
        return "(sin ubicación)"
    location_path.short_description = "Ubicación completa"
