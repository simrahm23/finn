"""Promise Tracker: management guidance from transcripts vs what the reported numbers show.
LLM extracts statements (with verbatim quotes we verify); code decides every verdict."""
from __future__ import annotations

import re
from typing import Optional

from .. import config, contracts as c
from ..extract import validate as v
from ..ingest import documents
from ..ingest.screener import Company, Transcript
from ..llm import client as llm
from . import snapshot

METRICS = ["revenue_growth", "ebitda_margin", "pat_growth", "order_inflow_growth", "capex", "volume_growth", "other"]
CHECKABLE = {"revenue_growth", "ebitda_margin", "pat_growth"}     # computable from reported tables
PARTLY_TOLERANCE = {"ebitda_margin": 1.0}                          # percentage points; growth rates get 3.0

SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "metric": {"type": "string", "enum": METRICS}, "target_period": {"type": "string"},
    "target_low": {"type": "number", "nullable": True}, "target_high": {"type": "number", "nullable": True},
    "unit": {"type": "string"}, "target_text": {"type": "string"}, "quote": {"type": "string"},
    "page": {"type": "integer"}, "measurable": {"type": "boolean"},
    "scope": {"type": "string", "enum": ["company", "segment"]}},
    "required": ["metric", "target_period", "unit", "target_text", "quote", "page", "measurable", "scope"]}}},
    "required": ["items"]}

REPORTABLE = {"revenue_growth", "ebitda_margin", "pat_growth", "order_inflow_growth", "volume_growth"}
ACTUALS_SCHEMA = {"type": "object", "properties": {"results": {"type": "array", "items": {"type": "object", "properties": {
    "id": {"type": "string"}, "found": {"type": "boolean"}, "value": {"type": "number"}, "quote": {"type": "string"},
    "page": {"type": "integer"}}, "required": ["id", "found", "value", "quote", "page"]}}}, "required": ["results"]}

COMMENTARY_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"},
                                                      "cites": {"type": "array", "items": {"type": "string"}}},
                     "required": ["text", "cites"]}


SEGMENT_WORDS = re.compile(r"\b(core|p&m|ppm|portfolio|segment|division|business|vertical|subsidiar|services|"
                           r"projects|manufacturing|hi-?tech|ipo|nbfc|financial services|it&ts|realty|ebit)\b", re.I)


def is_segment(scope: Optional[str], text: str) -> bool:
    """A segment promise can't be checked against company totals. The model's label OR our keyword rule."""
    return scope == "segment" or SEGMENT_WORDS.search(text or "") is not None


def period_ended(period: str, reported: set[str]) -> Optional[bool]:
    """True/False when we can tell from what has been reported; None for an unrecognised period."""
    period = (period or "").strip()
    if re.match(r"^(FY\d{2}|Q[1-4] FY\d{2})$", period):
        return period in reported
    m = re.match(r"^H([12]) (FY\d{2})$", period)
    if m:
        return (f"Q2 {m.group(2)}" in reported) if m.group(1) == "1" else (m.group(2) in reported or f"Q4 {m.group(2)}" in reported)
    return None


def verdict(metric: str, period: str, lo: Optional[float], hi: Optional[float], company: Company,
            reported_periods: set[str], segment: bool = False) -> tuple[str, Optional[float]]:
    """pending (period not over) -> unverifiable (over, but no trustworthy figure) -> met / partly / missed.
    Higher is better for every checked metric. Segment targets are never checked against company totals."""
    ended = period_ended(period, reported_periods)
    if ended is False:
        return "pending", None
    if ended is None or segment or metric not in CHECKABLE or lo is None or period.startswith("H"):
        return "unverifiable", None
    act = snapshot.actual(company, metric, period)
    if act is None:
        return "unverifiable", None
    return compare(metric, lo, act), act


def compare(metric: str, lo: float, act: float) -> str:
    if act >= lo:
        return "met"
    return "partly" if act >= lo - PARTLY_TOLERANCE.get(metric, 3.0) else "missed"


def reporting_quarter(period: str) -> Optional[str]:
    """Which call reports on a period: FY26 -> the Q4 FY26 call; Q2 FY27 -> the Q2 FY27 call."""
    if re.match(r"^FY\d{2}$", period):
        return f"Q4 {period}"
    if re.match(r"^Q[1-4] FY\d{2}$", period):
        return period
    return None


