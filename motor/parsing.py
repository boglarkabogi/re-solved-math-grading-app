"""A modell válaszának feldolgozása."""

import json
import re

PONTOK = [0.0, 0.25, 0.5, 0.75, 1.0]


def strip_think_blocks(szoveg):
    """A gondolkodó modellek <think>...</think> blokkjainak eltávolítása."""
    return re.sub(r"<think>.*?</think>", "", szoveg or "", flags=re.DOTALL).strip()


def extract_json(szoveg):
    """Az első teljes JSON-objektum kinyerése a válaszból (LaTeX-biztosan)."""
    szoveg = strip_think_blocks(szoveg)
    kezdet = szoveg.find("{")
    if kezdet == -1:
        raise ValueError("A válasz nem tartalmaz JSON-objektumot")
    melyseg = 0
    szovegben = False
    escape = False
    for i in range(kezdet, len(szoveg)):
        karakter = szoveg[i]
        if szovegben:
            if escape:
                escape = False
            elif karakter == "\\":
                escape = True
            elif karakter == '"':
                szovegben = False
            continue
        if karakter == '"':
            szovegben = True
        elif karakter == "{":
            melyseg += 1
        elif karakter == "}":
            melyseg -= 1
            if melyseg == 0:
                return json.loads(szoveg[kezdet : i + 1])
    raise ValueError("A JSON-objektum nem záródik le")


def normalize_pont(ertek):
    """A pontot a megengedett skálára igazítja."""
    if ertek is None:
        raise ValueError("Hiányzó pont")
    if isinstance(ertek, str):
        ertek = ertek.replace(",", ".").strip()
    szam = float(ertek)
    return min(PONTOK, key=lambda p: abs(p - szam))
