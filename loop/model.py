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

The endpoint also accepts an OpenAI-style `tools` array (see `loop.tools`):
if the model's response carries `tool_calls` instead of final content, we
run `loop.tools.call_tool` for each one, feed the results back as `tool`
messages, and re-ask — so the model can pull fresh trial/FDA/news/price data
mid-classification rather than judging on the headline alone.

Env:
    AKASH_MODEL_URL   e.g. https://<akash-lease>.akash.network   (blank = off)
    AKASH_MODEL_NAME  e.g. llama-3.1-8b-instruct
"""

import json
import os

import httpx

from loop import tools as loop_tools

ALLOWED_TYPES = {
    "phase3_readout_positive",
    "new_indication_sleep_apnea",
    "approval",
    "rx_volume",
}

_URL = os.getenv("AKASH_MODEL_URL", "").rstrip("/")
_MODEL = os.getenv("AKASH_MODEL_NAME", "llama-3.1-8b-instruct")
_MAX_TOOL_ROUNDS = 4

_PROMPT = (
    "You classify GLP-1 / weight-loss drug market catalysts. "
    "You may call the provided tools if you need fresher trial, FDA, news, "
    "or price data before deciding. "
    "Once you're done, reply with EXACTLY ONE of these labels and nothing "
    "else: " + ", ".join(sorted(ALLOWED_TYPES))
    + ".\nHeadline: {headline}"
)


def enabled() -> bool:
    return bool(_URL)


def _chat_with_tools(messages, max_rounds=_MAX_TOOL_ROUNDS):
    """Round-trip chat-completions, executing any `tool_calls` in between.

    Returns the final message's `content` string, or None if the model never
    settles on plain content within `max_rounds`.
    """
    for _ in range(max_rounds):
        r = httpx.post(
            f"{_URL}/v1/chat/completions",
            json={
                "model": _MODEL,
                "temperature": 0,
                "max_tokens": 16,
                "messages": messages,
                "tools": loop_tools.TOOLS,
            },
            timeout=4.0,
        )
        r.raise_for_status()
        message = r.json()["choices"][0]["message"]
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return message.get("content", "").strip()

        messages.append(message)
        for call in tool_calls:
            fn = call["function"]
            args = json.loads(fn.get("arguments") or "{}")
            try:
                result = loop_tools.call_tool(fn["name"], args)
            except Exception as exc:
                result = {"error": str(exc)}
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result),
            })
    return None


def classify(catalyst: dict):
    """Return (chosen_type, source_label).

    source_label is 'akash-model' when the hosted model decided, else
    'deterministic' — the loop logs this so the judges can see the model fired.
    """
    declared = catalyst.get("type")
    if not _URL:
        return declared, "deterministic"
    try:
        messages = [
            {"role": "user",
             "content": _PROMPT.format(headline=catalyst.get("headline", ""))},
        ]
        answer = _chat_with_tools(messages)
        if answer in ALLOWED_TYPES:
            return answer, "akash-model"
    except Exception:
        pass  # any failure -> deterministic fallback, demo never breaks
    return declared, "deterministic"
