"""HTML parsers for each source. Each returns rows in the source's CSV schema (see csvio.SCHEMAS).

Parsers locate tables by their header text rather than by CSS ids, so small layout changes don't break them.
If a site changes its table structure, the parser raises ParseError and the previous snapshot stays active.
"""
import re

from bs4 import BeautifulSoup

from ..core import names

NBA_TEAMS = {
    "atlanta hawks": "ATL", "boston celtics": "BOS", "brooklyn nets": "BKN", "charlotte hornets": "CHA",
    "chicago bulls": "CHI", "cleveland cavaliers": "CLE", "dallas mavericks": "DAL", "denver nuggets": "DEN",
    "detroit pistons": "DET", "golden state warriors": "GS", "houston rockets": "HOU", "indiana pacers": "IND",
    "la clippers": "LAC", "los angeles clippers": "LAC", "los angeles lakers": "LAL", "memphis grizzlies": "MEM",
    "miami heat": "MIA", "milwaukee bucks": "MIL", "minnesota timberwolves": "MIN", "new orleans pelicans": "NO",
    "new york knicks": "NY", "oklahoma city thunder": "OKC", "orlando magic": "ORL", "philadelphia 76ers": "PHI",
    "phoenix suns": "PHO", "portland trail blazers": "POR", "sacramento kings": "SAC", "san antonio spurs": "SA",
    "toronto raptors": "TOR", "utah jazz": "UTA", "washington wizards": "WAS",
}


class ParseError(ValueError):
    pass


def _txt(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el is not None else ""


def _num(s):
    s = (s or "").replace(",", "").replace("$", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _player_name(cell) -> str:
    a = cell.find("a")
    return _txt(a) if a is not None and _txt(a) else _txt(cell)


def _tables(html):
    return BeautifulSoup(html, "lxml").find_all("table")


def _header(table) -> list[str]:
    ths = table.find_all("th")
    return [_txt(th).upper() for th in ths]


def hashtag_adp(html: str) -> list[dict]:
    """Hashtag Basketball ADP: NAME | TEAM | Yahoo (POS ADP ORDER) | ESPN (...) | Fantrax (...) | BLEND (ADP ORDER)."""
    best = None
    for t in _tables(html):
        if "BLEND" in " ".join(_header(t)) or "NAME" in _header(t):
            best = t if best is None or len(t.find_all("tr")) > len(best.find_all("tr")) else best
    if best is None:
        raise ParseError("Couldn't find the ADP table (no BLEND column).")
    rows = []
    for tr in best.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        adp, order = _num(_txt(tds[-2])), _num(_txt(tds[-1]))
        if adp is None or order is None:
            continue
        pos = next((_txt(td) for td in tds[2:-2] if names.positions(_txt(td)) and _num(_txt(td)) is None), "")
        rows.append({"rank": order, "player": _player_name(tds[0]), "team": names.team(_txt(tds[1])),
                     "pos": "/".join(names.positions(pos)), "adp": adp})
    rows.sort(key=lambda r: r["rank"])
    return rows


def hashtag_auction(html: str) -> list[dict]:
    """Hashtag Basketball auction values: R# | PLAYER | POS | TEAM | GP | MPG | TOTAL | VALUED AT | Y! AVG | ESPN AVG | BLEND AVG."""
    for t in _tables(html):
        head = _header(t)
        if "VALUED AT" in head and "Y! AVG" in head:
            ix = {h: i for i, h in enumerate(head)}
            rows = []
            for tr in t.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < len(head):
                    continue
                v, y, e = (_num(_txt(tds[ix[k]])) for k in ("VALUED AT", "Y! AVG", "ESPN AVG"))
                if v is None:
                    continue
                rows.append({"player": _player_name(tds[ix["PLAYER"]]), "team": names.team(_txt(tds[ix["TEAM"]])),
                             "hb_value": v, "yahoo_aav": y, "espn_aav": e})
            return rows
    raise ParseError("Couldn't find the auction values table (no VALUED AT / Y! AVG columns).")


def fantasypros_proj(html: str) -> list[dict]:
    """FantasyPros projections: Player (TEAM - POS) | PTS | REB | AST | BLK | STL | FG% | FT% | 3PM | GP | MIN | TO."""
    want = {"PTS": "pts", "REB": "reb", "AST": "ast", "BLK": "blk", "STL": "stl", "FG%": "fgp", "FT%": "ftp",
            "3PM": "tpm", "GP": "gp", "MIN": "min", "TO": "to"}
    for t in _tables(html):
        head = _header(t)
        if not all(k in head for k in want):
            continue
        ix = {h: i for i, h in enumerate(head)}
        p_ix = next((i for i, h in enumerate(head) if h.startswith("PLAYER")), 0)
        rows = []
        for tr in t.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < len(head):
                continue
            cell = tds[p_ix]
            m = re.search(r"\(([A-Z]{2,4})\s*-\s*([A-Z,/ ]+)\)", _txt(cell))
            rec = {"player": names.strip_status(_player_name(cell)),
                   "team": names.team(m.group(1)) if m else "", "pos": "/".join(names.positions(m.group(2))) if m else ""}
            ok = True
            for k, f in want.items():
                v = _num(_txt(tds[ix[k]]))
                if v is None:
                    ok = False
                    break
                rec[f] = v
            if ok:
                rows.append(rec)
        return rows
    raise ParseError("Couldn't find the projections table (expected PTS, REB, AST, BLK, STL, FG%, FT%, 3PM, GP, MIN, TO).")


def rotoworld_rank(html: str) -> list[dict]:
    """Rotoworld Top 200 article: Rank | Position(s) | Name | Team."""
    for t in _tables(html):
        rows = []
        for tr in t.find_all("tr"):
            cells = [_txt(c) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 4 and _num(cells[0]) is not None:
                rows.append({"rank": _num(cells[0]), "player": names.strip_status(cells[2]),
                             "team": NBA_TEAMS.get(cells[3].lower(), names.team(cells[3]))})
        if len(rows) >= 100:
            return rows
    raise ParseError("Couldn't find a ranking table with at least 100 rows (Rank, Position, Name, Team).")


def rotoworld_mock(html: str) -> list[dict]:
    """Rotoworld salary mock: the 'final price' chart, Position | Player | Team | Price (four columns)."""
    for t in _tables(html):
        rows = []
        for tr in t.find_all("tr"):
            cells = [_txt(c) for c in tr.find_all(["td", "th"])]
            if len(cells) == 4 and _num(cells[3]) is not None and _num(cells[1]) is None:
                rows.append({"player": names.strip_status(cells[1]),
                             "team": NBA_TEAMS.get(cells[2].lower(), names.team(cells[2])), "price": _num(cells[3])})
        if len(rows) >= 100:
            return rows
    raise ParseError("Couldn't find the final-price table (Position, Player, Team, Price) with at least 100 rows.")


PARSERS = {
    "hashtag_adp": hashtag_adp, "hashtag_auction": hashtag_auction, "fantasypros_proj": fantasypros_proj,
    "rotoworld_rank": rotoworld_rank, "rotoworld_mock": rotoworld_mock,
}
