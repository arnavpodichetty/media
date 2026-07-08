"""Shared ingest + recommendation pipeline. Used by both HTTP endpoints and
the standalone seed script, so there's exactly one implementation of each
flow."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item
from app.schemas import RecommendationOut, SearchResult
from app.services import anilist, hardcover, lastfm, llm, rawg, tmdb
from app.services.embeddings import embed_text

# Every source module implements the same shape:
#   async def search(medium, query) -> list[SearchResult]
#   async def get_details(medium, source_id) -> dict (raw provider payload)
#   def summarize_metadata(medium, details) -> dict (trimmed, sent to the LLM)
#   def extract_display(medium, details) -> (title, year, poster_url)
SOURCE_MODULES = {
    "tmdb": tmdb,
    "anilist": anilist,
    "hardcover": hardcover,
    "rawg": rawg,
    "lastfm": lastfm,
}

MEDIUM_TO_SOURCE = {
    "movie": "tmdb",
    "tv": "tmdb",
    "anime": "anilist",
    "manga": "anilist",
    "book": "hardcover",
    "game": "rawg",
    "music": "lastfm",
}


def module_for_medium(medium: str):
    source = MEDIUM_TO_SOURCE.get(medium)
    if source is None:
        raise ValueError(f"Unsupported medium: {medium}")
    return source, SOURCE_MODULES[source]


async def search_medium(medium: str, query: str, db: AsyncSession) -> list[SearchResult]:
    source, module = module_for_medium(medium)
    results = await module.search(medium, query)

    if results:
        existing = await db.execute(
            select(Item.source_id).where(
                Item.source == source, Item.source_id.in_([r.source_id for r in results])
            )
        )
        ingested_ids = {row[0] for row in existing.all()}
        for r in results:
            r.already_ingested = r.source_id in ingested_ids

    return results


async def ingest_item(db: AsyncSession, medium: str, source: str, source_id: str) -> Item:
    expected_source, module = module_for_medium(medium)
    if source != expected_source:
        raise ValueError(f"medium={medium!r} must be ingested with source={expected_source!r}")

    existing = await db.scalar(select(Item).where(Item.source == source, Item.source_id == source_id))
    if existing is not None:
        return existing

    details = await module.get_details(medium, source_id)
    raw_metadata = module.summarize_metadata(medium, details)
    title, year, poster_url = module.extract_display(medium, details)

    profile = await llm.generate_taste_profile(medium, title, raw_metadata)
    vector = await embed_text(profile.embedding_text)

    item = Item(
        medium=medium,
        source=source,
        source_id=source_id,
        title=title,
        year=year,
        poster_url=poster_url,
        raw_metadata=raw_metadata,
        logline=profile.logline,
        mood=profile.mood,
        themes=profile.themes,
        pacing=profile.pacing,
        tone=profile.tone,
        emotional_arc=profile.emotional_arc,
        aesthetic=profile.aesthetic,
        comparable_to=profile.comparable_to,
        embedding_text=profile.embedding_text,
        embedding=vector,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


def _profile_dict(item: Item, include_id: bool = False) -> dict:
    """The medium-agnostic taste-profile fields, shaped for an LLM prompt."""
    d = {
        "title": item.title,
        "medium": item.medium,
        "logline": item.logline,
        "mood": item.mood,
        "themes": item.themes,
        "pacing": item.pacing,
        "tone": item.tone,
        "emotional_arc": item.emotional_arc,
        "aesthetic": item.aesthetic,
    }
    if include_id:
        d = {"item_id": item.id, **d}
    return d


async def vector_candidates(db: AsyncSession, seed: Item, pool_size: int) -> list[tuple[Item, float]]:
    """Top `pool_size` items by cosine distance to the seed, excluding the seed itself."""
    distance = Item.embedding.cosine_distance(seed.embedding).label("distance")
    stmt = select(Item, distance).where(Item.id != seed.id).order_by(distance).limit(pool_size)
    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def recommend(db: AsyncSession, item_id: int, limit: int, candidate_pool_size: int):
    """Returns (seed_item, list[RecommendationOut], reranked: bool)."""
    seed = await db.get(Item, item_id)
    if seed is None:
        raise ValueError(f"No item with id={item_id}")

    candidates = await vector_candidates(db, seed, candidate_pool_size)
    if not candidates:
        return seed, [], False

    distance_by_id = {item.id: distance for item, distance in candidates}
    items_by_id = {item.id: item for item, _ in candidates}

    reranked_list = await llm.rerank_candidates(
        seed_profile=_profile_dict(seed),
        candidates=[_profile_dict(item, include_id=True) for item, _ in candidates],
        top_k=limit,
    )

    recommendations: list[RecommendationOut] = []
    if reranked_list:
        for rank, entry in enumerate(reranked_list, start=1):
            item = items_by_id.get(entry.item_id)
            if item is None:
                continue
            recommendations.append(
                RecommendationOut(
                    item=item,
                    why_this_matches=entry.why_this_matches,
                    rank=rank,
                    vector_distance=distance_by_id[item.id],
                )
            )
        return seed, recommendations, True

    # Fallback: raw vector-similarity order, generic blurb.
    for rank, (item, distance) in enumerate(candidates[:limit], start=1):
        recommendations.append(
            RecommendationOut(
                item=item,
                why_this_matches="Ranked by embedding similarity (LLM re-ranking was unavailable).",
                rank=rank,
                vector_distance=distance,
            )
        )
    return seed, recommendations, False
