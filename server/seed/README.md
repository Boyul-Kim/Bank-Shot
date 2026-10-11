# Seed data and CSV import formats

These files are the Oct 10, 2026 snapshot the app loads on first run. You can import a CSV in the same format for any source from the Sources tab.

Each CSV needs a header row with the column names below; the order of the columns doesn't matter. Player names are matched across sources after accents, punctuation, suffixes (Jr., III) and status tags like "(OUT)" are removed. Team codes like NYK and GS are both accepted. Numbers may include `$` and thousands separators.

| File / source | Required columns | Optional | Notes |
|---|---|---|---|
| `hashtag_adp.csv` | `rank, player, team, pos, adp` | | `rank` = draft order (1 = first). `pos` like `PG/SG` or `PF,C`. At least 100 rows. This list defines the board. |
| `hashtag_auction.csv` | `player, hb_value, yahoo_aav, espn_aav` | `team` | Average auction cost on Yahoo and ESPN, plus Hashtag's own projected $. At least 10 rows. |
| `fantasypros_proj.csv` | `player, pts, reb, ast, blk, stl, fgp, ftp, tpm, gp, min, to` | `team, pos` | **Season totals** (the app divides by `gp`). `fgp`/`ftp` as decimals (`.475`). At least 100 rows. |
| `rotoworld_rank.csv` | `rank, player` | `team` | Expert rank. At least 100 rows. |
| `rotoworld_mock.csv` | `player, price` | `team` | Prices from a 12-team $200 salary mock. At least 100 rows. |

A file that is missing a column, has too few rows, or has many unreadable numbers is rejected with a message that says what to fix. The data already in use stays active.
