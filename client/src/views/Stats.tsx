import { useMemo, useState } from "react";
import { PosFilter, SearchBox, SortHeader, useSort } from "../components";
import type { Board, Cat, Proj, Row } from "../types";
import { compare, heat, matches, posText } from "../util";

type Key = "rank" | "player" | "ztot" | "zrank" | keyof Proj;
const STAT_COLS: { k: keyof Proj; label: string; cat: Cat; fmt: (v: number) => string }[] = [
  { k: "fgp", label: "FG%", cat: "fg", fmt: (v) => v.toFixed(3).replace(/^0/, "") },
  { k: "ftp", label: "FT%", cat: "ft", fmt: (v) => v.toFixed(3).replace(/^0/, "") },
  { k: "tpm", label: "3PM", cat: "tpm", fmt: (v) => v.toFixed(1) },
  { k: "pts", label: "PTS", cat: "pts", fmt: (v) => v.toFixed(1) },
  { k: "reb", label: "REB", cat: "reb", fmt: (v) => v.toFixed(1) },
  { k: "ast", label: "AST", cat: "ast", fmt: (v) => v.toFixed(1) },
  { k: "stl", label: "STL", cat: "stl", fmt: (v) => v.toFixed(1) },
  { k: "blk", label: "BLK", cat: "blk", fmt: (v) => v.toFixed(1) },
  { k: "to", label: "TO", cat: "to", fmt: (v) => v.toFixed(1) },
];

export default function StatsView({ board }: { board: Board }) {
  const [q, setQ] = useState("");
  const [pos, setPos] = useState("ALL");
  const { sort, onSort } = useSort<Key>("rank", ["rank", "zrank", "player", "to"]);
  const cats = new Set(board.settings.league.categories);
  const list = useMemo(() => {
    const get = (r: Row) =>
      sort.key === "rank" || sort.key === "player" || sort.key === "ztot" || sort.key === "zrank" ? r[sort.key] : r.proj ? r.proj[sort.key] : null;
    return board.rows.filter((r) => matches(r, q, pos)).sort(compare(get, sort.dir, (r) => r.rank));
  }, [board.rows, q, pos, sort]);
  const na = <span className="na">—</span>;

  return (
    <section aria-label="Projected stats" style={{ display: "grid", gap: 12 }}>
      <div className="controls">
        <SearchBox id="stats-q" value={q} onChange={setQ} />
        <PosFilter value={pos} onChange={setPos} />
        <div className="count">{list.length} players · per-game projections</div>
      </div>
      <div className="legend">
        <span>Shading compares each player with the projected pool in that category:</span>
        <span><i className="sw" style={{ background: "color-mix(in srgb, var(--good) 45%, transparent)" }} />helps</span>
        <span><i className="sw" style={{ background: "color-mix(in srgb, var(--bad) 45%, transparent)" }} />hurts</span>
        {board.lg.fg != null && <span>Pool FG% {board.lg.fg.toFixed(3).replace(/^0/, "")} · FT% {board.lg.ft!.toFixed(3).replace(/^0/, "")}</span>}
      </div>
      <div className="board">
        <table>
          <thead>
            <tr>
              <SortHeader k="rank" label="#" sub="ADP order" sort={sort} onSort={onSort} left />
              <SortHeader k="player" label="Player" sort={sort} onSort={onSort} left className="pl" />
              <SortHeader k="ztot" label={`${board.settings.league.categories.length}-cat`} sub="value (z)" sort={sort} onSort={onSort} />
              <SortHeader k="zrank" label="Stat rk" sub="by value" sort={sort} onSort={onSort} />
              <SortHeader k="gp" label="GP" sort={sort} onSort={onSort} />
              <SortHeader k="min" label="MIN" sort={sort} onSort={onSort} />
              {STAT_COLS.map((c) => <SortHeader key={c.k} k={c.k} label={c.label} sort={sort} onSort={onSort} sub={cats.has(c.cat) ? undefined : "not scored"} />)}
            </tr>
          </thead>
          <tbody>
            {list.length === 0 && <tr><td colSpan={15} className="empty">No players match. Clear the search or pick another position.</td></tr>}
            {list.map((r) => (
              <tr key={r.id}>
                <td className="l rk">{r.rank}</td>
                <td className="l pl"><b>{r.player}</b><span className="meta">{r.team} · {posText(r.pos)}</span></td>
                <td className="z" style={{ ...heat(r.ztot == null ? null : r.ztot / 3), fontWeight: 600 }}>
                  {r.ztot == null ? na : `${r.ztot > 0 ? "+" : ""}${r.ztot.toFixed(1)}`}
                </td>
                <td className="z">{r.zrank ?? na}</td>
                <td className="z">{r.proj ? r.proj.gp.toFixed(0) : na}</td>
                <td className="z">{r.proj ? r.proj.min.toFixed(1) : na}</td>
                {STAT_COLS.map((c) => (
                  <td key={c.k} className="z" style={r.proj && r.z && cats.has(c.cat) ? heat(r.z[c.cat]) : undefined}>
                    {r.proj ? c.fmt(r.proj[c.k]) : na}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ margin: 0, maxWidth: "80ch" }}>
        Source: FantasyPros consensus season projections divided by projected games. FG% and FT% value is weighted by estimated shot volume.
        {board.unmatched.board_without_projection?.length ? ` No projection: ${board.unmatched.board_without_projection.join(", ")}.` : ""}
      </p>
    </section>
  );
}
