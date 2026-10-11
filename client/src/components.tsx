import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { CatResult, Row } from "./types";
import { POSITIONS, posText, winStyle } from "./util";

export function SortHeader<K extends string>(props: {
  k: K; label: string; sub?: string; sort: { key: K; dir: 1 | -1 }; onSort: (k: K) => void; left?: boolean; className?: string;
}) {
  const active = props.sort.key === props.k;
  return (
    <th className={[props.left ? "l" : "", props.className ?? ""].join(" ").trim()}
        aria-sort={active ? (props.sort.dir === 1 ? "ascending" : "descending") : undefined}>
      <button type="button" className="sort" onClick={() => props.onSort(props.k)}>
        {props.label}<span className="arr">{active ? (props.sort.dir === 1 ? "▲" : "▼") : "▲"}</span>
      </button>
      {props.sub && <small>{props.sub}</small>}
    </th>
  );
}

export function useSort<K extends string>(initial: K, ascKeys: K[]) {
  const [sort, setSort] = useState<{ key: K; dir: 1 | -1 }>({ key: initial, dir: 1 });
  const onSort = (k: K) =>
    setSort((s) => (s.key === k ? { key: k, dir: (s.dir * -1) as 1 | -1 } : { key: k, dir: ascKeys.includes(k) ? 1 : -1 }));
  return { sort, onSort };
}

export function PosFilter(props: { value: string; onChange: (p: string) => void }) {
  return (
    <div className="field">
      <span className="lbl">Position</span>
      <div className="seg" role="group" aria-label="Position filter">
        {["ALL", ...POSITIONS].map((p) => (
          <button key={p} type="button" aria-pressed={props.value === p} onClick={() => props.onChange(p)}>
            {p === "ALL" ? "All" : p}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SearchBox(props: { value: string; onChange: (s: string) => void; id: string; placeholder?: string }) {
  return (
    <div className="field">
      <label htmlFor={props.id}>Find player</label>
      <input id={props.id} type="search" autoComplete="off" placeholder={props.placeholder ?? "Name or team"}
             value={props.value} onChange={(e) => props.onChange(e.target.value)} />
    </div>
  );
}

export function CatStrip({ cats }: { cats: CatResult[] }) {
  return (
    <div className="cats" style={{ ["--n" as string]: cats.length }}>
      {cats.map((c) =>
        c.punted ? (
          <div key={c.cat} className="cat punted" title={`${c.cat}: punted`}>{c.cat}<b>punt</b></div>
        ) : (
          <div key={c.cat} className="cat" style={winStyle(c.win)} title={`${c.cat}: ${Math.round(c.win * 100)}% weekly win chance`}>
            {c.cat}<b>{Math.round(c.win * 100)}%</b>
          </div>
        ))}
    </div>
  );
}

export function Notice(props: { kind?: "error" | "warn" | "info"; children: ReactNode }) {
  return <div className={`notice ${props.kind ?? ""}`} role={props.kind === "error" ? "alert" : undefined}>{props.children}</div>;
}

/** Type-ahead player picker. */
export function PlayerPicker(props: {
  rows: Row[]; onPick: (r: Row) => void; id: string; label: string; exclude?: Set<string>; extra?: (r: Row) => ReactNode;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  const hits = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    return props.rows.filter((r) => !props.exclude?.has(r.id) && r.player.toLowerCase().includes(s)).slice(0, 12);
  }, [q, props.rows, props.exclude]);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const pick = (r: Row) => { props.onPick(r); setQ(""); setOpen(false); setCursor(0); };
  return (
    <div className="field search" ref={box}>
      <label htmlFor={props.id}>{props.label}</label>
      <input id={props.id} type="search" autoComplete="off" placeholder="Start typing a name" value={q}
             role="combobox" aria-expanded={open && hits.length > 0} aria-controls={`${props.id}-list`}
             onChange={(e) => { setQ(e.target.value); setOpen(true); setCursor(0); }}
             onFocus={() => setOpen(true)}
             onKeyDown={(e) => {
               if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, hits.length - 1)); }
               else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
               else if (e.key === "Enter" && hits[cursor]) { e.preventDefault(); pick(hits[cursor]); }
               else if (e.key === "Escape") setOpen(false);
             }} />
      {open && hits.length > 0 && (
        <div className="results" id={`${props.id}-list`} role="listbox">
          {hits.map((r, i) => (
            <button key={r.id} type="button" role="option" aria-selected={i === cursor} onMouseDown={(e) => e.preventDefault()} onClick={() => pick(r)}>
              <span><b>{r.player}</b> <span className="meta">{r.team} · {posText(r.pos)} · #{r.rank}</span></span>
              <span className="meta">{props.extra ? props.extra(r) : `$${r.cons}`}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
