import uuid
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


# =========================
#  Multi-tenant helpers
# =========================

class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant_id):
        return self.filter(tenant_id=tenant_id)


class TenantManager(models.Manager):
    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant_id):
        return self.get_queryset().for_tenant(tenant_id)


DEFAULT_TENANT = getattr(
    settings,
    "DEFAULT_TENANT",
    uuid.UUID("00000000-0000-0000-0000-000000000001"),
)


# =========================
#  Utils
# =========================

def normalize_name(s: str) -> str:
    """
    Normaliza nombres para búsquedas/comparaciones:
    - Quita acentos
    - Pasa a ASCII
    - Minúsculas + strip
    """
    return (
        unicodedata.normalize("NFKD", s or "")
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


# =========================
#  Location (jerárquica)
# =========================

class Location(models.Model):
    name = models.CharField(max_length=255)
    tenant_id = models.UUIDField(
        default=DEFAULT_TENANT,
        editable=False,
        db_index=True,
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )

    objects = TenantManager()

    class Meta:
        # Evita duplicados tipo: mismo tenant, mismo padre, mismo nombre
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "parent", "name"],
                name="uniq_location_per_parent_tenant",
            )
        ]
        ordering = ["name"]

    def clean(self):
        """
        Evita bucles: una ubicación no puede ser su propio ancestro.
        """
        ancestor = self.parent
        while ancestor:
            if ancestor == self:
                raise ValidationError(
                    "Una ubicación no puede ser su propio ancestro."
                )
            ancestor = ancestor.parent

    def __str__(self):
        """
        Representación legible: ruta completa, tipo
        'Armario 1 / Caja 2 / Fondo 3'.
        """
        parts = []
        current = self
        while current:
            parts.append(current.name)
            current = current.parent
        return " / ".join(reversed(parts))

    def full_path(self, sep=" > "):
        """
        Devuelve la ruta completa desde la raíz hasta esta ubicación.
        Ejemplo: 'Salón > Estantería 1 > Caja Roja'
        """
        parts = [self.name]
        parent = self.parent
        while parent:
            parts.append(parent.name)
            parent = parent.parent
        return sep.join(reversed(parts))

    def descendant_ids(self, include_self=True):
        """
        Devuelve una lista con los IDs de todas las ubicaciones
        descendientes. Si include_self=True, incluye también el ID
        de la propia ubicación.
        Útil para auditorías recursivas (subárbol).
        """
        ids = []
        stack = [self]

        while stack:
            node = stack.pop()
            if include_self or node.pk != self.pk:
                ids.append(node.pk)
            # children viene de related_name="children"
            stack.extend(list(node.children.all()))

        return ids

    def descendants_qs(self, include_self=True):
        """
        Devuelve un queryset de Location con todos los descendientes
        (y opcionalmente la propia ubicación).
        """
        return Location.objects.filter(pk__in=self.descendant_ids(include_self))


# =========================
#  Product
# =========================

class Product(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tenant_id = models.UUIDField(
        default=DEFAULT_TENANT,
        editable=False,
        db_index=True,
    )
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=20, default="unit")
    min_stock = models.IntegerField(default=0)

    qr_payload = models.CharField(
        max_length=120,
        unique=True,
        editable=False,
    )
    qr_image = models.ImageField(
        upload_to="qr/",
        blank=True,
        null=True,
    )
    nfc_tag_uid = models.CharField(max_length=64, blank=True)

    expiration_date = models.DateField(null=True, blank=True)
    consumption_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    objects = TenantManager()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    name_normalized = models.CharField(
        max_length=220,
        db_index=True,
        editable=False,
        blank=True,
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                check=Q(min_stock__gte=0),
                name="product_min_stock_gte_0",
            ),
            models.UniqueConstraint(
                fields=["tenant_id", "location", "name_normalized"],
                name="uniq_product_per_location_tenant_norm",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant_id", "location", "name_normalized"]),
            models.Index(fields=["tenant_id", "name"]),
        ]

    def __str__(self):
        if self.location:
            return f"{self.name} ({self.location.full_path()})"
        return self.name

    def location_path(self):
        """
        Devuelve la ruta jerárquica completa de la ubicación del producto.
        """
        return self.location.full_path() if self.location else "(sin ubicación)"

    @staticmethod
    def normalize_name_value(s: str) -> str:
        """
        Versión estática por si quieres usarla desde otros sitios.
        """
        return normalize_name(s)

    def save(self, *args, **kwargs):
        """
        Lógica unificada de guardado:
        - Normaliza name_normalized
        - Genera SKU si falta
        - Genera qr_payload si falta
        - Genera imagen QR al crear, si falta
        """
        creating = self._state.adding

        # Normalización del nombre para búsquedas + constraint
        self.name_normalized = normalize_name(self.name or "")

        # Aseguramos que hay ID antes de montar payload/SKU
        if creating and not self.id:
            self.id = uuid.uuid4()

        # SKU autogenerado si no se ha definido
        if creating and not self.sku:
            base_sku = (slugify(self.name)[:10] or "prd").upper()
            self.sku = f"{base_sku}-{str(self.id)[:4]}"

        # qr_payload (PRD:<uuid>) si no existe
        if (creating or not self.qr_payload) and self.id:
            self.qr_payload = f"PRD:{self.id}"

        super().save(*args, **kwargs)

        # Generación de imagen QR solo al crear y si no existía ya
        if creating and not self.qr_image and self.qr_payload:
            from .utils import make_qr_contentfile

            filename = f"product-{slugify(self.name)}-{str(self.id)[:8]}.png"
            content = make_qr_contentfile(self.qr_payload)
            # Este save vuelve a llamar a save(), pero creating=False,
            # por lo que no se regenera nada.
            self.qr_image.save(filename, content, save=True)


# =========================
#  Movement
# =========================

class Movement(models.Model):
    IN, OUT, ADJ, AUD = "IN", "OUT", "ADJ", "AUD"
    TYPES = [
        (IN, "Entry"),
        (OUT, "Exit"),
        (ADJ, "Adjust"),
        (AUD, "Audit"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    tenant_id = models.UUIDField(
        default=DEFAULT_TENANT,
        editable=False,
        db_index=True,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    quantity = models.IntegerField(
        help_text="Positivo para entradas, negativo para salidas",
    )
    movement_type = models.CharField(max_length=4, choices=TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    objects = TenantManager()

    class Meta:
        ordering = ["-created_at"]


# =========================
#  Batch
# =========================

class Batch(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="batches",
    )
    tenant_id = models.UUIDField(
        default=DEFAULT_TENANT,
        editable=False,
        db_index=True,
    )
    quantity = models.PositiveIntegerField(default=0)
    entry_date = models.DateField(auto_now_add=True)
    expiration_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    depleted_at = models.DateTimeField(null=True, blank=True)
    is_depleted = models.BooleanField(default=False, db_index=True)

    objects = TenantManager()

    class Meta:
        ordering = ["entry_date"]
        constraints = [
            models.CheckConstraint(
                check=Q(quantity__gte=0),
                name="batch_quantity_gte_0",
            ),
        ]

    def __str__(self):
        return f"Lote de {self.product.name} ({self.quantity} uds, {self.entry_date})"
