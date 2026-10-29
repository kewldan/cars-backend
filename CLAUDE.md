# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

Python 3.13, FastAPI, MongoDB via Beanie ODM, pyrofork (Telegram MTProto, imports as `pyrogram`), pydantic v2. Package manager is **uv**; lint/format with **ruff**; type check with **ty** (Astral's experimental checker, in dev deps).

`src/` is the source root — scripts under `src/scripts/` prepend it to `sys.path` themselves so they can be invoked directly.

## Common commands

```powershell
uv sync                                  # install deps
uv run src/main.py                       # run API server (uvicorn, SERVER_HOST:SERVER_PORT)
uv run ruff check . ; uv run ruff format .
uv run ty check

# one-time Telegram login (needs TG_API_ID / TG_API_HASH from my.telegram.org)
uv run src/scripts/tg_login.py

# pull posts from a channel and upsert as Listings
uv run src/scripts/ingest_channel.py [channel_id] [--limit N] [--qwen] [--dry-run]
# default channel is 1525185710; --qwen swaps HeuristicParser → QwenParser
```

Docker: `docker compose up --build`. Compose runs the API and MongoDB 8 and expects one **external** network, `cars-backend`, shared with the frontend's nginx — create it with `docker network create cars-backend` first.

There is no test suite yet.

## Architecture

The system is a **scraper + read API** for car-for-sale ads posted to Georgian Telegram channels. Two halves connected by MongoDB:

1. **Ingest** (`src/ingest/`, `src/scripts/ingest_channel.py`) — a pyrofork client pulls recent posts from a channel. Each post's text/caption goes through a `Parser` (`Protocol` with `async def parse(text) -> ParsedCar | None`); a `None` return means "not a listing, skip." Two implementations live in `src/ingest/parsers.py`:
   - `HeuristicParser` — regex/keyword extraction; the default.
   - `QwenParser` — POSTs to any OpenAI-compatible `/v1/chat/completions` endpoint with `response_format=json_object` (defaults: Ollama at `http://localhost:11434/v1`, `qwen2.5:7b`).

   `pipeline._build_listing` turns a `ParsedCar` + `pyrogram.Message` into a `Listing` document keyed by `id_code = "tg-{channel}-{msg_id}"` and dedupes against existing rows.

2. **Read API** (`src/server.py` + `src/routers/`) — FastAPI app with lifespan-managed Mongo connection. Routers: `/health`, `/listings`, `/facets`, `/favorites`, `/saved-searches`, `/map`. Filters/sort come in as query params, are normalized in `src/deps.py` into `ListingFilters`, then translated to a Mongo query by `services/filters.build_query` and a sort spec by `services/sorting.resolve_sort`.

### Identity model (no JWT yet)

Favorites and saved searches are scoped per **device**, not per user. Endpoints take `X-Device-Id` via `deps.get_device_id` (must be ≥8 chars). The `User` model exists but auth isn't wired.

### Wire format: camelCase JSON, snake_case Python

All response models inherit `schemas/common.py:CamelModel` (`alias_generator=to_camel`, `populate_by_name=True`). Routes set `response_model_by_alias=True` so JSON keys are camelCase. When adding a new field, just name it snake_case and the alias is generated for you. Filters in `deps.py:listing_filters` declare their query-param names manually (camelCase to match the frontend), then map into snake_case `ListingFilters`.

### Listing identifier conventions

- `Listing.id_code` is the **public, stable** ID (`"tg-{channel_id}-{msg_id}"`). It's also what `ListingOut.id` exposes — the Mongo `ObjectId` is never sent to clients.
- Telegram **channel IDs are stored bare** (no `-100` prefix). The `-100` prefix lives only inside `ingest/pipeline.py:_peer()` when calling pyrogram. Storing/querying anywhere else uses the bare integer.

### Filters: request vs. saved

`ListingFilters` (request, has `q` free-text) and `SavedSearchFilters` (persisted, no `q`) are deliberately separate — text-search scoring isn't stable across snapshots, so saved searches drop `q`. `services/filters.filters_to_saved` is the bridge; `build_query` accepts either.

The `q` filter uses Mongo's **text index** on `Listing` (`make`/`model`/`city`/`id_code`, weighted), not regex. Don't add `$regex` substring matching for these fields — query the text index instead.

### Pricing & sort

`services/pricing.rate(price, fair) -> (PriceRating, rank)` buckets a listing into `great`/`good`/`fair`/`high`/`overpriced` plus a numeric rank used by `sort=best_deal`. **Today `fair_price` is set to `price` in the pipeline as a placeholder, so every listing currently rates "fair".** A real fair-price model needs to plug into `_build_listing`.

### Caching

- `/listings` and `/map/*` set `Cache-Control: public, max-age=30, stale-while-revalidate=120`.
- `/facets` has a 300s in-process memo (`_cache` dict in `routers/facets.py`) on top of client cache headers — restart the server to bust it.

## Conventions and gotchas

- **Beanie registration is two-step.** Adding a new `Document`: re-export it from `models/__init__.py` *and* add it to the `document_models=[…]` list in `db.connect()`. Miss either and the model silently has no indexes/queries.
- **`map` router shadows the builtin** — it's imported as `from routers import … map as map_router` in `server.py`. Keep the alias.
- **Pyrofork, not pyrogram.** The package imports as `pyrogram` but is the `pyrofork` fork. Don't `uv add pyrogram` — it'll clobber the install.
- **uvloop is platform-gated.** `pyproject.toml` only installs it on linux/darwin; `main.py` falls back to `asyncio.run` on Windows.
- **Datetime hygiene.** `posted_at` may be tz-naive on older docs; `_build_listing` and `ListingOut.from_doc` both coerce to UTC. Match that pattern in any new code that touches `posted_at`.
- **Geo is scaffolded, not populated.** `Listing.location` has a 2dsphere index but is `None` on insert — `routers/map.py` falls back to per-city centroids in the `CITY_COORDS` dict.
- **Indexes are declarative.** `Listing.Settings.indexes` is the source of truth for compound/text/geo indexes; on first connect Beanie creates them. Drop+recreate if you change index definitions on an existing collection.
- **Channel-ID arithmetic.** When in doubt, `_peer(bare_id)` in `ingest/pipeline.py` is the only place the `-100` prefix is added.

## Configuration

`.env` (see `.env.example`) populates `src/settings.py:Settings` (pydantic-settings). Notable: `MONGO_URL`, `MONGO_DB`, `CORS_ORIGINS` (JSON list literal), `TG_API_ID`/`TG_API_HASH`, `TG_SESSION_DIR` (sessions persist here — keep it out of git), `QWEN_BASE_URL`, `QWEN_MODEL`. `JWT_SECRET` is declared but unused.
