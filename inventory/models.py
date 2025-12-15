import uuid
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()

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
#  Organization (tenant)
# =========================

class Organization(models.Model):
    """
    Capa de organización/tenant.
    El id de esta tabla será el que usemos en tenant_id de Product, Location, etc.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(max_length=150)

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization",
        help_text="Usuario propietario de esta organización",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self):
        return self.name

# =========================
#  Signals: auto-crear Organization
# =========================

@receiver(post_save, sender=User)
def create_user_organization(sender, instance, created, **kwargs):
    """
    Cada vez que se crea un usuario nuevo, le damos una Organization propia.
    Más adelante usaremos Organization.id como tenant_id de todo su inventario.
    """
    if not created:
        return

    # Evitar duplicados por si algún día creas usuarios a mano
    if hasattr(instance, "organization"):
        return

    Organization.objects.create(
        owner=instance,
        name=f"Inventario de {instance.username}",
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
    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        null=True,
        blank=True,
        db_index=True,
    )

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

    # Fechas “globales” del producto
    expiration_date = models.DateField(null=True, blank=True)
    consumption_date = models.DateField(null=True, blank=True)

    #control opcional de etapa “abierto”
    track_open_state = models.BooleanField(
        default=False,
        help_text="Si está activo, este producto tiene etapa de ‘abierto’ con segunda caducidad."
    )
    default_open_shelf_life_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Días que dura tras abrir (p. ej. 7). Se usa si no se indican días manualmente."
    )

    notes = models.TextField(blank=True, null=True)

        # === v0.1-alpha — campos informativos opcionales ===
    brand = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )

    origin = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )

    primary_color = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
    )

    dimensions = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        help_text="Formato libre, ej: 10x20x5 cm",
    )

    estimated_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )


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
    # Caducidad “cerrado” del lote
    expiration_date = models.DateField(null=True, blank=True)
    # --- Metadatos específicos del lote (v0.1) ---
    brand = models.CharField(max_length=100, blank=True, null=True)
    origin = models.CharField(max_length=100, blank=True, null=True)
    primary_color = models.CharField(max_length=50, blank=True, null=True)
    dimensions = models.CharField(max_length=120, blank=True, null=True)
    estimated_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    notes = models.TextField(blank=True, null=True)

    # === Gestión de unidades abiertas dentro del lote ===
    # nº de unidades abiertas en este lote (normalmente 0 o 1)
    opened_units = models.PositiveIntegerField(default=0)
    # cuándo se abrió la unidad actual
    opened_at = models.DateTimeField(null=True, blank=True)
    # hasta cuándo es válida esa unidad tras abrir
    open_expires_at = models.DateTimeField(null=True, blank=True)

    # Estado de agotamiento del lote
    depleted_at = models.DateTimeField(null=True, blank=True)
    is_depleted = models.BooleanField(default=False, db_index=True)

    objects = TenantManager()

    # Constantes de acción para el escaneo
    ACTION_AUTO_CONSUME = "AUTO_CONSUME"
    ACTION_CONSUME_OPEN = "CONSUME_OPEN"
    ACTION_ASK_OPEN_OR_CONSUME = "ASK_OPEN_OR_CONSUME"
    ACTION_NO_STOCK = "NO_STOCK"

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
    
    def decide_action(self):
        """
        Devuelve una de las acciones posibles para este lote
        cuando el usuario escanea un producto en modo SALIDA.
        """
        if self.quantity <= 0:
            return Batch.ACTION_NO_STOCK

        # Si ya hay una unidad abierta → siempre consumirla
        if self.opened_units == 1:
            return Batch.ACTION_CONSUME_OPEN

        # Si no hay unidad abierta → preguntar al usuario
        return Batch.ACTION_ASK_OPEN_OR_CONSUME


    # ========= Helpers de estado =========

    @property
    def available_units(self) -> int:
        """
        Unidades disponibles en este lote.
        Ahora mismo es simplemente 'quantity'.
        """
        return self.quantity

    @property
    def has_open_unit(self) -> bool:
        """
        Indica si hay al menos una unidad abierta en este lote.
        En el flujo normal será 0 o 1.
        """
        return self.opened_units > 0

    @property
    def effective_expiry(self):
        """
        Fecha real para avisos:
        - Si hay bote abierto → mínima entre caducidad cerrada y caducidad tras abrir
        - Si no, usar caducidad normal
        """
        dates = []

        if self.expiration_date:
            dates.append(
                timezone.make_aware(
                    datetime.combine(self.expiration_date, datetime.min.time())
                )
            )
        if self.open_expires_at:
            dates.append(self.open_expires_at)

        if not dates:
            return None

        return min(dates)

    # ========= Acciones sobre el lote =========

    def consume_one(self, *, mark_depleted: bool = True, save: bool = True):
        """
        Consume 1 unidad del lote.

        - Si la unidad consumida era la abierta, limpia el estado de apertura.
        - Si el lote se queda a 0 y mark_depleted=True, se marca como agotado.
        """
        if self.quantity <= 0:
            raise ValueError("No hay unidades disponibles en este lote para consumir.")

        # Restamos una unidad
        self.quantity -= 1

        # Si había unidades abiertas, asumimos que consumimos la abierta
        if self.has_open_unit:
            self.opened_units -= 1
            if self.opened_units <= 0:
                self.opened_units = 0
                self.opened_at = None
                self.open_expires_at = None

        # Si ya no quedan unidades en el lote, lo marcamos como agotado
        if self.quantity == 0 and mark_depleted:
            self.is_depleted = True
            self.depleted_at = timezone.now()

        if save:
            self.save()

    def open_one(self, *, shelf_life_days: int, now=None, save: bool = True):
        """
        Marca 1 unidad de este lote como abierta y le asigna una caducidad 'tras abrir'.

        Reglas:
        - Solo se puede abrir si hay unidades disponibles.
        - Solo tiene sentido si el producto tiene track_open_state=True.
        - Se permite 1 unidad abierta por lote (por ahora).
        """
        if self.quantity <= 0:
            raise ValueError("No se puede abrir un bote de un lote sin unidades.")

        if not getattr(self.product, "track_open_state", False):
            raise ValueError("Este producto no tiene etapa de apertura activada.")

        if shelf_life_days <= 0:
            raise ValueError("Los días de vida tras abrir deben ser > 0.")

        if now is None:
            now = timezone.now()

        if self.has_open_unit:
            # Hay que decidir en la vista qué hacer antes de llegar aquí,
            # abrir un segundo bote del mismo lote sin control es mala idea.
            raise ValueError("Este lote ya tiene un bote abierto.")

        self.opened_units = 1
        self.opened_at = now
        self.open_expires_at = now + timedelta(days=shelf_life_days)

        if save:
            self.save()

    # ========= Lógica de escaneo (QR) =========

    @classmethod
    def choose_for_scan(cls, product, tenant_id):
        """
        Decide qué hacer al escanear el QR de un producto:

        - Si product.track_open_state es False:
            → AUTO_CONSUME sobre el lote más antiguo con stock.

        - Si product.track_open_state es True:
            1) Si hay una unidad abierta en algún lote:
                → CONSUME_OPEN sobre ese lote.
            2) Si no hay abiertas pero sí stock:
                → ASK_OPEN_OR_CONSUME sobre el lote más antiguo con stock.
            3) Si no hay stock:
                → NO_STOCK.

        Devuelve (action, batch) donde batch puede ser None si no hay stock.
        """
        qs = cls.objects.filter(
            tenant_id=tenant_id,
            product=product,
            is_depleted=False,
            quantity__gt=0,
        ).order_by("expiration_date", "entry_date", "id")

        if not qs.exists():
            return cls.ACTION_NO_STOCK, None

        # Caso 1: producto sin etapa de apertura
        if not getattr(product, "track_open_state", False):
            return cls.ACTION_AUTO_CONSUME, qs.first()

        # Caso 2: producto con etapa abierto/cerrado

        # 2.1) ¿Hay alguna unidad abierta en algún lote?
        open_batch = qs.filter(opened_units__gt=0).order_by(
            "open_expires_at", "expiration_date"
        ).first()
        if open_batch:
            return cls.ACTION_CONSUME_OPEN, open_batch

        # 2.2) No hay unidades abiertas pero sí stock → preguntar
        target_batch = qs.first()
        if not target_batch:
            return cls.ACTION_NO_STOCK, None

        return cls.ACTION_ASK_OPEN_OR_CONSUME, target_batch


class AppMeta(models.Model):
    tenant_id = models.UUIDField(
        default=DEFAULT_TENANT,
        editable=False,
        db_index=True,
    )

    schema_version = models.PositiveIntegerField(default=1)
    app_version = models.CharField(
        max_length=50,
        default="0.1-alpha (tester-local)",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id"],
                name="uniq_appmeta_per_tenant",
            )
        ]

# =========================
#  Signals: auto-crear Organization por usuario
# =========================

@receiver(post_save, sender=User)
def create_user_organization(sender, instance, created, **kwargs):
    """
    Cada vez que se crea un usuario nuevo, le damos una Organization propia.
    """
    if not created:
        return

    # Si por algún motivo ya tiene, no duplicar
    if hasattr(instance, "organization"):
        return

    Organization.objects.create(
        owner=instance,
        name=f"Inventario de {instance.username}",
    )
