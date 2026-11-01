"""The whole pull pipeline for one ticker, top to bottom. Works for any NSE symbol screener.in covers.

  screener page -> tables (snapshot, computed in code)
                -> newest transcripts -> guidance statements (LLM, quotes verified) -> verdicts (code)
                -> short commentary (LLM, numbers verified) -> research_<SYMBOL>.json
"""
from __future__ import annotations

import datetime as dt
import json

from .. import config, contracts as c, db
from ..ingest import screener
from . import promises, snapshot

N_TRANSCRIPTS = 6          # last 4 quarters + the year-start calls where last year's full-year guidance was set


def _now() -> str:
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds")


def _call_key(t: screener.Transcript) -> int:
    q = t.quarter or ""
    try:
        return int(q.split("FY")[1]) * 10 + int(q[1])
    except (IndexError, ValueError):
        return 0


def build(symbol: str, verbose: bool = True) -> c.ResearchPack:
    symbol = symbol.upper()
    log_rows: list[c.BuildStep] = []

    def log(step, status, detail=None):
        log_rows.append(c.BuildStep(ts=_now(), step=step, status=status, detail=detail))
        if verbose:
            print(f"  [{status:<7}] {step}: {detail or ''}", flush=True)

    log("screener", "running", "financial tables + document links")
    comp = screener.fetch(symbol)
    log("screener", "done", f"{comp.name} ({comp.basis}); {len(comp.transcripts)} transcripts listed")

    snap = snapshot.build(comp)
    log("snapshot", "done", f"{len(snap.years)} years; missing: {', '.join(snap.missing) or 'nothing'}")

    picks = sorted(comp.transcripts, key=_call_key, reverse=True)[:N_TRANSCRIPTS]
    if picks:
        prom = promises.build(comp, picks, log)
        sc = prom.scorecard
        log("promises", "done", f"{len(prom.items)} measurable ({sc.met} met, {sc.partly} partly, {sc.missed} missed, "
                                f"{sc.pending} pending, {sc.unverifiable} can't check); {len(prom.qualitative)} qualitative")
    else:
        prom = None
        log("promises", "skipped", "no transcripts listed")

    sector = None
    with db.session() as con:
        r = con.execute("SELECT sector FROM companies WHERE symbol=?", (symbol,)).fetchone()
        sector = r["sector"] if r else None
    docs = [c.DocumentRef(id=f"t{i}", kind="transcript", period=t.quarter or t.call_month, title=f"{t.quarter or t.call_month} earnings call transcript",
                          url=t.url) for i, t in enumerate(picks)]
    pack = c.ResearchPack(symbol=symbol, name=comp.name, sector=sector, status="ready", built_at=_now(), mock=False,
                          snapshot=snap, promises=prom, documents=docs, build_log=log_rows)
    write(pack)
    return pack


def write(pack: c.ResearchPack) -> None:
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (config.EXPORT_DIR / f"research_{pack.symbol}.json").write_text(pack.model_dump_json(indent=1), encoding="utf-8")
    idx_path = config.EXPORT_DIR / "research_index.json"
    try:
        idx = [e for e in json.loads(idx_path.read_text(encoding="utf-8")) if e["symbol"] != pack.symbol]
    except (FileNotFoundError, ValueError):
        idx = []
    idx.append({"symbol": pack.symbol, "name": pack.name, "built_at": pack.built_at, "mock": pack.mock})
    idx.sort(key=lambda e: e["symbol"])
    idx_path.write_text(json.dumps(idx, indent=1), encoding="utf-8")
    with db.session() as con:
        con.execute("INSERT OR REPLACE INTO research_jobs VALUES (?,?,?,?,?,?)",
                    (pack.symbol, pack.status, "done", None, pack.built_at, None))
