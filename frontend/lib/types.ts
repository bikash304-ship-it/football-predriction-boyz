export type Team = { id: number; name: string; logo: string | null; initials: string };

export type PredictionSummary = {
  "1x2": { home: number; draw: number; away: number };
  btts: { yes: number; no: number };
  ou25: { over: number; under: number };
  xg: { home: number; away: number };
  confidence: "High" | "Medium" | "Low";
  completeness: number;
  top_pick: { market: string; selection: string; p: number };
  updated_at: string;
  model_version: string;
};

export type Fixture = {
  id: number;
  league_slug: string;
  league_name: string;
  country: string;
  country_code: string;
  kickoff_utc: string;
  status: string;
  status_long: string;
  elapsed: number | null;
  home: Team;
  away: Team;
  venue: string | null;
  city: string | null;
  round: string | null;
  score: { home: number | null; away: number | null };
  ft: { home: number | null; away: number | null };
  demo: boolean;
  prediction: PredictionSummary | null;
};

export type League = {
  slug: string; name: string; country: string; country_code: string; logo: string | null; today: number; demo: boolean;
};

export type Split = {
  played: number; wins: number; draws: number; losses: number;
  gf_per_match: number | null; ga_per_match: number | null; btts_rate: number | null;
  over15_rate: number | null; over25_rate: number | null; over35_rate: number | null;
  clean_sheet_rate: number | null; failed_to_score_rate: number | null;
  xg_for_per_match: number | null; xg_against_per_match: number | null; form: string;
};

export type Profile = { team: string; last5: Split; last10: Split; home: Split; away: Split; rest_days: number | null };

export type Prediction = {
  model_version: string;
  created_at: string;
  kickoff: string;
  home: string;
  away: string;
  demo?: boolean;
  markets: {
    home: number; draw: number; away: number; btts_yes: number; btts_no: number;
    over: Record<string, number>; under: Record<string, number>;
    expected_home_goals: number; expected_away_goals: number;
    top_scores: { score: string; home: number; away: number; p: number }[];
    total_goals_dist: number[];
  };
  display: {
    "1x2": { home: number; draw: number; away: number };
    btts: { yes: number; no: number };
    ou: Record<string, { over: number; under: number }>;
  };
  picks: { market: string; selection: string; p: number }[];
  score_matrix: number[][];
  rates: { home: number; away: number; base_home: number; base_away: number; rho: number; home_adv: number };
  adjustments: { side: string; factor: number; reason: string }[];
  uncertainty: { home: [number, number]; draw: [number, number]; away: [number, number] };
  completeness: { score: number; missing: string[]; components: Record<string, number> };
  confidence: "High" | "Medium" | "Low";
  context: {
    home_profile: Profile; away_profile: Profile;
    h2h: { date: string; home: string; away: string; home_goals: number; away_goals: number }[];
    injuries: { player: string; team: string; type: string; reason: string | null }[] | null;
    injuries_status: "verified" | "unavailable";
    lineups: Record<string, { formation: string | null; start_xi: string[] }> | null;
    lineups_status: "confirmed" | "not confirmed";
    standings: Record<string, { rank: number; points: number; played: number }> | null;
  };
  model_fit: { fitted_at: string; n_matches: number };
};

export type Sentence = { kind: "fact" | "model"; text: string };
export type Explanation = {
  headline: string;
  summary?: string;
  source: string;
  sections: Record<"home_case" | "away_case" | "draw" | "btts" | "goals" | "key_stats" | "risks", Sentence[]>;
};

export type StandingRow = {
  rank: number; team: string; initials: string; logo?: string | null; played: number; won: number; drawn: number;
  lost: number; goals_for: number; goals_against: number; points: number; form: string | null; group_name?: string | null;
};

export type FixtureDetail = {
  fixture: Fixture;
  prediction: Prediction | null;
  explanation: Explanation | null;
  standings: StandingRow[];
  settlement: { market: string; selection: string; p?: number; probability?: number; outcome: string }[] | null;
  prediction_history: { created_at: string; home: number; draw: number; away: number }[];
  freshness: Record<string, unknown> | null;
  demo: boolean;
};

export type TopItem = {
  market: string; selection: string; p: number; score: number; confidence: string; completeness: number; fixture: Fixture;
};

export type Agg = {
  n: number; hit_rate?: number; avg_probability?: number; brier?: number; log_loss?: number; ece?: number | null;
  hypothetical_roi?: { bets: number; profit_units: number; roi: number } | null;
};

export type Analytics = {
  windows: Record<"7" | "30" | "90", Agg>;
  by_league: Record<string, Agg>;
  by_market: Record<string, Agg>;
  calibration: { bin_low: number; bin_high: number; count: number; mean_predicted: number | null; observed_rate: number | null }[] | null;
  demo: boolean;
  note?: string;
};

export type Health = {
  demo: boolean; provider: string; live_data_configured: boolean; last_sync: Record<string, string | null>;
  warnings: string[]; app: string; tagline: string; default_timezone: string;
};

export type HistoryRow = {
  fixture_id: number; league_slug: string; market: string; selection: string; probability: number; outcome: string;
  home: string; away: string; final: [number, number]; settled_at: string; kickoff_utc: string; demo: boolean;
};
