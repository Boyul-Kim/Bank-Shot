# Auction Board — Web Application Spec

Status: v1 scope agreed · Oct 10, 2026

## 1. Summary

A local web app for 2026-27 fantasy basketball salary-cap (auction) drafts. A Python server fetches source data, computes prices, projections, category values and optimal rosters, and runs a live draft room. A React client presents it.

It has five working areas:

1. **Auction board.** The top N players in ADP order. Each row shows a blended target price, the source range, the expert rank and the production value (Stats $).
2. **Projected stats.** Per-game projections for the 9 categories, shaded by category value.
3. **Build-around teams.** The optimal roster built around any player, with a punt choice and weekly category win chances.
4. **Live draft room.** Record each sale as it happens. The room tracks every team's budget and roster, measures price inflation, re-plans your roster from what is left, and suggests nominations.
5. **Sources and settings.** Fetch fresh data, import CSVs, and edit the league and model settings.

## 2. Decisions from review

| Question | Decision |
|---|---|
| Where it runs | Your computer only. Single user, no logins, binds to `127.0.0.1`. |
| Data updates | Fetch from the sites automatically, with CSV import as a fallback. |
| League | 12 teams, $200, 10 roster spots, 9-cat H2H. |
| Live draft mode | In v1. |

## 3. Goals and non-goals

### Goals
- Reproduce the existing board and builds exactly from the Oct 10, 2026 snapshot when run with the reference settings (§11).
- Default to your league: 12 teams, $200, 10 spots (PG, SG, G, SF, PF, F, C, C, UT, UT), 9-cat.
- Make every number traceable: each result records which source snapshot it used, and when that snapshot was retrieved.
- Keep working offline. Bundled seed data means a failed fetch never leaves the app empty.
- Make draft-room actions feel instant: recording a sale is under 100 ms, and a full re-plan is under 5 s.

### Non-goals (v1)
- Hosting, accounts, sharing, or multiple drafts at once.
- Points leagues.
- Data that sits behind a paywall. Hashtag's paid auction values beyond its free top 30 are not scraped.
- Predicting what other managers will bid. Only inflation is modelled.

## 4. Architecture

```
React client (Vite + React 18 + TypeScript)
   │  JSON over HTTP (/api/*)
   ▼
Python server (FastAPI + Uvicorn + Pydantic v2)
   ├── sources/     fetchers + CSV import → snapshots
   ├── core/        pure functions: names, merge, pricing, z-scores, valuation
   ├── optimizer/   roster MILP (scipy.optimize.milp / HiGHS)
   ├── draft.py     live draft state, inflation, re-plan, nominations
   ├── jobs.py      background build runner with progress
   └── store.py     SQLite (stdlib sqlite3)
```

- **Server.**
  - FastAPI, Uvicorn, Pydantic v2, NumPy, SciPy, requests, BeautifulSoup4 and lxml.
  - Request bodies are Pydantic models, so FastAPI validates them and documents every endpoint at `/docs` while the server runs. Endpoints are listed in §10.
- **Client.**
  - React 18, TypeScript and Vite, with no state or table library; plain hooks are enough at this size.
  - Styling uses theme tokens carried over from the current page, in both light and dark.
- **One-command mode.** After `npm run build`, the server also serves `client/dist`, so a single `python -m app` opens the whole app at `http://127.0.0.1:8000`.
- **Purity.** The `core`, `optimizer` and the calculation parts of `draft` do no I/O, so they are unit-testable.

## 5. Data sources

Every adapter returns a `Snapshot`: `{source_id, retrieved_at, url, method: fetch|seed|import, rows[]}`. Snapshots are stored and versioned, and the newest valid one per source is active.

| source_id | Provides | URL | Fetch |
|---|---|---|---|
| `hashtag_adp` | Blended ADP (Yahoo/ESPN/Fantrax), team, positions | hashtagbasketball.com/fantasy-basketball-adp | auto |
| `hashtag_auction` | Yahoo AAV, ESPN AAV, Hashtag projected $ (free top 30) | hashtagbasketball.com/fantasy-basketball-auction-values | auto |
| `fantasypros_proj` | Season projections: PTS, REB, AST, BLK, STL, FG%, FT%, 3PM, GP, MIN, TO | fantasypros.com/nba/projections/overall.php | auto |
| `rotoworld_rank` | Expert 9-cat Top 200 | URL setting (a dated article) | auto |
| `rotoworld_mock` | Industry salary mock prices | URL setting (a dated article) | auto |

