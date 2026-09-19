"""Az értékelés: egy feladat + egy megoldásszöveg -> pont és indoklás."""
from . import llm
from .config import beallitasok
from .parsing import extract_json, normalize_pont
from .prompts import SYSTEM_PROMPT, TEMAKOR_KIEGESZITES, felhasznaloi_uzenet


def ertekel(feladat, helyes_megoldas, megoldas_szoveg, diak_megjegyzes=None,
            temakor=None, modell=None):
    """Visszaad egy szótárat: pont, indoklás, magabiztosság, nyers válasz, prompt."""
    rendszer = SYSTEM_PROMPT
    if temakor and temakor in TEMAKOR_KIEGESZITES:
        rendszer += "\n\n" + TEMAKOR_KIEGESZITES[temakor]

    felhasznaloi = felhasznaloi_uzenet(feladat, helyes_megoldas, megoldas_szoveg, diak_megjegyzes)
    uzenetek = [
        {"role": "system", "content": rendszer},
        {"role": "user", "content": felhasznaloi},
    ]

    nyers = llm.chat(uzenetek, modell=modell or beallitasok.ertekelo_modell)
    eredmeny = extract_json(nyers)
    eredmeny["pont"] = normalize_pont(eredmeny.get("pont"))
    eredmeny["_nyers_valasz"] = nyers
    eredmeny["_prompt"] = rendszer + "\n\n---\n\n" + felhasznaloi
    eredmeny["_modell"] = modell or beallitasok.ertekelo_modell
    return eredmeny
