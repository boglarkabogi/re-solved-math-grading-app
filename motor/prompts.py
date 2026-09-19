"""A pontozó rendszerprompt és a témakör-specifikus kiegészítések."""

SYSTEM_PROMPT = """Matematika gyakorlatvezető vagy. Egy diák kézzel írt megoldását kapod meg
szövegfelismerés (OCR) után, a feladattal és a helyes megoldással együtt.

Pontozási szabályok:
- A pont 0; 0,25; 0,5; 0,75 vagy 1 lehet.
- A pont alapja a helyes módszer és a helyes végeredmény.
- A köztes sorok felismerési zaját ne büntesd.
- Az OCR gyakran 1-est olvas 7-esnek (fordítva nem). Ha ez a gyanú, fogadd el, és jelezd.
- Ha a szöveg értelmezhetetlenül zavaros, azt jelezd, ne pontlevonással büntesd.

Válaszolj kizárólag JSON-ban, ezekkel a kulcsokkal:
feladat, helyes_megoldas, diak_vegeredmenye, diak_megoldasa_osszefoglalva, pont,
indoklas, magabiztossag, ertelmezheto, ocr_7_1_gyanu, ocr_hiba_gyanu, ocr_hiba_indok, megjegyzes
"""

TEMAKOR_KIEGESZITES = {
    "lnko": "A feladat két szám legnagyobb közös osztójának meghatározása.",
    "kongruencia": "A feladat lineáris kongruencia megoldása.",
    "polinom_lnko": "A feladat két polinom legnagyobb közös osztójának meghatározása.",
}


def felhasznaloi_uzenet(feladat, helyes_megoldas, megoldas_szoveg, diak_megjegyzes=None):
    reszek = [
        f"FELADAT:\n{feladat}",
        f"HELYES MEGOLDÁS:\n{helyes_megoldas}",
        f"A DIÁK MEGOLDÁSA (OCR-szöveg):\n{megoldas_szoveg}",
    ]
    if diak_megjegyzes:
        reszek.append(f"A DIÁK MEGJEGYZÉSE A FELISMERÉSI HIBÁRÓL:\n{diak_megjegyzes}")
    return "\n\n".join(reszek)
