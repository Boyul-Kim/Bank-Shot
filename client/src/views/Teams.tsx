import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { CatStrip, Notice, PlayerPicker } from "../components";
import type { Board, Build, Job } from "../types";
import { posText } from "../util";

export default function TeamsView({ board }: { board: Board }) {
  const projected = useMemo(() => board.rows.filter((r) => r.proj), [board.rows]);
  const defaults = useMemo(() => projected.slice(0, board.settings.model.anchors).map((r) => r.id), [projected, board.settings.model.anchors]);
  const [anchors, setAnchors] = useState<string[]>(defaults);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const byId = useMemo(() => new Map(board.rows.map((r) => [r.id, r])), [board.rows]);

  const stop = () => { if (timer.current) window.clearTimeout(timer.current); timer.current = null; };
  const poll = useCallback((id: string) => {
    timer.current = window.setTimeout(async () => {
      try {
        const j = await api.build(id);
        setJob(j);
        if (j.status === "running") poll(id);
        else if (j.status === "failed") setError(j.error ?? "The build failed.");
      } catch (e) { setError((e as Error).message); }
    }, 800);
  }, []);

  const run = useCallback(async (ids: string[]) => {
    stop();
    setError(null);
    try {
      const j = await api.startBuilds(ids);
      setJob(j);
      if (j.status === "running") poll(j.id);
    } catch (e) { setError((e as Error).message); }
  }, [poll]);

  useEffect(() => { setAnchors(defaults); run(defaults); return stop; }, [defaults, run]);

  const running = job?.status === "running";
  const results = (job?.status === "done" ? job.results : null) ?? [];

  return (
    <section aria-label="Build-around teams" style={{ display: "grid", gap: 14 }}>
      <div className="panel">
        <div className="controls">
          <div style={{ flex: "1 1 260px", maxWidth: 360 }}>
            <PlayerPicker id="anchor-add" label="Add an anchor" rows={projected} exclude={new Set(anchors)}
                          onPick={(r) => setAnchors((a) => [...a, r.id])} />
          </div>
          <button className="btn primary" type="button" disabled={running || anchors.length === 0} onClick={() => run(anchors)}>
            {running ? "Building…" : `Build ${anchors.length} team${anchors.length === 1 ? "" : "s"}`}
          </button>
          <button className="btn" type="button" disabled={running} onClick={() => setAnchors(defaults)}>Reset to top {defaults.length}</button>
          <div className="count">{job?.cached ? "Loaded from cache" : running ? `${job!.done} of ${job!.total} built` : ""}</div>
        </div>
        <div className="chips">
          {anchors.map((id) => (
            <span key={id} className="chip">
              {byId.get(id)?.player ?? id}{" "}
              <button type="button" className="btn sm" style={{ border: 0, padding: "0 2px" }} aria-label={`Remove ${byId.get(id)?.player}`}
                      onClick={() => setAnchors((a) => a.filter((x) => x !== id))}>×</button>
            </span>
          ))}
        </div>
        {running && <div className="progress" aria-label="Build progress"><i style={{ width: `${(job!.done / Math.max(job!.total, 1)) * 100}%` }} /></div>}
        <div className="legend">
          <span>Each roster spends ${board.settings.league.budget} on {board.roster} players around the anchor. Cells show the chance of winning each category in a typical week.</span>
          <span><span className="tag" style={{ marginLeft: 0 }}>value</span> priced below production</span>
        </div>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!running && results.length === 0 && !error && <div className="empty">Pick anchors and press Build.</div>}
      <div className="teams">{results.map((b) => <TeamCard key={b.anchor_id} b={b} />)}</div>
    </section>
  );
}

function TeamCard({ b }: { b: Build }) {
  if (b.error) {
    return <article className="team"><h3>{b.anchor}</h3><Notice kind="warn">{b.error}</Notice></article>;
  }
  const plan = b.punt ? `Punt ${b.punt}` : "Balanced build";
  const alt = b.alternatives.filter((a) => a.punt !== b.punt).slice(0, 2)
    .map((a) => `${a.punt ? "punt " + a.punt : "balanced"} ${a.expected_cats.toFixed(1)}`).join(" · ");
  const big = b.roster.filter((p) => p.price >= 15).reduce((s, p) => s + p.price, 0);
  return (
    <article className="team">
      <div className="thead">
        <div><h3>{b.anchor}</h3><span className="meta">Anchor at ${b.anchor_price} · {plan.toLowerCase()}</span></div>
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <span className="plan">{plan}</span>
          <div className="score"><b>{b.expected_cats.toFixed(1)}</b><span>of {b.cats.length} cats / wk</span></div>
        </div>
      </div>
      <CatStrip cats={b.cats} />
      <div className="rwrap">
        <table className="roster">
          <thead><tr><th className="l">Slot</th><th className="l">Player</th><th>ADP</th><th>Pay</th></tr></thead>
          <tbody>
            {b.roster.map((p, i) => (
              <tr key={p.id} className={i === 0 ? "anchor" : undefined}>
                <td className="l slot">{p.slot}</td>
                <td className="l">{p.player}{p.bargain && <span className="tag">value</span>}<span className="meta"> · {p.team} · {posText(p.pos)}</span></td>
                <td className="src">{p.rank}</td>
                <td className="pr">${p.price}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="tfoot"><span>${b.spend} spent · ${big} on players at $15+</span><span>Next best: {alt || "none"}</span></div>
    </article>
  );
}