def number_in(value: float, quote: str) -> bool:
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.?\d*", quote)]
    return any(abs(n - value) < 0.051 for n in nums)


def fill_reported_actuals(items: list, transcripts: list, pages_by_quarter: dict, log) -> int:
    """For ended-period promises the tables can't check, look for management's own stated actual in the call that
    reported on that period. Quote must be on the page and contain the number; the verdict is computed here."""
    todo: dict[str, list] = {}
    for p in items:
        rq = reporting_quarter(p.target_period)
        if p.verdict == "unverifiable" and p.target_low is not None and p.metric.split(" ")[0] in REPORTABLE \
                and rq in pages_by_quarter:
            todo.setdefault(rq, []).append(p)
    filled = 0
    for rq, ps in todo.items():
        pages = pages_by_quarter[rq]
        url = next(t.url for t in transcripts if t.quarter == rq)
        payload = {"promises": [{"id": p.id, "metric": p.metric, "period": p.target_period, "promise": p.target_text}
                                for p in ps], "transcript": _numbered_text(pages)[:150_000]}
        try:
            out = llm.generate_json("actuals", payload, ACTUALS_SCHEMA, purpose="actuals")
        except llm.LlmError as e:
            log("actuals", "failed", f"{rq}: {e}")
            continue
        by_id = {p.id: p for p in ps}
        for r in out.get("results", []):
            p, q, pg = by_id.get(r.get("id")), (r.get("quote") or "").strip(), r.get("page") or 0
            if not p or not r.get("found") or not q or not number_in(r["value"], q):
                continue
            page_text = pages[pg - 1] if 1 <= pg <= len(pages) else ""
            if not v.fuzzy_in(q, page_text, 88):
                hit = next((i + 1 for i, t in enumerate(pages) if v.fuzzy_in(q, t, 88)), None)
                if hit is None:
                    continue
                pg = hit
            p.actual, p.actual_basis = float(r["value"]), "reported"
            p.actual_source = c.Source(label=f"Reported, {rq} call p.{pg}", kind="transcript", url=url, page=pg)
            p.verdict = compare(p.metric.split(" ")[0], p.target_low, p.actual)
            filled += 1
        log("actuals", "done", f"{rq} call: {sum(1 for p in ps if p.actual_basis == 'reported')}/{len(ps)} actuals found")
    return filled


def _q_order(q: str) -> int:
    m = re.match(r"Q(\d) FY(\d+)", q or "")
    return int(m.group(2)) * 10 + int(m.group(1)) if m else 0


def merge_repeats(items: list) -> list:
    """The same target restated on several calls is ONE promise (kept from the call where it was first made),
    with the later calls listed in `repeated_in`. Counting it once per call would inflate the scorecard."""
    groups: dict = {}
    for p in items:
        key = (p.metric, p.target_period, p.target_low, p.target_high)
        groups.setdefault(key, []).append(p)
    out = []
    for ps in groups.values():
        ps.sort(key=lambda p: _q_order(p.said_in))
        first = ps[0]
        first.repeated_in = [p.said_in for p in ps[1:] if p.said_in != first.said_in]
        best = next((p for p in ps if p.actual is not None), None)      # any copy that found the actual
        if best and first.actual is None:
            first.actual, first.actual_basis, first.actual_source, first.verdict = \
                best.actual, best.actual_basis, best.actual_source, best.verdict
        out.append(first)
    return out


def _numbered_text(pages: list[str]) -> str:
    return "\n".join(f"[[p{i + 1}]]\n{' '.join(t.split())}" for i, t in enumerate(pages))


