"""Merge source rows and compute targets, projections, category z-scores and production value.

Pure functions only. Input rows are already in each source's standard shape (see app/sources).
"""
import statistics
from typing import Any

from . import names
from ..settings import CATS, Settings


def _index(rows, field="player"):
    out = {}
    for r in rows or []:
        out.setdefault(names.key(r[field]), r)
    return out


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def per_game(p: dict) -> dict | None:
    gp = _num(p.get("gp"))
    if not gp:
        return None
    vals = {k: _num(p.get(k)) for k in ("pts", "reb", "ast", "blk", "stl", "tpm", "min", "to", "fgp", "ftp")}
    if any(v is None for v in vals.values()):
        return None
    out = {"gp": gp}
    for k in ("min", "pts", "reb", "ast", "stl", "blk", "tpm", "to"):
        out[k] = vals[k] / gp
    out["fgp"], out["ftp"] = vals["fgp"], vals["ftp"]
    return out


def compute_board(src: dict[str, list[dict]], settings: Settings) -> dict[str, Any]:
    L, M = settings.league, settings.model
    adp_rows = sorted(src.get("hashtag_adp") or [], key=lambda r: float(r["rank"]))[: L.board_size]
    auction = _index(src.get("hashtag_auction"))
    proj_src = _index(src.get("fantasypros_proj"))
    rank_src = _index(src.get("rotoworld_rank"))
    mock_src = _index(src.get("rotoworld_mock"))
    mock_prices = [float(r["price"]) for r in (src.get("rotoworld_mock") or []) if _num(r.get("price")) is not None]
    curve = sorted(mock_prices, reverse=True)

    rows = []
    for i, a in enumerate(adp_rows, 1):
        k = names.key(a["player"])
        m = mock_src.get(k); h = auction.get(k); rw = rank_src.get(k); pj = proj_src.get(k)
        mock = _num(m["price"]) if m else None
        c = curve[i - 1] if i <= len(curve) else 1.0
        inputs = [c] + ([mock] if mock is not None else [])
        yahoo = _num(h.get("yahoo_aav")) if h else None
        espn = _num(h.get("espn_aav")) if h else None
        if h and yahoo is not None and espn is not None:
            inputs += [yahoo, espn]
        rows.append({
            "id": names.slug(a["player"]), "rank": i, "player": names.strip_status(a["player"]),
            "team": names.team(a.get("team", "")), "pos": names.positions(a.get("pos", "")),
            "adp": round(float(a["adp"]), 1), "rw": int(float(rw["rank"])) if rw else None,
            "mock": _int_or(mock), "curve": _int_or(c),
            "hb": _num(h.get("hb_value")) if h else None, "yahoo": yahoo, "espn": espn,
            "cons": round(statistics.mean(inputs)), "low": min(inputs), "high": max(inputs), "n": len(inputs),
            "proj": per_game(pj) if pj else None,
        })

    # Rescale market prices to this league's money per drafted player.
    scale = 1.0
    if M.rescale_market and rows:
        n_drafted = min(L.teams * L.roster, len(rows))
        top = sorted((r["cons"] for r in rows), reverse=True)[:n_drafted]
        if sum(top) > 0:
            scale = L.teams * L.budget / sum(top)
            for r in rows:
                r["cons"] = max(1, round(r["cons"] * scale))
                r["low"] = round(r["low"] * scale, 1)
                r["high"] = round(r["high"] * scale, 1)

    # Category z-scores over the projected pool (per game).
    pool = [r for r in rows if r["proj"]]
    lg = {"fg": None, "ft": None}
    if pool:
        for r in pool:
            p = r["proj"]
            fta = M.fta_per_pt * p["pts"]
            ftm = fta * p["ftp"]
            p["_fga"] = max((p["pts"] - ftm - p["tpm"]) / 2, 0.1) / p["fgp"] if p["fgp"] else 0.0
            p["_fta"] = fta
        fga_sum = sum(r["proj"]["_fga"] for r in pool) or 1
        fta_sum = sum(r["proj"]["_fta"] for r in pool) or 1
        lg_fg = sum(r["proj"]["fgp"] * r["proj"]["_fga"] for r in pool) / fga_sum
        lg_ft = sum(r["proj"]["ftp"] * r["proj"]["_fta"] for r in pool) / fta_sum
        lg = {"fg": round(lg_fg, 3), "ft": round(lg_ft, 3)}
        raw = []
        for r in pool:
            p = r["proj"]
            raw.append({"fg": (p["fgp"] - lg_fg) * p["_fga"], "ft": (p["ftp"] - lg_ft) * p["_fta"], "tpm": p["tpm"],
                        "pts": p["pts"], "reb": p["reb"], "ast": p["ast"], "stl": p["stl"], "blk": p["blk"], "to": -p["to"]})
        mu = {c: statistics.mean(v[c] for v in raw) for c in CATS}
        sd = {c: statistics.pstdev(v[c] for v in raw) or 1.0 for c in CATS}
        for r, v in zip(pool, raw):
            z = {c: (v[c] - mu[c]) / sd[c] for c in CATS}
            r["z"] = {c: round(x, 2) for c, x in z.items()}
            r["ztot"] = round(sum(z[c] for c in L.categories), 2)
        for i, r in enumerate(sorted(pool, key=lambda r: -r["ztot"]), 1):
            r["zrank"] = i

        # Production value on the market's own price ladder.
        market = sorted((r["cons"] for r in rows), reverse=True)
        for i, r in enumerate(sorted(pool, key=lambda r: -(r["ztot"] * avail(r))), 0):
            r["val"] = market[i] if i < len(market) else 1

    for r in rows:
        if r["proj"]:
            r["pay"] = max(r["cons"], round(r["cons"] + M.bargain_bid_up * (r["val"] - r["cons"])), 1)
            r["bargain"] = r["val"] - r["pay"] >= M.bargain_threshold
            r["proj"] = {k: (round(v, 3) if k in ("fgp", "ftp") else round(v, 1) if k != "gp" else v)
                         for k, v in r["proj"].items() if not k.startswith("_")}
        else:
            r.update({"z": None, "ztot": None, "zrank": None, "val": None, "pay": max(r["cons"], 1), "bargain": False})

    known = {names.key(x["player"]) for x in src.get("hashtag_adp") or []}
    unmatched = {sid: sorted(r["player"] for r in (src.get(sid) or []) if names.key(r["player"]) not in known)
                 for sid in ("hashtag_auction", "fantasypros_proj", "rotoworld_rank", "rotoworld_mock")}
    unmatched["board_without_projection"] = [r["player"] for r in rows if not r["proj"]]
    return {"rows": rows, "lg": lg, "scale": round(scale, 4), "unmatched": unmatched}


def avail(r) -> float:
    return min(r["proj"]["gp"] / 75, 1.0)


def _int_or(v):
    if v is None:
        return None
    return int(v) if float(v).is_integer() else v
