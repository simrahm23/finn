// Client-side rules: the user's thresholds, time windows, and which items reach "Needs you".
// Pure functions (tested in rules.test.ts). Alert maths mirrors backend/finn/signals/price_volume.py `triggers`.
import type { BriefItem, Category, Prices, Tier } from "./types";

export interface Prefs {
  priceMovePct: number;
  volumeMultiple: number;
  categories: Category[]; // categories allowed to reach "Needs you"
  seen: string[];         // BriefItem ids the user marked seen
}

// Defaults = config/rules.yaml alert_defaults
export const DEFAULT_PREFS: Prefs = {
  priceMovePct: 4,
  volumeMultiple: 2,
  categories: ["results", "M&A", "management_change", "fund_raise", "litigation", "pledging", "credit_rating"],
  seen: [],
};

export const CATEGORY_GROUPS: { title: string; items: { key: Category; label: string }[] }[] = [
  { title: "Usually critical", items: [
    { key: "results", label: "Results" }, { key: "M&A", label: "M&A" },
    { key: "management_change", label: "Management change" }, { key: "fund_raise", label: "Fund raise" },
    { key: "litigation", label: "Litigation" }, { key: "pledging", label: "Pledging" },
    { key: "credit_rating", label: "Credit rating" } ] },
  { title: "Usually notable", items: [
    { key: "capex", label: "Capex" }, { key: "insider_trading", label: "Insider trades" },
    { key: "bonus_split", label: "Bonus / split" }, { key: "dividend", label: "Dividend" },
    { key: "press_release", label: "Updates & orders" }, { key: "earnings_call", label: "Earnings calls" } ] },
  { title: "Usually routine", items: [
    { key: "investor_meetings", label: "Investor meetings" }, { key: "agm_egm", label: "AGM / EGM" },
    { key: "postal_ballot", label: "Postal ballot" }, { key: "unclassified", label: "Compliance paperwork" } ] },
];

export const CATEGORY_LABEL: Record<string, string> = Object.fromEntries(
  CATEGORY_GROUPS.flatMap((g) => g.items.map((i) => [i.key, i.label])),
);

const KEY = "finn.prefs.v1";

export function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULT_PREFS, ...JSON.parse(raw) } : DEFAULT_PREFS;
  } catch {
    return DEFAULT_PREFS;
  }
}

export function savePrefs(p: Prefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* private mode or storage blocked: prefs live for this session only */
  }
}

// ---------- time windows ----------
export type WindowKey = "24h" | "session" | "3d" | "7d";
export const WINDOWS: { key: WindowKey; label: string }[] = [
  { key: "24h", label: "24h" },
  { key: "session", label: "Since last close" },
  { key: "3d", label: "3 days" },
  { key: "7d", label: "7 days" },
];

/** Start of a window. `now` is the data snapshot time (static data), `pricesAsOf` the last trading date. */
export function windowStart(key: WindowKey, now: string, pricesAsOf: string | null): Date {
  const n = new Date(now).getTime();
  const h = 3600_000;
  if (key === "session" && pricesAsOf) return new Date(`${pricesAsOf}T15:30:00+05:30`);
  const hours = key === "24h" ? 24 : key === "3d" ? 72 : key === "7d" ? 168 : 24;
  return new Date(n - hours * h);
}

export function inWindow(items: BriefItem[], start: Date): BriefItem[] {
  return items.filter((i) => new Date(i.filed_at).getTime() >= start.getTime());
}

/** The user decides which categories may interrupt them: others drop one tier. */
export function effectiveTier(item: BriefItem, prefs: Prefs): Tier {
  if (item.tier === "needs_you" && !prefs.categories.includes(item.category)) return "worth_knowing";
  return item.tier;
}

export function byTier(items: BriefItem[], prefs: Prefs) {
  const out: Record<Tier, BriefItem[]> = { needs_you: [], worth_knowing: [], routine: [] };
  for (const i of items) out[effectiveTier(i, prefs)].push(i);
  out.needs_you.sort((a, b) => b.materiality - a.materiality);
  out.worth_knowing.sort((a, b) => b.materiality - a.materiality);
  return out;
}

// ---------- price / volume alerts ----------
export type TriggerKind = "price" | "volume";

export function triggers(ret: number | null, vr: number | null, priceThr: number, volThr: number): TriggerKind[] {
  const out: TriggerKind[] = [];
  if (ret !== null && Math.abs(ret) >= priceThr) out.push("price");
  if (vr !== null && vr >= volThr) out.push("volume");
  return out;
}

export interface Alert {
  symbol: string;
  name: string;
  date: string;
  ret: number | null;
  volRatio: number | null;
  kinds: TriggerKind[];
}

/** Alerts over the last `sessions` trading sessions, newest first, strongest first within a day. */
export function alerts(prices: Prices, prefs: Pick<Prefs, "priceMovePct" | "volumeMultiple">, sessions = 1): Alert[] {
  const out: Alert[] = [];
  for (const [symbol, p] of Object.entries(prices.symbols)) {
    const n = p.dates.length;
    for (let i = Math.max(0, n - sessions); i < n; i++) {
      const kinds = triggers(p.ret_pct[i], p.vol_ratio[i], prefs.priceMovePct, prefs.volumeMultiple);
      if (kinds.length) out.push({ symbol, name: p.name, date: p.dates[i], ret: p.ret_pct[i], volRatio: p.vol_ratio[i], kinds });
    }
  }
  const strength = (a: Alert) => Math.abs(a.ret ?? 0) / prefs.priceMovePct + (a.volRatio ?? 0) / prefs.volumeMultiple;
  return out.sort((a, b) => (a.date === b.date ? strength(b) - strength(a) : a.date < b.date ? 1 : -1));
}


// ---------- triage ----------
/** Split "Needs you" into what's left to look at and what's been seen. */
export function triage(needs: BriefItem[], seen: string[]) {
  const s = new Set(seen);
  return { open: needs.filter((i) => !s.has(i.id)), seen: needs.filter((i) => s.has(i.id)) };
}

export function toggleSeenIds(seen: string[], id: string): string[] {
  return seen.includes(id) ? seen.filter((x) => x !== id) : [...seen, id];
}
