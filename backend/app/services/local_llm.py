"""LLM backend for taste-profile generation and recommendation re-ranking,
talking to any OpenAI-compatible chat-completions endpoint over HTTP — a
local server (llama.cpp's llama-server, Ollama, LM Studio) or a hosted API
(Groq, DeepSeek, OpenRouter, ...).

Structured output is requested via the OpenAI `response_format` /
`json_schema` mechanism, which llama-server enforces with a GBNF grammar
derived from the schema — so the model is constrained to emit exactly the
JSON shape we expect."""

import json
import logging

import httpx

from app.config import settings
from app.schemas import TasteProfile
from app.services._llm_shared import (
    RERANK_SYSTEM_INSTRUCTION,
    TASTE_SYSTEM_INSTRUCTION,
    RerankedItem,
    RerankResult,
    build_rerank_prompt,
    build_taste_prompt,
    filter_reranked,
)

logger = logging.getLogger(__name__)

# Local generation of a big structured JSON can take a while, especially on
# the first call while the model is still warming up / loading into VRAM.
_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


async def _chat_json(system: str, user: str, schema_name: str, schema: dict, temperature: float) -> dict:
    payload = {
        "model": settings.local_llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        },
        # Qwen3.x are hybrid reasoning models; the "thinking" phase burns a lot
        # of tokens/latency and adds nothing when the output is already schema-
        # constrained JSON. Disabling it makes generation several times faster.
        # (Ignored by non-Qwen templates, so harmless for other local models.)
        "chat_template_kwargs": {"enable_thinking": False},
    }

    url = settings.local_llm_base_url.rstrip("/") + "/chat/completions"
    headers = {}
    if settings.local_llm_api_key:
        headers["Authorization"] = f"Bearer {settings.local_llm_api_key}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


async def generate_taste_profile(medium: str, title: str, raw_metadata: dict) -> TasteProfile:
    parsed = await _chat_json(
        system=TASTE_SYSTEM_INSTRUCTION,
        user=build_taste_prompt(medium, title, raw_metadata),
        schema_name="TasteProfile",
        schema=TasteProfile.model_json_schema(),
        # Lower temperature keeps output length/format consistent across items
        # (higher values were producing wildly varying logline/embedding lengths).
        temperature=0.3,
    )
    return TasteProfile.model_validate(parsed)


async def rerank_candidates(
    seed_profile: dict, candidates: list[dict], top_k: int = 10
) -> list[RerankedItem] | None:
    """Rerank candidates via the LLM. Returns None on any failure so the
    caller falls back to raw vector-similarity order."""
    try:
        parsed = await _chat_json(
            system=RERANK_SYSTEM_INSTRUCTION,
            user=build_rerank_prompt(seed_profile, candidates, top_k),
            schema_name="RerankResult",
            schema=RerankResult.model_json_schema(),
            temperature=0.3,
        )
        result = RerankResult.model_validate(parsed)
    except Exception:
        logger.exception("LLM re-ranking failed; caller will fall back to vector order")
        return None

    filtered = filter_reranked(result, candidates)
    return filtered[:top_k] if filtered else None
