"""OpenAI-kompatibilis kliens sebességkorláttal és újrapróbálkozással."""

import random
import threading
import time
from functools import lru_cache

from .config import settings

FATAL_ERRORS = {400, 401, 403, 404, 410, 422}
MAX_WAIT = 120


class Throttle:
    """Percenkénti hívásszám betartása (szálbiztos)."""

    def __init__(self, req_per_min):
        self.interval = 60.0 / max(1, req_per_min)
        self.last = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            wait = self.interval - (now - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()


_throttle = Throttle(settings.req_per_min)


@lru_cache(maxsize=1)
def client():
    from openai import OpenAI  # lusta import, hogy a tesztekhez ne kelljen

    return OpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key,
        timeout=settings.timeout,
        max_retries=0,
    )


def waiting(error, i):
    try:
        return min(float(error.response.headers["retry-after"]), MAX_WAIT)
    except Exception:
        return min(2**i * 5, MAX_WAIT) + random.random()


def chat(messages, modell=None, reasoning_fallback=True, json_mode=False, **kwargs):
    """Egy hívás a modellhez. Visszaadja a válasz szövegét."""
    modell = modell or settings.grading_model
    tries = settings.max_retry
    last_error = None
    for i in range(tries):
        _throttle.wait()
        extra = dict(kwargs)
        if json_mode:
            extra["response_format"] = {"type": "json_object"}

        try:
            answer = client().chat.completions.create(model=modell, messages=messages, **extra)

        except Exception as error:  # 429, 5xx, időtúllépés, hálózati hiba
            last_error = error
            status = getattr(error, "status_code", None)

            if status == 400 and json_mode:
                print("      JSON-mód nem támogatott, újra sima szöveggel...")
                json_mode = False
                continue

            if status in FATAL_ERRORS:
                text = getattr(getattr(error, "response", None), "text", "")[:300]
                raise RuntimeError(
                    f"HTTP {status}: a '{modell}' modell nem érhető el. A szerver válasza: {text}"
                ) from error

            if i < tries - 1:  # az utolsó sikertelen próba után már nem várunk
                wait = waiting(error, i)
                print(
                    f"      Hiba ({status or type(error).__name__}), "
                    f"{i + 1}. próba. Várakozás {wait:.0f} mp..."
                )
                time.sleep(wait)
            continue

        # Előfordul, hogy a szerver üres választ ad (nincs choices, vagy üres szöveg).
        if not answer.choices:
            last_error = RuntimeError("Üres válasz (nincs choices).")
            continue

        message = answer.choices[0].message
        # Reasoning modelleknél a szöveg néha csak a reasoning_content mezőben van.
        text = message.content or ""
        if not text.strip() and reasoning_fallback:
            text = getattr(message, "reasoning_content", None) or ""
        if text.strip():
            return text.strip()

        last_error = RuntimeError(f"Üres válasz (finish_reason={answer.choices[0].finish_reason}).")

    raise RuntimeError(f"A modellhívás {tries} próbálkozás után sem sikerült") from last_error
