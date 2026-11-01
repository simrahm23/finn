"""FINN command line. Run from backend/:  python -m finn.pipeline <command>

  init-db            create tables + load the portfolio into `companies`
  mocks              write clearly-labelled mock JSON into frontend/public/data (for UI work)
  validate           check every JSON file in frontend/public/data against the contracts
  prices             ingest EOD prices (yfinance, bhavcopy fallback) + write prices.json   (A1)
  push [--days N]    ingest NSE announcements + rule classification (A2-A3; LLM, scores, cards next)
  gold-template      write 60 filings to tests/gold/announcements.csv for hand-labelling
  export             write brief.json / prices.json / meta.json for the frontend      (A7)
  research SYMBOL    build the research pack for one ticker                           (A8-A11)
"""
from __future__ import annotations

import argparse
import json
import sys

from . import config, contracts, db

FILES = {
    "brief.json": contracts.Brief,
    "prices.json": contracts.Prices,
    "meta.json": contracts.Meta,
}


def cmd_init_db(_args) -> None:
    tables = db.init_db()
    print(f"DB ready at {config.DB_PATH}")
    print("Tables:", ", ".join(tables))


def cmd_mocks(_args) -> None:
    from . import mocks
    for name in mocks.write_all():
        print("wrote", name)


def cmd_validate(_args) -> None:
    bad = 0
    for path in sorted(config.EXPORT_DIR.glob("*.json")):
        model = FILES.get(path.name) or (contracts.ResearchPack if path.name.startswith("research_") else None)
        if model is None:
            print(f"skip  {path.name}")
            continue
        try:
            model.model_validate(json.loads(path.read_text(encoding="utf-8")))
            print(f"ok    {path.name}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"FAIL  {path.name}\n{e}")
    sys.exit(1 if bad else 0)


def cmd_prices(_args) -> None:
    from . import export
    from .ingest import prices
    db.init_db()
    s = prices.run()
    print(f"Prices: {len(s['ok'])}/{len(s['ok']) + len(s['empty'])} symbols, latest session {s['latest']}")
    if s["fallback"]:
        print("  filled from NSE bhavcopy:", ", ".join(s["fallback"]))
    if s["empty"]:
        print("  NO DATA:", ", ".join(s["empty"]))
    if s["error"]:
        print("  warnings:", s["error"])
    p = export.write_prices()
    fired = [(sym, d.ret_pct[-1], d.vol_ratio[-1]) for sym, d in p.symbols.items()
             if (d.vol_ratio[-1] or 0) >= 2 or abs(d.ret_pct[-1] or 0) >= 4]
    print(f"Wrote prices.json (as of {p.as_of}). Default-rule alerts on the last session:")
    for sym, r, v in sorted(fired, key=lambda x: -(x[2] or 0)):
        print(f"  {sym:<12} move {r:+.2f}%   volume {v}x")


def cmd_push(args) -> None:
    from collections import Counter

    from .ingest import announcements
    from .signals import classify_rules
    db.init_db()
    s = announcements.run(days=args.days)
    print(f"Announcements {s['from']} -> {s['to']}: {s['rows']} filings")
    print("  per symbol:", ", ".join(f"{k} {v}" for k, v in s["per_symbol"].items()))
    if s["errors"]:
        print("  ERRORS:", s["errors"])

    hit, miss = Counter(), Counter()
    with db.session() as con:
        rows = con.execute("SELECT a.id, a.exchange_category, a.headline FROM announcements a "
                           "LEFT JOIN ann_enrichment e ON e.ann_id = a.id WHERE e.method IS NULL OR e.method='rule'").fetchall()
        for r in rows:
            rule = classify_rules.classify(r["exchange_category"], r["headline"])
            if rule is None:
                miss[r["exchange_category"]] += 1
                continue
            hit[rule.category] += 1
            db.upsert(con, "ann_enrichment", {"ann_id": r["id"], "category": rule.category, "confidence": rule.confidence,
                                              "method": "rule", "reasons_json": json.dumps({"sub": rule.sub}),
                                              "prompt_version": "rules-v1"}, ["ann_id"])
    total = sum(hit.values()) + sum(miss.values())
    print(f"\nRules classified {sum(hit.values())}/{total} ({100 * sum(hit.values()) / max(total, 1):.0f}%). By category:")
    print("  " + ", ".join(f"{k} {v}" for k, v in hit.most_common()))
    print(f"Left for the LLM (A4): {sum(miss.values())}. Their NSE categories:")
    for k, v in miss.most_common(15):
        print(f"  {v:>3}  {k}")


def cmd_gold_template(args) -> None:
    """60 filings to hand-label: every rule miss first, then a spread of rule hits."""
    import csv
    import random
    with db.session() as con:
        rows = con.execute("SELECT a.id, a.symbol, a.exchange_category, a.headline, e.category AS rule_category "
                           "FROM announcements a LEFT JOIN ann_enrichment e ON e.ann_id=a.id").fetchall()
    rows = [dict(r) for r in rows]
    random.Random(1).shuffle(rows)
    rows.sort(key=lambda r: r["rule_category"] is not None)
    out = config.BACKEND / "tests" / "gold" / "announcements.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "symbol", "exchange_category", "headline", "rule_category", "label"])
        w.writeheader()
        for r in rows[: args.n]:
            w.writerow({**r, "headline": r["headline"][:300], "label": ""})
    print(f"Wrote {min(args.n, len(rows))} rows to {out}. Fill the `label` column with one of the 17 categories.")


def _todo(task: str):
    def run(_args):
        sys.exit(f"Not built yet: task {task} in the roadmap.")
    return run


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="finn.pipeline", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db").set_defaults(fn=cmd_init_db)
    sub.add_parser("mocks").set_defaults(fn=cmd_mocks)
    sub.add_parser("validate").set_defaults(fn=cmd_validate)
    sub.add_parser("prices").set_defaults(fn=cmd_prices)
    pu = sub.add_parser("push")
    pu.add_argument("--days", type=int, default=10)
    pu.set_defaults(fn=cmd_push)
    g = sub.add_parser("gold-template")
    g.add_argument("--n", type=int, default=60)
    g.set_defaults(fn=cmd_gold_template)
    sub.add_parser("export").set_defaults(fn=_todo("A7"))
    r = sub.add_parser("research")
    r.add_argument("symbol")
    r.set_defaults(fn=_todo("A8-A11"))
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
