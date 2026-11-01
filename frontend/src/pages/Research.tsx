// Pull: on-demand analysis grounded in the company's own filings. Snapshot + Promise Tracker.
import { useState } from "react";
import type { Promise_, ResearchPack, Snapshot } from "../lib/types";
import { useResearch, useResearchIndex } from "../lib/data";
import { crore } from "../lib/format";
import { SourceChip } from "../components/bits";

const VERDICT_LABEL = { met: "Met", partly: "Partly", missed: "Missed", pending: "Pending", unverifiable: "Can't check" } as const;

function TrajectoryChart({ s }: { s: Snapshot }) {
  const W = 340, H = 150, pad = { l: 4, r: 4, t: 14, b: 22 };
  const n = s.years.length;
  const rev = s.revenue.map((v) => v ?? 0);
  const maxRev = Math.max(...rev, 1);
  const m = s.ebitda_margin_pct.filter((v): v is number => v !== null);
  const mLo = Math.min(...m, 0), mHi = Math.max(...m, 1);
  const bw = (W - pad.l - pad.r) / n;
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / maxRev);
  const ym = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - (v - mLo) / (mHi - mLo || 1));
  const line = s.ebitda_margin_pct.map((v, i) => (v === null ? null : `${pad.l + bw * i + bw / 2},${ym(v)}`)).filter(Boolean).join(" ");
  const last = n - 1;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Revenue bars and EBITDA margin line by year">
      {rev.map((v, i) => (
        <rect key={i} x={pad.l + bw * i + bw * 0.18} width={bw * 0.64} y={y(v)} height={H - pad.b - y(v)} rx="2"
              fill={i === last ? "var(--ink)" : "#d9d4c8"} />
      ))}
      <polyline points={line} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" />
      {s.ebitda_margin_pct.map((v, i) => v !== null && (i === 0 || i === last) && (
        <text key={i} x={pad.l + bw * i + bw / 2} y={ym(v) - 6} textAnchor="middle" fontSize="10" fill="var(--accent)" fontFamily="var(--mono)">{v.toFixed(1)}%</text>
      ))}
      <text x={pad.l} y={H - 6} fontSize="10" fill="var(--ink-3)" fontFamily="var(--mono)">{s.years[0]}</text>
      <text x={W - pad.r} y={H - 6} fontSize="10" fill="var(--ink-3)" fontFamily="var(--mono)" textAnchor="end">{s.years[last]}</text>
    </svg>
  );
}

function CashChart({ s }: { s: Snapshot }) {
  const vals = s.cash_conversion_pct;
  const W = 340, H = 90, base = 70, n = vals.length, bw = W / n;
  const max = Math.max(150, ...vals.map((v) => Math.abs(v ?? 0)));
  const h = (v: number) => (Math.min(Math.abs(v), max) / max) * (base - 8);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Cash from operations as a percent of profit, by year">
      <line x1="0" x2={W} y1={base - h(100)} y2={base - h(100)} stroke="var(--ink-3)" strokeDasharray="3 3" />
      <text x={W} y={base - h(100) - 3} textAnchor="end" fontSize="9.5" fill="var(--ink-3)" fontFamily="var(--mono)">100%</text>
      {vals.map((v, i) => v !== null && (
        <rect key={i} x={bw * i + bw * 0.2} width={bw * 0.6} y={v >= 0 ? base - h(v) : base} height={h(v)} rx="2"
              fill={v >= 80 ? "var(--up)" : "var(--down)"} opacity={i === n - 1 ? 1 : 0.55} />
      ))}
      <text x="0" y={H - 4} fontSize="10" fill="var(--ink-3)" fontFamily="var(--mono)">{s.years[0]}</text>
      <text x={W} y={H - 4} fontSize="10" fill="var(--ink-3)" fontFamily="var(--mono)" textAnchor="end">{s.years[n - 1]}</text>
    </svg>
  );
}

