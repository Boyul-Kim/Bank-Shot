import { Fragment, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { CatStrip, Notice, PlayerPicker } from "../components";
import type { Board, Draft, Plan, Row } from "../types";
import { posText } from "../util";

interface Props { board: Board; draft: Draft | null; setDraft: (d: Draft) => void; reload: () => void }

export default function DraftView({ board, draft, setDraft, reload }: Props) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [planBusy, setPlanBusy] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Row | null>(null);

  const salesKey = draft ? draft.sales.map((s) => s.id).join(",") : "";
  const settingsKey = JSON.stringify(board.settings);
  const refreshPlan = async () => {
    setPlanBusy(true);
    try { setPlan(await api.plan()); setPlanError(null); }
    catch (e) { setPlanError((e as Error).message); setPlan(null); }
    finally { setPlanBusy(false); }
  };
  useEffect(() => { if (draft) refreshPlan(); }, [salesKey, settingsKey, draft != null]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!draft) return <div className="empty">Loading the draft room…</div>;
  const me = draft.teams.find((t) => t.is_me);

  return (
    <section aria-label="Live draft" style={{ display: "grid", gap: 14 }}>
      {draft.warning && <Notice kind="warn">{draft.warning}</Notice>}
      <Setup draft={draft} onDone={(d) => { setDraft(d); setSelected(null); }} />
      <div className="draft">
        <UpForBid board={board} draft={draft} plan={plan} selected={selected} setSelected={setSelected}
                  onSold={(d) => { setDraft(d); setSelected(null); }} />
        <div className="panel" aria-label="Your team">
          <div className="thead" style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <h2>{me?.name ?? "Your team"}</h2>
            <button className="btn" type="button" onClick={refreshPlan} disabled={planBusy}>{planBusy ? "Planning…" : "Re-plan"}</button>
          </div>
          {me && (
            <div className="kv">
              <div><b>${me.left}</b><span>Budget left</span></div>
              <div><b>${me.max_bid}</b><span>Max bid</span></div>
              <div><b>{me.spots_left}</b><span>Spots left</span></div>
              {plan && <div><b>{plan.expected_cats.toFixed(1)}</b><span>Cats won / wk</span></div>}
            </div>
          )}
          {planError && <Notice kind="error">{planError}</Notice>}
          {!plan && !planError && <div className="empty">Working out your best roster…</div>}
          {plan && <PlanView plan={plan} busy={planBusy} onPick={(id) => setSelected(board.rows.find((r) => r.id === id) ?? null)} />}
        </div>
        <League draft={draft} onUndo={async (id) => { try { setDraft(await api.undo(id)); } catch { reload(); } }} />
      </div>
    </section>
  );
}

