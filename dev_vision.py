"""Which vision models does this NVIDIA key actually answer with?

Run:  python web/manage.py shell -c "exec(open('dev_vision.py', encoding='utf-8').read())"
"""

import logging

logger = logging.getLogger(__name__)

import base64
import json
import urllib.error
import urllib.request

from motor.config import settings
from submissions.models import OcrAttempt

CANDIDATES = [
    "meta/llama-3.2-11b-vision-instruct",
    "google/paligemma",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "meta/llama-3.2-90b-vision-instruct",
    "microsoft/phi-3-vision-128k-instruct",
    "nvidia/nemotron-3.5-super-vl-120b-a12b",
    "meta/llama-3.2-11b-vision-instruct",
    "nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1",
    "nvidia/llama-nemotron-embed-vl-1b-v2"
]

attempt = OcrAttempt.objects.exclude(image="").last()
print("kép:", attempt.image.name)

attempt.image.open("rb")
try:
    encoded = base64.b64encode(attempt.image.read()).decode("utf-8")
finally:
    attempt.image.close()

for model in CANDIDATES:
    payload = {
        "model": model,
        "max_tokens": 32,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Írd le egy szóval, mit látsz."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
                ],
            }
        ],
    }

    request = urllib.request.Request(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as answer:
            text = json.load(answer)["choices"][0]["message"].get("content") or ""
        print(f"  MEGY  {model} -> {text.strip()[:50]!r}")
    except urllib.error.HTTPError as error:
        print(f"  NEM   {model}  HTTP {error.code}")
        print(f"        {error.read().decode('utf-8', 'replace')[:160]}")
    except Exception as error:
        print(f"  NEM   {model}  {type(error).__name__}: {error}")
