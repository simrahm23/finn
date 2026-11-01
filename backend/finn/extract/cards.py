"""Attach purpose-built cards to the filings that deserve them. Skips anything already carded."""
from __future__ import annotations

import json

from . import management, results


def run(con, max_results_tries: int = 3) -> dict:
    stats = {"results": 0, "management": 0, "skipped": [], "errors": []}
    lender = {r["symbol"]: bool(r["lender"]) for r in con.execute("SELECT symbol, lender FROM companies")}

    # Results: newest results filing per symbol that actually contains the table.
    rows = con.execute("SELECT a.id, a.symbol, a.attachment_url, e.card_json FROM announcements a JOIN ann_enrichment e "
                       "ON e.ann_id=a.id WHERE e.category='results' AND e.tier!='routine' ORDER BY a.filed_at DESC").fetchall()
    done, tries = {r["symbol"] for r in rows if r["card_json"]}, {}
    for r in rows:
        s = r["symbol"]
        if s in done or tries.get(s, 0) >= max_results_tries:
            continue
        tries[s] = tries.get(s, 0) + 1
        con.commit()
        try:
            card, why = results.extract(r["attachment_url"], lender.get(s, False))
        except Exception as e:  # noqa: BLE001  one bad PDF or LLM error must not stop the run
            stats["errors"].append(f"{s} results: {type(e).__name__}: {e}")
            continue
        if card:
            con.execute("UPDATE ann_enrichment SET card_json=? WHERE ann_id=?", (card.model_dump_json(), r["id"]))
            done.add(s)
            stats["results"] += 1
        else:
            stats["skipped"].append(f"{s} results: {why}")

    rows = con.execute("SELECT a.id, a.symbol, a.attachment_url FROM announcements a JOIN ann_enrichment e ON "
                       "e.ann_id=a.id WHERE e.category='management_change' AND e.tier!='routine' AND e.card_json IS NULL"
                       ).fetchall()
    for r in rows:
        con.commit()
        try:
            card, why = management.extract(r["attachment_url"])
        except Exception as e:  # noqa: BLE001
            stats["errors"].append(f"{r['symbol']} management: {type(e).__name__}: {e}")
            continue
        if card:
            con.execute("UPDATE ann_enrichment SET card_json=? WHERE ann_id=?", (card.model_dump_json(), r["id"]))
            stats["management"] += 1
        else:
            stats["skipped"].append(f"{r['symbol']} management: {why}")
    return stats


def summary_line(card_json: str | None) -> str:
    if not card_json:
        return ""
    d = json.loads(card_json)
    if d.get("kind") == "results":
        m = {x["name"]: x for x in d["metrics"]}
        rev, pat = m["Revenue"], m["PAT"]
        tick = "verified" if d["verified"] else "NOT verified"
        return (f"{d['period']} {d['basis']}: Revenue {rev['current']:,} cr (YoY {rev['yoy_pct']}%), "
                f"PAT {pat['current']} cr (YoY {pat['yoy_pct']}%) [{tick}]")
    return f"{d['direction']}: {d['person']}, {d['role']}" + (" (profile quoted)" if d.get("profile") else "")
