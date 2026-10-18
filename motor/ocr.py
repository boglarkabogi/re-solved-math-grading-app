"""Kézírásos kép -> szöveg."""

import base64
import io
import logging

from . import llm
from .config import settings
from .parsing import strip_think_blocks

try:
    from PIL import Image, ImageOps

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)

MAX_IMAGE_SIDE = 2000

OCR_PROMPT = """
Matematikai kézírás-transzkripciós rendszer vagy.

Kizárólag a képen ténylegesen látható tartalmat írd át.

Ne:
- oldd meg;
- javítsd ki;
- magyarázd;
- értékeld;
- egészítsd ki;
- találj ki hiányzó tartalmat.

A matematikai kifejezéseket Markdown + LaTeX formában add vissza.
Tartsd meg a lépések sorrendjét.

A válasz kizárólag a transzkripció legyen.
"""


def pic_to_data_url(pic_bytes: bytes):
    """Feltöltött kép (bármilyen formátum) -> JPEG data URL.

    A formátumot a Pillow a tartalomból ismeri fel. A telefonos forgatást (EXIF)
    helyreállítja, a nagy képet kicsinyíti, és mindig JPEG-et ad vissza.
    """
    if HAS_PIL:
        try:
            with Image.open(io.BytesIO(pic_bytes)) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))

                # Átlátszó háttér (pl. PNG képernyőkép) -> fehér, ne fekete legyen
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGBA")
                    background = Image.new("RGB", img.size, "white")
                    background.paste(img, mask=img.split()[-1])
                    img = background

                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=90)
                encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
                return f"data:image/jpeg;base64,{encoded}"
        except Exception:
             logger.warning("Could not prepare the image, sending it unchanged", exc_info=True)
            

    # Tartalék Pillow nélkül: a formátumot a fájl első bájtjaiból ismerjük fel
    if pic_bytes.startswith(b"\x89PNG"):
        mime = "image/png"
    elif pic_bytes[:4] == b"RIFF" and pic_bytes[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        mime = "image/jpeg"

    encoded = base64.b64encode(pic_bytes).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def ocr_pic(pic_bytes: bytes, modell=None) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": OCR_PROMPT},
                {"type": "image_url", "image_url": {"url": pic_to_data_url(pic_bytes)}},
            ],
        }
    ]
    text = llm.chat(messages, modell or settings.ocr_model, reasoning_fallback=False)
    return strip_think_blocks(text)
