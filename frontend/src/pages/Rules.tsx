// The investor decides what "unusual" means. Changes apply instantly and are kept in this browser.
import type { Brief, Prices } from "../lib/types";
import { alerts, byTier, CATEGORY_GROUPS, DEFAULT_PREFS, inWindow, windowStart, type Prefs } from "../lib/rules";
import { dayLabel, pct } from "../lib/format";

export function RulesPage({ prefs, setPrefs, prices, brief, now }: {
  prefs: Prefs; setPrefs: (p: Prefs) => void; prices: Prices | null; brief: Brief | null; now: string;
}) {
  const week = prices ? alerts(prices, prefs, 5) : [];
  const needs = brief ? byTier(inWindow(brief.items, windowStart("7d", now, null)), prefs).needs_you.length : 0;
  const toggle = (k: Prefs["categories"][number]) =>
    setPrefs({ ...prefs, categories: prefs.categories.includes(k) ? prefs.categories.filter((c) => c !== k) : [...prefs.categories, k] });

  return (
    <>
      <header className="masthead">
        <div className="masthead__top"><div className="wordmark">Rules</div><div className="dateline">saved on this device</div></div>
        <p className="subline">You decide what counts as unusual. FINN watches.</p>
      </header>

      <div className="preview" aria-live="polite">
        <div style={{ display: "flex", gap: 18, alignItems: "baseline" }}>
          <div><div className="preview__n">{week.length}</div><div className="muted" style={{ fontSize: 12.5 }}>price/volume alerts, last 5 sessions</div></div>
          <div><div className="preview__n">{needs}</div><div className="muted" style={{ fontSize: 12.5 }}>filings in "Needs you", 7 days</div></div>
        </div>
        {week.length > 0 && (
          <div style={{ marginTop: 10, display: "grid", gap: 4 }}>
            {week.slice(0, 6).map((a) => (
              <div key={a.symbol + a.date} className="num" style={{ fontSize: 12.5, display: "flex", justifyContent: "space-between" }}>
                <span><b style={{ fontFamily: "var(--sans)" }}>{a.symbol}</b> <span className="faint">{dayLabel(a.date)}</span></span>
                <span><span className={a.ret && a.ret > 0 ? "up" : "down"}>{pct(a.ret)}</span> · {a.volRatio?.toFixed(1)}×</span>
              </div>
            ))}
            {week.length > 6 && <div className="faint" style={{ fontSize: 12 }}>+{week.length - 6} more</div>}
          </div>
        )}
      </div>

      <div className="section"><h2>Price move</h2></div>
      <div className="rule">
        <div className="rule__head"><span>Alert when a stock moves at least</span><b>±{prefs.priceMovePct.toFixed(1)}%</b></div>
        <p>Close-to-close, last session.</p>
        <input type="range" min={1} max={10} step={0.5} value={prefs.priceMovePct} aria-label="Price move threshold"
               onChange={(e) => setPrefs({ ...prefs, priceMovePct: Number(e.target.value) })} />
      </div>
      <div className="section"><h2>Volume</h2></div>
      <div className="rule">
        <div className="rule__head"><span>Alert when volume is at least</span><b>{prefs.volumeMultiple.toFixed(1)}×</b></div>
        <p>Compared with the average of the previous 20 sessions (today excluded).</p>
        <input type="range" min={1.5} max={5} step={0.1} value={prefs.volumeMultiple} aria-label="Volume threshold"
               onChange={(e) => setPrefs({ ...prefs, volumeMultiple: Number(e.target.value) })} />
      </div>

      <div className="section"><h2>Which filings may interrupt you</h2></div>
      {CATEGORY_GROUPS.map((g) => (
        <div key={g.title}>
          <div className="faint" style={{ fontSize: 12, marginTop: 6 }}>{g.title}</div>
          <div className="toggles">
            {g.items.map((c) => (
              <button key={c.key} className={`chip ${prefs.categories.includes(c.key) ? "chip--on" : ""}`}
                      aria-pressed={prefs.categories.includes(c.key)} onClick={() => toggle(c.key)}>{c.label}</button>
            ))}
          </div>
        </div>
      ))}
      <p className="fineprint">Off = still shown, but never in "Needs you". Routine paperwork is always folded.</p>
      <button className="btn btn--ghost" style={{ width: "100%", marginTop: 8 }} onClick={() => setPrefs({ ...DEFAULT_PREFS, seen: prefs.seen })}>
        Reset to defaults
      </button>
    </>
  );
}
