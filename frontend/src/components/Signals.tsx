// How a filing is shown at each tier: full card (needs you), compact row (worth knowing), folded line (routine).
import { useRef, useState, type PointerEvent as RPE } from "react";
import type { BriefItem, ManagementCard, ResultsCard } from "../lib/types";
import { CATEGORY_LABEL } from "../lib/rules";
import { cleanHeadline, crore, pct, signClass, when } from "../lib/format";
import { Reasons } from "./bits";

function MiniResults({ card }: { card: ResultsCard }) {
  return (
    <>
      <div className="mini-results">
        {card.metrics.map((m) => (
          <div key={m.name}>
            {m.name}
            {m.applicable ? (
              <>
                <b>{crore(m.current)}</b>
                <small className={signClass(m.yoy_pct)}>{pct(m.yoy_pct)} YoY</small>
              </>
            ) : <b className="faint">n/a</b>}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="faint" style={{ fontSize: 11.5 }}>{card.period.split(" (")[0]} · {card.basis} · ₹ cr</span>
        {card.verified ? <span className="verified">✓ checked against filing</span>
                       : <span className="unverified">Couldn't verify, open the filing</span>}
      </div>
    </>
  );
}

function MiniPerson({ card }: { card: ManagementCard }) {
  return (
    <div className="person-line">
      <span className={card.direction === "leaving" ? "down" : "up"} style={{ fontWeight: 600 }}>
        {card.direction === "leaving" ? "Leaving" : "Joining"}
      </span>{" · "}<b>{card.person.replace(/^(Mr|Ms|Mrs|Dr)\.?\s+/i, "")}</b>, {card.role}
      {card.profile && <div className="faint" style={{ fontSize: 12, marginTop: 2 }}>Profile from the filing inside →</div>}
    </div>
  );
}

export function SignalCard({ item, now, onOpen, onSeen }: {
  item: BriefItem; now: string; onOpen: (i: BriefItem) => void; onSeen?: (id: string) => void;
}) {
  // Swipe left (or tap "Seen") to clear a card: the Brief counts down to inbox zero.
  const start = useRef<number | null>(null);
  const moved = useRef(false);
  const [dx, setDx] = useState(0);
  const down = (e: RPE) => { start.current = e.clientX; moved.current = false; };
  const move = (e: RPE) => {
    if (start.current === null) return;
    const d = Math.min(0, e.clientX - start.current);
    if (Math.abs(d) > 8) moved.current = true;
    setDx(d);
  };
  const up = () => {
    if (dx < -90 && onSeen) onSeen(item.id);
    start.current = null;
    setDx(0);
  };
  const results = item.card?.kind === "results" ? item.card : null;
  const person = item.card?.kind === "management" ? item.card : null;
  const showResults = results && results.verified;
  return (
    <div className="swipe">
      {onSeen && <div className="swipe__under" style={{ opacity: Math.min(1, -dx / 90) }}>✓ Seen</div>}
    <button className="card" onClick={() => { if (!moved.current) onOpen(item); }}
            onPointerDown={onSeen ? down : undefined} onPointerMove={onSeen ? move : undefined}
            onPointerUp={onSeen ? up : undefined} onPointerCancel={onSeen ? up : undefined}
            style={{ transform: dx ? `translateX(${dx}px)` : undefined, transition: dx ? "none" : "transform .2s" }}>
      <div className="card__meta">
        <span><span className="card__sym">{item.symbol}</span> · {CATEGORY_LABEL[item.category] ?? item.category}</span>
        <span className="mono">{when(item.filed_at, now)}</span>
      </div>
      <h3 className="card__title">{person ? `${person.person.replace(/^(Mr|Ms|Mrs|Dr)\.?\s+/i, "")} ${person.direction === "leaving" ? "steps down" : "comes in"} as ${person.role}`
        : results ? `${item.company} ${results.period.split(" (")[0]} results` : cleanHeadline(item.headline, item.company)}</h3>
      {item.summary && !showResults && !person && <p className="card__summary">{item.summary}</p>}
      {(showResults || person) && (
        <div className="card__body">{showResults ? <MiniResults card={results} /> : person && <MiniPerson card={person} />}</div>
      )}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 8 }}>
        <Reasons reasons={item.reasons} />
        {onSeen && (
          <span role="button" tabIndex={0} className="seen-btn" aria-label="Mark as seen"
                onClick={(e) => { e.stopPropagation(); onSeen(item.id); }}
                onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); onSeen(item.id); } }}>✓ Seen</span>
        )}
      </div>
    </button>
    </div>
  );
}

export function SignalRow({ item, now, onOpen }: { item: BriefItem; now: string; onOpen: (i: BriefItem) => void }) {
  return (
    <button className="row" onClick={() => onOpen(item)}>
      <span className="row__sym">{item.symbol}</span>
      <span className="row__text">
        {item.summary ?? cleanHeadline(item.headline, item.company)}
        <small>{item.reasons.join(" · ")}</small>
      </span>
      <span className="row__when">{when(item.filed_at, now)}</span>
    </button>
  );
}

export function RoutineAccordion({ items }: { items: BriefItem[] }) {
  if (!items.length) return null;
  const groups = new Map<string, BriefItem[]>();
  for (const i of items) {
    const k = i.exchange_category || CATEGORY_LABEL[i.category] || "Other";
    groups.set(k, [...(groups.get(k) ?? []), i]);
  }
  const sorted = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
  return (
    <details className="routine">
      <summary>{items.length} routine filings, folded away</summary>
      <div className="routine__groups">
        {sorted.map(([k, list]) => (
          <div className="routine__group" key={k}>
            <h3><span>{k}</span><span className="mono">{list.length}</span></h3>
            {list.map((i) => (
              <a className="routine__item" key={i.id} href={i.filing_url} target="_blank" rel="noreferrer">
                <span>{i.symbol}</span>{cleanHeadline(i.headline, i.company).slice(0, 90)}
              </a>
            ))}
          </div>
        ))}
      </div>
    </details>
  );
}
