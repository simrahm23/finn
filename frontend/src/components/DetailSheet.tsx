// The first cut of one signal, one tap from the Brief, with a handoff to research.
import { useEffect } from "react";
import type { BriefItem, ManagementCard, Prices, ResultsCard } from "../lib/types";
import { CATEGORY_LABEL } from "../lib/rules";
import { cleanHeadline, crore, dayLabel, pct, price, signClass, when } from "../lib/format";
import { Reasons, SourceChip, Sparkline } from "./bits";

function ResultsBlock({ card }: { card: ResultsCard }) {
  return (
    <div className="block">
      <h3><span>{card.period}</span><span>{card.basis} · ₹ cr</span></h3>
      <table className="results-table">
        <thead><tr><th></th><th>This qtr</th><th>QoQ</th><th>YoY</th></tr></thead>
        <tbody>
          {card.metrics.map((m) => (
            <tr key={m.name}>
              <td>{m.name}</td>
              {m.applicable ? (
                <>
                  <td>{crore(m.current)}</td>
                  <td className={signClass(m.qoq_pct)}>{pct(m.qoq_pct)}</td>
                  <td className={signClass(m.yoy_pct)}>{pct(m.yoy_pct)}</td>
                </>
              ) : <td colSpan={3} className="faint" style={{ fontFamily: "var(--sans)", fontSize: 13 }}>Not meaningful for lenders</td>}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10, gap: 8 }}>
        {card.verified
          ? <span className="verified">✓ Every number found on the cited page · PAT = PBT − tax holds</span>
          : <span className="unverified">Checks failed: treat these numbers with care and read the filing.</span>}
        <SourceChip source={card.source} />
      </div>
      <p className="fineprint">EBITDA = {card.ebitda_formula}. Growth is blank when the base period was a loss.
        {card.checks.cross_check === null ? "" : card.checks.cross_check ? " Matches screener.in." : " Differs from screener.in."}</p>
    </div>
  );
}

function PersonBlock({ card }: { card: ManagementCard }) {
  return (
    <div className="block">
      <h3><span>{card.direction === "leaving" ? "Leaving" : "Joining"}</span><SourceChip source={card.source} /></h3>
      <div style={{ fontSize: 17, fontWeight: 600 }}>{card.person}</div>
      <div className="muted" style={{ fontSize: 14 }}>{card.role}</div>
      {(card.effective_date || card.reason) && (
        <div style={{ fontSize: 13, marginTop: 6 }}>
          {card.reason && <span>{card.reason}</span>}
          {card.reason && card.effective_date && " · "}
          {card.effective_date && <span className="mono">effective {card.effective_date}</span>}
        </div>
      )}
      {card.profile
        ? <><div className="fineprint" style={{ marginTop: 10 }}>Profile, quoted from the filing:</div><p className="profile">{card.profile}</p></>
        : card.direction === "joining" && <p className="fineprint">No profile in the filing.</p>}
    </div>
  );
}

function PriceContext({ item, prices }: { item: BriefItem; prices: Prices | null }) {
  const p = prices?.symbols[item.symbol];
  if (!p) return null;
  const n = Math.min(30, p.close.length);
  const closes = p.close.slice(-n);
  const dates = p.dates.slice(-n);
  const day = item.filed_at.slice(0, 10);
  const mark = dates.findIndex((d) => d >= day);
  const last = p.close.length - 1;
  return (
    <div className="block">
      <h3><span>Price, last {n} sessions</span><span className="num">₹{price(p.close[last])}</span></h3>
      <Sparkline values={closes} width={330} height={56} markIndex={mark >= 0 ? mark : null} />
      <div className="fineprint">
        Dashed line = filing day. Last session {dayLabel(p.dates[last])}: <span className={signClass(p.ret_pct[last])}>{pct(p.ret_pct[last])}</span>
        {p.vol_ratio[last] !== null && <> · volume {p.vol_ratio[last]?.toFixed(1)}× its 20-day average</>}
      </div>
    </div>
  );
}

export function DetailSheet({ item, prices, now, researchable, onClose, seen, onToggleSeen }: {
  item: BriefItem; prices: Prices | null; now: string; researchable: boolean; onClose: () => void;
  seen: boolean; onToggleSeen: (id: string) => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);
  const results = item.card?.kind === "results" ? item.card : null;
  const person = item.card?.kind === "management" ? item.card : null;
  const digIn = `#/research/${item.symbol}${results ? "?q=promises" : ""}`;
  return (
    <>
      <div className="backdrop" onClick={onClose} />
      <div className="sheet" role="dialog" aria-modal="true" aria-label={item.company}>
        <div className="sheet__grip" />
        <button className="sheet__close" onClick={onClose} aria-label="Close">×</button>
        <div className="sheet__meta"><b style={{ color: "var(--ink)" }}>{item.company}</b> · {CATEGORY_LABEL[item.category] ?? item.category} · {when(item.filed_at, now)}</div>
        <h1>{cleanHeadline(item.headline, item.company)}</h1>
        <Reasons reasons={item.reasons} />
        {item.summary && <p style={{ margin: "12px 0 0", fontSize: 15 }}>{item.summary}</p>}
        {results && <ResultsBlock card={results} />}
        {person && <PersonBlock card={person} />}
        <PriceContext item={item} prices={prices} />
        <p className="fineprint">
          Ranked {item.tier.replace("_", " ")} with a score of {item.materiality.toFixed(0)}/100.
          Category by {item.category_method === "rule" ? "rule" : "model"}. Exchange category: {item.exchange_category || "—"}.
        </p>
        <div className="actions">
          {researchable
            ? <a className="btn btn--primary" href={digIn} onClick={onClose}>{results ? "Dig in: did they deliver?" : `Research ${item.company}`}</a>
            : <span className="btn btn--ghost faint" style={{ fontWeight: 500, fontSize: 13.5 }}>Research for {item.symbol} isn't pre-built in this demo yet</span>}
          {item.filing_url && <a className="btn btn--ghost" href={item.filing_url} target="_blank" rel="noreferrer">Open the filing</a>}
          {item.tier === "needs_you" && (
            <button className="btn btn--ghost" onClick={() => { onToggleSeen(item.id); onClose(); }}>
              {seen ? "Move back to Needs you" : "✓ Mark as seen"}
            </button>
          )}
        </div>
      </div>
    </>
  );
}