def extract_from_transcript(t: Transcript, symbol: str) -> tuple[list[dict], list[str], str]:
    """Returns (validated statements, page texts, note)."""
    path = documents.fetch_pdf(t.url, folder=symbol)
    if not path:
        return [], [], "transcript download failed"
    pages = documents.page_texts(path)
    if sum(len(p) for p in pages) < 2000:
        return [], pages, "transcript looks scanned"
    raw = llm.generate_json("guidance", {"call": t.call_month, "quarter": t.quarter,
                                         "transcript": _numbered_text(pages)[:150_000]},
                            SCHEMA, purpose="guidance")
    kept = []
    for it in raw.get("items", []):
        q = (it.get("quote") or "").strip()
        pg = it.get("page") or 0
        page_text = pages[pg - 1] if 1 <= pg <= len(pages) else ""
        if not q:
            continue
        if not v.fuzzy_in(q, page_text, 88):           # wrong page? search the whole transcript
            hit = next((i + 1 for i, p in enumerate(pages) if v.fuzzy_in(q, p, 88)), None)
            if hit is None:
                continue                                 # quote not in the transcript: drop it
            it["page"] = hit
        kept.append(it)
    return kept, pages, f"{len(kept)}/{len(raw.get('items', []))} statements kept"


def build(company: Company, transcripts: list[Transcript], log) -> c.Promises:
    reported = set(company.columns.get("profit-loss", [])) | set(company.columns.get("quarters", []))
    items, qual = [], []
    pages_by_quarter: dict[str, list[str]] = {}
    n = 0
    for t in transcripts:
        log("guidance", "running", f"{t.quarter or t.call_month} transcript")
        try:
            stmts, pages, note = extract_from_transcript(t, company.symbol)
            if t.quarter and pages:
                pages_by_quarter[t.quarter] = pages
        except llm.LlmError as e:
            log("guidance", "failed", f"{t.quarter}: {e}")
            continue
        log("guidance", "done", f"{t.quarter or t.call_month}: {note}")
        for s in stmts:
            n += 1
            period = (s.get("target_period") or "").strip()
            lo, hi = s.get("target_low"), s.get("target_high")
            seg = is_segment(s.get("scope"), s.get("target_text", ""))   # short text only: quotes mention "business" freely
            ver, act = verdict(s["metric"], period, lo, hi, company, reported, segment=seg)
            p = c.Promise(
                id=f"p{n}", said_in=t.quarter or t.call_month or "Earlier call", target_period=period or "unspecified",
                metric=s["metric"] + (" (segment)" if seg else ""), target_text=s.get("target_text") or s["quote"][:60], target_low=lo, target_high=hi,
                unit=s.get("unit") or "%", actual=act, actual_basis="tables" if act is not None else None,
                verdict=ver, quote=s["quote"],
                source=c.Source(label=f"{t.quarter or t.call_month} transcript p.{s['page']}", kind="transcript",
                                url=t.url, page=s["page"]),
            )
            (items if s.get("measurable") and lo is not None else qual).append(p)

    fill_reported_actuals(items, transcripts, pages_by_quarter, log)
    before = len(items)
    items = merge_repeats(items)
    if before != len(items):
        log("promises", "done", f"merged {before - len(items)} restated promises")
    sc = c.Scorecard()
    for p in items:
        setattr(sc, p.verdict, getattr(sc, p.verdict) + 1)
    commentary = _commentary(company.name, items) if any(p.verdict in ("met", "partly", "missed") for p in items) else None
    return c.Promises(scorecard=sc, items=items, qualitative=qual[:15], commentary=commentary)


def _commentary(name: str, items: list[c.Promise]) -> Optional[c.Commentary]:
    rows = [{"id": p.id, "said_in": p.said_in, "target_period": p.target_period, "promise": p.target_text,
             "target_low": p.target_low, "target_high": p.target_high, "actual": p.actual, "verdict": p.verdict}
            for p in items if p.verdict != "unverifiable"]
    try:
        out = llm.generate_json("commentary", {"company": name, "promises": rows}, COMMENTARY_SCHEMA,
                                model=config.MODEL_FLASH, purpose="commentary")
    except llm.LlmError:
        return None
    ids = {r["id"] for r in rows}
    cites = [x for x in out.get("cites", []) if x in ids]
    text = (out.get("text") or "").strip()
    vals = [float(r[k]) for r in rows for k in ("target_low", "target_high", "actual") if r[k] is not None]
    nums = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
    if not text or not cites or not all(any(abs(n - v) < 0.051 for v in vals) for n in nums):
        return None                      # a number the table doesn't contain: show the table alone
    return c.Commentary(text=text, cites=cites)
