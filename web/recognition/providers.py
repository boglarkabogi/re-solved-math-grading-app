import os


OCR_MODELS = {
    "dots": {
        "name": "dots-studio/dots-3-note-preview:free",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "api_key_env": "OPENROUTER_API_KEY",
    },

    "kimi": {
        "name": "moonshotai/kimi-k3",
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "api_key_env": "LLM_API_KEY",
        "reasoning_effort": "low",
    },

    "qwen": {
        "name": "Qwen/Qwen2.5-VL-72B-Instruct:ovhcloud",
        "url": "https://router.huggingface.co/v1/chat/completions",
        "api_key_env": "HF_KEY",
    },

    "llama": {
        "name": "meta/llama-3.2-11b-vision-instruct",
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "api_key_env": "LLM_API_KEY",
    },
}


def get_ocr_model():
    model_key = os.getenv("OCR_MODEL", "kimi")

    if model_key not in OCR_MODELS:
        raise RuntimeError(
            f"Unknown OCR model: {model_key}"
        )

    config = OCR_MODELS[model_key].copy()

    api_key = os.getenv(
        config["api_key_env"]
    )

    if not api_key:
        raise RuntimeError(
            f"Missing API key: {config['api_key_env']}"
        )

    config["key"] = api_key
    config["key_name"] = model_key

    return config