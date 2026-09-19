"""OpenAI-kompatibilis kliens sebességkorláttal és újrapróbálkozással."""
import time
import threading

from .config import beallitasok


class Throttle:
    """Percenkénti hívásszám betartása (szálbiztos)."""

    def __init__(self, keres_per_perc):
        self.koz = 60.0 / max(1, keres_per_perc)
        self.utolso = 0.0
        self.lakat = threading.Lock()

    def var(self):
        with self.lakat:
            most = time.monotonic()
            varakozas = self.koz - (most - self.utolso)
            if varakozas > 0:
                time.sleep(varakozas)
            self.utolso = time.monotonic()


_throttle = Throttle(beallitasok.kerés_per_perc)


def _kliens():
    from openai import OpenAI  # lusta import, hogy a tesztekhez ne kelljen

    return OpenAI(base_url=beallitasok.base_url, api_key=beallitasok.api_key)


def chat(uzenetek, modell=None, probalkozas=3, **kwargs):
    """Egy hívás a modellhez. Visszaadja a válasz szövegét."""
    modell = modell or beallitasok.ertekelo_modell
    utolso_hiba = None
    for i in range(probalkozas):
        _throttle.var()
        try:
            valasz = _kliens().chat.completions.create(
                model=modell, messages=uzenetek, **kwargs
            )
            return valasz.choices[0].message.content
        except Exception as hiba:  # 429, időtúllépés, hálózati hiba
            utolso_hiba = hiba
            time.sleep(2 ** i * 5)
    raise RuntimeError(f"A modellhívás {probalkozas} próbálkozás után sem sikerült") from utolso_hiba
