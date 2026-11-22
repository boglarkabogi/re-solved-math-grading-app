from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parent / "system_prompt.txt"


def load_system_prompt():
    """Az értékelő prompt. Minden híváskor újraolvassuk, hogy a szerkesztés
    újraindítás nélkül is érvényesüljön."""
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def save_system_prompt(text):
    """Visszaírja a promptot abba a fájlba, amit a repó követ."""
    cleaned = text.replace("\r\n", "\n").strip() + "\n"
    PROMPT_PATH.write_text(cleaned, encoding="utf-8")
    return cleaned

JSON_SCHEMA_BLOCK = """\
Add vissza pontosan ezt a JSON-t (más szöveg ne legyen a válaszban):
{
  "feladat": "<a feladat megadott szövege>",
  "helyes_megoldas": "<a feladat megadott helyes megoldása>",
  "diak_vegeredmenye": "<amit a diák végeredményként megadott; ha csak az algoritmusból olvasható ki, akkor is add meg>",
  "diak_megoldasa_osszefoglalva": "<1-3 mondat a diák levezetéséről>",
  "pont": 0,
  "indoklas": "<miért kapott/nem kapott pontot>",
  "magabiztossag": 0,
  "ertelmezheto": true,
  "ocr_hiba_gyanu": false,
  "ocr_hiba_indok": "<1 mondat: mi utal OCR-hibára, vagy üres>"
}

Emlékeztető:
- A pontozás fő alapja a helyes MÓDSZER és a helyes VÉGEREDMÉNY. A köztes sorok apró
  OCR-hibáiért ne büntess.
- A "pont" csak 0, 0.25, 0.5, 0.75 vagy 1 lehet.
- A "magabiztossag" (0-100) a SAJÁT értékelésed magabiztossága, nem a bemenet olvashatósága.
- Az "ocr_hiba_gyanu" legyen true, ha a szöveg annyira zavaros/értelmezhetetlen, hogy nem
  lehet megbízhatóan értékelni, ilyenkor az "ocr_hiba_indok" adjon rövid indokot.
- A JSON string mezőiben NE legyen LaTeX (se `$...$`, se `\\in`, `\\mathbb`, `\\gcd`, `\\frac`
  stb.) — a matekot sima szöveggel írd (pl. `x^2 + x + 1`, `Z_5[x]`, `gcd`).
"""


def user_message(feladat, helyes_megoldas, megoldas_szoveg, diak_megjegyzes=None):
    parts = [
        f"FELADAT:\n{feladat}",
        f"HELYES MEGOLDÁS:\n{helyes_megoldas}",
        f"A DIÁK MEGOLDÁSA (OCR-szöveg):\n{megoldas_szoveg}",
    ]
    if diak_megjegyzes:
        parts.append(f"A DIÁK MEGJEGYZÉSE A FELISMERÉSI HIBÁRÓL:\n{diak_megjegyzes}")
    parts.append(JSON_SCHEMA_BLOCK)
    return "\n\n".join(parts)
