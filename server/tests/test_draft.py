"""Live draft rules: sale validation, inflation, and re-plans that respect who owns whom."""
import unittest
from pathlib import Path

from app import draft
from app.core.engine import compute_board
from app.optimizer import Infeasible
from app.settings import defaults
from app.sources import csvio

SEED = Path(__file__).resolve().parent.parent / "seed"
SRC = {sid: csvio.validate(sid, csvio.read_csv((SEED / f"{sid}.csv").read_text())) for sid in csvio.SCHEMAS}
SETTINGS = defaults()
ROWS = compute_board(SRC, SETTINGS)["rows"]
BY_ID = {r["id"]: r for r in ROWS}
TEAMS = [{"id": i, "name": "Me" if i == 0 else f"T{i + 1}", "is_me": i == 0} for i in range(12)]


def state(*sales):
    return {"teams": TEAMS, "sales": [{"id": i + 1, "player_id": p, "team_id": t, "price": c} for i, (p, t, c) in enumerate(sales)]}


class Sales(unittest.TestCase):
    def test_max_bid_keeps_a_dollar_per_open_spot(self):
        t = draft.team_status(BY_ID, SETTINGS, state())[1]
        self.assertEqual(t["max_bid"], 200 - 9)
        with self.assertRaises(draft.SaleError) as ctx:
            draft.validate_sale(BY_ID, SETTINGS, state(), "nikola-jokic", 1, 192)
        self.assertIn("at most $191", str(ctx.exception))

    def test_duplicate_and_full_roster(self):
        s = state(("nikola-jokic", 1, 80))
        with self.assertRaises(draft.SaleError):
            draft.validate_sale(BY_ID, SETTINGS, s, "nikola-jokic", 2, 10)
        full = state(*[(ROWS[i]["id"], 2, 1) for i in range(10)])
        with self.assertRaises(draft.SaleError) as ctx:
            draft.validate_sale(BY_ID, SETTINGS, full, ROWS[20]["id"], 2, 1)
        self.assertIn("full roster", str(ctx.exception))

    def test_unknown_player(self):
        with self.assertRaises(draft.SaleError):
            draft.validate_sale(BY_ID, SETTINGS, state(), "nobody", 0, 5)


class Inflation(unittest.TestCase):
    def test_starts_near_one_and_rises_after_a_bargain(self):
        start = draft.inflation(ROWS, SETTINGS, state())["factor"]
        self.assertAlmostEqual(start, 1.0, delta=0.02)
        cheap = draft.inflation(ROWS, SETTINGS, state(("nikola-jokic", 1, 40)))["factor"]
        self.assertGreater(cheap, start)
        pricey = draft.inflation(ROWS, SETTINGS, state(("nikola-jokic", 1, 120)))["factor"]
        self.assertLess(pricey, start)


class Plan(unittest.TestCase):
    def test_plan_keeps_my_players_and_skips_taken_ones(self):
        s = state(("victor-wembanyama", 0, 85), ("nikola-jokic", 3, 84), ("tyrese-maxey", 0, 50))
        p = draft.plan(ROWS, SETTINGS, s)
        ids = [x["id"] for x in p["roster"]]
        self.assertIn("victor-wembanyama", ids)
        self.assertIn("tyrese-maxey", ids)
        self.assertNotIn("nikola-jokic", ids)
        self.assertEqual(len(ids), 10)
        self.assertLessEqual(p["planned_spend"], 200)
        self.assertEqual(p["spent"], 135)

    def test_what_if_and_nominations(self):
        s = state()
        base = draft.plan(ROWS, SETTINGS, s)
        what = draft.plan(ROWS, SETTINGS, s, {"player_id": "luka-doncic", "price": 75})
        self.assertTrue(any(x["id"] == "luka-doncic" and x["forced"] for x in what["roster"]))
        noms = draft.nominations(ROWS, SETTINGS, s, base["plan_ids"])
        self.assertTrue(noms)
        self.assertFalse(set(n["id"] for n in noms) & set(base["plan_ids"]))

    def test_overspend_what_if_is_refused(self):
        with self.assertRaises(Infeasible):
            draft.plan(ROWS, SETTINGS, state(("victor-wembanyama", 0, 150)), {"player_id": "luka-doncic", "price": 60})


if __name__ == "__main__":
    unittest.main()
