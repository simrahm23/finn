// Holdings at a glance: move, unusual volume, 30-day shape, unread signals.
import type { Brief, Prices } from "../lib/types";
import { type Prefs } from "../lib/rules";
import { pct, price, signClass } from "../lib/format";
import { Sparkline } from "../components/bits";

export function PortfolioPage({ prices, brief, prefs }: { prices: Prices; brief: Brief | null; prefs: Prefs }) {
  const signals = new Map<string, number>();
  for (const i of brief?.items ?? []) if (i.tier !== "routine") signals.set(i.symbol, (signals.get(i.symbol) ?? 0) + 1);
  const rows = Object.entries(prices.symbols).map(([sym, p]) => {
    const n = p.close.length - 1;
    return { sym, p, ret: p.ret_pct[n], vr: p.vol_ratio[n], sig: signals.get(sym) ?? 0 };
  }).sort((a, b) => b.sig - a.sig || Math.abs(b.ret ?? 0) - Math.abs(a.ret ?? 0));

  return (
    <>
      <header className="masthead">
        <div className="masthead__top"><div className="wordmark">Portfolio</div><div className="dateline">as of {prices.as_of}</div></div>
        <p className="subline">{rows.length} holdings · sorted by open signals, then size of move</p>
      </header>
      <div className="holdings">
        {rows.map(({ sym, p, ret, vr, sig }) => (
          <a className="holding" key={sym} href={`#/brief?s=${sym}`} style={{ textDecoration: "none" }}>
            <div style={{ minWidth: 0 }}>
              <div className="holding__sym">
                {sym}
                {sig > 0 && <span className="dot" title={`${sig} open signals`} />}
                {vr !== null && vr >= prefs.volumeMultiple && <span className="badge">VOL {vr.toFixed(1)}×</span>}
                {p.stale && <span className="badge" style={{ background: "var(--line-2)", color: "var(--ink-2)" }}>STALE</span>}
              </div>
              <div className="holding__name">{p.name}</div>
            </div>
            <Sparkline values={p.close.slice(-30)} width={76} height={28} />
            <div className="holding__px num">
              ₹{price(p.close[p.close.length - 1])}
              <small className={signClass(ret)}>{pct(ret)}</small>
            </div>
          </a>
        ))}
      </div>
    </>
  );
}
