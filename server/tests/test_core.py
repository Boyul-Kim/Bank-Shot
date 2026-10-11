"""Name matching, CSV validation and HTML parsers (against small fixtures shaped like each site's table)."""
import unittest

from app.core import names
from app.sources import csvio, parsers


class Names(unittest.TestCase):
    def test_keys_fold_suffixes_accents_and_status(self):
        self.assertEqual(names.key("Trey Murphy III"), names.key("Trey Murphy"))
        self.assertEqual(names.key("Alperen Şengün"), names.key("Alperen Sengun"))
        self.assertEqual(names.key("Michael Porter Jr. (DTD)"), names.key("Michael Porter Jr."))
        self.assertEqual(names.key("P.J. Washington Jr."), names.key("P.J. Washington"))
        self.assertEqual(names.key("Kel’el Ware"), names.key("Kel'el Ware"))
        self.assertEqual(names.key("Herb Jones"), names.key("Herbert Jones"))

    def test_positions_and_teams(self):
        self.assertEqual(names.positions("SFPFC"), ["SF", "PF", "C"])
        self.assertEqual(names.positions("PG,SG"), ["PG", "SG"])
        self.assertEqual(names.positions("C"), ["C"])
        self.assertEqual(names.team("NYK"), "NY")
        self.assertEqual(names.team("UTH"), "UTA")


class Csv(unittest.TestCase):
    def test_missing_column_is_explained(self):
        rows = [{"player": f"P{i}", "price": "1"} for i in range(100)]
        with self.assertRaises(csvio.InvalidData) as ctx:
            csvio.validate("rotoworld_rank", rows)
        self.assertIn("rank", str(ctx.exception))

    def test_too_few_rows(self):
        with self.assertRaises(csvio.InvalidData):
            csvio.validate("hashtag_adp", [{"rank": 1, "player": "A", "team": "X", "pos": "C", "adp": 1}])

    def test_numbers_are_cleaned(self):
        rows = [{"player": f"P{i}", "price": "$1,0" + str(i % 10)} for i in range(100)]
        out = csvio.validate("rotoworld_mock", rows)
        self.assertEqual(out[3]["price"], 103.0)


def _rows(n, fn):
    return "".join(fn(i) for i in range(1, n + 1))


class Parsers(unittest.TestCase):
    def test_hashtag_adp(self):
        html = ("<table><tr><th>NAME</th><th>TEAM</th><th>YAHOO</th><th>ESPN</th><th>FANTRAX</th><th>BLEND</th></tr>"
                + _rows(120, lambda i: f"<tr><td><a href='/p'>Player {i}</a><a>P.{i}</a></td><td>NYK</td><td>PGSG</td><td>{i}.1</td>"
                                       f"<td>{i}</td><td>PG</td><td>{i}.2</td><td>{i}</td><td>C</td><td>{i}.3</td><td>{i}</td>"
                                       f"<td>{i}.5</td><td>{i}</td></tr>") + "</table>")
        rows = csvio.validate("hashtag_adp", parsers.hashtag_adp(html))
        self.assertEqual(len(rows), 120)
        self.assertEqual(rows[0], {"rank": 1.0, "player": "Player 1", "team": "NY", "pos": "PG/SG", "adp": 1.5})

    def test_hashtag_auction(self):
        head = "".join(f"<th>{h}</th>" for h in ["R#", "PLAYER", "POS", "TEAM", "GP", "MPG", "TOTAL", "VALUED AT", "Y! AVG", "ESPN AVG", "BLEND AVG"])
        html = (f"<table><tr>{head}</tr>" + _rows(30, lambda i: f"<tr><td>{i}</td><td><a>Player {i}</a></td><td>C</td><td>DEN</td><td>70</td>"
                                                          f"<td>30</td><td>5</td><td>${80 - i}.0</td><td>${81 - i}.5</td><td>${79 - i}.5</td><td>$1</td></tr>")
                + "</table>")
        rows = csvio.validate("hashtag_auction", parsers.hashtag_auction(html))
        self.assertEqual(rows[0]["hb_value"], 79.0)
        self.assertEqual(rows[0]["yahoo_aav"], 80.5)

    def test_fantasypros(self):
        cols = ["Player", "PTS", "REB", "AST", "BLK", "STL", "FG%", "FT%", "3PM", "GP", "MIN", "TO"]
        head = "".join(f"<th>{h}</th>" for h in cols)
        html = (f"<table id='data'><thead><tr>{head}</tr></thead><tbody>"
                + _rows(110, lambda i: f"<tr><td><a class='player-name'>Player {i}</a> <small>(OKC - PG,SG)</small></td>"
                                       f"<td>2,000</td><td>400</td><td>300</td><td>50</td><td>90</td><td>.480</td><td>.850</td>"
                                       f"<td>150</td><td>75</td><td>2,500</td><td>180</td></tr>") + "</tbody></table>")
        rows = csvio.validate("fantasypros_proj", parsers.fantasypros_proj(html))
        self.assertEqual(rows[0]["pts"], 2000.0)
        self.assertEqual(rows[0]["team"], "OKC")
        self.assertEqual(rows[0]["pos"], "PG/SG")

    def test_rotoworld(self):
        rank = "<table>" + _rows(150, lambda i: f"<tr><td>{i}</td><td>C</td><td>Player {i}</td><td>Denver Nuggets</td></tr>") + "</table>"
        rows = csvio.validate("rotoworld_rank", parsers.rotoworld_rank(rank))
        self.assertEqual(rows[0]["team"], "DEN")
        mock = ("<table><thead><tr><th>C</th><th>Player 1</th><th>Denver Nuggets</th><th>82</th></tr></thead><tbody>"
                + _rows(120, lambda i: f"<tr><td>G</td><td>Player {i + 1}</td><td>San Antonio Spurs</td><td>{max(1, 80 - i)}</td></tr>")
                + "</tbody></table>")
        rows = csvio.validate("rotoworld_mock", parsers.rotoworld_mock(mock))
        self.assertEqual(rows[0]["price"], 82.0)
        self.assertEqual(len(rows), 121)

    def test_unrecognized_page_raises(self):
        with self.assertRaises(parsers.ParseError):
            parsers.fantasypros_proj("<html><body>Please enable JavaScript</body></html>")


if __name__ == "__main__":
    unittest.main()
