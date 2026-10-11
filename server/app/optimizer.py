"""Roster optimizer: a mixed-integer program solved with SciPy's HiGHS (scipy.optimize.milp).

Used for build-around teams (one anchor fixed) and for live-draft re-plans (your purchases fixed).
"""
import math

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from .core.engine import avail
from .settings import CAT_LABEL, Settings

ELIG = {
    "PG": lambda p: "PG" in p, "SG": lambda p: "SG" in p, "G": lambda p: "PG" in p or "SG" in p,
    "SF": lambda p: "SF" in p, "PF": lambda p: "PF" in p, "F": lambda p: "SF" in p or "PF" in p,
    "C": lambda p: "C" in p,
}


def phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


class Infeasible(Exception):
    pass


def baseline(rows, settings: Settings) -> dict:
    """Category totals of a typical opposing roster.

    'drafted': roster size x the average of the players a league this size actually drafts (top teams*roster by target).
    'pool': zero, i.e. the average of the whole projected board (the original page's assumption).
    """
    cats = settings.league.categories
    if settings.model.opponent_baseline == "pool":
        return {c: 0.0 for c in cats}
    pool = [r for r in rows if r["proj"]]
    n = min(settings.league.teams * settings.league.roster, len(pool))
    top = sorted(pool, key=lambda r: -r["cons"])[:n]
    return {c: settings.league.roster * sum(r["z"][c] * avail(r) for r in top) / max(n, 1) for c in cats}


def solve_once(pool, settings: Settings, *, punt, weights, cost, star_basis, fixed, excluded, bargain_ids, opp, budget=None, roster=None):
    """One MILP solve. Returns (selected rows, slot labels by id, team z by category, win prob by category)."""
    L, M = settings.league, settings.model
    cats = L.categories
    slots = [s for s in L.slots if s != "UT"]
    n, S = len(pool), len(slots)
    nv = n + n * S
    val = np.array([sum(weights[c] * r["z"][c] for c in cats if c != punt) * avail(r) for r in pool])
    obj = np.zeros(nv)
    obj[:n] = -val
    A, lo, hi = [], [], []

    def row():
        return np.zeros(nv)

    R = L.roster if roster is None else roster
    a = row(); a[:n] = 1; A.append(a); lo.append(R); hi.append(R)
    a = row(); a[:n] = [cost[r["id"]] for r in pool]; A.append(a); lo.append(0); hi.append(budget if budget is not None else L.budget)
    a = row(); a[:n] = [1 if star_basis[r["id"]] >= M.star_price else 0 for r in pool]; A.append(a); lo.append(0); hi.append(M.max_stars)
    a = row(); a[:n] = [1 if r["id"] in bargain_ids else 0 for r in pool]; A.append(a); lo.append(0); hi.append(M.max_bargains)
    for s in range(S):
        a = row()
        for i in range(n):
            a[n + i * S + s] = 1
        A.append(a); lo.append(1); hi.append(1)
    for i in range(n):
        a = row(); a[n + i * S:n + (i + 1) * S] = 1; a[i] = -1
        A.append(a); lo.append(-np.inf); hi.append(0)
    ub = np.ones(nv); lb = np.zeros(nv)
    for i, r in enumerate(pool):
        if r["id"] in fixed:
            lb[i] = 1
        elif r["id"] in excluded or r["proj"]["gp"] < M.min_gp:
            ub[i] = 0
        for s, sl in enumerate(slots):
            if not ELIG[sl](r["pos"]):
                ub[n + i * S + s] = 0
    res = milp(obj, constraints=LinearConstraint(np.array(A), lo, hi), integrality=np.ones(nv), bounds=Bounds(lb, ub))
    if not res.success or res.x is None:
        raise Infeasible("No roster fits these constraints: check the budget, roster slots, and the players already taken.")
    team = [pool[i] for i in range(n) if res.x[i] > 0.5]
    slot_of = {}
    for i in range(n):
        for s in range(S):
            if res.x[n + i * S + s] > 0.5:
                slot_of[pool[i]["id"]] = slots[s]
    n_ut = L.slots.count("UT")
    for r in sorted((r for r in team if r["id"] not in slot_of), key=lambda r: -r["ztot"]):
        slot_of[r["id"]] = "UT" if n_ut > 0 else "BN"
        n_ut -= 1
    tz = {c: sum(r["z"][c] * avail(r) for r in team) for c in cats}
    win = {c: phi((tz[c] - opp[c]) / M.sigma) for c in cats}
    return team, slot_of, tz, win


