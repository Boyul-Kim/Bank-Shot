import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Notice } from "./components";
import type { Board, Draft } from "./types";
import { when } from "./util";
import BoardView from "./views/Board";
import StatsView from "./views/Stats";
import TeamsView from "./views/Teams";
import DraftView from "./views/Draft";
import SourcesView from "./views/Sources";
import SettingsView from "./views/Settings";

const TABS = [
  { id: "board", label: "Auction board" },
  { id: "stats", label: "Projected stats" },
  { id: "teams", label: "Build-around teams" },
  { id: "draft", label: "Live draft" },
  { id: "sources", label: "Sources" },
  { id: "settings", label: "Settings" },
] as const;
type Tab = (typeof TABS)[number]["id"];

function useHashTab(): Tab {
  const read = () => {
    const h = window.location.hash.replace(/^#\/?/, "") as Tab;
    return TABS.some((t) => t.id === h) ? h : "board";
  };
  const [tab, setTab] = useState<Tab>(read);
  useEffect(() => {
    const on = () => setTab(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return tab;
}

export default function App() {
  const tab = useHashTab();
  const [board, setBoard] = useState<Board | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadBoard = useCallback(async () => {
    try {
      setBoard(await api.board());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  const loadDraft = useCallback(async () => {
    try {
      setDraft(await api.draft());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { loadBoard(); loadDraft(); }, [loadBoard, loadDraft]);

  const league = board?.settings.league;
  const newest = board ? Math.max(...Object.values(board.sources).map((s) => s?.retrieved_at ?? 0)) : 0;
  const live = (draft?.sales.length ?? 0) > 0;

  return (
    <div className="wrap">
      <header className="top">
        <div>
          <div className="eyebrow">Fantasy basketball · 2026-27 · Data updated {when(newest)}</div>
          <h1>2026-27 <span>Auction</span> Board</h1>
        </div>
        {league && (
          <div className="chips">
            <span className="chip">{league.teams} teams</span>
            <span className="chip">${league.budget}</span>
            <span className="chip">{board.roster} spots</span>
            <span className="chip">{league.categories.length}-cat H2H</span>
            {live && <span className="chip live">Draft live · {draft!.sales.length} sold</span>}
          </div>
        )}
      </header>

      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => (
          <a key={t.id} href={`#/${t.id}`} aria-current={tab === t.id ? "page" : undefined}>{t.label}</a>
        ))}
      </nav>

      {error && <Notice kind="error">{error}</Notice>}
      {!board && !error && <div className="empty">Loading the board…</div>}

      {board && tab === "board" && <BoardView board={board} draft={draft} />}
      {board && tab === "stats" && <StatsView board={board} />}
      {board && tab === "teams" && <TeamsView board={board} />}
      {board && tab === "draft" && <DraftView board={board} draft={draft} setDraft={setDraft} reload={loadDraft} />}
      {tab === "sources" && <SourcesView onChanged={loadBoard} />}
      {tab === "settings" && <SettingsView onSaved={() => { loadBoard(); loadDraft(); }} />}
    </div>
  );
}
