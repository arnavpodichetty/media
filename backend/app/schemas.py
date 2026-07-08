from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Medium = Literal["movie", "tv", "book", "anime", "manga", "game", "music"]
Pacing = Literal["slow-burn", "moderate", "fast-paced"]

# Hard cap for the user-facing logline. The LLM can't be fully trusted to obey
# "one sentence", so we enforce it in code (see the validator below) as a
# safety net. ~160 chars comfortably fits one sentence without allowing a
# runaway paragraph.
_LOGLINE_MAX_CHARS = 160


class TasteProfile(BaseModel):
    """The core cross-medium comparison schema. The LLM generates one of these
    for every item, regardless of medium, so a book and an album can be
    compared on equal footing."""

    title: str
    medium: Medium
    logline: str = Field(
        description=(
            "A SINGLE concise sentence (max ~25 words / 160 characters) stating the premise/subject, "
            "grounded in the source description. Human-facing — it is shown in the UI. "
            "Never a paragraph, never multiple sentences. Do NOT list genres or tags; for music (no plot), "
            "briefly describe the sound/subject instead."
        )
    )
    mood: list[str] = Field(description="3-6 adjectives, e.g. melancholic, tense, whimsical, cozy.")
    themes: list[str] = Field(description="3-6 short phrases, e.g. found family, loss of innocence.")
    pacing: Pacing
    tone: str = Field(description="Short phrase, e.g. 'wry and understated'.")
    emotional_arc: str = Field(description="One sentence describing the emotional shape/journey.")
    aesthetic: list[str] = Field(description="2-4 phrases, e.g. 'muted color palette', 'lush prose'.")
    comparable_to: list[str] = Field(description="2-3 well-known other works, any medium, with a similar vibe.")
    embedding_text: str = Field(
        description=(
            "Exactly 4-5 sentences (roughly 90-130 words) as a single flowing natural-language paragraph "
            "that synthesizes mood, themes, pacing, tone, emotional arc, and aesthetic. NOT a tag list. "
            "This is embedded for similarity search (not shown to users), so keep the length consistent "
            "across every item regardless of how much source metadata was available."
        )
    )

    @field_validator("logline")
    @classmethod
    def _clamp_logline(cls, v: str) -> str:
        """Safety net: the grammar can't enforce prose length, so if the model
        returns a paragraph we keep only the first sentence and hard-cap the
        length. Keeps the UI clean even when the model misbehaves."""
        text = " ".join((v or "").split())  # collapse whitespace/newlines
        # Keep only the first sentence (split on the first ., ! or ?).
        for i, ch in enumerate(text):
            if ch in ".!?":
                text = text[: i + 1]
                break
        if len(text) > _LOGLINE_MAX_CHARS:
            text = text[:_LOGLINE_MAX_CHARS].rstrip() + "…"
        return text


class SearchResult(BaseModel):
    source: str
    source_id: str
    title: str
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None
    already_ingested: bool = False


class IngestRequest(BaseModel):
    medium: Medium
    source: str
    source_id: str


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    medium: str
    source: str
    source_id: str
    title: str
    year: int | None
    poster_url: str | None
    logline: str
    mood: list[str]
    themes: list[str]
    pacing: str
    tone: str
    emotional_arc: str
    aesthetic: list[str]
    comparable_to: list[str]
    embedding_text: str
    created_at: datetime


class RecommendRequest(BaseModel):
    item_id: int
    limit: int = 10
    candidate_pool_size: int = 30


class RecommendationOut(BaseModel):
    item: ItemOut
    why_this_matches: str
    rank: int
    vector_distance: float


class RecommendResponse(BaseModel):
    seed: ItemOut
    recommendations: list[RecommendationOut]
    reranked: bool  # False means LLM re-ranking failed and we fell back to raw vector order
