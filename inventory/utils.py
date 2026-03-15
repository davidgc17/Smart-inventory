import io, qrcode, os
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.conf import settings


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

"""
def save_qr_to_media(data: str, filename: str) -> str:
    """
    Genera un QR PNG y lo guarda en media/qr/.
    Devuelve la ruta absoluta del archivo.
    """
    qr_dir = os.path.join(settings.MEDIA_ROOT, "qr")
    os.makedirs(qr_dir, exist_ok=True)

    path = os.path.join(qr_dir, filename)

    img = qrcode.make(data)
    img.save(path, format="PNG")

    return path

""""