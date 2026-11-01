"""Which models can this API key actually call?

Run:  python web/manage.py shell -c "exec(open('dev_models.py', encoding='utf-8').read())"
"""

import json
import urllib.request

from motor.config import settings

request = urllib.request.Request(
    settings.base_url.rstrip("/") + "/models",
    headers={"Authorization": f"Bearer {settings.api_key}"},
)

with urllib.request.urlopen(request, timeout=60) as answer:
    ids = sorted(model["id"] for model in json.load(answer)["data"])

print(len(ids), "elérhető modell")
print("\nbeállítva most:")
print(
    "  grading:", settings.grading_model, "->", "OK" if settings.grading_model in ids else "NINCS A LISTÁBAN"
)
print("  ocr:    ", settings.ocr_model, "->", "OK" if settings.ocr_model in ids else "NINCS A LISTÁBAN")

print("\nképet is értő modellek:")
for model_id in ids:
    if "vl" in model_id.lower() or "vision" in model_id.lower():
        print("   ", model_id)

print("\nszöveges jelöltek:")
for model_id in ids:
    if any(word in model_id.lower() for word in ("nemotron", "llama-3.3", "gpt-oss", "qwen", "mistral")):
        print("   ", model_id)