### Fetch policy
- **When:** the server refreshes on startup any auto source whose active snapshot is older than `fetch_max_age_hours` (default 12). The Sources view also has a Refresh button for each source and for all of them.
- **Politeness:**
  - Check robots.txt first.
  - Use a descriptive User-Agent.
  - Allow at least 5 s between requests to the same host, with a 20 s timeout.
  - Make no more than one attempt per source per refresh.
- **Validation:** each parser checks the expected columns and a minimum row count (ADP ≥ 100, projections ≥ 100, mock ≥ 100, rank ≥ 100, auction ≥ 10).
  - A parse that fails these checks is stored as a failed attempt and never becomes active.
  - The previous snapshot stays in use, and the UI shows the error.
- **Seed:** the Oct 10, 2026 data ships in `server/seed/*.csv` and loads on first run.
- **Import:** a CSV upload for any source, using the same column schema as the seed files (documented in `server/seed/README.md`).

### Matching
- **Names are normalized** before matching:
  - accents stripped
  - punctuation removed
  - suffixes (Jr., Sr., II, III) folded
  - status tags like "(OUT)" or "(DTD)" removed
- **An alias table** covers known variants, such as "Trey Murphy" → "Trey Murphy III".
- **Team codes** are mapped to one set (NYK→NY, GSW→GS, SAS→SA, UTH→UTA, NOR→NO).
- **Unmatched names** are listed on the Sources view, never silently dropped.

## 6. Domain model

```text
Player       id (slug), name, team, positions[]
PriceInputs  adp_rank, adp, rw_rank, mock, yahoo_aav, espn_aav, hb_value, slot_price
Projection   gp, min, pts, reb, ast, stl, blk, tpm, fgp, ftp, to          (per game)
Scores       z{cat}, z_total, z_rank
Valuation    target, low, high, n_sources, stats_value, pay, bargain
Build        anchor_id, punt, expected_cats, spend, roster[{id, slot, price, bargain}],
             cat_win{cat: p}, alternatives[{punt, expected_cats}]
DraftState   teams[{id, name, is_me}], sales[{id, player_id, team_id, price, at}]
```

## 7. Settings

### League (defaults = your league)
| field | default |
|---|---|
| `teams` | 12 |
| `budget` | 200 |
| `slots` | `[PG, SG, G, SF, PF, F, C, C, UT, UT]` (roster size = number of slots + `bench`) |
| `bench` | 0 |
| `categories` | 9-cat: FG%, FT%, 3PM, PTS, REB, AST, STL, BLK, TO |
| `board_size` | 150 |

### Model
| field | default | meaning |
|---|---|---|
| `rescale_market` | true | Scale market targets so the top `teams × roster` targets add up to `teams × budget`. The sources describe 12-team, 13–14-spot leagues; a 10-spot league puts more money on fewer players. |
| `fta_per_pt` | 0.25 | Estimated FT attempts per point. Attempts aren't published. |
| `bargain_bid_up` | 0.5 | pay = max(target, target + f·(stats_value − target)) |
| `bargain_threshold` | 4 | A player is a bargain when stats_value − pay ≥ this. |
| `max_bargains` | 3 | Per roster. |
| `star_price` / `max_stars` | 40 / 2 | At most `max_stars` players priced at or above `star_price`. |
| `min_gp` | 50 | Players projected below this are excluded from builds and plans. |
| `sigma` | 5.0 | Weekly noise used for win probabilities. |
| `opponent_baseline` | drafted | Win chances are measured against an average drafted roster (`drafted`) or the board average (`pool`, the original page). |
| `punt_options` | none, FT%, FG%, TO, AST, 3PM, BLK, PTS | |
| `anchor_punt_guard` | 0.5 | Never punt a category where the anchor's z is above this. |
| `reweight_iters` | 6 (builds), 3 (draft re-plan) | |
| `fetch_max_age_hours` | 12 | |
| `rotoworld_rank_url`, `rotoworld_mock_url` | Oct 7 / Aug 28 articles | |

The **reference settings** (§11) match the original page and are used by the golden tests: 13 spots (8 positional + 5 bench), `rescale_market = false`, `opponent_baseline = pool`.

## 8. Calculations

1. **Merge.** ADP order defines the board, rows 1 to `board_size`.
2. **Slot price.** `curve = sorted(mock prices, desc)`. `slot_price(rank) = curve[rank − 1]`, or 1 if the rank is past the end of the curve.
3. **Target.**
   - target = round(mean of the available values among {slot_price, mock, yahoo_aav, espn_aav}).
   - low and high are the min and max of the same values; n_sources is how many there are.
   - If `rescale_market` is on: k = teams·budget / Σ(top teams·roster targets). The target, low and high are each multiplied by k, and the target is rounded with a minimum of 1.
