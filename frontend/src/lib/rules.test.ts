// Run: npm test  (node's built-in test runner; no extra dependencies)
import { test } from "node:test";
import assert from "node:assert/strict";
import { alerts, byTier, effectiveTier, triggers, windowStart, DEFAULT_PREFS } from "./rules.ts";
import type { BriefItem, Prices } from "./types.ts";

test("triggers mirror the backend (inclusive thresholds)", () => {
  assert.deepEqual(triggers(-4.5, 1.0, 4, 2), ["price"]);
  assert.deepEqual(triggers(1.0, 2.0, 4, 2), ["volume"]);
  assert.deepEqual(triggers(null, null, 4, 2), []);
});

test("since-last-close window starts at the last session's 15:30 IST", () => {
  const s = windowStart("session", "2026-11-01T13:55:00+05:30", "2026-10-30");
  assert.equal(s.toISOString(), "2026-10-30T10:00:00.000Z");
});

const item = (over: Partial<BriefItem>): BriefItem => ({
  id: "x", symbol: "LT", company: "L&T", filed_at: "2026-10-30T10:00:00+05:30", headline: "h",
  exchange_category: "", category: "results", category_method: "rule", materiality: 80, tier: "needs_you",
  reasons: [], summary: null, filing_url: "", price_reaction_pct: null, card: null, ...over,
});

test("unsubscribed categories drop to worth knowing", () => {
  const prefs = { ...DEFAULT_PREFS, categories: [] };
  assert.equal(effectiveTier(item({}), prefs), "worth_knowing");
  assert.equal(effectiveTier(item({}), DEFAULT_PREFS), "needs_you");
});

test("needs-you sorted by materiality", () => {
  const t = byTier([item({ id: "a", materiality: 76 }), item({ id: "b", materiality: 90 })], DEFAULT_PREFS);
  assert.deepEqual(t.needs_you.map((i) => i.id), ["b", "a"]);
});

test("alerts respect user thresholds and look back N sessions", () => {
  const prices: Prices = { as_of: "2026-10-30", lookback_sessions: 20, symbols: {
    TRENT: { name: "Trent", dates: ["2026-10-29", "2026-10-30"], close: [1, 1], volume: [1, 1], ret_pct: [1.0, 5.44],
             vol_ratio: [1.6, 3.86], high_52w: false, low_52w: false, stale: false } } };
  assert.equal(alerts(prices, { priceMovePct: 4, volumeMultiple: 2 }).length, 1);
  assert.equal(alerts(prices, { priceMovePct: 4, volumeMultiple: 1.5 }, 2).length, 2);
  assert.equal(alerts(prices, { priceMovePct: 6, volumeMultiple: 4 }).length, 0);
});
