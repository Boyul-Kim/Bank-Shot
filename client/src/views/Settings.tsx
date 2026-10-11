import { useEffect, useState } from "react";
import { api } from "../api";
import { Notice } from "../components";
import type { Cat, Settings } from "../types";
import { CAT_LABEL } from "../util";

const CATS: Cat[] = ["fg", "ft", "tpm", "pts", "reb", "ast", "stl", "blk", "to"];

export default function SettingsView({ onSaved }: { onSaved: () => void }) {
  const [s, setS] = useState<Settings | null>(null);
  const [defaults, setDefaults] = useState<Settings | null>(null);
  const [slotsText, setSlotsText] = useState("");
  const [msg, setMsg] = useState<{ kind: "error" | "info"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const adopt = (x: Settings) => { setS(x); setSlotsText(x.league.slots.join(", ")); };
  useEffect(() => {
    api.settings().then((r) => { adopt(r.settings); setDefaults(r.defaults); }).catch((e) => setMsg({ kind: "error", text: e.message }));
  }, []);
  if (!s || !defaults) return msg ? <Notice kind="error">{msg.text}</Notice> : <div className="empty">Loading settings…</div>;

  const L = <K extends keyof Settings["league"]>(k: K, v: Settings["league"][K]) => setS({ ...s, league: { ...s.league, [k]: v } });
  const M = <K extends keyof Settings["model"]>(k: K, v: Settings["model"][K]) => setS({ ...s, model: { ...s.model, [k]: v } });
  const S = <K extends keyof Settings["sources"]>(k: K, v: Settings["sources"][K]) => setS({ ...s, sources: { ...s.sources, [k]: v } });

  const save = async () => {
    setBusy(true); setMsg(null);
    const slots = slotsText.split(/[\s,]+/).map((x) => x.trim().toUpperCase()).filter(Boolean);
    try {
      const r = await api.saveSettings({ ...s, league: { ...s.league, slots } });
      adopt(r.settings);
      setMsg({ kind: "info", text: `Saved. Rosters are ${r.roster} players; the board, builds and draft room now use these settings.` });
      onSaved();
    } catch (e) { setMsg({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(false); }
  };
  const reset = async () => {
    setBusy(true);
    try { adopt((await api.resetSettings()).settings); setMsg({ kind: "info", text: "Restored the defaults." }); onSaved(); }
    catch (e) { setMsg({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(false); }
  };

  const num = (id: string, label: string, value: number, set: (v: number) => void, help: string, step = 1) => (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="number" step={step} value={value} onChange={(e) => set(Number(e.target.value))} />
      <span className="help">{help}</span>
    </div>
  );

  return (
    <section aria-label="Settings" style={{ display: "grid", gap: 14 }}>
      <div className="panel">
        <h2>League</h2>
        <div className="form-grid">
          {num("teams", "Teams", s.league.teams, (v) => L("teams", v), `Default ${defaults.league.teams}.`)}
          {num("budget", "Budget per team", s.league.budget, (v) => L("budget", v), `Default $${defaults.league.budget}.`)}
          <div className="field">
            <label htmlFor="slots">Starting slots</label>
            <input id="slots" type="text" value={slotsText} onChange={(e) => setSlotsText(e.target.value)} />
            <span className="help">Comma separated from PG, SG, G, SF, PF, F, C, UT. Default: {defaults.league.slots.join(", ")}.</span>
          </div>
          {num("bench", "Bench spots", s.league.bench, (v) => L("bench", v), "Roster size = slots + bench.")}
          {num("board", "Board size", s.league.board_size, (v) => L("board_size", v), "Players shown and valued, in ADP order.")}
        </div>
        <div className="field">
          <span className="lbl">Categories</span>
          <div className="checks">
            {CATS.map((c) => (
              <label key={c}>
                <input type="checkbox" checked={s.league.categories.includes(c)}
                       onChange={(e) => L("categories", e.target.checked ? CATS.filter((x) => x === c || s.league.categories.includes(x)) : s.league.categories.filter((x) => x !== c))} />
                {CAT_LABEL[c]}
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Model</h2>
        <div className="form-grid">
          <label className="toggle"><input type="checkbox" checked={s.model.rescale_market} onChange={(e) => M("rescale_market", e.target.checked)} /> Rescale market prices to this league</label>
          <div className="field">
            <label htmlFor="opp">Weekly opponent</label>
            <select id="opp" value={s.model.opponent_baseline} onChange={(e) => M("opponent_baseline", e.target.value as "drafted" | "pool")}>
              <option value="drafted">Average drafted roster</option>
              <option value="pool">Average of the whole board</option>
            </select>
            <span className="help">Who win chances are measured against.</span>
          </div>
          {num("bid", "Bargain bid-up", s.model.bargain_bid_up, (v) => M("bargain_bid_up", v), "0 = pay target, 1 = pay full production value.", 0.05)}
          {num("bthr", "Bargain threshold ($)", s.model.bargain_threshold, (v) => M("bargain_threshold", v), "Stats $ minus pay needed to count as a bargain.")}
          {num("maxb", "Bargains per roster", s.model.max_bargains, (v) => M("max_bargains", v), "Rivals chase the same values.")}
          {num("star", "Star price ($)", s.model.star_price, (v) => M("star_price", v), "Players at or above this count as stars.")}
          {num("maxs", "Stars per roster", s.model.max_stars, (v) => M("max_stars", v), "Cap on stars per roster.")}
          {num("mingp", "Minimum projected games", s.model.min_gp, (v) => M("min_gp", v), "Players below this are left out of plans.")}
          {num("sigma", "Weekly noise (σ)", s.model.sigma, (v) => M("sigma", v), "Higher = closer to coin flips.", 0.5)}
          {num("fta", "FT attempts per point", s.model.fta_per_pt, (v) => M("fta_per_pt", v), "Estimate; projections lack attempts.", 0.01)}
          {num("anchors", "Default anchors", s.model.anchors, (v) => M("anchors", v), "How many top players get a build.")}
          {num("iters", "Build passes", s.model.reweight_iters, (v) => M("reweight_iters", v), "More passes = slower, slightly better.")}
          {num("diters", "Draft re-plan passes", s.model.draft_reweight_iters, (v) => M("draft_reweight_iters", v), "Keep low for speed during the draft.")}
        </div>
        <div className="field">
          <span className="lbl">Punts the optimizer may try</span>
          <div className="checks">
            {CATS.filter((c) => s.league.categories.includes(c)).map((c) => (
              <label key={c}>
                <input type="checkbox" checked={s.model.punt_options.includes(c)}
                       onChange={(e) => M("punt_options", e.target.checked ? [...s.model.punt_options, c] : s.model.punt_options.filter((x) => x !== c))} />
                {CAT_LABEL[c]}
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Data sources</h2>
        <div className="form-grid">
          <label className="toggle"><input type="checkbox" checked={s.sources.auto_fetch} onChange={(e) => S("auto_fetch", e.target.checked)} /> Fetch from the sites automatically</label>
          {num("age", "Refresh after (hours)", s.sources.fetch_max_age_hours, (v) => S("fetch_max_age_hours", v), "For draft order, projections and auction values.")}
        </div>
        {(["hashtag_adp_url", "hashtag_auction_url", "fantasypros_proj_url", "rotoworld_rank_url", "rotoworld_mock_url"] as const).map((k) => (
          <div key={k} className="field">
            <label htmlFor={k}>{k.replace(/_url$/, "").replace(/_/g, " ")}</label>
            <input id={k} type="url" value={s.sources[k]} onChange={(e) => S(k, e.target.value)} />
          </div>
        ))}
        <span className="help">Rotoworld rankings and the salary mock are dated articles; paste a newer article's link to follow it.</span>
      </div>

      {msg && <Notice kind={msg.kind === "error" ? "error" : "info"}>{msg.text}</Notice>}
      <div className="row">
        <button className="btn primary" type="button" onClick={save} disabled={busy}>Save settings</button>
        <button className="btn" type="button" onClick={reset} disabled={busy}>Restore defaults</button>
      </div>
    </section>
  );
}
