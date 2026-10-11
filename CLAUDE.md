# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local, single-user web app for fantasy basketball auction (salary-cap) drafts. A Python FastAPI server (`server/`) fetches source data, computes prices/projections/optimal rosters, and runs a live draft room. A React + TypeScript + Vite client (`client/`) presents it. `spec.md` is the full design spec. Note that parts of it have drifted from the code: the client uses React 19, and all five scrapers live in `sources/parsers.py`, not in per-site modules.

## Commands

Server (run from `server/`, Python ≥ 3.11):

```bash
pip install -r requirements.txt
python -m app                                   # serves API + built client on http://127.0.0.1:8000 (PORT env overrides)
python -m unittest discover -s tests -t .       # full suite (~1 min; pytest also works)
python -m unittest tests.test_draft             # one module
python -m unittest tests.test_draft.Sales.test_max_bid_keeps_a_dollar_per_open_spot   # one test
```

Set `AUCTION_DB=/path/to/test.db` to point the server at a throwaway SQLite file instead of `server/data/auction.db`. Delete the DB file to start fresh.

Client (run from `client/`):

```bash
npm install
npm run dev        # http://127.0.0.1:5173, proxies /api to :8000 (keep python -m app running)
npm run typecheck  # tsc --noEmit
npm run build      # writes client/dist
```

`client/dist` is committed, and the Python server serves it at `/`. **After any client change, run `npm run build` and commit the updated `dist/`.** Otherwise `python -m app` keeps serving the old UI.

Optional browser smoke test: `pip install playwright && playwright install chromium`, start a server with `AUCTION_DB` pointed at a temp file, then `python tests/e2e_smoke.py http://127.0.0.1:8000`.

## Architecture

### Data flow
1. **Sources → snapshots.** `sources/service.py` has the `SOURCES` registry (5 sources). Each source produces rows in one of three ways: by fetching (`sources/base.py`, which checks robots.txt, waits 5 s per host and times out after 20 s, then hands the HTML to `parsers.py`), from the seed (`server/seed/<source_id>.csv`), or from a CSV import. Every path goes through `csvio.validate` (which checks the column schema and a minimum row count) and is stored as a row in the `snapshots` table. The **newest `status='ok'` snapshot per source is active**. Failed fetches are stored as `status='failed'` and never replace good data.
2. **Startup** (`main.startup`): init the DB, load seed CSVs for any source with no active snapshot, then refresh stale sources on a background daemon thread.
3. **Board.** `core/engine.compute_board(data, settings)` merges the sources by normalized name (`core/names.py`: accent/suffix/status-tag folding, alias table, team code map) and computes the target (blended price), z-scores, Stats $, pay and bargain flags. `main.board()` memoizes the result, keyed on active snapshot IDs plus the settings JSON. Most endpoints call `board()` first.
4. **Builds.** `optimizer.build_around` is a MILP (`scipy.optimize.milp`/HiGHS) that tries each punt option and iteratively reweights categories. `jobs.py` fans the anchors out over a `ProcessPoolExecutor`, the client polls `/api/builds/{job_id}`, and results are cached in `build_cache` keyed by a hash of snapshot IDs, league/model settings and anchors.
5. **Draft.** `draft.py` holds pure functions (`team_status`, `validate_sale`, `inflation`, `derive`, `plan`, `nominations`). Teams are stored in `kv['draft_teams']` and sales in the `sales` table. `main._draft_lock` serializes validating and recording a sale, because FastAPI runs sync handlers in a threadpool.

### Purity boundary
`core/`, `optimizer.py` and the calculation functions in `draft.py` do no I/O and take plain row dicts plus a `Settings`. Tests call them directly on seed data. `store.py` (stdlib sqlite3, module-level lock for writes) and `main.py` are the only I/O layers. Keep it that way.

### Settings
`settings.py` defines Pydantic models `League`, `Model` and `Sources`, combined into `Settings`. They are persisted as JSON in `kv['settings']`. There are two presets:
- `defaults()`: the user's league (12 teams, $200, 10 slots, 9-cat).
- `reference()`: the settings behind the original single-page board (8 slots + 5 bench, no market rescale, `opponent_baseline="pool"`).