4. **Per game.** Season totals are divided by GP.
5. **Percentage impact.**
   - FTA = `fta_per_pt`·PTS
   - FTM = FTA·FT%
   - FGA = max((PTS − FTM − 3PM)/2, 0.1)/FG%
   - League rates are attempt-weighted.
   - Impact = (pct − league)·attempts.
6. **Z-scores.** Computed over the projected board pool, using the population standard deviation; TO is negated. z_total is the sum of the selected categories, and z_rank is its rank.
7. **Stats $.** Rank players by z_total · min(GP/75, 1). The Nth player gets the Nth highest target.
8. **Pay.** pay = max(target, round(target + bargain_bid_up·(stats_value − target)), 1). A player is a bargain when stats_value − pay ≥ `bargain_threshold`.
9. **Roster MILP.** Shared by builds and draft re-plans.
   - **Variables:** y_p (player p is on the roster) and x_{p,s} for each positional slot s the player is eligible for. UT and bench slots need no variables: the roster-size constraint fills them.
   - **Constraints:**
     - Σy = roster size.
     - Σ price·y ≤ budget, where fixed players count at their fixed price.
     - Each positional slot is filled exactly once.
     - Σ_s x_{p,s} ≤ y_p.
     - Star cap: at most `max_stars` players priced at or above `star_price`.
     - Bargain cap: at most `max_bargains` bargains. In draft re-plans, players you already own don't count; in build-around teams the anchor counts, as on the original page.
     - Fixed players have y = 1.
     - Excluded players (projected below `min_gp`, or already taken) have y = 0.
   - **Objective:** maximize Σ y_p · Σ_c w_c · z_{p,c} · min(GP/75, 1) over the non-punted categories.
   - **Reweighting:** run `reweight_iters` passes. After each pass, update w_c ← ½w_c + ½·φ(team_z_c/σ)/max, which shifts weight toward categories still close to a coin flip.
   - **Scoring:** each pass is scored by expected categories won, Σ_c Φ(team_z_c/σ). The best pass is kept across all passes and every allowed punt.
10. **Determinism.** The same snapshots and settings give the same output. Results are cached by a hash of the snapshot IDs and the settings.

## 9. Live draft mode

### Setup
- Name the 12 teams and mark one as yours.
- Budget and roster size come from settings.
- **Reset** clears all sales after an in-page confirmation step.

### Record a sale
- **Input:** a player picked through type-ahead, the winning team, and the price.
- **Validation:** the server rejects the sale, with a clear message, if:
  - the player is already sold
  - the team's roster is full
  - the price is below $1
  - the price is above the team's max bid, where max bid = remaining budget − (spots left − 1)
- **Undo:** "Undo last" plus a delete button on any sale in the log.
- All state persists in SQLite, so it survives restarts.

### Derived state (recomputed after every change)
- **Per team:** spent, remaining, spots left, max bid, and the roster.
- **Inflation:** inflation = Σ remaining budgets / Σ targets of the top R available players, where R is the total spots left. Each available player's adjusted target is round(target × inflation), with a minimum of 1.
- **Your roster:** your players placed into lineup slots, plus your current category profile.

### Re-plan
- Runs the MILP with your purchases fixed at what you paid.
- The pool is the available players at inflation-adjusted pay prices, and the budget is your $200.
- **Returns:**
  - the plan: the players to target, each with a **bid up to** price
  - the punt
  - expected categories won
  - each category's win chance
- Runs automatically after each sale and can be triggered manually.

### Bid helper
Select the player currently up for bid to see:
- his adjusted target
- your max bid
- whether he's in your plan
- **"If I win at $X":** a what-if re-plan with him fixed at $X, showing how expected categories change against your current plan

### Nomination suggestions
The top 5 available players by adjusted target who are:
- **not** in your plan, and
- affordable for at least 2 other teams

Nominating them drains rivals' budgets.

## 10. API

Base path `/api`. All responses are JSON. Errors return `{error: "message"}` with status 400, 404, 409 or 422.

