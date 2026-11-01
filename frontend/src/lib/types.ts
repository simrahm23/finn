// JSON contracts — hand-mirrored from backend/finn/contracts.py. Change one, change the other.

export type Category =
  | "results" | "M&A" | "fund_raise" | "management_change" | "litigation" | "insider_trading"
  | "earnings_call" | "investor_meetings" | "credit_rating" | "dividend" | "bonus_split" | "capex"
  | "press_release" | "postal_ballot" | "agm_egm" | "pledging" | "unclassified";
export type Tier = "needs_you" | "worth_knowing" | "routine";
export type Verdict = "met" | "partly" | "missed" | "pending" | "unverifiable";

export interface Source {
  label: string;
  kind: "filing" | "transcript" | "annual_report" | "screener";
  url: string;
  page: number | null; // open as `${url}#page=${page}`
}

// ---------- meta.json ----------
export interface LlmUsage { calls: number; cached: number; tokens_in: number; tokens_out: number; cost_inr: number }
export interface Meta {
  generated_at: string;
  prices_as_of: string | null;
  filings_as_of: string | null;
  mock: boolean;
  sources: Record<string, string>;
  llm: LlmUsage;
}

// ---------- brief.json ----------
export interface ResultsMetric {
  name: "Revenue" | "EBITDA" | "PBT" | "PAT";
  applicable: boolean;
  current: number | null;
  prev_q: number | null;
  year_ago: number | null;
  qoq_pct: number | null;
  yoy_pct: number | null;
}
export interface ResultsCard {
  kind: "results";
  period: string;
  basis: "consolidated" | "standalone";
  unit: string;
  metrics: ResultsMetric[];
  ebitda_formula: string;
  checks: { verbatim: boolean; identities: boolean; cross_check: boolean | null };
  verified: boolean;
  source: Source;
}
export interface ManagementCard {
  kind: "management";
  direction: "joining" | "leaving";
  person: string;
  role: string;
  effective_date: string | null;
  reason: string | null;
  profile: string | null;
  source: Source;
}
export interface BriefItem {
  id: string;
  symbol: string;
  company: string;
  filed_at: string;
  headline: string;
  exchange_category: string;
  category: Category;
  category_method: "rule" | "llm";
  materiality: number;
  tier: Tier;
  reasons: string[];
  summary: string | null;
  filing_url: string;
  price_reaction_pct: number | null;
  card: ResultsCard | ManagementCard | null;
}
export interface Brief { generated_at: string; window_max_days: number; items: BriefItem[] }

// ---------- prices.json ----------
export interface SymbolPrices {
  name: string;
  dates: string[];
  close: number[];
  volume: number[];
  ret_pct: (number | null)[];
  vol_ratio: (number | null)[];
  high_52w: boolean;
  low_52w: boolean;
  stale: boolean;
}
export interface Prices { as_of: string; lookback_sessions: number; symbols: Record<string, SymbolPrices> }

// ---------- research pack ----------
export interface Kpi { label: string; value: number | null; unit: string; period: string; source: Source }
export interface Snapshot {
  kpis: Kpi[];
  years: string[];
  revenue: (number | null)[];
  ebitda_margin_pct: (number | null)[];
  cfo: (number | null)[];
  pat: (number | null)[];
  cash_conversion_pct: (number | null)[];
  debt_to_equity: number | null;
  business: string | null;
  business_source: Source | null;
  missing: string[];
}
export interface Promise_ {
  id: string;
  said_in: string;
  target_period: string;
  metric: string;
  target_text: string;
  target_low: number | null;
  target_high: number | null;
  unit: string;
  actual: number | null;
  actual_basis: "tables" | "reported" | null; // computed from reported tables, or stated by management on a later call
  actual_source: Source | null;
  repeated_in: string[]; // later calls that restated the same target
  verdict: Verdict;
  quote: string;
  source: Source;
}
export interface Scorecard { met: number; partly: number; missed: number; pending: number; unverifiable: number }
export interface Promises {
  scorecard: Scorecard;
  items: Promise_[];
  qualitative: Promise_[];
  commentary: { text: string; cites: string[] } | null;
}
export interface DocumentRef {
  id: string;
  kind: "annual_report" | "transcript" | "results" | "filing";
  period: string;
  title: string;
  url: string;
  pages: number | null;
}
export interface BuildStep { ts: string; step: string; status: "running" | "done" | "failed" | "skipped"; detail: string | null }
export interface ResearchPack {
  symbol: string;
  name: string;
  sector: string | null;
  status: "building" | "ready" | "failed";
  built_at: string | null;
  mock: boolean;
  snapshot: Snapshot | null;
  promises: Promises | null;
  documents: DocumentRef[];
  build_log: BuildStep[];
}
