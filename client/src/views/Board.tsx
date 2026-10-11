import { Fragment, useMemo, useState } from "react";
import { PosFilter, SearchBox, SortHeader, useSort } from "../components";
import type { Board, Draft, DraftPlayer, Row } from "../types";
import { compare, matches, money, posText, tierOf } from "../util";

type Key = "rank" | "player" | "cons" | "adj" | "adp" | "rw" | "val" | "yahoo" | "espn" | "mock" | "curve" | "hb";
const ASC: Key[] = ["rank", "adp", "rw", "player"];

export default function BoardView({ board, draft }: { board: Board; draft: Draft | null }) {
  const [q, setQ] = useState("");
  const [pos, setPos] = useState("ALL");
  const [showSrc, setShowSrc] = useState(true);
  const [hideSold, setHideSold] = useState(false);
  const { sort, onSort } = useSort<Key>("rank", ASC);
  const live = (draft?.sales.length ?? 0) > 0;
  const dp = useMemo(() => new Map<string, DraftPlayer>((draft?.players ?? []).map((p) => [p.id, p])), [draft]);
  const max = Math.max(...board.rows.map((r) => r.high), 1);

  const list = useMemo(() => {
    const get = (r: Row) => (sort.key === "adj" ? dp.get(r.id)?.adj_target ?? r.cons : (r as unknown as Record<string, number | string | null>)[sort.key]);
    return board.rows
      .filter((r) => matches(r, q, pos) && !(hideSold && dp.get(r.id)?.sold_to != null))
      .sort(compare(get, sort.dir, (r) => r.rank));
  }, [board.rows, q, pos, hideSold, sort, dp]);

  const tiers = (sort.key === "rank" && sort.dir === 1) || (sort.key === "cons" && sort.dir === -1);
  const total = list.reduce((s, r) => s + r.cons, 0);
  const cols = 10 + (showSrc ? 5 : 0) + (live ? 1 : 0);
  let lastTier = "";

  return (
    <section aria-label="Auction board" style={{ display: "grid", gap: 12 }}>
      <div className="controls">
        <SearchBox id="board-q" value={q} onChange={setQ} />
        <PosFilter value={pos} onChange={setPos} />
        <label className="toggle"><input type="checkbox" checked={showSrc} onChange={(e) => setShowSrc(e.target.checked)} /> Show each source</label>
        {live && <label className="toggle"><input type="checkbox" checked={hideSold} onChange={(e) => setHideSold(e.target.checked)} /> Hide sold</label>}
        <div className="count">{list.length} players · targets total ${total.toLocaleString()} of ${(board.settings.league.budget * board.settings.league.teams).toLocaleString()} league</div>
      </div>
      <div className="board">
        <table>
          <thead>
            <tr>
              <SortHeader k="rank" label="#" sub="ADP order" sort={sort} onSort={onSort} left />
              <SortHeader k="player" label="Player" sort={sort} onSort={onSort} left className="pl" />
              <SortHeader k="cons" label="Target" sub="blended $" sort={sort} onSort={onSort} />
              {live && <SortHeader k="adj" label="Now" sub={`inflation ×${draft!.inflation.factor.toFixed(2)}`} sort={sort} onSort={onSort} />}
              <th className="l range">Source range</th>
              <SortHeader k="adp" label="ADP" sub="Y!/ESPN/FTX" sort={sort} onSort={onSort} />
              <SortHeader k="rw" label="Expert" sub="Rotoworld rank" sort={sort} onSort={onSort} />
              <SortHeader k="val" label="Stats $" sub="production value" sort={sort} onSort={onSort} />
              {showSrc && <>
                <SortHeader k="yahoo" label="Y! AAV" sub="avg cost" sort={sort} onSort={onSort} />
                <SortHeader k="espn" label="ESPN AAV" sub="avg cost" sort={sort} onSort={onSort} />
                <SortHeader k="mock" label="Mock $" sub="salary mock" sort={sort} onSort={onSort} />
                <SortHeader k="curve" label="Slot $" sub="price at rank" sort={sort} onSort={onSort} />
                <SortHeader k="hb" label="Proj $" sub="Hashtag value" sort={sort} onSort={onSort} />
              </>}
            </tr>
          </thead>
          <tbody>
            {list.length === 0 && <tr><td colSpan={cols} className="empty">No players match. Clear the search or pick another position.</td></tr>}
            {list.map((r) => {
              const d = dp.get(r.id);
              const tier = tiers ? tierOf(r.cons) : "";
              const header = tiers && tier !== lastTier;
              lastTier = tier;
              const gap = r.rw == null ? 0 : r.rank - r.rw;
              return (
                <Fragment key={r.id}>
                  {header && <tr className="tier"><td colSpan={2} className="pl">{tier}</td><td colSpan={cols - 2} /></tr>}
                  <tr className={d?.sold_to != null ? "sold" : undefined}>
                    <td className="l rk">{r.rank}</td>
                    <td className="l pl">
                      <b>{r.player}</b>
                      <span className="meta">{r.team} · {posText(r.pos)}</span>
                      {d?.sold_to != null && <span className="soldtag"> · sold to {d.sold_to_name} ${d.sold_price}</span>}
                    </td>
                    <td><span className="price">{r.cons}</span></td>
                    {live && <td className="src">{d?.sold_to != null ? <span className="na">—</span> : `$${d?.adj_target ?? r.cons}`}</td>}
                    <td className="l range">
                      <span className="rtxt">${Math.round(r.low)}–${Math.round(r.high)} · {r.n} src</span>
                      <div className="rbar">
                        <i style={{ left: `${(r.low / max) * 100}%`, width: `${Math.max(((r.high - r.low) / max) * 100, 1)}%` }} />
                        <u style={{ left: `calc(${(r.cons / max) * 100}% - 1px)` }} />
                      </div>
                    </td>
                    <td className="src">{r.adp.toFixed(1)}</td>
                    <td className="src">
                      {r.rw ?? <span className="na">—</span>}
                      {Math.abs(gap) >= 8 && <span className={`diff ${gap > 0 ? "up" : "dn"}`} title="Expert rank vs ADP rank">{gap > 0 ? "+" : ""}{gap}</span>}
                    </td>
                    <td className={`src ${r.val != null && r.val - r.cons >= 4 ? "good" : ""}`}>{money(r.val) ?? <span className="na">—</span>}</td>
                    {showSrc && <>
                      <td className="src">{money(r.yahoo, 1) ?? <span className="na">—</span>}</td>
                      <td className="src">{money(r.espn, 1) ?? <span className="na">—</span>}</td>
                      <td className="src">{money(r.mock) ?? <span className="na">—</span>}</td>
                      <td className="src">{money(r.curve) ?? <span className="na">—</span>}</td>
                      <td className="src">{money(r.hb, 1) ?? <span className="na">—</span>}</td>
                    </>}
                  </tr>
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ margin: 0, maxWidth: "80ch" }}>
        Target averages the Yahoo and ESPN average cost, the salary-mock price and the slot price, then
        {board.settings.model.rescale_market ? ` scales by ×${board.scale.toFixed(2)} so the top ${board.settings.league.teams * board.roster} targets spend your league's $${(board.settings.league.teams * board.settings.league.budget).toLocaleString()}.` : " uses the sources' scale as is."}
        {" "}Stats $ prices projected production on the same ladder; green marks a likely bargain. Source columns show raw, unscaled source values.
      </p>
    </section>
  );
}
