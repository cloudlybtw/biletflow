import io

import segno
from PIL import Image, ImageDraw, ImageFont


def promo_png(target_url: str) -> bytes:
    """Keep Segno's quiet zone intact; add an orange PROMO label below the QR."""
    qr = segno.make(target_url, error="h", micro=False)
    raw = io.BytesIO()
    qr.save(raw, kind="png", scale=6, border=4, dark="#102b46", light="#ffffff")
    with Image.open(io.BytesIO(raw.getvalue())) as source:
        image = source.convert("RGB")
    result = Image.new("RGB", (image.width, image.height + 60), "white")
    result.paste(image, (0, 0))
    draw = ImageDraw.Draw(result)
    draw.rectangle((0, image.height, image.width, result.height), fill="#f59e0b")
    font = ImageFont.load_default(size=28)
    draw.text((image.width / 2, image.height + 30), "PROMO", font=font, fill="#102b46", anchor="mm")
    out = io.BytesIO()
    result.save(out, format="PNG")
    return out.getvalue()
