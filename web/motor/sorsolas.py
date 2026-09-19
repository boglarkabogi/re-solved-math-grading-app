"""Feladatsorsolás a feladatbankból."""

import random


def sorsol(feladatok, mar_kapott_ids=(), csoport_darabszamok=None, seed=None):
    """Kiválaszt egy feladatot.

    feladatok: (id, ...) azonosítható elemek listája
    mar_kapott_ids: amit ez a diák már megkapott -> ezeket kerüljük
    csoport_darabszamok: {feladat_id: hányan kapták a csoportban}
    """
    if not feladatok:
        raise ValueError("Üres a feladatkészlet")

    darab = csoport_darabszamok or {}
    jeloltek = [f for f in feladatok if f.id not in mar_kapott_ids] or list(feladatok)

    legkevesebb = min(darab.get(f.id, 0) for f in jeloltek)
    legritkabbak = [f for f in jeloltek if darab.get(f.id, 0) == legkevesebb]

    rng = random.Random(seed)
    return rng.choice(legritkabbak)
