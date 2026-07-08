"""AniList integration (GraphQL, no auth required): anime + manga search/details."""

import re

import httpx

from app.schemas import SearchResult

ANILIST_URL = "https://graphql.anilist.co"

MEDIUMS = {"anime", "manga"}
SOURCE_NAME = "anilist"

SEARCH_QUERY = """
query ($search: String, $type: MediaType, $perPage: Int) {
  Page(page: 1, perPage: $perPage) {
    media(search: $search, type: $type) {
      id
      title { romaji english native }
      startDate { year }
      coverImage { large }
      description(asHtml: false)
    }
  }
}
"""

DETAILS_QUERY = """
query ($id: Int) {
  Media(id: $id) {
    id
    title { romaji english native }
    description(asHtml: false)
    genres
    tags { name rank isMediaSpoiler }
    startDate { year }
    status
    format
    episodes
    chapters
    volumes
    averageScore
    studios(isMain: true) { nodes { name } }
    staff(perPage: 5) { edges { role node { name { full } } } }
    coverImage { large }
  }
}
"""


def _anilist_type(medium: str) -> str:
    return "ANIME" if medium == "anime" else "MANGA"


def _best_title(title_obj: dict) -> str:
    title_obj = title_obj or {}
    return title_obj.get("english") or title_obj.get("romaji") or title_obj.get("native") or "Untitled"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").replace("\n", " ").strip()


async def _post(query: str, variables: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(ANILIST_URL, json={"query": query, "variables": variables})
        resp.raise_for_status()
        payload = resp.json()
    if payload.get("errors"):
        raise RuntimeError(f"AniList error: {payload['errors']}")
    return payload["data"]


async def search(medium: str, query: str) -> list[SearchResult]:
    data = await _post(SEARCH_QUERY, {"search": query, "type": _anilist_type(medium), "perPage": 8})
    media_list = (data.get("Page") or {}).get("media") or []

    results = []
    for m in media_list:
        description = _strip_html(m.get("description") or "")
        results.append(
            SearchResult(
                source=SOURCE_NAME,
                source_id=str(m["id"]),
                title=_best_title(m.get("title")),
                year=(m.get("startDate") or {}).get("year"),
                poster_url=(m.get("coverImage") or {}).get("large"),
                overview=description[:500] or None,
            )
        )
    return results


async def get_details(medium: str, source_id: str) -> dict:
    data = await _post(DETAILS_QUERY, {"id": int(source_id)})
    return data["Media"]


def summarize_metadata(medium: str, details: dict) -> dict:
    tags = [t["name"] for t in (details.get("tags") or []) if not t.get("isMediaSpoiler")][:12]
    studios = [s["name"] for s in ((details.get("studios") or {}).get("nodes") or [])]
    staff = [
        f"{e['node']['name']['full']} ({e['role']})"
        for e in ((details.get("staff") or {}).get("edges") or [])
        if e.get("node")
    ]
    return {
        "title": _best_title(details.get("title")),
        "description": _strip_html(details.get("description") or ""),
        "genres": details.get("genres") or [],
        "tags": tags,
        "format": details.get("format"),
        "status": details.get("status"),
        "episodes": details.get("episodes"),
        "chapters": details.get("chapters"),
        "volumes": details.get("volumes"),
        "average_score": details.get("averageScore"),
        "studios": studios,
        "key_staff": staff,
        "start_year": (details.get("startDate") or {}).get("year"),
    }


def extract_display(medium: str, details: dict) -> tuple[str, int | None, str | None]:
    title = _best_title(details.get("title"))
    year = (details.get("startDate") or {}).get("year")
    poster_url = (details.get("coverImage") or {}).get("large")
    return title, year, poster_url
