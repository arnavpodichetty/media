from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Medium = Literal["movie", "tv", "book", "anime", "manga", "game", "music"]
Pacing = Literal["slow-burn", "moderate", "fast-paced"]


class TasteProfile(BaseModel):
    """The core cross-medium comparison schema. The LLM generates one of these
    for every item, regardless of medium, so a book and an album can be
    compared on equal footing."""

    title: str
    medium: Medium
    logline: str = Field(description="One neutral sentence describing what it's about.")
    mood: list[str] = Field(description="3-6 adjectives, e.g. melancholic, tense, whimsical, cozy.")
    themes: list[str] = Field(description="3-6 short phrases, e.g. found family, loss of innocence.")
    pacing: Pacing
    tone: str = Field(description="Short phrase, e.g. 'wry and understated'.")
    emotional_arc: str = Field(description="One sentence describing the emotional shape/journey.")
    aesthetic: list[str] = Field(description="2-4 phrases, e.g. 'muted color palette', 'lush prose'.")
    comparable_to: list[str] = Field(description="2-3 well-known other works, any medium, with a similar vibe.")
    embedding_text: str = Field(
        description="A 3-5 sentence flowing natural-language paragraph combining all of the above. This is what gets embedded."
    )


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