function SnapshotView({ pack }: { pack: ResearchPack }) {
  const s = pack.snapshot;
  if (!s) return <div className="empty">No snapshot: the financial tables could not be read.</div>;
  const conv = s.cash_conversion_pct.filter((v): v is number => v !== null);
  const avg = conv.length ? conv.slice(-5).reduce((a, b) => a + b, 0) / Math.min(5, conv.length) : null;
  return (
    <>
      <div className="kpis">
        {s.kpis.map((k) => (
          <div className="kpi" key={k.label}>
            <small>{k.label}</small>
            <b>{k.unit === "%" ? `${k.value?.toFixed(1)}%` : crore(k.value)}</b>
            <span>{k.unit !== "%" ? `${k.unit} · ` : ""}{k.period}</span>
          </div>
        ))}
      </div>
      <div className="block">
        <h3><span>Trajectory</span><span>revenue ▮ · EBITDA margin —</span></h3>
        <TrajectoryChart s={s} />
      </div>
      <div className="block">
        <h3><span>Cash quality</span><span>CFO ÷ PAT</span></h3>
        <CashChart s={s} />
        <p className="fineprint">
          {avg !== null && <>Last 5 years averaged <b className="num">{avg.toFixed(0)}%</b>: {avg >= 90 ? "profits are turning into cash." : avg >= 70 ? "most profit turns into cash." : "profit is not consistently turning into cash. Worth a look."}</>}
          {s.debt_to_equity !== null && <> Debt to equity {s.debt_to_equity.toFixed(2)}.</>}
        </p>
      </div>
      {s.business && (
        <div className="block">
          <h3><span>What they do</span>{s.business_source && <SourceChip source={s.business_source} />}</h3>
          <p style={{ margin: 0, fontSize: 14 }}>{s.business}</p>
        </div>
      )}
      {s.missing.length > 0 && <p className="fineprint">Not available: {s.missing.join(", ")}.</p>}
      {s.kpis[0] && <p className="fineprint">Figures: <SourceChip source={s.kpis[0].source} /> standardised from company filings.</p>}
    </>
  );
}

function PromiseItem({ p }: { p: Promise_ }) {
  const actual = p.actual === null ? "—" : `${p.actual.toFixed(1)}${p.unit === "%" ? "%" : ` ${p.unit}`}`;
  return (
    <div className="promise">
      <div className="promise__top">
        <div>
          <div className="promise__target">{p.target_text}</div>
          <div className="promise__meta">Said in {p.said_in} · for {p.target_period}
            {p.repeated_in?.length > 0 && <> · reiterated {p.repeated_in.length === 1 ? "once more" : `on ${p.repeated_in.length} later calls`}</>}</div>
        </div>
        <span className={`pill pill--${p.verdict}`}>{VERDICT_LABEL[p.verdict]}</span>
      </div>
      {p.verdict !== "unverifiable" && p.target_low !== null && (
        <div className="promise__vs">
          <span className="muted">Promised <b className="num" style={{ color: "var(--ink)" }}>
            {p.target_low !== null ? (p.target_high !== null && p.target_high !== p.target_low ? `${p.target_low}–${p.target_high}` : p.target_low) : "—"}{p.unit === "%" ? "%" : ""}</b></span>
          <span className="muted">Delivered <b className="num" style={{ color: "var(--ink)" }}>{actual}</b>
            {p.actual_basis === "tables" && <span className="faint" style={{ fontSize: 11.5 }}> · from reported financials</span>}
          </span>
        </div>
      )}
      <p className="quote">“{p.quote}”</p>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <SourceChip source={p.source} />
        {p.actual_source && <SourceChip source={p.actual_source} />}
      </div>
    </div>
  );
}

function PromisesView({ pack }: { pack: ResearchPack }) {
  const pr = pack.promises;
  if (!pr) return <div className="empty">No transcripts found, so there's no guidance to check.</div>;
  const sc = pr.scorecard;
  const order = (q: string) => { const m = q.match(/Q(\d)\s*FY(\d+)/); return m ? Number(m[2]) * 10 + Number(m[1]) : 0; };
  const judged = pr.items.filter((p) => p.verdict === "met" || p.verdict === "partly" || p.verdict === "missed");
  const pending = pr.items.filter((p) => p.verdict === "pending");
  const unver = pr.items.filter((p) => p.verdict === "unverifiable");
  const groups = new Map<string, Promise_[]>();
  for (const p of judged) groups.set(p.said_in, [...(groups.get(p.said_in) ?? []), p]);
  const sortedGroups = [...groups.entries()].sort((a, b) => order(b[0]) - order(a[0]));
  return (
    <>
      <div className="scorecard">
        <div><b className="up">{sc.met}</b><small>met</small></div>
        <div><b style={{ color: "#8a5200" }}>{sc.partly}</b><small>partly</small></div>
        <div><b className="down">{sc.missed}</b><small>missed</small></div>
        <div><b className="muted">{sc.pending}</b><small>still open</small></div>
      </div>
      {pr.commentary && <div className="block" style={{ fontSize: 14.5 }}>{pr.commentary.text}</div>}
      {judged.length === 0 && (
        <div className="empty" style={{ marginTop: 12 }}><b>No promise has come due yet.</b> Management's targets in these calls are for
          periods that haven't ended. They're listed below and will be judged as results arrive.</div>
      )}
      {sortedGroups.map(([q, list]) => (
        <div key={q}>
          <div className="section"><h2>Promised in {q}</h2><span className="count">{list.length}</span></div>
          {list.map((p) => <PromiseItem key={p.id} p={p} />)}
        </div>
      ))}
      {pending.length > 0 && (
        <details className="routine" style={{ marginTop: 14 }} open={judged.length === 0}>
          <summary>{pending.length} {pending.length === 1 ? "promise" : "promises"} still open (period not over yet)</summary>
          <div className="routine__groups" style={{ paddingTop: 8 }}>{pending.map((p) => <PromiseItem key={p.id} p={p} />)}</div>
        </details>
      )}
      {unver.length > 0 && (
        <details className="routine" style={{ marginTop: 10 }}>
          <summary>{unver.length} couldn't be checked (segment target, or no figure reported)</summary>
          <div className="routine__groups" style={{ paddingTop: 8 }}>{unver.map((p) => <PromiseItem key={p.id} p={p} />)}</div>
        </details>
      )}
      {pr.qualitative.length > 0 && (
        <details className="routine" style={{ marginTop: 10 }}>
          <summary>{pr.qualitative.length} qualitative statements (no number to check)</summary>
          <div className="routine__groups">{pr.qualitative.map((p) => <p key={p.id} className="quote">“{p.quote}” <SourceChip source={p.source} /></p>)}</div>
        </details>
      )}
      <p className="fineprint">Promises come from management's own call transcripts; every quote is checked against the transcript.
        "Delivered" is either computed from reported financials, or the figure management stated on the call that reported
        that period (quote checked, number must appear in it). Verdicts are computed in code, never by the model.
        Segment targets aren't checked against company-wide totals.</p>
    </>
  );
}

