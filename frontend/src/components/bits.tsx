// Small shared pieces: sparkline, reason chips, source chip.
import type { Source } from "../lib/types";
import { pdfLink } from "../lib/format";

export function Sparkline({ values, width = 140, height = 28, markIndex, stroke }: {
  values: (number | null)[]; width?: number; height?: number; markIndex?: number | null; stroke?: string;
}) {
  const pts = values.map((v, i) => [i, v] as const).filter((p): p is readonly [number, number] => p[1] !== null);
  if (pts.length < 2) return <svg width={width} height={height} aria-hidden="true" />;
  const ys = pts.map((p) => p[1]);
  const lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
  const x = (i: number) => (i / (values.length - 1)) * (width - 2) + 1;
  const y = (v: number) => height - 2 - ((v - lo) / span) * (height - 4);
  const d = pts.map(([i, v], k) => `${k ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");
  const last = pts[pts.length - 1];
  const color = stroke ?? (last[1] >= pts[0][1] ? "var(--up)" : "var(--down)");
  const mark = markIndex !== undefined && markIndex !== null ? pts.find((p) => p[0] === markIndex) : undefined;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      {mark && <line x1={x(mark[0])} x2={x(mark[0])} y1="0" y2={height} stroke="var(--accent)" strokeDasharray="2 2" />}
      <circle cx={x(last[0])} cy={y(last[1])} r="2" fill={color} />
    </svg>
  );
}

function chipClass(r: string): string {
  if (/^Move \+|^PAT \+/.test(r)) return "reason reason--up";
  if (/^Move [-−]|^PAT -/.test(r)) return "reason reason--down";
  if (/^Vol|Top exit|Downgrade|Top hire/.test(r)) return "reason reason--hot";
  return "reason";
}

export function Reasons({ reasons }: { reasons: string[] }) {
  if (!reasons.length) return null;
  return <div className="reasons">{reasons.map((r) => <span key={r} className={chipClass(r)}>{r}</span>)}</div>;
}

export function SourceChip({ source }: { source: Source }) {
  return (
    <a className="source" href={pdfLink(source.url, source.page)} target="_blank" rel="noreferrer"
       onClick={(e) => e.stopPropagation()}>
      {source.label}
    </a>
  );
}
