# Cross-Media Recommendation Engine

Input a movie, book, anime, or game and get recommendations both within that medium and
across others, matched on theme/tone/mood rather than surface genre tags.

**Current status:** Backend feature-complete. All five source APIs (TMDB, AniList,
Hardcover, RAWG, Last.fm) are wired up behind one shared ingest pipeline, plus
`/api/recommend` (pgvector cosine search + LLM re-ranking with "why this matches"
blurbs) and a seed script for bulk-populating the library. A minimal test frontend is
served at `/`; a richer React UI is the remaining major piece — see "Next milestones".

## Architecture

```
User input (title + medium)
    │
    ▼
Source API search (TMDB / AniList / Hardcover / RAWG / Last.fm) → canonical metadata
    │
    ▼
LLM (OpenAI-compatible): generate standardized "taste profile" JSON
    │
    ▼
Embed the taste profile locally (sentence-transformers, bge-small-en-v1.5)
    │
    ▼
Store item + profile + vector in Postgres (pgvector)

--- recommendations, given an already-ingested item ---

pgvector cosine similarity search → top ~30 nearest-neighbor candidates (any medium)
    │
    ▼
LLM re-ranking: picks + ranks the best matches, writes a "why this matches" blurb each
    │
    ▼
Falls back to raw vector-similarity order (no blurbs) if the LLM call fails
```

| Medium | Source | Auth needed |
|---|---|---|
| movie, tv | TMDB | API key |
| anime, manga | AniList | none |
| book | Hardcover | Bearer token (beta) |
| game | RAWG | API key |
| music (albums) | Last.fm | API key |

### LLM backend (OpenAI-compatible)

The LLM stage (taste-profile generation + recommendation reranking) talks to **any
OpenAI-compatible chat-completions endpoint**, configured in `.env`. That covers both a
local model and hosted cloud providers with the same code — only the URL/model/key change:

| Setup | `LOCAL_LLM_BASE_URL` | `LOCAL_LLM_MODEL` | `LOCAL_LLM_API_KEY` | Cost |
|---|---|---|---|---|
| **Local** (llama.cpp) | `http://127.0.0.1:8080/v1` | `qwen3.5-4b` | *(blank)* | free, needs a GPU/CPU |
| **Groq** | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | your key | free tier, fast |
| **DeepSeek** | `https://api.deepseek.com/v1` | `deepseek-chat` | your key | very cheap |

Prompts and schema-constrained JSON output live in `app/services/_llm_shared.py`, so
results are consistent regardless of which endpoint you point at. Structured output is
enforced via the OpenAI `response_format`/`json_schema` mechanism.

