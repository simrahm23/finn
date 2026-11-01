// Price and volume alerts for the last session, using the user's own thresholds.
import type { Prices } from "../lib/types";
import { alerts, type Prefs } from "../lib/rules";
import { pct, signClass } from "../lib/format";
import { Sparkline } from "./bits";

export function AlertStrip({ prices, prefs, onPick }: { prices: Prices; prefs: Prefs; onPick: (symbol: string) => void }) {
  const list = alerts(prices, prefs, 1);
  if (!list.length) {
    return <div className="alerts-empty">No stock crossed ±{prefs.priceMovePct}% or {prefs.volumeMultiple}× volume last session.</div>;
  }
  return (
    <div className="alerts" role="list">
      {list.map((a) => {
        const p = prices.symbols[a.symbol];
        return (
          <button className="alert" key={a.symbol + a.date} role="listitem" onClick={() => onPick(a.symbol)}>
            <div className="alert__sym">{a.symbol}</div>
            <div className="alert__vals num">
              <span className={signClass(a.ret)} style={{ fontWeight: a.kinds.includes("price") ? 700 : 400 }}>{pct(a.ret)}</span>
              <span style={{ fontWeight: a.kinds.includes("volume") ? 700 : 400, color: a.kinds.includes("volume") ? "#8a5200" : undefined }}>
                {a.volRatio?.toFixed(1)}× vol
              </span>
            </div>
            <Sparkline values={p.close.slice(-20)} width={144} height={24} />
          </button>
        );
      })}
    </div>
  );
}
