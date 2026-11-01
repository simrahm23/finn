// Home: what changed and what matters. Ranked, folded, explained.
import { useMemo, useState } from "react";
import type { Brief as BriefT, BriefItem, Meta, Prices } from "../lib/types";
import { byTier, inWindow, windowStart, WINDOWS, type Prefs, type WindowKey } from "../lib/rules";
import { when } from "../lib/format";
import { AlertStrip } from "../components/AlertStrip";
import { RoutineAccordion, SignalCard, SignalRow } from "../components/Signals";

export function BriefPage({ brief, prices, meta, prefs, symbol, onOpen }: {
  brief: BriefT; prices: Prices | null; meta: Meta | null; prefs: Prefs; symbol: string | null; onOpen: (i: BriefItem) => void;
}) {
  const now = meta?.generated_at ?? brief.generated_at;
  const [win, setWin] = useState<WindowKey>("24h");
  const start = windowStart(win, now, prices?.as_of ?? meta?.prices_as_of ?? null);
  const all = useMemo(() => {
    const w = inWindow(brief.items, start);
    return symbol ? w.filter((i) => i.symbol === symbol) : w;
  }, [brief.items, start.getTime(), symbol]); // eslint-disable-line react-hooks/exhaustive-deps
  const tiers = byTier(all, prefs);
  const quiet = win === "24h" && tiers.needs_you.length + tiers.worth_knowing.length < 3;
  const winLabel = WINDOWS.find((w) => w.key === win)?.label.toLowerCase();

  return (
    <>
      <header className="masthead">
        <div className="masthead__top">
          <div className="wordmark">FINN<span>.</span></div>
          <div className="dateline">{new Date(now).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", weekday: "short", day: "numeric", month: "short" })}</div>
        </div>
        <p className="headline-count">
          {tiers.needs_you.length === 0 ? "Nothing needs you" : <><em>{tiers.needs_you.length}</em> {tiers.needs_you.length === 1 ? "thing needs" : "things need"} you</>}
          {symbol ? ` in ${symbol}` : ""}
        </p>
        <p className="subline">
          {all.length} filings {win === "session" ? "since the last close" : `in the last ${winLabel}`}
          {" · "}{tiers.routine.length} folded as routine
        </p>
      </header>

      <div className="chips" role="tablist" aria-label="Time window">
        {WINDOWS.map((w) => (
          <button key={w.key} className={`chip ${win === w.key ? "chip--on" : ""}`} onClick={() => setWin(w.key)} aria-pressed={win === w.key}>{w.label}</button>
        ))}
        {symbol && <a className="chip chip--on" href="#/brief">{symbol} ×</a>}
      </div>

      {quiet && (
        <div className="nudge">
          <span>Quiet 24 hours: markets were shut for the weekend.</span>
          <button onClick={() => setWin("7d")}>Show 7 days</button>
        </div>
      )}

      {prices && !symbol && (
        <>
          <div className="section"><h2>Unusual moves · last session</h2><span className="count">±{prefs.priceMovePct}% · {prefs.volumeMultiple}× vol</span></div>
          <AlertStrip prices={prices} prefs={prefs} onPick={(s) => { location.hash = `#/brief?s=${s}`; }} />
        </>
      )}

      <div className="section"><h2>Needs you</h2><span className="count">{tiers.needs_you.length}</span></div>
      {tiers.needs_you.length
        ? tiers.needs_you.map((i) => <SignalCard key={i.id} item={i} now={now} onOpen={onOpen} />)
        : <div className="empty"><b>All clear.</b> Nothing in this window crossed your bar. That's the point.</div>}

      {tiers.worth_knowing.length > 0 && (
        <>
          <div className="section"><h2>Worth knowing</h2><span className="count">{tiers.worth_knowing.length}</span></div>
          <div className="rows">{tiers.worth_knowing.map((i) => <SignalRow key={i.id} item={i} now={now} onOpen={onOpen} />)}</div>
        </>
      )}

      {tiers.routine.length > 0 && (
        <>
          <div className="section"><h2>Routine</h2><span className="count">{tiers.routine.length}</span></div>
          <RoutineAccordion items={tiers.routine} />
        </>
      )}

      {meta && (
        <footer className="ops">
          {meta.mock && <div style={{ color: "var(--accent)" }}>MOCK DATA, for development only</div>}
          Filings as of {meta.filings_as_of ? when(meta.filings_as_of, now) : "—"} · prices as of {meta.prices_as_of ?? "—"}<br />
          {meta.llm.calls} model requests · {meta.llm.cached} served from cache · ₹{meta.llm.cost_inr.toFixed(0)} spent<br />
          Sources: NSE filings, end-of-day prices ({meta.sources.prices ?? "yfinance"})
        </footer>
      )}
    </>
  );
}