| Method | Path | Purpose |
|---|---|---|
| GET | `/settings` | Current settings |
| PUT | `/settings` | Save settings (validated) |
| POST | `/settings/reset` | Restore defaults |
| GET | `/board` | All board rows: player, price inputs, valuation, projection, scores, plus snapshot info |
| POST | `/builds` | `{anchors?: [player_id]}` (default: top 12) → `{job_id}`. Returns immediately if cached. |
| GET | `/builds/{job_id}` | `{status, done, total, results?, error?}` |
| GET | `/sources` | Each source: active snapshot, last attempt, row count, unmatched names |
| POST | `/sources/refresh` | `{source_id?}`: refresh one source or all auto sources |
| POST | `/sources/{id}/import` | multipart CSV upload |
| GET | `/draft` | Draft state plus all derived state |
| POST | `/draft/setup` | `{teams: [names], me: index}` (also resets sales) |
| POST | `/draft/sales` | `{player_id, team_id, price}` |
| DELETE | `/draft/sales/{sale_id}` | Undo a sale |
| POST | `/draft/plan` | `{force?: {player_id, price}}` → plan |

## 11. Testing

- **Golden tests** use the seed data and the reference settings. They check:
  - Targets of Jokić 81, Wembanyama 79, Dončić 72, Gilgeous-Alexander 70 and Maxey 48, with a 150-row sum of 2343.
  - Maxey's Stats $ is 70 and his pay is 59.
  - Builds:
    - Every build has 13 players, spends at most $200, and fills each slot exactly once.
    - The punts are Wembanyama AST, Edwards AST and Giannis BLK, with every other build balanced.
    - Expected categories match the original output within ±0.01.
- **Unit tests:**
  - names and aliases
  - CSV validation
  - each fetcher's parser, using saved HTML fixtures
  - inflation math
  - sale validation (over max bid, full roster, duplicate player)
  - the re-plan respecting fixed players
- **End-to-end:** a headless-browser smoke test that loads every view, records a sale, and sees the re-plan update.

## 12. Frontend

- **Routes:** `#/board`, `#/stats`, `#/teams`, `#/draft`, `#/sources`, `#/settings`. Hash routing, so no server routing is needed.
- **Layout:** a header, a tab bar, a shared filter bar on the board, stats and teams views, and the content. Light and dark themes. The layout works at a 400 px phone width.

### Board
- search by name or team
- position filter
- sortable columns
- tier rows
- target with a range bar
- an expert-vs-ADP chip
- Stats $ shown in green when he's a bargain
- a "show each source" toggle
- When a draft is in progress, a "Hide sold" toggle and an inflation-adjusted price column.

### Stats
- per-game columns
- cells shaded by z-score
- a 9-cat value and stat rank

### Teams
- One card per build, with these parts:
  - a strategy chip
  - expected categories won out of 9
  - category win chances
  - the roster with "value" tags
  - spend
  - the next-best plans
- An anchor picker, so you can build around anyone.
- A Rebuild button with a progress bar.

### Draft
Three columns on desktop, stacked on a phone.
1. **Up for bid:** player search, the bid helper, record-sale form, and nomination suggestions.
2. **Your team:** your roster and plan, budget left, max bid, category chances, and punt.
3. **League:** a 12-team budget table (spent, left, spots, max bid), the sale log with undo, and the inflation indicator.

### Sources
- per-source status: active date, method, rows
- the last error
- Refresh buttons
- CSV import
- unmatched names

### Settings
- league and model forms with their defaults and help text
- Save and Reset

### States
Every view has designed loading, empty and error states. Error text says what failed and what to do next.

## 13. Repository layout

```
auction-app/
  spec.md, README.md
  server/
    requirements.txt
    app/__main__.py            python -m app  (uvicorn on 127.0.0.1:8000)
    app/main.py                FastAPI app + routes + static client
    app/settings.py            defaults, reference settings, validation (Pydantic)
    app/store.py               SQLite
    app/sources/{base,hashtag,fantasypros,rotoworld,csvio,seed}.py
    app/core/{names,engine}.py
    app/optimizer.py
    app/draft.py
    app/jobs.py
    seed/*.csv, seed/README.md
    tests/                     unittest (also runs under pytest)
  client/
    package.json, vite.config.ts, tsconfig.json, index.html
    src/main.tsx, App.tsx, api.ts, types.ts, theme.css
    src/views/{Board,Stats,Teams,Draft,Sources,Settings}.tsx
    src/components/*.tsx
```

## 14. Later (v2+)

- Points leagues and custom category weights.
- Positional scarcity in Stats $.
- Modelling rival needs: which teams still need a C, for example.
- More projection sources, such as Basketball Monster and ESPN.
