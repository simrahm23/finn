"""Push enrichment: rules -> LLM for leftovers -> materiality -> summaries (validated).
Order matters for cost: the LLM only sees what rules could not decide, and only important items get summaries."""
from __future__ import annotations

import json
import re

from .. import config, db
from ..ingest import documents
from ..llm import client as llm
from . import classify_rules, materiality

CATEGORIES = list(materiality.LABEL)
SUBS = ["top_role", "other_role", "transcript", "upgrade", "downgrade", "reaffirm", "none"]
BATCH = 25

CLASSIFY_SCHEMA = {"type": "object", "properties": {"results": {"type": "array", "items": {
    "type": "object", "properties": {
        "i": {"type": "integer"}, "category": {"type": "string", "enum": CATEGORIES},
        "confidence": {"type": "number"}, "sub": {"type": "string", "enum": SUBS}, "summary": {"type": "string"}},
    "required": ["i", "category", "confidence", "sub", "summary"]}}}, "required": ["results"]}
SUMMARY_SCHEMA = {"type": "object", "properties": {"results": {"type": "array", "items": {
    "type": "object", "properties": {"i": {"type": "integer"}, "summary": {"type": "string"}},
    "required": ["i", "summary"]}}}, "required": ["results"]}

NUM = re.compile(r"\d[\d,]*\.?\d*")


def numbers_grounded(summary: str, source: str) -> bool:
    """Every number in the summary must appear in the source text (commas ignored)."""
    src = source.replace(",", "")
    return all(n.replace(",", "").rstrip(".") in src for n in NUM.findall(summary))


def _snip(url: str, k: int, n: int, step: str) -> str:
    print(f"\r  {step}: reading filing PDFs {k + 1}/{n}   ", end="", flush=True)
    text = documents.snippet(url)
    if k + 1 == n:
        print()
    return text


def _batches(xs, n=BATCH):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def run_rules(con) -> int:
    """Rules first, always: a rule match overrides any earlier model label (keeping its summary). A filing a rule
    used to match but no longer does is cleared, so the model classifies it on this run."""
    rows = con.execute("SELECT a.id, a.exchange_category, a.headline, e.method FROM announcements a "
                       "LEFT JOIN ann_enrichment e ON e.ann_id=a.id").fetchall()
    n = 0
    for r in rows:
        rule = classify_rules.classify(r["exchange_category"], r["headline"])
        if rule:
            n += 1
            con.execute("INSERT INTO ann_enrichment(ann_id, category, confidence, method, reasons_json, prompt_version) "
                        "VALUES (?,?,?,?,?,?) ON CONFLICT(ann_id) DO UPDATE SET category=excluded.category, "
                        "confidence=excluded.confidence, method='rule', reasons_json=excluded.reasons_json, "
                        "prompt_version=excluded.prompt_version",
                        (r["id"], rule.category, rule.confidence, "rule", json.dumps({"sub": rule.sub}), "rules-v2"))
        elif r["method"] == "rule":
            con.execute("DELETE FROM ann_enrichment WHERE ann_id=?", (r["id"],))
    return n


def run_llm_classify(con) -> dict:
    rows = con.execute("SELECT a.id, a.exchange_category, a.headline, a.attachment_url FROM announcements a "
                       "LEFT JOIN ann_enrichment e ON e.ann_id=a.id WHERE e.ann_id IS NULL").fetchall()
    stats = {"items": len(rows), "classified": 0, "summaries_dropped": 0, "errors": []}
    for b, batch in enumerate(_batches(list(rows)), 1):
        con.commit()                     # release the write lock before the LLM client writes its cache
        items = [{"i": k, "exchange_category": r["exchange_category"], "headline": r["headline"][:400],
                  "text": _snip(r["attachment_url"], k, len(batch), "classify")} for k, r in enumerate(batch)]
        print(f"  classify: asking {config.MODEL_LITE} about {len(items)} filings (batch {b})...", flush=True)
        try:
            out = llm.generate_json("classify", {"items": items}, CLASSIFY_SCHEMA, purpose="classify")
        except llm.LlmError as e:
            stats["errors"].append(str(e))
            continue
        for res in out.get("results", []):
            k = res.get("i")
            if not isinstance(k, int) or not 0 <= k < len(batch) or res.get("category") not in CATEGORIES:
                continue
            r, src = batch[k], items[k]["headline"] + " " + items[k]["text"]
            summary = (res.get("summary") or "").strip()
            if summary and not numbers_grounded(summary, src):
                summary, stats["summaries_dropped"] = "", stats["summaries_dropped"] + 1
            sub = None if res.get("sub") == "none" else res.get("sub")
            db.upsert(con, "ann_enrichment", {"ann_id": r["id"], "category": res["category"],
                                              "confidence": float(res.get("confidence") or 0), "method": "llm",
                                              "reasons_json": json.dumps({"sub": sub}), "summary": summary or None,
                                              "prompt_version": "classify-v1"}, ["ann_id"])
            stats["classified"] += 1
    return stats


