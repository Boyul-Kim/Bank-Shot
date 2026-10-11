import type { Board, Draft, Job, Plan, Settings, SourceStatus } from "./types";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new Error("Can't reach the server. Check that it's running (python -m app in the server folder).");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { error?: string }).error || `The server answered ${res.status}.`);
  return data as T;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  board: () => call<Board>("/board"),
  settings: () => call<{ settings: Settings; defaults: Settings; reference: Settings; roster: number }>("/settings"),
  saveSettings: (s: Settings) => call<{ settings: Settings; roster: number }>("/settings", { method: "PUT", body: json(s) }),
  resetSettings: () => call<{ settings: Settings }>("/settings/reset", { method: "POST" }),
  startBuilds: (anchors?: string[]) => call<Job>("/builds", { method: "POST", body: json(anchors ? { anchors } : {}) }),
  build: (id: string) => call<Job>(`/builds/${id}`),
  sources: () => call<{ sources: SourceStatus[]; unmatched: Record<string, string[]>; auto_fetch: boolean }>("/sources"),
  refresh: (source_id?: string) =>
    call<{ results: { source_id: string; status: string; error?: string; rows?: number }[]; sources: SourceStatus[] }>(
      "/sources/refresh", { method: "POST", body: json(source_id ? { source_id } : {}) }),
  importCsv: (source_id: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return call<{ result: { rows: number }; sources: SourceStatus[] }>(`/sources/${source_id}/import`, { method: "POST", body: fd });
  },
  draft: () => call<Draft>("/draft"),
  setupDraft: (teams: string[], me: number) => call<Draft>("/draft/setup", { method: "POST", body: json({ teams, me }) }),
  sell: (player_id: string, team_id: number, price: number) =>
    call<Draft>("/draft/sales", { method: "POST", body: json({ player_id, team_id, price }) }),
  undo: (sale_id: number) => call<Draft>(`/draft/sales/${sale_id}`, { method: "DELETE" }),
  plan: (force?: { player_id: string; price: number }) => call<Plan>("/draft/plan", { method: "POST", body: json(force ? { force } : {}) }),
};
