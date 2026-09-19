"""Beállítások környezeti változókból (a .env fájlból)."""
import os


def _get(name, default=None, required=False):
    ertek = os.environ.get(name, default)
    if required and not ertek:
        raise RuntimeError(f"Hiányzó környezeti változó: {name}")
    return ertek


class LlmBeallitasok:
    """Egy OpenAI-kompatibilis végpont adatai. Szolgáltatót váltani = ezeket átírni."""

    def __init__(self):
        self.base_url = _get("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.api_key = _get("LLM_API_KEY", "")
        self.ertekelo_modell = _get("LLM_GRADING_MODEL", "nvidia/nemotron-3-super-120b-a12b")
        self.ocr_modell = _get("LLM_OCR_MODEL", "qwen/qwen2.5-vl-7b-instruct")
        self.kerés_per_perc = int(_get("LLM_MAX_REQUESTS_PER_MINUTE", "30"))


beallitasok = LlmBeallitasok()
