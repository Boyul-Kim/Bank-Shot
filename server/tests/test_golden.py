"""The app reproduces the original Oct 10, 2026 board and build-around teams from the seed data and reference settings."""
import unittest
from pathlib import Path

from app.core.engine import compute_board
from app.optimizer import build_around
from app.settings import defaults, reference
from app.sources import csvio

SEED = Path(__file__).resolve().parent.parent / "seed"
SRC = {sid: csvio.validate(sid, csvio.read_csv((SEED / f"{sid}.csv").read_text())) for sid in csvio.SCHEMAS}

EXPECTED_BUILDS = [  # anchor, punt, expected categories won (original page)
    ("Nikola Jokic", None, 5.34), ("Victor Wembanyama", "AST", 5.28), ("Luka Doncic", None, 5.14),
    ("Shai Gilgeous-Alexander", None, 5.33), ("Cade Cunningham", None, 5.13), ("Giannis Antetokounmpo", "BLK", 5.16),
    ("Anthony Edwards", "AST", 5.38), ("Jayson Tatum", None, 5.23), ("Jalen Johnson", None, 5.18),
    ("Tyrese Maxey", None, 5.32), ("Cooper Flagg", None, 5.17), ("Donovan Mitchell", None, 5.33),
]


class GoldenBoard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = compute_board(SRC, reference())
        cls.by_name = {r["player"]: r for r in cls.board["rows"]}

    def test_targets(self):
        for name, target in [("Nikola Jokic", 81), ("Victor Wembanyama", 79), ("Luka Doncic", 72),
                             ("Shai Gilgeous-Alexander", 70), ("Tyrese Maxey", 48)]:
            self.assertEqual(self.by_name[name]["cons"], target, name)
        self.assertEqual(sum(r["cons"] for r in self.board["rows"]), 2343)

    def test_stats_value_and_pay(self):
        maxey = self.by_name["Tyrese Maxey"]
        self.assertEqual((maxey["val"], maxey["pay"]), (70, 59))
        self.assertEqual(self.by_name["Nikola Jokic"]["zrank"], 1)

    def test_missing_projections_are_reported(self):
        self.assertEqual(sorted(self.board["unmatched"]["board_without_projection"]), ["Maxime Raynaud", "Sandro Mamukelashvili"])


class GoldenBuilds(unittest.TestCase):
    def test_builds_match_original(self):
        settings = reference()
        board = compute_board(SRC, settings)
        ids = {r["player"]: r["id"] for r in board["rows"]}
        for anchor, punt, ecw in EXPECTED_BUILDS:
            b = build_around(board["rows"], settings, ids[anchor])
            self.assertEqual(b["punt"], punt, anchor)
            self.assertAlmostEqual(b["expected_cats"], ecw, delta=0.01, msg=anchor)
            self.assertEqual(len(b["roster"]), 13)
            self.assertLessEqual(b["spend"], 200)
            self.assertEqual(b["roster"][0]["player"], anchor)
            slots = [p["slot"] for p in b["roster"]]
            for s in ("PG", "SG", "G", "SF", "PF", "F"):
                self.assertEqual(slots.count(s), 1, f"{anchor} {s}")
            self.assertEqual(slots.count("C"), 2)


class DefaultLeague(unittest.TestCase):
    def test_rescale_spends_league_money(self):
        s = defaults()
        board = compute_board(SRC, s)
        top = sorted((r["cons"] for r in board["rows"]), reverse=True)[: s.league.teams * s.league.roster]
        self.assertAlmostEqual(sum(top), s.league.teams * s.league.budget, delta=25)

    def test_ten_man_build(self):
        s = defaults()
        board = compute_board(SRC, s)
        b = build_around(board["rows"], s, board["rows"][0]["id"])
        self.assertEqual(len(b["roster"]), 10)
        self.assertLessEqual(b["spend"], 200)
        self.assertEqual(sum(1 for p in b["roster"] if p["slot"] == "UT"), 2)


if __name__ == "__main__":
    unittest.main()
