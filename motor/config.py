"""Beállítások környezeti változókból (a .env fájlból)."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

def _get(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Hiányzó környezeti változó: {name}")
    return value


class LlmSettings:
    """Egy OpenAI-kompatibilis végpont adatai. Szolgáltatót váltani = ezeket átírni."""

    def __init__(self):
        self.base_url = _get("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.api_key = _get("LLM_API_KEY", required=True)
        self.grading_model = _get("LLM_GRADING_MODEL", "nvidia/nemotron-3-super-120b-a12b")
        self.ocr_model = _get("LLM_OCR_MODEL", "moonshotai/kimi-k3")
        self.req_per_min = int(_get("LLM_MAX_REQUESTS_PER_MINUTE", "30"))
        self.timeout = 300
        self.max_retry = 3

settings = LlmSettings()
