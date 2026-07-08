"""Local embedding generation via sentence-transformers. Runs on CPU, no API key."""

import asyncio
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def embed_text_sync(text: str) -> list[float]:
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


async def embed_text(text: str) -> list[float]:
    """Model inference is blocking/CPU-bound; run off the event loop."""
    return await asyncio.to_thread(embed_text_sync, text)
