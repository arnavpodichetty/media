from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Item
from app.pipeline import ingest_item, module_for_medium, recommend, search_medium
from app.schemas import IngestRequest, ItemOut, Medium, RecommendRequest, RecommendResponse, SearchResult

router = APIRouter()


@router.get("/search", response_model=list[SearchResult])
async def search(medium: Medium, query: str, db: AsyncSession = Depends(get_db)):
    if not query.strip():
        raise HTTPException(400, detail="query must not be empty")

    try:
        module_for_medium(medium)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    try:
        return await search_medium(medium, query, db)
    except Exception as exc:
        raise HTTPException(502, detail=f"search failed: {exc}") from exc


@router.post("/ingest", response_model=ItemOut)
async def ingest(payload: IngestRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await ingest_item(db, payload.medium, payload.source, payload.source_id)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, detail=f"ingest failed: {exc}") from exc


@router.get("/items", response_model=list[ItemOut])
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).order_by(Item.created_at.desc()))
    return result.scalars().all()


@router.post("/recommend", response_model=RecommendResponse)
async def recommend_endpoint(payload: RecommendRequest, db: AsyncSession = Depends(get_db)):
    try:
        seed, recommendations, reranked = await recommend(
            db, payload.item_id, payload.limit, payload.candidate_pool_size
        )
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, detail=f"recommend failed: {exc}") from exc
    return RecommendResponse(seed=seed, recommendations=recommendations, reranked=reranked)


@router.get("/recommend/{item_id}", response_model=RecommendResponse)
async def recommend_get(item_id: int, limit: int = 10, candidate_pool_size: int = 30, db: AsyncSession = Depends(get_db)):
    try:
        seed, recommendations, reranked = await recommend(db, item_id, limit, candidate_pool_size)
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, detail=f"recommend failed: {exc}") from exc
    return RecommendResponse(seed=seed, recommendations=recommendations, reranked=reranked)