function CompanyView({ symbol, tab }: { symbol: string; tab: "snapshot" | "promises" }) {
  const { data: pack, error, loading } = useResearch(symbol);
  const [view, setView] = useState(tab);
  if (loading) return <div className="loading">Loading {symbol}…</div>;
  if (error || !pack) return (
    <div className="empty" style={{ marginTop: 16 }}>
      <b>{symbol} isn't pre-built in this demo.</b> The engine works on any NSE ticker: run
      <code className="mono"> python -m finn.pipeline research {symbol}</code> and it builds the same pack from the company's own filings.
    </div>
  );
  return (
    <>
      <div className="company-head">
        <a href="#/research" className="faint" style={{ fontSize: 13, textDecoration: "none" }}>← All companies</a>
        <h1>{pack.name}</h1>
        <div className="muted" style={{ fontSize: 13 }}>{pack.symbol}{pack.sector ? ` · ${pack.sector}` : ""} · primary sources only</div>
      </div>
      {pack.mock && <div className="banner">Development mock: these numbers and quotes are placeholders.</div>}
      <div className="segmented">
        <button aria-pressed={view === "snapshot"} onClick={() => setView("snapshot")}>Snapshot</button>
        <button aria-pressed={view === "promises"} onClick={() => setView("promises")}>Did they deliver?</button>
      </div>
      {view === "snapshot" ? <SnapshotView pack={pack} /> : <PromisesView pack={pack} />}
    </>
  );
}

export function ResearchPage({ symbol, tab, allSymbols }: { symbol: string | null; tab: "snapshot" | "promises"; allSymbols: string[] }) {
  const [q, setQ] = useState("");
  const idx = useResearchIndex();
  if (symbol) return <CompanyView key={`${symbol}-${tab}`} symbol={symbol} tab={tab} />;
  const built = idx.data ?? [];
  const builtSet = new Set(built.map((b) => b.symbol));
  const term = q.trim().toUpperCase();
  const others = allSymbols.filter((s) => !builtSet.has(s) && (!term || s.includes(term)));
  return (
    <>
      <header className="masthead">
        <div className="masthead__top"><div className="wordmark">Research</div><div className="dateline">annual reports · concalls</div></div>
        <p className="subline">Snapshot and a promises-vs-delivery check, from each company's own filings.</p>
      </header>
      <input className="search" placeholder="Search a ticker, e.g. LT" value={q} onChange={(e) => setQ(e.target.value)}
             onKeyDown={(e) => { if (e.key === "Enter" && term) location.hash = `#/research/${term}`; }} aria-label="Search ticker" />
      <div className="section"><h2>Ready</h2><span className="count">{built.length}</span></div>
      <div className="rows">
        {built.filter((b) => !term || b.symbol.includes(term) || b.name.toUpperCase().includes(term)).map((b) => (
          <a className="row" key={b.symbol} href={`#/research/${b.symbol}`} style={{ textDecoration: "none" }}>
            <span className="row__sym">{b.symbol}</span>
            <span className="row__text">{b.name}<small>{b.mock ? "mock" : "snapshot · promise tracker"}</small></span>
            <span className="row__when">→</span>
          </a>
        ))}
      </div>
      {others.length > 0 && (
        <>
          <div className="section"><h2>Your holdings · not pre-built</h2><span className="count">{others.length}</span></div>
          <div className="rows">
            {others.map((s) => (
              <a className="row" key={s} href={`#/research/${s}`} style={{ textDecoration: "none" }}>
                <span className="row__sym">{s}</span><span className="row__text faint">Build with the research command</span><span className="row__when">→</span>
              </a>
            ))}
          </div>
        </>
      )}
    </>
  );
}
