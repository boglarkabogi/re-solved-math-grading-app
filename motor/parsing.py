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
    """A `pont`-ot a legközelebbi megengedett értékre kerekíti (0, 0.25, 0.5, 0.75, 1)."""
    try:
        score = float(result["pont"])
    except (KeyError, TypeError, ValueError):
        return
    result["pont"] = min(PONTOK, key=lambda v: abs(v - score))
