"""Az értékelés: egy feladat + egy megoldásszöveg -> pont és indoklás."""

from . import llm
from .config import settings
from .parsing import extract_json, normalize_score
from .prompts import SYSTEM_PROMPT, user_message

JSON_RETRY = 3

def grade(feladat, helyes_megoldas, megoldas_szoveg, diak_megjegyzes=None, modell=None):
    """Visszaad egy szótárat: pont, indoklás, magabiztosság, nyers válasz, prompt.
    Ha a modell többszöri próbálkozásra sem ad értelmes JSON-t, a 'pont' None,
    és a 'hiba' mező írja le, mi történt (a nyers válasz ilyenkor is megmarad)."""

    modell = modell or settings.grading_model

    user = user_message(feladat, helyes_megoldas, megoldas_szoveg, diak_megjegyzes)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    raw, result = None, None
    for i in range(JSON_RETRY):
        raw = llm.chat(messages, modell, json_mode=True)
        result = extract_json(raw)
        if result is not None:
            break
    if result is None:
        result = {"pont": None, "hiba": "A modell nem adott értelmezhető JSON választ."}
    else:
        normalize_score(result)
    result["nyers_valasz"] = raw
    result["prompt"] = SYSTEM_PROMPT + "\n\n---\n\n" + user
    result["modell"] = modell
    return result