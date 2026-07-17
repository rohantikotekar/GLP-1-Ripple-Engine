"""LOOP-ENG: the reasoning-model hook wired into the `act` step.

P3 hosts a model on Akash. This module lets the loop ask that model to
*classify / confirm* an incoming catalyst's type before the impact graph
propagates it. It is deliberately defensive:

  * If AKASH_MODEL_URL is unset OR the call errors/times out, we fall back to
    the catalyst's own declared `type`. The deterministic demo always fires.
  * The model can only ever return a type the impact graph understands; any
    other answer is ignored. This is a second guardrail alongside Pomerium.

Contract with P3 (OpenAI-compatible chat endpoint, e.g. vLLM/Ollama on Akash):
    POST {AKASH_MODEL_URL}/v1/chat/completions
    -> choices[0].message.content == one of ALLOWED_TYPES (bare string)

Env:
    AKASH_MODEL_URL   e.g. https://<akash-lease>.akash.network   (blank = off)
    AKASH_MODEL_NAME  e.g. llama-3.1-8b-instruct
"""

import os

import httpx

ALLOWED_TYPES = {
    "phase3_readout_positive",
    "new_indication_sleep_apnea",
    "approval",
    "rx_volume",
}

_URL = os.getenv("AKASH_MODEL_URL", "").rstrip("/")
_MODEL = os.getenv("AKASH_MODEL_NAME", "llama-3.1-8b-instruct")

_PROMPT = (
    "You classify GLP-1 / weight-loss drug market catalysts. "
    "Reply with EXACTLY ONE of these labels and nothing else: "
    + ", ".join(sorted(ALLOWED_TYPES))
    + ".\nHeadline: {headline}"
)


def enabled() -> bool:
    return bool(_URL)


def classify(catalyst: dict):
    """Return (chosen_type, source_label).

    source_label is 'akash-model' when the hosted model decided, else
    'deterministic' — the loop logs this so the judges can see the model fired.
    """
    declared = catalyst.get("type")
    if not _URL:
        return declared, "deterministic"
    try:
        r = httpx.post(
            f"{_URL}/v1/chat/completions",
            json={
                "model": _MODEL,
                "temperature": 0,
                "max_tokens": 16,
                "messages": [
                    {"role": "user",
                     "content": _PROMPT.format(headline=catalyst.get("headline", ""))},
                ],
            },
            timeout=4.0,
        )
        r.raise_for_status()
        answer = r.json()["choices"][0]["message"]["content"].strip()
        if answer in ALLOWED_TYPES:
            return answer, "akash-model"
    except Exception:
        pass  # any failure -> deterministic fallback, demo never breaks
    return declared, "deterministic"
