"""A modell válaszának feldolgozása."""

import json
import re

PONTOK = (0, 0.25, 0.5, 0.75, 1)


def strip_think_blocks(text):
    """A gondolkodó modellek <think>...</think> blokkjainak eltávolítása."""
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()


def _fix_latex_backslashes(s: str):
    """Duplázza azokat a '\\'-eket, amik nem érvényes JSON-escape-ek (pl. LaTeX: \\in, \\gcd)."""
    return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", s)


def _first_json_object(s: str) -> str | None:
    """Az első teljes {...} blokk, zárójel-mélység számolással (stringeken belül nem számol)."""
    start = s.find("{")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None  # csonka válasz


def extract_json(text):
    """Az első teljes JSON-objektum kinyerése a válaszból (LaTeX-biztosan)."""
    text = strip_think_blocks(text)
    block = _first_json_object(text)
    candidates = [block, _fix_latex_backslashes(block)] if block else []
    candidates += [text, _fix_latex_backslashes(text)]
    for cand in candidates:
        try:
            result = json.loads(cand)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    return None


def normalize_score(result: dict):
    """A `pont`-ot a legközelebbi megengedett értékre igazítja (0, 0.25, 0.5, 0.75, 1).

    Visszaadja, hogy hozzá kellett-e nyúlni. A hívó ebből tudja, hogy a modell
    nem tartotta be a saját pontskáláját, és érdemes emberi szemmel ránézni.

    A 0..1 tartományon kívüli érték nem kerekítendő, hanem értelmezhetetlen:
    a legközelebbi megengedett értékre húzva a 7-ből teljes pont lenne, a -3-ból
    nulla. Ilyenkor a pont None lesz, és a `hiba` mező írja le, mi történt.
    """
    try:
        score = float(result["pont"])
    except (KeyError, TypeError, ValueError):
        return False

    if not 0 <= score <= 1:
        result["pont"] = None
        result["hiba"] = f"A modell a skálán kívüli pontot adott: {score!r}"
        return True

    nearest = min(PONTOK, key=lambda allowed: abs(allowed - score))
    result["pont"] = nearest
    return nearest != score
