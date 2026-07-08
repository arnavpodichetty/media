"""RAWG integration (REST, API key): games search/details."""

import re

import httpx

from app.config import settings
from app.schemas import SearchResult

BASE_URL = "https://api.rawg.io/api"
MEDIUMS = {"game"}
SOURCE_NAME = "rawg"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").replace("\n", " ").strip()


async def search(medium: str, query: str) -> list[SearchResult]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/games",
            params={"key": settings.rawg_api_key, "search": query, "page_size": 8},
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for r in data.get("results", []):
        released = r.get("released") or ""
        results.append(
            SearchResult(
                source=SOURCE_NAME,
                source_id=str(r["id"]),
                title=r.get("name") or "Untitled",
                year=int(released[:4]) if released[:4].isdigit() else None,
                poster_url=r.get("background_image"),
                overview=None,
            )
        )
    return results


async def get_details(medium: str, source_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/games/{source_id}", params={"key": settings.rawg_api_key})
        resp.raise_for_status()
        return resp.json()


def summarize_metadata(medium: str, details: dict) -> dict:
    genres = [g["name"] for g in details.get("genres", [])]
    tags = [t["name"] for t in (details.get("tags") or [])[:15]]
    platforms = [p["platform"]["name"] for p in (details.get("platforms") or []) if p.get("platform")]
    developers = [d["name"] for d in (details.get("developers") or [])]
    publishers = [p["name"] for p in (details.get("publishers") or [])]
    return {
        "title": details.get("name"),
        "description": _strip_html(details.get("description_raw") or details.get("description") or ""),
        "genres": genres,
        "tags": tags,
        "platforms": platforms,
        "developers": developers,
        "publishers": publishers,
        "released": details.get("released"),
        "metacritic": details.get("metacritic"),
        "esrb_rating": (details.get("esrb_rating") or {}).get("name"),
    }


def extract_display(medium: str, details: dict) -> tuple[str, int | None, str | None]:
    released = details.get("released") or ""
    year = int(released[:4]) if released[:4].isdigit() else None
    return details.get("name") or "Untitled", year, details.get("background_image")
