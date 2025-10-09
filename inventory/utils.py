import io, qrcode
from django.core.files.base import ContentFile

def make_qr_contentfile(data: str) -> ContentFile:
    """Devuelve un ContentFile PNG con el QR de `data`."""
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return ContentFile(buf.getvalue())
