import type { CSSProperties } from "react";
import type { Cat, Row } from "./types";

export const POSITIONS = ["PG", "SG", "SF", "PF", "C"] as const;
export const CAT_LABEL: Record<Cat, string> = {
  fg: "FG%", ft: "FT%", tpm: "3PM", pts: "PTS", reb: "REB", ast: "AST", stl: "STL", blk: "BLK", to: "TO",
};

export const money = (v: number | null | undefined, digits = 0) =>
  v == null ? null : "$" + (Math.round(v * 10 ** digits) / 10 ** digits).toString();

export const posText = (p: string[]) => p.join("/");

export function tierOf(c: number): string {
  if (c >= 60) return "Tier 1 · $60+";
  if (c >= 40) return "Tier 2 · $40–59";
  if (c >= 25) return "Tier 3 · $25–39";
  if (c >= 15) return "Tier 4 · $15–24";
  if (c >= 8) return "Tier 5 · $8–14";
  if (c >= 3) return "Tier 6 · $3–7";
  return "Tier 7 · $1–2";
}

export function heat(z: number | null | undefined): CSSProperties | undefined {
  if (z == null) return undefined;
  const a = Math.min(Math.abs(z) / 2.5, 1) * 42;
  if (a < 4) return undefined;
  return { background: `color-mix(in srgb, var(${z > 0 ? "--good" : "--bad"}) ${a.toFixed(0)}%, transparent)` };
}

export function winStyle(w: number): CSSProperties {
  const pct = Math.round(Math.min(Math.abs(w - 0.5) * 2, 1) * 60 + 6);
  return { background: `color-mix(in srgb, var(${w >= 0.5 ? "--good" : "--bad"}) ${pct}%, transparent)` };
}

export function matches(r: Row, q: string, pos: string) {
  const s = q.trim().toLowerCase();
  return (pos === "ALL" || r.pos.includes(pos)) && (!s || r.player.toLowerCase().includes(s) || r.team.toLowerCase() === s);
}

export function compare<T>(get: (x: T) => number | string | null | undefined, dir: 1 | -1, tie: (x: T) => number) {
  return (a: T, b: T) => {
    const x = get(a), y = get(b);
    if (x == null && y == null) return tie(a) - tie(b);
    if (x == null) return 1;
    if (y == null) return -1;
    if (typeof x === "string" && typeof y === "string") return x.localeCompare(y) * dir;
    return ((x as number) - (y as number)) * dir || tie(a) - tie(b);
  };
}

export const when = (t?: number | null) =>
  t ? new Date(t * 1000).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "never";