function PlanView({ plan, busy, onPick }: { plan: Plan; busy: boolean; onPick: (id: string) => void }) {
  const toBuy = plan.roster.filter((p) => !p.owned);
  return (
    <div style={{ display: "grid", gap: 10, opacity: busy ? 0.6 : 1 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span className="plan">{plan.punt ? `Punt ${plan.punt}` : "Balanced build"}</span>
        <span className="meta">Next best: {plan.alternatives.filter((a) => a.punt !== plan.punt).slice(0, 2)
          .map((a) => `${a.punt ? "punt " + a.punt : "balanced"} ${a.expected_cats.toFixed(1)}`).join(" · ") || "none"}</span>
      </div>
      <CatStrip cats={plan.cats} />
      <div className="rwrap">
        <table className="roster">
          <thead><tr><th className="l">Slot</th><th className="l">Player</th><th>{toBuy.length ? "Paid / bid up to" : "Paid"}</th></tr></thead>
          <tbody>
            {plan.roster.map((p) => (
              <tr key={p.id} className={p.owned ? "owned" : undefined}>
                <td className="l slot">{p.slot}</td>
                <td className="l">
                  {p.owned ? p.player : <button type="button" className="btn sm" style={{ border: 0, padding: 0, background: "none", fontWeight: 500 }}
                                                 onClick={() => onPick(p.id)}>{p.player}</button>}
                  {p.owned && <span className="tag own">yours</span>}
                  {p.bargain && <span className="tag">value</span>}
                  <span className="meta"> · {p.team} · {posText(p.pos)}</span>
                </td>
                <td className="pr">${p.price}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="tfoot"><span>${plan.spent} spent · plan totals ${plan.planned_spend}</span><span>Prices ×{plan.inflation.toFixed(2)}</span></div>
      <div>
        <h3 style={{ marginBottom: 4 }}>Nominate to drain rivals</h3>
        <p className="help" style={{ margin: "0 0 6px" }}>Expensive players outside your plan that at least two rivals can afford.</p>
        <div className="list">
          {plan.nominations.length === 0 && <span className="muted">No good candidates right now.</span>}
          {plan.nominations.map((n) => (
            <div key={n.id} className="item">
              <button type="button" className="btn sm" style={{ border: 0, padding: 0, background: "none", fontWeight: 600 }} onClick={() => onPick(n.id)}>{n.player}</button>
              <span className="meta">{posText(n.pos)} · ~${n.adj_target} · {n.rivals_able} rivals can pay</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function UpForBid(props: { board: Board; draft: Draft; plan: Plan | null; selected: Row | null; setSelected: (r: Row | null) => void; onSold: (d: Draft) => void }) {
  const { board, draft, plan, selected } = props;
  const sold = useMemo(() => new Set(draft.sales.map((s) => s.player_id)), [draft.sales]);
  const adj = useMemo(() => new Map(draft.players.map((p) => [p.id, p])), [draft.players]);
  const me = draft.teams.find((t) => t.is_me);
  const [teamId, setTeamId] = useState<string>("");
  const [price, setPrice] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [whatIf, setWhatIf] = useState<{ price: number; plan: Plan } | { price: number; error: string } | null>(null);

  useEffect(() => {
    setError(null); setWhatIf(null);
    setPrice(selected ? String(adj.get(selected.id)?.adj_target ?? selected.cons) : "");
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const p = selected ? adj.get(selected.id) : undefined;
  const inPlan = selected && plan ? plan.roster.find((x) => x.id === selected.id && !x.owned) : undefined;

  const record = async () => {
    if (!selected) return;
    const n = Number(price);
    if (teamId === "") { setError("Pick the team that won the bid."); return; }
    if (!Number.isInteger(n) || n < 1) { setError("Enter the winning bid in whole dollars."); return; }
    setBusy(true);
    try { props.onSold(await api.sell(selected.id, Number(teamId), n)); setTeamId(""); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const tryWhatIf = async () => {
    if (!selected) return;
    const n = Number(price);
    if (!Number.isInteger(n) || n < 1) { setError("Enter a whole-dollar price for the what-if."); return; }
    setBusy(true);
    try { setWhatIf({ price: n, plan: await api.plan({ player_id: selected.id, price: n }) }); }
    catch (e) { setWhatIf({ price: n, error: (e as Error).message }); }
    finally { setBusy(false); }
  };

  return (
    <div className="panel" aria-label="Up for bid">
      <h2>Up for bid</h2>
      <PlayerPicker id="bid-player" label="Player nominated" rows={board.rows} exclude={sold} onPick={props.setSelected}
                    extra={(r) => `now ~$${adj.get(r.id)?.adj_target ?? r.cons}`} />
      {!selected && <p className="muted" style={{ margin: 0 }}>Type the nominated player's name, or click a name in your plan or the nomination list.</p>}
      {selected && (
        <div className="bidcard">
          <div>
            <div className="name">{selected.player}</div>
            <span className="meta">{selected.team} · {posText(selected.pos)} · ADP #{selected.rank}</span>
          </div>
          <div className="kv">
            <div><b>${p?.adj_target ?? selected.cons}</b><span>Price now</span></div>
            <div><b>${selected.cons}</b><span>Target</span></div>
            <div><b>{selected.val != null ? `$${selected.val}` : "—"}</b><span>Stats $</span></div>
            <div><b>${me?.max_bid ?? 0}</b><span>Your max</span></div>
          </div>
          <div className={inPlan ? "good" : "muted"}>
            {inPlan ? `In your plan: bid up to $${inPlan.price}.` : "Not in your current plan."}
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="sale-price">Price</label>
              <input id="sale-price" type="number" min={1} step={1} value={price} onChange={(e) => setPrice(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="sale-team">Won by</label>
              <select id="sale-team" value={teamId} onChange={(e) => setTeamId(e.target.value)}>
                <option value="">Pick a team…</option>
                {draft.teams.map((t) => (
                  <option key={t.id} value={t.id} disabled={t.spots_left <= 0}>
                    {t.name}{t.is_me ? " (you)" : ""} · max ${t.max_bid}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="row">
            <button className="btn primary" type="button" onClick={record} disabled={busy}>Record sale</button>
            <button className="btn" type="button" onClick={tryWhatIf} disabled={busy}>If I win at ${price || "?"}</button>
            <button className="btn" type="button" onClick={() => props.setSelected(null)}>Clear</button>
          </div>
          {error && <Notice kind="error">{error}</Notice>}
          {whatIf && "error" in whatIf && <Notice kind="warn">{whatIf.error}</Notice>}
          {whatIf && "plan" in whatIf && plan && (
            <div className="whatif">
              <b>At ${whatIf.price}:</b>{" "}
              {(() => {
                const d = whatIf.plan.expected_cats - plan.expected_cats;
                const verdict = d > 0.05 ? "better than your current plan" : d < -0.05 ? "worse than your current plan" : "about the same as your current plan";
                return <span className={d > 0.05 ? "good" : undefined}>{whatIf.plan.expected_cats.toFixed(2)} cats/wk ({d >= 0 ? "+" : ""}{d.toFixed(2)}), {verdict}.</span>;
              })()}
              <div className="meta" style={{ marginTop: 4 }}>
                Then: {whatIf.plan.punt ? `punt ${whatIf.plan.punt}` : "balanced"}, buy {whatIf.plan.roster.filter((x) => !x.owned).map((x) => x.player).slice(0, 4).join(", ") || "nobody else"}…
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function League({ draft, onUndo }: { draft: Draft; onUndo: (saleId: number) => void }) {
  const inf = draft.inflation.factor;
  const names = new Map(draft.teams.map((t) => [t.id, t.name]));
  const [open, setOpen] = useState<number | null>(null);
  const label = inf > 1.05 ? "Prices running hot" : inf < 0.95 ? "Prices running cold" : "Prices near target";
  return (
    <div className="panel" aria-label="League">
      <h2>League</h2>
      <div className="kv">
        <div><b>×{inf.toFixed(2)}</b><span>{label}</span></div>
        <div><b>${draft.inflation.money_left.toLocaleString()}</b><span>Money left</span></div>
        <div><b>{draft.inflation.spots_left}</b><span>Spots left</span></div>
      </div>
      <p className="help" style={{ margin: 0 }}>Inflation is money left divided by the target value of the best {draft.inflation.spots_left} players still available.</p>
      <div className="rwrap">
        <table className="teamsTable">
          <thead><tr><th className="l">Team</th><th>Spent</th><th>Left</th><th>Spots</th><th>Max bid</th></tr></thead>
          <tbody>
            {draft.teams.map((t) => (
              <Fragment key={t.id}>
                <tr className={t.is_me ? "me" : undefined} style={{ cursor: "pointer" }} onClick={() => setOpen(open === t.id ? null : t.id)}>
                  <td className="l">{t.name}{t.is_me ? " (you)" : ""}</td>
                  <td className="src">${t.spent}</td><td className="src">${t.left}</td>
                  <td className="src">{t.spots_left}</td><td className="src">${t.max_bid}</td>
                </tr>
                {open === t.id && (
                  <tr>
                    <td colSpan={5} className="l" style={{ whiteSpace: "normal" }}>
                      {t.roster.length ? t.roster.map((p) => `${p.player} $${p.price}`).join(" · ") : <span className="muted">No players yet.</span>}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <h3>Sale log</h3>
        {draft.sales.length > 0 && <button type="button" className="btn sm" onClick={() => onUndo(draft.sales[0].id)}>Undo last</button>}
      </div>
      <div className="list" aria-live="polite">
        {draft.sales.length === 0 && <span className="muted">No sales yet. Record the first winning bid on the left.</span>}
        {draft.sales.map((s, i) => {
          return (
            <div key={s.id} className="item">
              <span><span className="meta">#{draft.sales.length - i}</span> {nameOf(s.player_id)} → {names.get(s.team_id)} <b>${s.price}</b></span>
              <button type="button" className="btn sm danger" onClick={() => onUndo(s.id)} aria-label={`Undo sale ${draft.sales.length - i}`}>Undo</button>
            </div>
          );
        })}
      </div>
    </div>
  );
  function nameOf(id: string) {
    for (const t of draft.teams) for (const p of t.roster) if (p.id === id) return p.player;
    return id;
  }
}

function Setup({ draft, onDone }: { draft: Draft; onDone: (d: Draft) => void }) {
  const [names, setNames] = useState<string[]>(draft.setup.map((t) => t.name));
  const [me, setMe] = useState<number>(Math.max(0, draft.setup.findIndex((t) => t.is_me)));
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const teamsCount = draft.teams.length;
  useEffect(() => { setNames(draft.setup.map((t) => t.name)); setMe(Math.max(0, draft.setup.findIndex((t) => t.is_me))); }, [draft.setup]);
  const start = async () => {
    try { onDone(await api.setupDraft(names, me)); setConfirm(false); setError(null); }
    catch (e) { setError((e as Error).message); }
  };
  return (
    <details className="panel" open={draft.sales.length === 0}>
      <summary>Draft setup · {teamsCount} teams · you are {draft.setup[me]?.name ?? "—"}</summary>
      <p className="help" style={{ margin: 0 }}>Name the teams and mark yours. Starting a new draft clears every recorded sale.</p>
      <div className="form-grid">
        {names.map((n, i) => (
          <div key={i} className="field">
            <label htmlFor={`team-${i}`}>Team {i + 1}</label>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input id={`team-${i}`} type="text" value={n} maxLength={40} style={{ flex: 1 }}
                     onChange={(e) => setNames((a) => a.map((x, j) => (j === i ? e.target.value : x)))} />
              <label className="toggle" style={{ padding: 0 }}><input type="radio" name="me" checked={me === i} onChange={() => setMe(i)} /> Mine</label>
            </div>
          </div>
        ))}
      </div>
      <div className="row">
        {!confirm && <button className="btn primary" type="button" onClick={() => (draft.sales.length ? setConfirm(true) : start())}>Start new draft</button>}
        {confirm && <>
          <span>This clears {draft.sales.length} recorded sale{draft.sales.length === 1 ? "" : "s"}.</span>
          <button className="btn danger" type="button" onClick={start}>Clear and start</button>
          <button className="btn" type="button" onClick={() => setConfirm(false)}>Keep current draft</button>
        </>}
      </div>
      {error && <Notice kind="error">{error}</Notice>}
    </details>
  );
}
