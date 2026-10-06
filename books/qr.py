from io import BytesIO

import qrcode
from django.core.files.base import ContentFile

from books.models import Item


def generate_qr(item: Item) -> Item:
    code = f"VT-{item.pk:05d}"
    image = qrcode.make(code, box_size=8, border=2)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    item.code = code
    filename = f"{code}.png"
    if item.qr_image:
        item.qr_image.delete(save=False)
    item.qr_image.save(filename, ContentFile(buffer.getvalue()), save=False)
    item.save(update_fields=["code", "qr_image"])
    return item
