"""Shared prompt text, structured-output schemas, and helpers for the LLM
backend. Kept separate from transport so prompts/schemas live in one place."""

import json

from pydantic import BaseModel, Field

TASTE_SYSTEM_INSTRUCTION = """You are a media taste-profiling engine for a cross-medium \
recommendation system (movies, TV, books, anime, manga, games, music all compared \
side by side). Given raw metadata for one piece of media, produce a standardized \
"taste profile" that captures its mood, themes, pacing, tone, and aesthetic in a \
medium-agnostic way, so it can be meaningfully compared to works in totally \
different mediums based on vibe rather than surface genre labels.

Be specific and avoid generic filler (e.g. prefer "quiet grief processed through \
routine" over "sad"). The embedding_text field is the most important output: write \
it as a flowing natural-language paragraph (not a tag list), since it is what gets \
embedded and compared for similarity search."""


RERANK_SYSTEM_INSTRUCTION = """You are the re-ranking stage of a cross-medium taste-based \
recommendation engine. You will be given a SEED item's taste profile and a list of CANDIDATE \
items (each may be a movie, tv show, anime, manga, book, game, or music album) with their own \
taste profiles.

Your job: select and rank the candidates that most genuinely share the seed's mood, themes, \
tone, and emotional arc — not surface genre or medium. Vector similarity search (which produced \
this candidate list) is sometimes fooled by superficial word overlap, so use your judgment to \
correct for that. When multiple candidates are close in quality, prefer a mix across different \
mediums rather than returning many of the same medium as the seed — the whole point of this \
system is cross-medium discovery. Never include the seed item itself. Only return item_ids that \
appear in the candidate list."""


class RerankedItem(BaseModel):
    item_id: int
    why_this_matches: str = Field(
        description="One specific sentence explaining why THIS candidate matches the seed item's "
        "mood/theme/tone/vibe — not a generic description of the candidate on its own."
    )


class RerankResult(BaseModel):
    recommendations: list[RerankedItem]


def build_taste_prompt(medium: str, title: str, raw_metadata: dict) -> str:
    return (
        f"Medium: {medium}\n"
        f"Title: {title}\n\n"
        f"Raw source metadata (JSON):\n{json.dumps(raw_metadata, ensure_ascii=False, indent=2)}\n\n"
        "Generate the taste profile now."
    )


def build_rerank_prompt(seed_profile: dict, candidates: list[dict], top_k: int) -> str:
    return (
        f"SEED ITEM:\n{json.dumps(seed_profile, ensure_ascii=False, indent=2)}\n\n"
        f"CANDIDATES:\n{json.dumps(candidates, ensure_ascii=False, indent=2)}\n\n"
        f"Select and rank the best {top_k} candidates (fewer is fine if fewer are genuinely good "
        "matches). Best match first."
    )


def filter_reranked(result: RerankResult, candidates: list[dict]) -> list[RerankedItem] | None:
    """Drop any hallucinated item_ids the model returned that aren't in the
    candidate pool. Returns None if nothing valid is left."""
    valid_ids = {c["item_id"] for c in candidates}
    filtered = [r for r in result.recommendations if r.item_id in valid_ids]
    return filtered or None
