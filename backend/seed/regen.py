"""Regenerate taste profiles for items ALREADY in the database.

Use this after changing the taste-profile prompt/schema (e.g. tightening the
logline or embedding_text rules): it re-fetches each item's source metadata,
re-runs the LLM to produce a fresh taste profile, re-embeds it, and updates
the existing row in place — no new rows, ids are preserved.

Safe to interrupt (Ctrl+C) and re-run; each item is committed individually
and per-item failures are logged and skipped.

Usage (from backend/, venv activated):
    python -m seed.regen                     # regenerate every item
    python -m seed.regen --medium music       # only one medium (repeatable)
    python -m seed.regen --id 42 --id 43      # only specific item ids
    python -m seed.regen --from-cache         # reuse stored raw_metadata (no source API calls)
"""

import argparse
import asyncio
import time

from sqlalchemy import select

from app.config import settings
from app.db import async_session_maker
from app.models import Item
from app.pipeline import SOURCE_MODULES
from app.services import llm
from app.services.embeddings import embed_text

LLM_MIN_INTERVAL_SECONDS = settings.llm_min_interval_seconds
SOURCE_MIN_INTERVAL_SECONDS = 0.5


async def _regen_one(item: Item, from_cache: bool) -> None:
    module = SOURCE_MODULES[item.source]

    if from_cache:
        raw_metadata = item.raw_metadata
    else:
        details = await module.get_details(item.medium, item.source_id)
        raw_metadata = module.summarize_metadata(item.medium, details)
        await asyncio.sleep(SOURCE_MIN_INTERVAL_SECONDS)

    profile = await llm.generate_taste_profile(item.medium, item.title, raw_metadata)
    vector = await embed_text(profile.embedding_text)

    item.raw_metadata = raw_metadata
    item.logline = profile.logline
    item.mood = profile.mood
    item.themes = profile.themes
    item.pacing = profile.pacing
    item.tone = profile.tone
    item.emotional_arc = profile.emotional_arc
    item.aesthetic = profile.aesthetic
    item.comparable_to = profile.comparable_to
    item.embedding_text = profile.embedding_text
    item.embedding = vector


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--medium", action="append", help="Restrict to one or more mediums (repeatable).")
    parser.add_argument("--id", action="append", type=int, help="Restrict to specific item ids (repeatable).")
    parser.add_argument(
        "--from-cache",
        action="store_true",
        help="Reuse stored raw_metadata instead of re-fetching from the source API.",
    )
    args = parser.parse_args()

    async with async_session_maker() as db:
        stmt = select(Item).order_by(Item.id)
        if args.medium:
            stmt = stmt.where(Item.medium.in_(args.medium))
        if args.id:
            stmt = stmt.where(Item.id.in_(args.id))
        items = (await db.execute(stmt)).scalars().all()

        print(f"Regenerating {len(items)} item(s){' from cached metadata' if args.from_cache else ''}...\n")
        done = failed = 0
        llm_last_call = 0.0

        for item in items:
            try:
                elapsed = time.monotonic() - llm_last_call
                if elapsed < LLM_MIN_INTERVAL_SECONDS:
                    await asyncio.sleep(LLM_MIN_INTERVAL_SECONDS - elapsed)

                await _regen_one(item, args.from_cache)
                await db.commit()
                llm_last_call = time.monotonic()

                done += 1
                print(f"[{item.medium}] OK   id={item.id} {item.title!r}")
                print(f"           logline: {item.logline}")
            except Exception as exc:  # noqa: BLE001 - must survive per-item failures
                await db.rollback()
                failed += 1
                print(f"[{item.medium}] FAIL id={item.id} {item.title!r}: {exc}")

        print(f"\nRegen complete. updated={done} failed={failed}")


if __name__ == "__main__":
    asyncio.run(main())
