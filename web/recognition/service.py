import base64
import mimetypes

import requests

from .providers import get_ocr_model


SYSTEM_PROMPT = """
You are a mathematical handwriting transcription system.

Transcribe only the content that is actually visible in the image.

Do not:
- solve the task;
- correct the solution;
- explain it;
- evaluate it;
- complete missing content;
- invent missing content.

Return mathematical expressions using Markdown + LaTeX.

Preserve the order of the student's steps.

Your response must contain only the transcription.
"""


def image_to_data_url(image_field):
    image_field.open("rb")

    try:
        image_bytes = image_field.read()
    finally:
        image_field.close()

    mime_type, _ = mimetypes.guess_type(
        image_field.name
    )

    if mime_type is None:
        mime_type = "image/jpeg"

    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    return (
        f"data:{mime_type};base64,{encoded}"
    )


def recognise_solution(
    image_field,
    task_text,
):
    model = get_ocr_model()

    prompt = f"""
The image contains a handwritten student solution.

The corresponding task is:

--- TASK ---
{task_text}
--- END TASK ---

The task is context only.

Transcribe only the student's handwritten solution visible in the image.

Do not include the task text in the transcription.
"""

    payload = {
        "model": model["name"],
        "temperature": 0,
        "max_tokens": 4096,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_to_data_url(
                                image_field
                            )
                        },
                    },
                ],
            },
        ],
    }

    if "reasoning_effort" in model:
        payload["reasoning_effort"] = (
            model["reasoning_effort"]
        )

    response = requests.post(
        model["url"],
        headers={
            "Authorization": (
                f"Bearer {model['key']}"
            ),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )

    response.raise_for_status()

    data = response.json()

    content = (
        data["choices"][0]["message"]
        .get("content")
    )

    if not content:
        raise RuntimeError(
            "OCR model returned an empty response."
        )

    return {
        "text": content.strip(),
        "model_name": model["name"],
        "model_key": model["key_name"],
    }