def best_roster(pool, settings: Settings, *, cost, star_basis, fixed, excluded, bargain_ids, iters, opp, punt_guard=None, budget=None, roster=None):
    """Try every allowed punt with iterative category re-weighting; keep the plan that wins the most categories."""
    cats = settings.league.categories
    sigma = settings.model.sigma
    best, options = None, []
    for punt in settings.model.punt_options:
        if punt is not None and (punt not in cats or (punt_guard and punt_guard(punt))):
            continue
        w = {c: 1.0 for c in cats}
        pbest = None
        for _ in range(iters):
            team, slot_of, tz, win = solve_once(pool, settings, punt=punt, weights=w, cost=cost, star_basis=star_basis,
                                                fixed=fixed, excluded=excluded, bargain_ids=bargain_ids, opp=opp, budget=budget, roster=roster)
            ecw = sum(win.values())
            if pbest is None or ecw > pbest[0] + 1e-9:
                pbest = (ecw, punt, team, slot_of, tz, win)
            dens = {c: math.exp(-0.5 * ((tz[c] - opp[c]) / sigma) ** 2) for c in cats}
            m = max(dens.values())
            w = {c: 0.5 * w[c] + 0.5 * dens[c] / m for c in cats}
        options.append((punt, pbest[0]))
        if best is None or pbest[0] > best[0] + 1e-9:
            best = pbest
    if best is None:
        raise Infeasible("No punt option is allowed with these settings.")
    ecw, punt, team, slot_of, tz, win = best
    options.sort(key=lambda x: -x[1])
    return {
        "punt": CAT_LABEL[punt] if punt else None,
        "expected_cats": round(ecw, 2),
        "alternatives": [{"punt": CAT_LABEL[p] if p else None, "expected_cats": round(e, 2)} for p, e in options[:3]],
        "cats": [{"cat": CAT_LABEL[c], "z": round(tz[c] - opp[c], 1), "win": round(win[c], 2), "punted": c == punt} for c in cats],
        "team": team, "slot_of": slot_of,
    }


def build_around(rows, settings: Settings, anchor_id: str) -> dict:
    """Best roster around one anchor at his target price, everyone else at realistic pay."""
    pool = [r for r in rows if r["proj"]]
    anchor = next((r for r in pool if r["id"] == anchor_id), None)
    if anchor is None:
        raise Infeasible("That player has no projection, so a roster can't be built around him.")
    cost = {r["id"]: (max(r["cons"], 1) if r["id"] == anchor_id else r["pay"]) for r in pool}
    star_basis = {r["id"]: r["pay"] for r in pool}
    bargains = {r["id"] for r in pool if r["bargain"]}
    guard = settings.model.anchor_punt_guard
    res = best_roster(pool, settings, cost=cost, star_basis=star_basis, fixed={anchor_id}, excluded=set(),
                      bargain_ids=bargains, iters=settings.model.reweight_iters, opp=baseline(rows, settings),
                      punt_guard=lambda p: anchor["z"][p] > guard)
    team = sorted(res.pop("team"), key=lambda r: (r["id"] != anchor_id, -r["cons"]))
    slot_of = res.pop("slot_of")
    res.update({
        "anchor_id": anchor_id, "anchor": anchor["player"], "anchor_price": anchor["cons"],
        "spend": sum(cost[r["id"]] for r in team),
        "roster": [{"id": r["id"], "player": r["player"], "team": r["team"], "pos": r["pos"], "rank": r["rank"],
                    "price": cost[r["id"]], "target": max(r["cons"], 1), "slot": slot_of[r["id"]],
                    "bargain": r["bargain"] and r["id"] != anchor_id} for r in team],
    })
    return res
