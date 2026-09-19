"""Próbamegoldások generálása a fejlesztői felülethez."""
from . import llm

HIBATIPUSOK = {
    "jo": "helyes, szépen leírt megoldás",
    "elszamolas": "helyes módszer, de az utolsó lépésnél elszámol",
    "rossz_modszer": "rossz módszert használ, a végeredmény is hibás",
    "hianyos": "helyes végeredmény, de alig van leírt lépés",
    "ocr_zajos": "helyes megoldás, de úgy írd le, mintha az OCR néhány karaktert félreolvasott volna",
}


def general_megoldas(feladat, helyes_megoldas, hibatipus="jo", modell=None):
    leiras = HIBATIPUSOK.get(hibatipus, HIBATIPUSOK["jo"])
    uzenetek = [
        {"role": "system", "content": "Diák kézírásos megoldásának szövegét állítod elő tesztelési célra."},
        {"role": "user", "content": (
            f"FELADAT:\n{feladat}\n\nHELYES MEGOLDÁS:\n{helyes_megoldas}\n\n"
            f"Írj egy olyan megoldást, amelyre igaz: {leiras}. "
            "Csak a megoldás szövegét add vissza, magyarázat nélkül."
        )},
    ]
    return llm.chat(uzenetek, modell=modell)
