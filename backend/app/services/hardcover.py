"""Hardcover integration (GraphQL, beta, requires bearer token): books search/details.

The API is explicitly in beta and its schema may change without notice, so
every field access here goes through .get() with fallbacks rather than
assuming keys exist. Never expose the token to the browser — this module
only runs server-side.
"""

import json

import httpx

from app.config import settings
from app.schemas import SearchResult

BASE_URL = "https://api.hardcover.app/v1/graphql"
MEDIUMS = {"book"}
SOURCE_NAME = "hardcover"


def _auth_header() -> str:
    token = settings.hardcover_api_token.strip()
    return token if token.lower().startswith("bearer ") else f"Bearer {token}"


async def _post(query: str, variables: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            BASE_URL,
            json={"query": query, "variables": variables or {}},
            headers={"Authorization": _auth_header(), "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        payload = resp.json()
    if payload.get("errors"):
        raise RuntimeError(f"Hardcover error: {payload['errors']}")
    return payload.get("data") or {}


SEARCH_QUERY = """
query Search($q: String!) {
  search(query: $q, query_type: "Book", per_page: 8, page: 1) {
    results
  }
}
"""

DETAILS_QUERY = """
query BookDetails($id: Int!) {
  books(where: {id: {_eq: $id}}, limit: 1) {
    id
    title
    subtitle
    description
    release_date
    pages
    cached_tags
    cached_contributors
    rating
    image {
      url
    }
  }
}
"""


def _parse_results_blob(raw) -> list[dict]:
    """`results` is an opaque, typesense-shaped JSON blob. Be defensive about
    whether the GraphQL client already parsed it or handed back a string."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(raw, dict):
        return []
    hits = raw.get("hits") or []
    documents = []
    for hit in hits:
        doc = hit.get("document") if isinstance(hit, dict) else None
        if doc:
            documents.append(doc)
    return documents


async def search(medium: str, query: str) -> list[SearchResult]:
    data = await _post(SEARCH_QUERY, {"q": query})
    documents = _parse_results_blob((data.get("search") or {}).get("results"))

    results = []
    for doc in documents:
        book_id = doc.get("id")
        if book_id is None:
            continue
        image = doc.get("image")
        poster_url = image.get("url") if isinstance(image, dict) else None
        results.append(
            SearchResult(
                source=SOURCE_NAME,
                source_id=str(book_id),
                title=doc.get("title") or "Untitled",
                year=doc.get("release_year"),
                poster_url=poster_url,
                overview=doc.get("description"),
            )
        )
    return results


async def get_details(medium: str, source_id: str) -> dict:
    data = await _post(DETAILS_QUERY, {"id": int(source_id)})
    books = data.get("books") or []
    if not books:
        raise ValueError(f"Hardcover book id={source_id} not found")
    return books[0]


def _extract_genres(cached_tags) -> list[str]:
    if not isinstance(cached_tags, dict):
        return []
    genre_entries = cached_tags.get("Genre") or []
    return [g.get("tag") for g in genre_entries if isinstance(g, dict) and g.get("tag")][:8]


def _extract_authors(cached_contributors) -> list[str]:
    if not isinstance(cached_contributors, list):
        return []
    names = []
    for c in cached_contributors:
        author = c.get("author") if isinstance(c, dict) else None
        name = (author or {}).get("name") if isinstance(author, dict) else None
        if name:
            names.append(name)
    return names


def summarize_metadata(medium: str, details: dict) -> dict:
    return {
        "title": details.get("title"),
        "subtitle": details.get("subtitle"),
        "description": details.get("description"),
        "authors": _extract_authors(details.get("cached_contributors")),
        "genres": _extract_genres(details.get("cached_tags")),
        "pages": details.get("pages"),
        "release_date": details.get("release_date"),
        "rating": details.get("rating"),
    }


def extract_display(medium: str, details: dict) -> tuple[str, int | None, str | None]:
    release_date = details.get("release_date") or ""
    year = int(release_date[:4]) if release_date[:4].isdigit() else None
    image = details.get("image")
    poster_url = image.get("url") if isinstance(image, dict) else None
    return details.get("title") or "Untitled", year, poster_url
