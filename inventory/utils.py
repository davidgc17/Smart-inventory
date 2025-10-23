import io, qrcode
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.db.models.functions import Coalesce


def available_stock(product, tenant_id):
    from .models import Batch, Movement
    batch_total = Batch.objects.filter(product=product, tenant_id=tenant_id)\
        .aggregate(t=Coalesce(Sum("quantity"), 0))["t"]
    mov_delta = Movement.objects.filter(product=product, tenant_id=tenant_id)\
        .exclude(movement_type="IN")\
        .aggregate(t=Coalesce(Sum("quantity"), 0))["t"]
    return int(batch_total) + int(mov_delta)


def make_qr_contentfile(data: str) -> ContentFile:
    """Devuelve un ContentFile PNG con el QR de `data`."""
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return ContentFile(buf.getvalue())
