export type Cat = "fg" | "ft" | "tpm" | "pts" | "reb" | "ast" | "stl" | "blk" | "to";

export interface Proj {
  gp: number; min: number; pts: number; reb: number; ast: number; stl: number; blk: number;
  tpm: number; fgp: number; ftp: number; to: number;
}

export interface Row {
  id: string; rank: number; player: string; team: string; pos: string[]; adp: number; rw: number | null;
  mock: number | null; curve: number | null; hb: number | null; yahoo: number | null; espn: number | null;
  cons: number; low: number; high: number; n: number;
  proj: Proj | null; z: Record<Cat, number> | null; ztot: number | null; zrank: number | null;
  val: number | null; pay: number; bargain: boolean;
}

export interface SourceMeta { snapshot_id: number; retrieved_at: number; method: "seed" | "fetch" | "import" }

export interface League { teams: number; budget: number; slots: string[]; bench: number; categories: Cat[]; board_size: number }
export interface ModelParams {
  rescale_market: boolean; fta_per_pt: number; bargain_bid_up: number; bargain_threshold: number; max_bargains: number;
  star_price: number; max_stars: number; min_gp: number; sigma: number; opponent_baseline: "drafted" | "pool";
  punt_options: (Cat | null)[]; anchor_punt_guard: number; reweight_iters: number; draft_reweight_iters: number; anchors: number;
}
export interface SourceSettings {
  auto_fetch: boolean; fetch_max_age_hours: number; hashtag_adp_url: string; hashtag_auction_url: string;
  fantasypros_proj_url: string; rotoworld_rank_url: string; rotoworld_mock_url: string;
}
export interface Settings { league: League; model: ModelParams; sources: SourceSettings }

export interface Board {
  rows: Row[]; lg: { fg: number | null; ft: number | null }; scale: number;
  unmatched: Record<string, string[]>; sources: Record<string, SourceMeta | null>;
  settings: Settings; roster: number; categories: { key: Cat; label: string }[];
}

export interface CatResult { cat: string; z: number; win: number; punted: boolean }
export interface BuildPlayer {
  id: string; player: string; team: string; pos: string[]; rank: number; price: number; target: number; slot: string; bargain: boolean;
}
export interface Build {
  anchor_id: string; anchor: string; anchor_price: number; punt: string | null; expected_cats: number; spend: number;
  alternatives: { punt: string | null; expected_cats: number }[]; cats: CatResult[]; roster: BuildPlayer[]; error?: string;
}
export interface Job { id: string; status: "running" | "done" | "failed"; done: number; total: number; results: Build[] | null; error?: string; cached?: boolean }

export interface DraftTeam {
  id: number; name: string; is_me: boolean; spent: number; left: number; spots_left: number; max_bid: number;
  roster: { sale_id: number; id: string; player: string; pos: string[]; price: number }[];
}
export interface DraftPlayer { id: string; adj_target: number; adj_pay: number; sold_to: number | null; sold_to_name: string | null; sold_price: number | null }
export interface Sale { id: number; player_id: string; team_id: number; price: number; at: number }
export interface Draft {
  teams: DraftTeam[]; inflation: { factor: number; money_left: number; spots_left: number; value_left: number };
  players: DraftPlayer[]; sales: Sale[]; setup: { id: number; name: string; is_me: boolean }[];
  budget: number; roster: number; warning: string | null;
}
export interface PlanPlayer {
  id: string; player: string; team: string; pos: string[]; rank: number; price: number; owned: boolean; forced: boolean; slot: string; bargain: boolean;
}
export interface Plan {
  punt: string | null; expected_cats: number; alternatives: { punt: string | null; expected_cats: number }[];
  cats: CatResult[]; roster: PlanPlayer[]; spent: number; planned_spend: number; inflation: number; plan_ids: string[];
  nominations: { id: string; player: string; pos: string[]; adj_target: number; rivals_able: number }[];
}

export interface SourceStatus {
  id: string; label: string; provides: string; static: boolean; refreshing: boolean;
  active: { id: number; retrieved_at: number; method: string; url: string; row_count: number } | null;
  last_attempt: { retrieved_at: number; method: string; status: string; error: string | null } | null;
}
