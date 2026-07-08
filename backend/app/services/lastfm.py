"""Last.fm integration (REST, API key): music (album-level) search/details.

Last.fm has no stable numeric ID for albums, so we build a composite
source_id out of "Artist Name" + separator + "Album Name" and split it back
apart when fetching details.
"""

import re

import httpx

from app.config import settings
from app.schemas import SearchResult

BASE_URL = "https://ws.audioscrobbler.com/2.0/"
MEDIUMS = {"music"}
SOURCE_NAME = "lastfm"

_SEPARATOR = "::"


def make_source_id(artist: str, album: str) -> str:
    return f"{artist}{_SEPARATOR}{album}"


def _split_source_id(source_id: str) -> tuple[str, str]:
    artist, _, album = source_id.partition(_SEPARATOR)
    return artist, album


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").replace("\n", " ").strip()


def _best_image(images: list[dict]) -> str | None:
    for img in reversed(images or []):
        url = img.get("#text")
        if url:
            return url
    return None


async def search(medium: str, query: str) -> list[SearchResult]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            BASE_URL,
            params={
                "method": "album.search",
                "album": query,
                "api_key": settings.lastfm_api_key,
                "format": "json",
                "limit": 8,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    matches = ((data.get("results") or {}).get("albummatches") or {}).get("album") or []
    results = []
    for m in matches:
        results.append(
            SearchResult(
                source=SOURCE_NAME,
                source_id=make_source_id(m["artist"], m["name"]),
                title=f"{m['name']} \u2014 {m['artist']}",
                year=None,
                poster_url=_best_image(m.get("image") or []),
                overview=None,
            )
        )
    return results


async def get_details(medium: str, source_id: str) -> dict:
    artist, album = _split_source_id(source_id)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            BASE_URL,
            params={
                "method": "album.getinfo",
                "artist": artist,
                "album": album,
                "api_key": settings.lastfm_api_key,
                "format": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    album_data = data.get("album")
    if not album_data:
        raise ValueError(f"Last.fm album not found for {artist!r} / {album!r}")
    return album_data


def summarize_metadata(medium: str, details: dict) -> dict:
    tags = [t["name"] for t in ((details.get("tags") or {}).get("tag") or [])]
    tracks = [t["name"] for t in ((details.get("tracks") or {}).get("track") or [])][:15]
    wiki_summary = _strip_html((details.get("wiki") or {}).get("summary") or "")
    return {
        "title": details.get("name"),
        "artist": details.get("artist"),
        "tags": tags,
        "track_list": tracks,
        "listeners": details.get("listeners"),
        # Keyed as "description" across every source for consistency. Albums
        # often have no wiki text; when empty the LLM describes the sound from
        # the tags/tracklist per the logline instructions.
        "description": wiki_summary,
    }


def extract_display(medium: str, details: dict) -> tuple[str, int | None, str | None]:
    title = f"{details.get('name', 'Untitled')} \u2014 {details.get('artist', '')}".strip(" \u2014")
    poster_url = _best_image(details.get("image") or [])
    return title, None, poster_url
