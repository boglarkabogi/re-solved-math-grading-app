"""How fast do the candidate models answer a real grading request?

Run:  python web/manage.py shell -c "exec(open('dev_try_models.py', encoding='utf-8').read())"
"""

import time

from openai import OpenAI

from motor.config import settings

# Egyetlen próbálkozás, rövid határidő. A motor újrapróbálkozó burkolóját
# szándékosan kerüljük: itt pont az a kérdés, mi fér bele elsőre.
TIMEOUT = 30
RUNS = 2

CANDIDATES = [
    "openai/gpt-oss-20b",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-nano-3-30b-a3b",
    "nvidia/llama-3.1-nemotron-51b-instruct",
    "mistralai/mistral-large-2-instruct",
    "nvidia/nemotron-3-ultra-550b-a55b",
]

# Valódi munka: feladat, referenciamegoldás, diákmegoldás, JSON-válasz.
PROMPT = (
    "Feladat: Mennyi lnko(213, 200)?\n"
    "Helyes megoldás: euklideszi algoritmussal lnko(213, 200) = 1\n"
    "A diák megoldása:\n"
    "213 = 1*200 + 13\n200 = 15*13 + 5\n13 = 2*5 + 3\n5 = 1*3 + 2\n"
    "3 = 1*2 + 1\n2 = 2*1 + 0\ntehát 1 a legnagyobb közös osztójuk\n\n"
    'Értékeld. Válaszolj JSON-ban: {"pont": 0|0.25|0.5|0.75|1, "indoklas": "..."}'
)

client = OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=TIMEOUT, max_retries=0)

print(f"{'modell':<48} {'1.':>7} {'2.':>7}  válasz")
print("-" * 100)

results = []

for model in CANDIDATES:
    times = []
    note = ""
    ok = False

    for _ in range(RUNS):
        started = time.monotonic()

        try:
            answer = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": PROMPT}],
                response_format={"type": "json_object"},
            )
        except Exception as error:
            times.append(None)
            note = f"{type(error).__name__}: {str(error).splitlines()[0][:60]}"
            break

        times.append(time.monotonic() - started)
        text = (answer.choices[0].message.content or "").strip()
        ok = text.startswith("{") and "pont" in text
        note = text[:60].replace("\n", " ")

    shown = [f"{t:7.1f}" if t is not None else "      –" for t in times]
    shown += ["      –"] * (RUNS - len(shown))

    print(f"{model:<48} {shown[0]} {shown[1]}  {note}")

    if ok and all(t is not None for t in times):
        results.append((max(times), model))

print("\nHasználható, a lassabbik futás szerint:")

for seconds, model in sorted(results):
    print(f"  {seconds:6.1f} mp  {model}")

if not results:
    print("  egy sem – 30 másodpercen belül ez a végpont nem ad használható JSON-t")