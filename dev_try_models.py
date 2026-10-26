"""Which candidate models does this account actually get an answer from?

Run:  python web/manage.py shell -c "exec(open('dev_probe.py', encoding='utf-8').read())"
"""

from motor import llm

CANDIDATES = [
    "openai/gpt-oss-20b",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-nano-3-30b-a3b",
    "nvidia/llama-3.1-nemotron-51b-instruct",
    "mistralai/mistral-large-2-instruct",
    "nvidia/nemotron-3-ultra-550b-a55b",
]

messages = [{"role": "user", "content": "Csak ennyit válaszolj: OK"}]

for model in CANDIDATES:
    try:
        answer = llm.chat(messages, model)
    except Exception as error:
        first_line = str(error).split("\n")[0][:120]
        print(f"  NEM   {model}\n        {first_line}")
    else:
        print(f"  MEGY  {model} -> {answer[:40]!r}")
