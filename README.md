# Auction Board

A AI-driven workflow web app for 2026-27 fantasy basketball salary-cap drafts:

- **Auction board.** Blended auction targets for the top 150, with each source shown separately and a production-value price (Stats $).
- **Projected stats.** Per-game projections, shaded by category value.
- **Build-around teams.** The best roster around any player.
- **Live draft room.** Records sales and tracks every team's budget and max bid. It also measures price inflation, re-plans your roster after each sale, answers "what if I win him at $X", and suggests nominations.

The defaults match your league: 12 teams, a $200 budget, 10 roster spots (PG, SG, G, SF, PF, F, C, C, UT, UT), 9-cat head-to-head. You can change any of them on the Settings page. The full design is in [spec.md](spec.md).

## Run it

You need **Python 3.11 or newer**. Node is only needed if you want to change the web client.

```bash
cd server
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app
```

Open **http://127.0.0.1:8000**. The server only listens on your own computer. Interactive API docs are at http://127.0.0.1:8000/docs.

The web client ships prebuilt in `client/dist`, so the steps above are all you need. On first start the server:

1. Loads the bundled Oct 10, 2026 data.
2. Tries to refresh each source from the web in the background. This takes about 30 seconds, since requests to the same site are spaced 5 s apart.

The Sources tab shows what each source is using and whether its last fetch worked.

## Change the web client

```bash
cd client
npm install
npm run dev        # http://127.0.0.1:5173, sends /api calls to the server on :8000
npm run build      # writes client/dist, which the Python server serves
npm run typecheck
```

Keep `python -m app` running in another terminal while you use `npm run dev`.

## Tests

```bash
cd server
python -m unittest discover -s tests -t .       # or: pytest
```

The suite takes about a minute and covers:
- **Golden tests:** with the original page's settings, the app reproduces its targets, Stats $, pay prices and all 12 build-around rosters exactly.
- **Name matching and CSV validation.**
- **The HTML parsers,** run against fixture tables.
- **Draft rules:** max bids, duplicate sales, full rosters, inflation, and re-plans that respect who owns whom.

An optional browser smoke test loads every page and records and undoes a sale. To run it:
1. `pip install playwright && playwright install chromium`
2. Start a throwaway server: `AUCTION_DB=/tmp/test.db python -m app`
3. Run `python tests/e2e_smoke.py http://127.0.0.1:8000`

## Data sources

| Source | Used for | Refresh |
|---|---|---|
| Hashtag Basketball ADP | Draft order, teams, positions | Every 12 h |
| Hashtag Basketball auction values | Yahoo and ESPN average cost (free top 30 only) | Every 12 h |
| FantasyPros projections | Season stat projections | Every 12 h |
| Rotoworld Top 200 | Expert rank | Once per article link |
| Rotoworld salary mock | Mock auction prices | Once per article link |

How fetching behaves:
- Fetching checks each site's robots.txt, identifies itself with a descriptive User-Agent, and waits 5 s between requests to the same site.
- Every result is validated before it's used. A failed or odd-looking fetch is logged on the Sources tab, and the previous data stays in use.
- You can import a CSV for any source from the Sources tab. Column formats are in `server/seed/README.md`.
- The two Rotoworld sources are dated articles. To follow a newer article, paste its link in Settings.

**Live fetching:** all five parsers were tested against the live sites on Oct 10, 2026, and every source fetched and validated. If a site changes its layout later, the fetch fails, the Sources tab says why, and the previous data stays in use. The bundled data and CSV import still work, and the parsers live in `server/app/sources/parsers.py` if you want to adjust one.

## How the numbers work

- **Target.** The average of the Yahoo average cost, the ESPN average cost, the salary-mock price, and the slot price (what the Nth priciest player cost in the mock, where N is the player's ADP rank). The result is rescaled so the top 120 targets add up to your league's $2,400.
- **Stats $.** Ranks projected production (9-cat z-scores, adjusted for games played) and prices the Nth most productive player at the market's Nth highest target.
- **Pay.** What you'd realistically pay. Underpriced players get bid halfway up to their Stats $.
- **Build-around teams and draft re-plans.** These use an integer program (SciPy/HiGHS). It fills every lineup slot within budget, tries each allowed punt, and keeps the roster that wins the most categories per week against an average drafted opponent.
  - Each team is limited to 3 bargains and 2 players at $40 or more.
  - Players projected under 50 games are left out.
- **Inflation.** Money left in the league divided by the target value of the best players still available, counting as many players as there are open spots. In the draft room, prices are adjusted by this.

Every one of these settings can be changed on the Settings page.

## Layout

```
server/  Python (FastAPI, SciPy). app/ = API, engine, optimizer, draft, sources; seed/ = bundled data; tests/
client/  React + TypeScript (Vite). src/views = Board, Stats, Teams, Draft, Sources, Settings; dist/ = prebuilt
spec.md  The full specification
```

Your settings, fetched data and the live draft are saved in `server/data/auction.db`. Delete that file to start fresh.
