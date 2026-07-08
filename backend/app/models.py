from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.db import Base


class Item(Base):
    """A single piece of media, with its source metadata, LLM-generated taste
    profile, and embedding vector, all in one row so cross-medium similarity
    search is a single table scan/index lookup."""

    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_items_source_source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    medium: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # --- taste profile fields (see spec schema) ---
    logline: Mapped[str] = mapped_column(Text, nullable=False)
    mood: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    themes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    pacing: Mapped[str] = mapped_column(String(32), nullable=False)
    tone: Mapped[str] = mapped_column(String(256), nullable=False)
    emotional_arc: Mapped[str] = mapped_column(Text, nullable=False)
    aesthetic: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    comparable_to: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Item {self.medium}:{self.title!r} ({self.source}:{self.source_id})>"
