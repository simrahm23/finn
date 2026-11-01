"""Results card: Revenue, EBITDA, PBT, PAT for this quarter vs previous quarter (QoQ) vs a year ago (YoY).
The LLM only COPIES printed values and column mapping; code converts units, computes EBITDA and growth,
and refuses to show numbers that are not on the page or that break PAT = PBT - tax."""
from __future__ import annotations

import re
from typing import Optional

from .. import contracts as c
from ..ingest import documents
from ..llm import client as llm
from . import validate as v

LINES = ["revenue", "other_income", "finance_costs", "depreciation", "pbt", "tax", "pat"]
_cell = {"type": "object", "properties": {k: {"type": "string"} for k in ("cur", "prev", "yago")},
         "required": ["cur", "prev", "yago"]}
SCHEMA = {"type": "object", "properties": {
    "found": {"type": "boolean"},
    "basis": {"type": "string", "enum": ["consolidated", "standalone"]},
    "unit": {"type": "string", "enum": list(v.UNIT_TO_CRORE)},
    "current_period_end": {"type": "string"},
    "lines": {"type": "object", "properties": {k: _cell for k in LINES}, "required": LINES}},
    "required": ["found", "basis", "unit", "current_period_end", "lines"]}


def _sq(t: str) -> str:
    return re.sub(r"[^a-z]", "", t.lower())


def pick_page(texts: list[str]) -> Optional[int]:
    """Best page for the quarterly table. Matching ignores spaces/punctuation, so 'Profit / (Loss) before Tax'
    and words split across lines still match. Prefers consolidated, quarter columns, revenue line."""
    best, best_score = None, 0
    for i, t in enumerate(texts):
        q = _sq(t)
        if "beforetax" not in q and "beforeexceptionalitemsandtax" not in q:
            continue
        s = 1
        s += 2 if any(k in q for k in ("revenuefromoperations", "interestearned", "totalincome", "incomefromoperations",
                                       "totalrevenue")) else 0
        s += 2 if "consolidated" in q else 0
        s += 1 if any(k in q for k in ("quarterended", "threemonthsended", "quarterending")) else 0
        s += 1 if "netprofit" in q or "profitfortheperiod" in q or "profitafter" in q else 0
        if s > best_score:
            best, best_score = i, s
    return best if best_score >= 3 else None


def text_stats(texts: list[str]) -> dict:
    return {"pages": len(texts), "text_chars": sum(len(t) for t in texts),
            "pages_with_before_tax": [i + 1 for i, t in enumerate(texts) if "beforetax" in _sq(t)]}


def build_card(raw: dict, page_text: str, url: str, page_no: int, lender: bool) -> c.ResultsCard | None:
    if not raw.get("found"):
        return None
    lines = raw["lines"]
    printed = [lines[k][col] for k in LINES for col in ("cur", "prev", "yago") if lines.get(k)]
    verbatim = all(v.appears_verbatim(p, page_text) for p in printed if p)
    k = v.UNIT_TO_CRORE.get(raw.get("unit"), None)
    if k is None:
        return None
    val = {key: {col: (None if v.parse_number(lines[key][col]) is None else round(v.parse_number(lines[key][col]) * k, 2))
                 for col in ("cur", "prev", "yago")} for key in LINES}

    def ebitda(col):
        p, f, d, o = (val["pbt"][col], val["finance_costs"][col], val["depreciation"][col], val["other_income"][col])
        return None if None in (p, f, d) else round(p + f + d - (o or 0), 2)

    identities = v.close(val["pat"]["cur"], None if val["pbt"]["cur"] is None or val["tax"]["cur"] is None
                         else val["pbt"]["cur"] - val["tax"]["cur"])
    rows = []
    for name, key in (("Revenue", "revenue"), ("EBITDA", None), ("PBT", "pbt"), ("PAT", "pat")):
        if name == "EBITDA" and lender:
            rows.append(c.ResultsMetric(name="EBITDA", applicable=False))
            continue
        cur, prev, yago = (ebitda("cur"), ebitda("prev"), ebitda("yago")) if key is None else \
            (val[key]["cur"], val[key]["prev"], val[key]["yago"])
        rows.append(c.ResultsMetric(name=name, current=cur, prev_q=prev, year_ago=yago,
                                    qoq_pct=v.pct_change(cur, prev), yoy_pct=v.pct_change(cur, yago)))
    if rows[0].current is None:
        return None
    period = v.quarter_label(raw.get("current_period_end", "")) or raw.get("current_period_end") or "Latest quarter"
    return c.ResultsCard(
        period=period, basis=raw.get("basis", "standalone"), metrics=rows,
        checks=c.ResultsChecks(verbatim=verbatim, identities=identities, cross_check=None),
        verified=verbatim and identities,
        source=c.Source(label=f"Results filing p.{page_no}", kind="filing", url=url, page=page_no),
    )


def extract(url: str, lender: bool = False) -> tuple[c.ResultsCard | None, str]:
    """Returns (card or None, reason). Reason is logged so we can see why a card was not made."""
    path = documents.fetch_pdf(url)
    if not path:
        return None, "pdf unavailable"
    texts = documents.page_texts(path, 60)
    i = pick_page(texts)
    if i is None:
        st = text_stats(texts)
        why = "scanned PDF (no text)" if st["text_chars"] < 300 * max(1, st["pages"]) // 3 else \
            f"no results table ({st['pages']} pages, 'before tax' on {st['pages_with_before_tax'] or 'none'})"
        return None, why
    page_text = texts[i] + ("\n" + texts[i + 1] if i + 1 < len(texts) and "profit" not in texts[i].lower()[-800:] else "")
    raw = llm.generate_json("results", {"page_text": re.sub(r"[ \t]+", " ", page_text)[:9000]}, SCHEMA,
                            purpose="results")
    card = build_card(raw, page_text, url, i + 1, lender)
    return card, "ok" if card else "model found no quarterly table"
