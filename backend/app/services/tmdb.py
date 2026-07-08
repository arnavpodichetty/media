"""TMDB (The Movie Database) integration: search + full detail fetch for movies and TV."""

import httpx

from app.config import settings
from app.schemas import SearchResult

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w342"

MEDIUMS = {"movie", "tv"}
SOURCE_NAME = "tmdb"


def _endpoint_type(medium: str) -> str:
    return "movie" if medium == "movie" else "tv"


async def search(medium: str, query: str) -> list[SearchResult]:
    endpoint_type = _endpoint_type(medium)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/search/{endpoint_type}",
            params={"api_key": settings.tmdb_api_key, "query": query, "include_adult": "false"},
        )
        resp.raise_for_status()
        data = resp.json()

    results: list[SearchResult] = []
    for r in data.get("results", [])[:8]:
        title = r.get("title") if endpoint_type == "movie" else r.get("name")
        date_field = (r.get("release_date") if endpoint_type == "movie" else r.get("first_air_date")) or ""
        results.append(
            SearchResult(
                source=SOURCE_NAME,
                source_id=str(r["id"]),
                title=title or "Untitled",
                year=int(date_field[:4]) if date_field[:4].isdigit() else None,
                poster_url=f"{IMAGE_BASE}{r['poster_path']}" if r.get("poster_path") else None,
                overview=r.get("overview"),
            )
        )
    return results


async def get_details(medium: str, source_id: str) -> dict:
    endpoint_type = _endpoint_type(medium)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/{endpoint_type}/{source_id}",
            params={"api_key": settings.tmdb_api_key, "append_to_response": "keywords,credits"},
        )
        resp.raise_for_status()
        details = resp.json()
    details["_medium"] = medium
    return details


def summarize_metadata(medium: str, details: dict) -> dict:
    endpoint_type = _endpoint_type(medium)
    if endpoint_type == "movie":
        keywords = [k["name"] for k in details.get("keywords", {}).get("keywords", [])]
        title = details.get("title")
        date_field = details.get("release_date")
        runtime = details.get("runtime")
        number_of_seasons = None
    else:
        # TMDB's TV keyword payload shape differs from movies: {"results": [...]}.
        keywords = [k["name"] for k in details.get("keywords", {}).get("results", [])]
        title = details.get("name")
        date_field = details.get("first_air_date")
        runtime = (details.get("episode_run_time") or [None])[0]
        number_of_seasons = details.get("number_of_seasons")

    genres = [g["name"] for g in details.get("genres", [])]
    cast = [c["name"] for c in details.get("credits", {}).get("cast", [])[:6]]
    directors = [c["name"] for c in details.get("credits", {}).get("crew", []) if c.get("job") == "Director"]

    return {
        "title": title,
        "release_date": date_field,
        "overview": details.get("overview"),
        "genres": genres,
        "keywords": keywords,
        "runtime_minutes": runtime,
        "number_of_seasons": number_of_seasons,
        "directors": directors,
        "cast": cast,
        "tagline": details.get("tagline"),
        "vote_average": details.get("vote_average"),
    }


def extract_display(medium: str, details: dict) -> tuple[str, int | None, str | None]:
    endpoint_type = _endpoint_type(medium)
    title = details.get("title") if endpoint_type == "movie" else details.get("name")
    date_field = (details.get("release_date") if endpoint_type == "movie" else details.get("first_air_date")) or ""
    year = int(date_field[:4]) if date_field[:4].isdigit() else None
    poster_path = details.get("poster_path")
    poster_url = f"{IMAGE_BASE}{poster_path}" if poster_path else None
    return title or "Untitled", year, poster_url
