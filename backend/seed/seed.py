"""Seeding script: populate the library with a curated batch of well-known
titles across every medium, running each through the full pipeline
(search -> pick top match -> LLM taste profile -> embed -> store).

Safe to interrupt (Ctrl+C) and re-run: progress is persisted to
seed_progress.json next to this file, and already-completed titles are
skipped on the next run. Failed titles are retried automatically next run.

Usage (from the backend/ directory, with the venv activated):
    python -m seed.seed                      # seed every configured medium
    python -m seed.seed --medium movie        # just one medium (repeatable)
    python -m seed.seed --medium movie --medium tv
    python -m seed.seed --limit 20            # cap NEW items ingested per medium this run
    python -m seed.seed --retry-failed        # also retry items previously marked failed
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.db import Base, async_session_maker, engine
from app.pipeline import MEDIUM_TO_SOURCE, SOURCE_MODULES, ingest_item
from seed.titles import SEED_TITLES

PROGRESS_FILE = Path(__file__).resolve().parent / "seed_progress.json"

# Minimum gap between LLM calls. A local server has no rate limit (0.0); set
# LLM_MIN_INTERVAL_SECONDS in .env if a hosted provider throttles you.
LLM_MIN_INTERVAL_SECONDS = settings.llm_min_interval_seconds
# Be polite to the source APIs too, even though their limits are looser.
SOURCE_MIN_INTERVAL_SECONDS = 0.5

REQUIRED_SETTING_BY_SOURCE = {
    "tmdb": "tmdb_api_key",
    "anilist": None,  # no auth required
    "hardcover": "hardcover_api_token",
    "rawg": "rawg_api_key",
    "lastfm": "lastfm_api_key",
}


def _source_is_configured(source: str) -> bool:
    setting_name = REQUIRED_SETTING_BY_SOURCE.get(source)
    if setting_name is None:
        return True
    return bool(getattr(settings, setting_name, ""))


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {}


def save_progress(progress: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2, sort_keys=True))


def progress_key(medium: str, query: str) -> str:
    return f"{medium}::{query}"


async def ensure_schema() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def seed_medium(
    medium: str,
    queries: list[str],
    progress: dict,
    limit: int | None,
    retry_failed: bool,
    llm_last_call: list[float],
) -> tuple[int, int, int]:
    source = MEDIUM_TO_SOURCE[medium]
    if not _source_is_configured(source):
        print(f"[{medium}] SKIPPING entire medium — {source} key/token not set in .env")
        return (0, 0, len(queries))

    module = SOURCE_MODULES[source]
    done = failed = skipped = 0

    for query in queries:
        key = progress_key(medium, query)
        prior = progress.get(key)
        if prior and prior.get("status") == "done":
            skipped += 1
            continue
        if prior and prior.get("status") == "failed" and not retry_failed:
            skipped += 1
            continue

        if limit is not None and done >= limit:
            print(f"[{medium}] reached --limit {limit} new items, stopping this medium for this run")
            break

        try:
            results = await module.search(medium, query)
            await asyncio.sleep(SOURCE_MIN_INTERVAL_SECONDS)
            if not results:
                raise ValueError("no search results")
            top = results[0]

            elapsed = time.monotonic() - llm_last_call[0]
            if elapsed < LLM_MIN_INTERVAL_SECONDS:
                await asyncio.sleep(LLM_MIN_INTERVAL_SECONDS - elapsed)

            async with async_session_maker() as db:
                item = await ingest_item(db, medium, source, top.source_id)
            llm_last_call[0] = time.monotonic()

            progress[key] = {
                "status": "done",
                "item_id": item.id,
                "title": item.title,
                "year": item.year,
            }
            done += 1
            print(f"[{medium}] OK    {query!r} -> {item.title!r} ({item.year}) [id={item.id}]")

        except Exception as exc:  # noqa: BLE001 - seeding must survive per-item failures
            progress[key] = {"status": "failed", "error": str(exc)}
            failed += 1
            print(f"[{medium}] FAIL  {query!r}: {exc}")

        save_progress(progress)

    return done, failed, skipped


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--medium",
        action="append",
        choices=sorted(SEED_TITLES.keys()),
        help="Restrict to one or more mediums (repeatable). Default: all.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Cap NEW items ingested per medium this run.")
    parser.add_argument(
        "--retry-failed", action="store_true", help="Also retry titles previously marked failed."
    )
    args = parser.parse_args()

    mediums = args.medium or list(SEED_TITLES.keys())

    await ensure_schema()
    progress = load_progress()
    llm_last_call = [0.0]

    totals = {"done": 0, "failed": 0, "skipped": 0}
    for medium in mediums:
        queries = SEED_TITLES.get(medium, [])
        if not queries:
            continue
        print(f"\n=== {medium} ({len(queries)} titles) ===")
        done, failed, skipped = await seed_medium(medium, queries, progress, args.limit, args.retry_failed, llm_last_call)
        totals["done"] += done
        totals["failed"] += failed
        totals["skipped"] += skipped

    print(
        f"\nSeed run complete. newly ingested={totals['done']} "
        f"failed={totals['failed']} skipped(already done or previously failed)={totals['skipped']}"
    )
    print(f"Progress saved to {PROGRESS_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
