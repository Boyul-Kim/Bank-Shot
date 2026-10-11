import { useEffect, useState } from "react";
import { api } from "../api";
import { Notice } from "../components";
import type { SourceStatus } from "../types";
import { when } from "../util";

const METHOD: Record<string, string> = { seed: "Bundled Oct 10 data", fetch: "Fetched from site", import: "Imported CSV" };
const UNMATCHED_LABEL: Record<string, string> = {
  hashtag_auction: "Auction values", fantasypros_proj: "Projections", rotoworld_rank: "Expert rankings",
  rotoworld_mock: "Salary mock", board_without_projection: "Board players with no projection",
};

export default function SourcesView({ onChanged }: { onChanged: () => void }) {
  const [sources, setSources] = useState<SourceStatus[] | null>(null);
  const [unmatched, setUnmatched] = useState<Record<string, string[]>>({});
  const [autoFetch, setAutoFetch] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "error" | "info"; text: string } | null>(null);

  const load = async () => {
    try {
      const r = await api.sources();
      setSources(r.sources); setUnmatched(r.unmatched); setAutoFetch(r.auto_fetch);
    } catch (e) { setMsg({ kind: "error", text: (e as Error).message }); }
  };
  useEffect(() => { load(); }, []);

  const refresh = async (id?: string) => {
    setBusy(id ?? "all"); setMsg(null);
    try {
      const r = await api.refresh(id);
      setSources(r.sources);
      const failed = r.results.filter((x) => x.status === "failed");
      setMsg(failed.length
        ? { kind: "error", text: failed.map((f) => `${f.source_id}: ${f.error}`).join(" ") + " The previous data stays in use." }
        : { kind: "info", text: r.results.length ? `Updated ${r.results.map((x) => `${x.source_id} (${x.rows} rows)`).join(", ")}.` : "Everything is up to date." });
      onChanged(); load();
    } catch (e) { setMsg({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };

  const upload = async (id: string, file: File | undefined) => {
    if (!file) return;
    setBusy(id); setMsg(null);
    try {
      const r = await api.importCsv(id, file);
      setSources(r.sources);
      setMsg({ kind: "info", text: `Imported ${r.result.rows} rows into ${id}.` });
      onChanged(); load();
    } catch (e) { setMsg({ kind: "error", text: (e as Error).message }); }
    finally { setBusy(null); }
  };

  if (!sources) return msg ? <Notice kind="error">{msg.text}</Notice> : <div className="empty">Loading sources…</div>;

  return (
    <section aria-label="Sources" style={{ display: "grid", gap: 14 }}>
      <div className="controls">
        <p className="muted" style={{ margin: 0, maxWidth: "70ch" }}>
          {autoFetch ? "The server refreshes stale sources when it starts (draft order and projections every 12 hours; articles once per link)." : "Automatic fetching is off in Settings."}
          {" "}A failed fetch never replaces good data.
        </p>
        <button className="btn primary" type="button" onClick={() => refresh()} disabled={busy != null} style={{ marginLeft: "auto" }}>
          {busy === "all" ? "Refreshing… (about 30 s)" : "Refresh all"}
        </button>
      </div>
      {msg && <Notice kind={msg.kind === "error" ? "error" : "info"}>{msg.text}</Notice>}
      <div className="board" style={{ maxHeight: "none" }}>
        <table>
          <thead><tr><th className="l">Source</th><th className="l">In use</th><th className="l">Last attempt</th><th className="l">Update</th></tr></thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id}>
                <td className="l" style={{ whiteSpace: "normal" }}><b>{s.label}</b><div className="meta">{s.provides}</div></td>
                <td className="l" style={{ whiteSpace: "normal" }}>
                  {s.active ? <>{METHOD[s.active.method] ?? s.active.method}<div className="meta">{when(s.active.retrieved_at)} · {s.active.row_count} rows</div></> : <span className="na">none</span>}
                </td>
                <td className="l" style={{ whiteSpace: "normal", maxWidth: 360 }}>
                  {s.last_attempt ? (
                    <>
                      <span className={s.last_attempt.status === "ok" ? "good" : undefined} style={s.last_attempt.status === "failed" ? { color: "var(--bad)" } : undefined}>
                        {s.last_attempt.status === "ok" ? "OK" : "Failed"}
                      </span> <span className="meta">{when(s.last_attempt.retrieved_at)}</span>
                      {s.last_attempt.error && <div className="meta" style={{ whiteSpace: "normal" }}>{s.last_attempt.error}</div>}
                    </>
                  ) : <span className="na">—</span>}
                </td>
                <td className="l">
                  <div className="row" style={{ alignItems: "center" }}>
                    <button className="btn sm" type="button" onClick={() => refresh(s.id)} disabled={busy != null}>{busy === s.id ? "Working…" : "Refresh"}</button>
                    <label className="btn sm" style={{ display: "inline-block" }}>
                      Import CSV
                      <input type="file" accept=".csv,text/csv" hidden onChange={(e) => { upload(s.id, e.target.files?.[0]); e.target.value = ""; }} />
                    </label>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="panel">
        <summary>Names that didn't match the draft-order list</summary>
        <p className="help" style={{ margin: 0 }}>Usually players outside the top of the ADP list. A star here means a spelling difference worth adding to the alias table in server/app/core/names.py.</p>
        {Object.entries(unmatched).map(([k, v]) => (
          <div key={k}><b>{UNMATCHED_LABEL[k] ?? k}</b> <span className="meta">({v.length})</span>
            <div className="meta" style={{ whiteSpace: "normal" }}>{v.length ? v.join(", ") : "none"}</div></div>
        ))}
      </details>
      <p className="help" style={{ margin: 0 }}>CSV columns match the files in server/seed (see server/seed/README.md).</p>
    </section>
  );
}
