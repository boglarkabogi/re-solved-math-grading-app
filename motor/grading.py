"""Az értékelés: egy feladat + egy megoldásszöveg -> pont és indoklás."""

from . import llm
from .config import settings
from .parsing import extract_json, normalize_score
from .prompts import load_system_prompt, user_message

JSON_RETRY = 3


def grade(feladat, helyes_megoldas, megoldas_szoveg, diak_megjegyzes=None, modell=None, system_prompt=None):
    """Visszaad egy szótárat: pont, indoklás, magabiztosság, nyers válasz, prompt.
    A system_prompt megadásával egy futtatás eltérő prompttal mérhető anélkül,
    hogy a fájlban lévő prompt megváltozna."""

    modell = modell or settings.grading_model
    system = (system_prompt or "").strip() or load_system_prompt()

    user = user_message(feladat, helyes_megoldas, megoldas_szoveg, diak_megjegyzes)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    raw, result = None, None
    for _i in range(JSON_RETRY):
        raw = llm.chat(messages, modell, json_mode=True)
        result = extract_json(raw)
        if result is not None:
            break
    if result is None:
        result = {
            "pont": None,
            "hiba": "A modell nem adott értelmezhető JSON választ.",
            "pont_kerekitve": False,
        }
    else:
        result["pont_kerekitve"] = normalize_score(result)
    result["nyers_valasz"] = raw
    result["prompt"] = system + "\n\n---\n\n" + user
    result["modell"] = modell
    return result
