"""Kézírásos kép -> szöveg."""
import base64

from . import llm
from .config import beallitasok

OCR_PROMPT = (
    "Írd le pontosan, sorról sorra, ami a képen olvasható. Matematikai jelöléseket "
    "LaTeX-ként add vissza. Ne javíts, ne magyarázz, csak a leírt tartalmat add vissza."
)


def ocr_kep(kep_bytes, modell=None, mime="image/jpeg"):
    b64 = base64.b64encode(kep_bytes).decode("ascii")
    uzenetek = [{
        "role": "user",
        "content": [
            {"type": "text", "text": OCR_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ],
    }]
    return llm.chat(uzenetek, modell=modell or beallitasok.ocr_modell)