> **Hosting note:** the local model runs on your own GPU, which isn't available on a
> typical cloud host. For a deployed instance, point the same variables at a hosted
> provider (Groq's free tier is a good starting point).

### Running a local LLM (llama.cpp)

This is the setup used during development on an RTX 3080 (10GB VRAM); any modern GPU with
~6GB+ free, or even CPU-only (slower), works.

```powershell
# 1. Install llama.cpp (one time)
winget install ggml.llamacpp

# 2. Download a model (Qwen3.5-4B Q5_K_M, ~3GB — great quality/speed balance for this task)
curl.exe -L -o "backend\models\Qwen3.5-4B-Q5_K_M.gguf" `
  "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q5_K_M.gguf"

# 3. Start the model server (-ngl 99 offloads all layers to GPU; drop it for CPU-only)
llama-server -m "backend\models\Qwen3.5-4B-Q5_K_M.gguf" `
  --host 127.0.0.1 --port 8080 -ngl 99 -c 8192 --jinja -a qwen3.5-4b
```

Then set in `.env`:

```
LOCAL_LLM_BASE_URL=http://127.0.0.1:8080/v1
LOCAL_LLM_MODEL=qwen3.5-4b
LOCAL_LLM_API_KEY=
```

Notes:
- Qwen3.5 is a *reasoning* model; the backend sends `enable_thinking: false` so it skips
  the slow "thinking" phase (which isn't needed for schema-constrained JSON). This took
  per-item generation from ~65s down to ~9s on the reference GPU.
- Ollama works too: `ollama serve`, `ollama pull <model>`, then point
  `LOCAL_LLM_BASE_URL` at `http://127.0.0.1:11434/v1` and set `LOCAL_LLM_MODEL` to the
  pulled model's name.

## One-time setup

You need a Postgres URL, a TMDB key, and an LLM backend before this will run. None require
a credit card.

### 1. Postgres with pgvector — via Neon (free, no local install)

1. Go to [neon.tech](https://neon.tech) and sign up (GitHub/Google login works).
2. Create a new project (any name/region).
3. On the project dashboard, open **Connection Details** and copy the connection string.
   It looks like:
   `postgresql://user:password@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`
4. Neon has the `pgvector` extension available — you don't need to install anything; the
   app runs `CREATE EXTENSION IF NOT EXISTS vector` automatically on startup.

### 2. TMDB API key (free, instant)

1. Create an account at [themoviedb.org](https://www.themoviedb.org/signup).
2. Go to **Settings → API** ([direct link](https://www.themoviedb.org/settings/api)) and
   request a free "Developer" API key (personal/hobby use is fine).
3. Copy the **API Key (v3 auth)** value.

### 3. LLM backend (free)

Either run a model locally or use a free hosted provider — see "LLM backend
(OpenAI-compatible)" above. Quickest local path: `winget install ggml.llamacpp`, download
a GGUF, and run `llama-server` (full commands in "Running a local LLM"). Then leave
`LOCAL_LLM_API_KEY` blank. For a hosted option, grab a free key from
[Groq](https://console.groq.com/keys) and set the three `LOCAL_LLM_*` variables.

### 4. RAWG API key (free, instant) — needed for games

1. Sign up at [rawg.io](https://rawg.io/apidocs) and go to the API docs page.
2. Register for a free API key (personal/hobby use).
3. Copy the key.

### 5. Last.fm API key (free, instant) — needed for music

1. Go to [Last.fm's API account creation page](https://www.last.fm/api/account/create).
2. Fill in an application name (anything, e.g. "cross-media-recommender") — no callback
   URL is required for this use case.
3. Copy the **API key** (you don't need the "Shared secret" for read-only calls).

### 6. Hardcover API token (free, beta) — needed for books

1. Sign up at [hardcover.app](https://hardcover.app).
2. Go to **Settings → Hardcover API** to find your token.
3. Copy it. Note: this API is explicitly in beta — Hardcover warns the schema may change
   without notice, and the token itself may occasionally need to be regenerated.

### Configure the backend

```powershell
cd backend
Copy-Item .env.example .env
notepad .env   # paste DATABASE_URL, TMDB_API_KEY, LOCAL_LLM_*, RAWG_API_KEY, LASTFM_API_KEY, HARDCOVER_API_TOKEN
```

You don't need every source key to get started — a Postgres URL + TMDB key + a running LLM
backend is enough to use movies/TV. Each medium's ingest endpoint independently errors out
(502, with a clear message) if its specific key is missing/blank, without affecting the
others.

## Running the backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Port 8001 (not the default 8000) because Windows sometimes reserves 8000 for other
services, causing a `WinError 10013` permission error. `--reload` is convenient during
development, but on Windows it occasionally left orphaned/stuck worker processes during
this project's development — if you see weird hangs after editing code, kill all
`python.exe` processes for this venv and restart plain (no `--reload`) instead.

The first `sentence-transformers` model load will download `BAAI/bge-small-en-v1.5`
(~130MB) from Hugging Face the first time it's used — this happens lazily on the first
`/api/ingest` call, not at startup.

Visit `http://127.0.0.1:8001/docs` for interactive API docs.

## Trying it out

```powershell
# 1. Search any medium: movie, tv, anime, manga, book, game, music
curl "http://127.0.0.1:8001/api/search?medium=movie&query=Eternal+Sunshine"
curl "http://127.0.0.1:8001/api/search?medium=anime&query=Violet+Evergarden"
curl "http://127.0.0.1:8001/api/search?medium=game&query=Disco+Elysium"

# 2. Ingest the one you want (source/source_id come from the search response)
curl -X POST "http://127.0.0.1:8001/api/ingest" `
  -H "Content-Type: application/json" `
  -d '{\"medium\":\"movie\",\"source\":\"tmdb\",\"source_id\":\"38\"}'

# 3. List everything ingested so far, across all mediums
curl "http://127.0.0.1:8001/api/items"

# 4. Get recommendations for an already-ingested item (item_id is the internal DB id,
#    from step 2's response or step 3's list — NOT the source_id)
curl -X POST "http://127.0.0.1:8001/api/recommend" `
  -H "Content-Type: application/json" `
  -d '{\"item_id\":22,\"limit\":10,\"candidate_pool_size\":30}'
# or: curl "http://127.0.0.1:8001/api/recommend/22?limit=10"
```

A successful ingest returns the generated taste profile (mood, themes, pacing, tone,
emotional arc, aesthetic, comparable_to, embedding_text) alongside the stored item.

A successful recommend call returns the seed item, a ranked list of recommendations (each
with `item`, `why_this_matches`, `rank`, and `vector_distance`), and a `reranked` boolean
(`false` means the LLM re-ranking call failed and results fell back to raw vector-
similarity order with a generic blurb — still useful, just less curated). Recommendations
intentionally span every medium in the library, not just the seed's own medium.

Note: `medium` and `source` are paired — the API enforces the correct source per medium
(`movie`/`tv` → `tmdb`, `anime`/`manga` → `anilist`, `book` → `hardcover`, `game` → `rawg`,
`music` → `lastfm`) and rejects mismatches with a 400.

## Seeding the library

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m seed.seed                      # seed every medium in seed/titles.py
python -m seed.seed --medium book --medium game   # just specific mediums (repeatable)
python -m seed.seed --retry-failed       # also retry titles that failed last time
python -m seed.seed --limit 10           # cap NEW items ingested per medium this run
```

Safe to interrupt (Ctrl+C) and re-run — progress is saved to `seed/seed_progress.json`;
already-succeeded titles are skipped, failed ones are skipped unless `--retry-failed` is
passed. With a local LLM there's no rate limit; if you use a hosted provider that throttles
you, set `LLM_MIN_INTERVAL_SECONDS` in `.env` to add a gap between calls. `seed/titles.py`
documents the curated list — add more titles there whenever you want to grow it.

## Project layout

```
backend/
  app/
    main.py          FastAPI app, CORS, startup (creates pgvector extension + tables)
    config.py         Settings loaded from .env
    db.py             Async SQLAlchemy engine/session
    models.py         Item table (metadata + taste profile + vector(384) column)
    schemas.py         Pydantic models: TasteProfile, ItemOut, Recommend* request/response
    pipeline.py        Shared ingest + recommend orchestration (search/ingest/vector search)
    services/
      tmdb.py          TMDB search + detail fetch (movie, tv)
      anilist.py       AniList GraphQL search + detail fetch (anime, manga)
      hardcover.py     Hardcover GraphQL search + detail fetch (book), beta-defensive
      rawg.py          RAWG search + detail fetch (game)
      lastfm.py        Last.fm search + detail fetch (music/albums)
      llm.py           LLM dispatch (re-exports the backend below)
      local_llm.py     OpenAI-compatible LLM client: taste profiles + re-ranking
      _llm_shared.py   Shared prompts + structured-output schemas
      embeddings.py    Local sentence-transformers embedding
    routers/
      health.py        GET /health
      ingest.py        search/ingest/items/recommend endpoints (medium dispatcher)
  static/
    index.html         Minimal test frontend served at /
  seed/
    titles.py          Curated per-medium title lists used by the seed script
    seed.py            Bulk-populate script: throttled, resumable, retry-failed support
    seed_progress.json Generated at runtime — per-title status (done/failed) + item id
  requirements.txt
  .env.example
```

Every source module in `services/` implements the same four functions
(`search`, `get_details`, `summarize_metadata`, `extract_display`), so `app/pipeline.py`
can treat all five sources identically via a `medium -> source module` lookup table, and
both `routers/ingest.py` and `seed/seed.py` share that exact same logic.

## Next milestones

- React frontend: search box → medium picker → ingest → recommend results grouped/tabbed
  by medium, showing poster, taste-profile highlights, and each `why_this_matches` blurb
  (a minimal single-file version already exists at `static/index.html`)
- Deploy: host the app (e.g. HF Spaces / Render) pointed at a hosted LLM provider + Neon
- Grow `seed/titles.py` and re-run seeding to expand the library