**The golden tests (`tests/test_golden.py`) use `reference()` and assert exact targets, Stats $ and build outputs.** Any change to engine/optimizer math must keep them passing.

### API and client
- **API.** Every route is in `main.py` under `/api/*`. Errors are always returned as `{"error": "<human-readable message>"}`. Custom exception handlers flatten FastAPI validation errors into that shape.
- **Client.**
  - `client/src/api.ts` is the single typed wrapper around those endpoints. Response types are in `types.ts`.
  - `App.tsx` uses hash routing (`#/board`, `#/stats`, `#/teams`, `#/draft`, `#/sources`, `#/settings`) and holds the shared `board`/`draft` state. Views live in `src/views/`.
  - There is no state or table library: plain hooks only.

### Adding or changing a source
- Update `SOURCES` in `service.py`, the parser in `parsers.py` (registered in `PARSERS`), and the schema in `csvio.SCHEMAS`.
- Add a URL field in `settings.Sources` (and point the source's `url_key` at it), a seed CSV in `server/seed/`, and its column docs in `server/seed/README.md`.
- Mark dated-article sources `static: True`. They are fetched once per URL, not on the 12 h schedule.

## How to work in this repo

### Scope and planning
- If a change touches more than ~3 files or the approach is unclear, propose a short plan and wait for an OK. Just do small, obvious changes.
- If a wrong guess would be expensive to undo, ask one clarifying question first. Here that means changes to the SQLite schema (`store.py`), the `/api/*` response shapes the client depends on, the `Settings` models persisted in `kv`, or anything that deletes data.
- Stay in scope. Don't refactor, rename or reformat code you didn't need to touch. List unrelated problems in your summary instead of fixing them.
- Ask before adding a dependency (to `requirements.txt` or `package.json`). Prefer the standard library and what the project already uses.

### Definition of done
- Run the checks that cover what you changed, and show the command and its result:
  - Server: `python -m unittest discover -s tests -t .` (or the relevant module). Engine or optimizer changes must keep `tests/test_golden.py` passing.
  - Client: `npm run typecheck`, then `npm run build`.
  - There is no linter configured, so don't claim a lint pass.
- For a bug fix, first write a test that fails because of the bug, then make it pass.
- Never delete, skip or loosen a test (including the golden values) to get it passing. Never silence an error (`# type: ignore`, `@ts-ignore`, bare `except`) without saying why.
- If you couldn't verify something, such as UI behaviour you didn't run in a browser, say so plainly.

### Git and safety
- Never commit, push or open a PR unless asked. When asked to commit a client change, include the rebuilt `client/dist` in the same commit.
- Ask before anything destructive: `git push --force`, `git reset --hard`, `git clean -fd`, `rm -rf`, `DROP`/`DELETE` on tables, or deleting `server/data/auction.db`. For experiments, point `AUCTION_DB` at a throwaway file instead.
- Commit messages: imperative mood, subject ≤ 72 characters, body explains why.
- Never print, log or commit secrets. Read config from environment variables (as with `PORT` and `AUCTION_DB`).

### Backend conventions
- Validate input at the boundary (Pydantic models and `csvio.validate`). Return errors as `{"error": "<message with context>"}`; don't swallow them.
- Use parameterized `sqlite3` queries only. Never build SQL with string formatting.
- Any read-modify-write on shared state needs serialization. Writes go through `store._lock`, and draft sales go through `main._draft_lock`. Say which mechanism a change relies on.
- The schema uses `CREATE TABLE IF NOT EXISTS` and there are no migrations, so a schema change won't apply to an existing DB file. Raise this before changing a table.
- Network calls go through `sources/base.py`, which applies the timeout, robots.txt check and per-host rate limit. Don't add retry loops against scraped sites. A failed fetch is recorded as `status='failed'` and the next scheduled refresh tries again.
- Logging: use the module loggers (`auction`, `auction.sources`) in their existing `%`-style format.

### Explanations
- The user is sharpening their backend skills. When you make a non-obvious design choice (concurrency, consistency, data model, error handling), add 1–2 sentences on the trade-off and the alternative you rejected.
- Otherwise keep it brief: what changed, how you verified it, and anything the user needs to decide.