def _price_index(con) -> dict:
    from .price_volume import daily_returns_pct, volume_ratios
    idx = {}
    for (s,) in con.execute("SELECT DISTINCT symbol FROM prices_daily").fetchall():
        rows = con.execute("SELECT date, close, volume FROM prices_daily WHERE symbol=? ORDER BY date", (s,)).fetchall()
        dates = [r["date"] for r in rows]
        rets = daily_returns_pct([r["close"] for r in rows])
        vrs = volume_ratios([r["volume"] or 0 for r in rows])
        idx[s] = (dates, dict(zip(dates, zip(rets, vrs))))
    return idx


def run_materiality(con) -> int:
    """Score every filing. Two passes: (1) score without market boost; (2) give the reaction-session price/volume
    boost to the single most material filing per stock-session, and cap 2nd+ filings on the same results/person."""
    from .. import config
    weights = {r["symbol"]: r["weight"] or 0 for r in con.execute("SELECT symbol, weight FROM companies")}
    prices = _price_index(con)
    rows = con.execute("SELECT a.id, a.symbol, a.filed_at, a.headline, e.category, e.reasons_json, e.summary, "
                       "e.card_json FROM announcements a JOIN ann_enrichment e ON e.ann_id=a.id").fetchall()
    scored = []
    for r in rows:
        sub = json.loads(r["reasons_json"] or "{}").get("sub")
        card = json.loads(r["card_json"]) if r["card_json"] else None
        ret = vr = sess = None
        if r["symbol"] in prices:
            dates, mk = prices[r["symbol"]]
            sess = materiality.reaction_session(r["filed_at"], dates)
            if sess:
                ret, vr = mk[sess]
        text = f"{r['headline']} {r['summary'] or ''}"
        args = (r["category"], sub, text, weights.get(r["symbol"], 0), ret, vr)
        s0 = materiality.score(*args, card=card, market_boost=False)
        scored.append({"r": r, "sub": sub, "card": card, "sess": sess, "ret": ret, "args": args, "res": s0})

    # (2a) market boost to the top filing per (symbol, session)
    best: dict = {}
    for x in scored:
        if x["sess"] and x["res"][1] != "routine":
            k = (x["r"]["symbol"], x["sess"])
            rank = (x["r"]["category"] == "results", x["card"] is not None, x["res"][0])  # results explain moves first
            if k not in best or rank > best[k][0]:
                best[k] = (rank, x)
    for _, x in best.values():
        x["res"] = materiality.score(*x["args"], card=x["card"], market_boost=True)

    # (2b) related filings: one primary per symbol for results, one per person for management changes
    cap = float(config.rules()["related_filing_cap"])
    groups: dict = {}
    for x in scored:
        r = x["r"]
        if r["category"] == "results":
            key = ("results", r["symbol"])
        elif r["category"] == "fund_raise" and x["sub"] != "debt":
            key = ("fund_raise", r["symbol"])          # one equity raise = one card; the rest are related filings
        elif r["category"] == "management_change" and x["card"]:
            key = ("mgmt", r["symbol"], x["card"].get("person", "").lower())
        else:
            continue
        groups.setdefault(key, []).append(x)
    for members in groups.values():
        members.sort(key=lambda x: (x["card"] is not None, x["res"][0]), reverse=True)
        for x in members[1:]:
            s, _, chips = x["res"]
            if s > cap:
                x["res"] = materiality.finish(cap, chips[:1] + ["Related filing"])

    for x in scored:
        s, tier, chips = x["res"]
        con.execute("UPDATE ann_enrichment SET materiality=?, tier=?, reasons_json=? WHERE ann_id=?",
                    (s, tier, json.dumps({"sub": x["sub"], "chips": chips, "reaction_pct": x["ret"]}), x["r"]["id"]))
    return len(scored)


def run_summaries(con) -> dict:
    rows = con.execute("SELECT a.id, a.headline, a.attachment_url, e.category FROM announcements a JOIN ann_enrichment e "
                       "ON e.ann_id=a.id WHERE e.tier IN ('needs_you','worth_knowing') AND e.summary IS NULL").fetchall()
    stats = {"items": len(rows), "written": 0, "dropped": 0, "errors": []}
    for b, batch in enumerate(_batches(list(rows)), 1):
        con.commit()
        items = [{"i": k, "category": r["category"], "headline": r["headline"][:400],
                  "text": _snip(r["attachment_url"], k, len(batch), "summaries")} for k, r in enumerate(batch)]
        print(f"  summaries: asking {config.MODEL_LITE} about {len(items)} filings (batch {b})...", flush=True)
        try:
            out = llm.generate_json("summarise", {"items": items}, SUMMARY_SCHEMA, purpose="summarise")
        except llm.LlmError as e:
            stats["errors"].append(str(e))
            continue
        for res in out.get("results", []):
            k = res.get("i")
            if not isinstance(k, int) or not 0 <= k < len(batch):
                continue
            summary = (res.get("summary") or "").strip()
            src = items[k]["headline"] + " " + items[k]["text"]
            if not summary:
                continue
            if not numbers_grounded(summary, src):
                stats["dropped"] += 1
                continue
            con.execute("UPDATE ann_enrichment SET summary=? WHERE ann_id=?", (summary, batch[k]["id"]))
            stats["written"] += 1
    return stats
