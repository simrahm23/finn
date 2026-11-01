"""Morning note: 3 sentences over the week's "Needs you" cards. Flash writes; code checks every number.
If anything doesn't check out, there is no note (the Brief stands on its own)."""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import Optional

from .. import contracts as c
from ..llm import client as llm

SCHEMA = {"type": "object", "properties": {"text": {"type": "string"},
                                           "item_ids": {"type": "array", "items": {"type": "string"}}},
          "required": ["text", "item_ids"]}
NUM = re.compile(r"[+-−]?\d[\d,]*\.?\d*")
LABELS = re.compile(r"\b(Q[1-4]|H[12]|9M)\s*FY\s?'?\d{2,4}\b|\bFY\s?'?\d{2,4}\b|\b(19|20)\d{2}\b", re.I)
LAST_REASON = ""


def _facts(i: c.BriefItem) -> dict:
    d = {"id": i.id, "company": i.company, "symbol": i.symbol, "category": i.category, "headline": i.headline[:200],
         "summary": i.summary or "", "chips": i.reasons}
    if i.card and i.card.kind == "results" and i.card.verified:
        d["period"] = i.card.period
        d["results"] = {m.name: {"current_cr": m.current, "yoy_pct": m.yoy_pct, "qoq_pct": m.qoq_pct}
                        for m in i.card.metrics if m.applicable}
    if i.card and i.card.kind == "management":
        d["person"] = {"name": i.card.person, "role": i.card.role, "direction": i.card.direction}
    return d


def numbers_ok(text: str, source: str) -> bool:
    """Every number in the note appears in the source facts (sign, commas and trailing zeros ignored)."""
    def norm(x: str) -> str:
        x = x.replace(",", "").replace("−", "-").lstrip("+-")
        return x.rstrip("0").rstrip(".") if "." in x else x
    text = LABELS.sub(" ", text)            # period labels and years are not numerical claims
    src = {norm(n) for n in NUM.findall(source)}
    return all(norm(n) in src for n in NUM.findall(text) if norm(n))


def generate(items: list[c.BriefItem], now: Optional[str] = None, days: int = 7) -> Optional[c.MorningNote]:
    global LAST_REASON
    ref = dt.datetime.fromisoformat(now) if now else dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    start = ref - dt.timedelta(days=days)
    top = [i for i in items if i.tier == "needs_you" and dt.datetime.fromisoformat(i.filed_at) >= start]
    top = sorted(top, key=lambda i: -i.materiality)[:8]
    if len(top) < 2:
        LAST_REASON = f"only {len(top)} 'needs you' items in the last {days} days"
        return None
    facts = [_facts(i) for i in top]
    try:
        out = llm.generate_json_with_fallback("morning", {"items": facts}, SCHEMA, purpose="morning")
    except llm.LlmError as e:
        LAST_REASON = f"model call failed: {e}"
        return None
    text = " ".join((out.get("text") or "").split())
    ids = [x for x in out.get("item_ids", []) if x in {i.id for i in top}]
    src = json.dumps(facts, ensure_ascii=False)
    if not text or not ids or len(text.split()) > 80 or not numbers_ok(text, src):
        bad = [n for n in NUM.findall(LABELS.sub(" ", text)) if not numbers_ok(n, src)]
        LAST_REASON = f"rejected: numbers not in the cards {bad}" if bad else "rejected: empty, too long, or no item ids"
        print(f"  (rejected note was: {text})")
        return None
    LAST_REASON = "ok"
    return c.MorningNote(text=text, item_ids=ids, window=f"last {days} days")
