"""Live draft room: sale validation, league budgets, inflation, re-planning and nomination ideas. Pure functions."""
from .optimizer import Infeasible, baseline, best_roster
from .settings import Settings


class SaleError(ValueError):
    pass


def team_status(rows_by_id, settings: Settings, state: dict) -> list[dict]:
    L = settings.league
    out = []
    for t in state["teams"]:
        sales = [s for s in state["sales"] if s["team_id"] == t["id"]]
        spent = sum(s["price"] for s in sales)
        left = L.budget - spent
        spots = L.roster - len(sales)
        out.append({
            **t, "spent": spent, "left": left, "spots_left": spots,
            "max_bid": left - (spots - 1) if spots > 0 else 0,
            "roster": [{"sale_id": s["id"], "id": s["player_id"], "player": rows_by_id.get(s["player_id"], {}).get("player", s["player_id"]),
                        "pos": rows_by_id.get(s["player_id"], {}).get("pos", []), "price": s["price"]} for s in sales],
        })
    return out


def validate_sale(rows_by_id, settings: Settings, state: dict, player_id: str, team_id: int, price: int):
    if player_id not in rows_by_id:
        raise SaleError("That player isn't on the board. Pick him from the search list.")
    sold = next((s for s in state["sales"] if s["player_id"] == player_id), None)
    if sold:
        owner = next((t["name"] for t in state["teams"] if t["id"] == sold["team_id"]), "another team")
        raise SaleError(f"{rows_by_id[player_id]['player']} was already sold to {owner} for ${sold['price']}.")
    team = next((t for t in team_status(rows_by_id, settings, state) if t["id"] == team_id), None)
    if team is None:
        raise SaleError("Pick the team that won the bid.")
    if team["spots_left"] <= 0:
        raise SaleError(f"{team['name']} already has a full roster.")
    if price < 1:
        raise SaleError("A winning bid is at least $1.")
    if price > team["max_bid"]:
        raise SaleError(f"{team['name']} can bid at most ${team['max_bid']}: ${team['left']} left with "
                        f"{team['spots_left']} spots to fill at $1 minimum.")


def inflation(rows, settings: Settings, state: dict, teams=None) -> dict:
    sold = {s["player_id"] for s in state["sales"]}
    teams = teams if teams is not None else team_status({r["id"]: r for r in rows}, settings, state)
    money = sum(t["left"] for t in teams)
    spots = sum(max(t["spots_left"], 0) for t in teams)
    avail = sorted((r for r in rows if r["id"] not in sold), key=lambda r: -r["cons"])[:spots]
    value = sum(r["cons"] for r in avail)
    factor = money / value if value > 0 and spots > 0 else 1.0
    return {"factor": round(factor, 4), "money_left": money, "spots_left": spots, "value_left": value}


def derive(rows, settings: Settings, state: dict) -> dict:
    by_id = {r["id"]: r for r in rows}
    teams = team_status(by_id, settings, state)
    inf = inflation(rows, settings, state, teams)
    owner = {s["player_id"]: s for s in state["sales"]}
    names = {t["id"]: t["name"] for t in state["teams"]}
    players = []
    for r in rows:
        s = owner.get(r["id"])
        players.append({"id": r["id"], "adj_target": max(1, round(r["cons"] * inf["factor"])),
                        "adj_pay": max(1, round(r["pay"] * inf["factor"])),
                        "sold_to": s["team_id"] if s else None, "sold_to_name": names.get(s["team_id"]) if s else None,
                        "sold_price": s["price"] if s else None})
    return {"teams": teams, "inflation": inf, "players": players,
            "sales": sorted(state["sales"], key=lambda s: s["id"], reverse=True)}


def plan(rows, settings: Settings, state: dict, force: dict | None = None) -> dict:
    """Best finish for my roster: my purchases fixed, everyone else's excluded, the rest at inflated pay."""
    me = next((t for t in state["teams"] if t.get("is_me")), None)
    if me is None:
        raise Infeasible("Mark one team as yours in the draft setup.")
    inf = inflation(rows, settings, state)["factor"]
    by_id = {r["id"]: r for r in rows}
    mine = {s["player_id"]: s["price"] for s in state["sales"] if s["team_id"] == me["id"]}
    taken = {s["player_id"] for s in state["sales"] if s["team_id"] != me["id"]}
    if force:
        pid, price = force["player_id"], int(force["price"])
        if pid in taken or pid in mine:
            raise Infeasible("That player is already sold.")
        if pid not in by_id:
            raise Infeasible("That player isn't on the board.")
        mine = {**mine, pid: price}
    pool = [r for r in rows if r["proj"]]
    no_proj = [pid for pid in mine if not by_id.get(pid, {}).get("proj")]
    budget = settings.league.budget - sum(mine[p] for p in no_proj)
    roster = settings.league.roster - len(no_proj)
    cost = {r["id"]: mine.get(r["id"], max(1, round(r["pay"] * inf))) for r in pool}
    bargains = {r["id"] for r in pool if r["bargain"] and r["id"] not in mine}
    if sum(mine.values()) > settings.league.budget:
        raise Infeasible("Those prices go over your budget.")
    if len(mine) > settings.league.roster:
        raise Infeasible("Your roster is already full.")
    res = best_roster(pool, settings, cost=cost, star_basis=cost, fixed=set(mine) - set(no_proj), excluded=taken,
                      bargain_ids=bargains, iters=settings.model.draft_reweight_iters, opp=baseline(rows, settings),
                      budget=budget, roster=roster)
    team = sorted(res.pop("team"), key=lambda r: (r["id"] not in mine, -cost[r["id"]]))
    slot_of = res.pop("slot_of")
    roster_out = [{"id": r["id"], "player": r["player"], "team": r["team"], "pos": r["pos"], "rank": r["rank"],
                   "price": cost[r["id"]], "owned": r["id"] in mine, "forced": bool(force and r["id"] == force["player_id"]),
                   "slot": slot_of[r["id"]], "bargain": r["id"] in bargains} for r in team]
    roster_out += [{"id": p, "player": by_id[p]["player"], "team": by_id[p]["team"], "pos": by_id[p]["pos"],
                    "rank": by_id[p]["rank"], "price": mine[p], "owned": True, "forced": False, "slot": "—", "bargain": False}
                   for p in no_proj]
    spent = sum(mine.values())
    res.update({"roster": roster_out, "spent": spent, "planned_spend": sum(x["price"] for x in roster_out),
                "inflation": inf, "plan_ids": [x["id"] for x in roster_out if not x["owned"]]})
    return res


def nominations(rows, settings: Settings, state: dict, plan_ids: list[str], n: int = 5) -> list[dict]:
    """Players worth nominating: expensive, not in my plan, and affordable for at least two rivals."""
    d = derive(rows, settings, state)
    adj = {p["id"]: p for p in d["players"]}
    rivals = [t for t in d["teams"] if not t.get("is_me") and t["spots_left"] > 0]
    out = []
    for r in sorted(rows, key=lambda r: -r["cons"]):
        p = adj[r["id"]]
        if p["sold_to"] is not None or r["id"] in plan_ids:
            continue
        able = sum(1 for t in rivals if t["max_bid"] >= p["adj_target"])
        if able >= 2:
            out.append({"id": r["id"], "player": r["player"], "pos": r["pos"], "adj_target": p["adj_target"], "rivals_able": able})
        if len(out) >= n:
            break
    return out
