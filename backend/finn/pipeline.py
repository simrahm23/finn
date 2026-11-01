"""FINN command line. Run from backend/:  python -m finn.pipeline <command>

  init-db            create tables + load the portfolio into `companies`
  mocks              write clearly-labelled mock JSON into frontend/public/data (for UI work)
  validate           check every JSON file in frontend/public/data against the contracts
  prices             ingest EOD prices (yfinance, bhavcopy fallback) + write prices.json   (A1)
  push [--days N]    ingest NSE filings, rules -> LLM -> materiality -> summaries; prints the ranked Brief
  debug-pdf SYMBOL   show why a results PDF did or didn't yield a card
  eval-gold          accuracy of categories vs your labels in tests/gold/announcements.csv
  gold-template      write 60 filings to tests/gold/announcements.csv for hand-labelling
  export             write brief.json / prices.json / meta.json from the DB (push does this too)
  research SYMBOL    build the research pack for any NSE ticker (or --demo for the 4)
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
    from .ingest import announcements
    from .llm import client as llm
    from .signals import enrich
    db.init_db()
    if not args.skip_fetch:
        s = announcements.run(days=args.days)
        print(f"Announcements {s['from']} -> {s['to']}: {s['rows']} filings")
        if s["errors"]:
            print("  ERRORS:", s["errors"])
    with db.session() as con:
        total = con.execute("SELECT COUNT(*) FROM announcements").fetchone()[0]
        n_rules = enrich.run_rules(con)
    print(f"Rules: {n_rules}/{total} classified ({100 * n_rules / max(total, 1):.0f}%)")
    before = llm.usage()
    if not args.no_llm:
        with db.session() as con:
            st = enrich.run_llm_classify(con)
        print(f"LLM classify: {st['classified']}/{st['items']} (summaries dropped for ungrounded numbers: "
              f"{st['summaries_dropped']}) {st['errors'] or ''}")
    with db.session() as con:
        enrich.run_materiality(con)
    if not args.no_llm:
        with db.session() as con:
            st = enrich.run_summaries(con)
        print(f"Summaries: {st['written']}/{st['items']} written, {st['dropped']} dropped (ungrounded) {st['errors'] or ''}")
    if not args.no_llm and not args.no_cards:
        from .extract import cards
        with db.session() as con:
            st = cards.run(con)
        print(f"Cards: {st['results']} results, {st['management']} management")
        with db.session() as con:
            enrich.run_materiality(con)          # re-score: results surprises and related filings need the cards
        for x in st["skipped"]:
            print(f"  skipped {x}")
        for x in st["errors"]:
            print(f"  ERROR {x}")
    after = llm.usage()
    print(f"LLM this run: {after['calls'] - before['calls']} requests, {after['cached'] - before['cached']} from cache, "
          f"{after['tokens_in'] - before['tokens_in']} tokens in")

    with db.session() as con:
        rows = con.execute("SELECT a.symbol, a.filed_at, a.headline, e.category, e.method, e.materiality, e.tier, "
                           "e.reasons_json, e.summary, e.card_json FROM announcements a JOIN ann_enrichment e ON e.ann_id=a.id "
                           "ORDER BY e.materiality DESC, a.filed_at DESC").fetchall()
        unscored = total - len(rows)
    tiers = {t: sum(r["tier"] == t for r in rows) for t in ("needs_you", "worth_knowing", "routine")}
    print(f"\nBrief: {tiers['needs_you']} need you, {tiers['worth_knowing']} worth knowing, {tiers['routine']} routine"
          + (f", {unscored} unclassified (LLM skipped/failed)" if unscored else ""))
    for r in rows[: args.top]:
        chips = ", ".join(json.loads(r["reasons_json"] or "{}").get("chips", []))
        print(f"  {r['materiality']:>5}  {r['tier']:<13} {r['symbol']:<11} {r['category']:<17} [{chips}]")
        print(f"         {r['headline'][:110]}")
        if r["summary"]:
            print(f"         -> {r['summary']}")
        if r["card_json"]:
            from .extract.cards import summary_line
            print(f"         [card] {summary_line(r['card_json'])}")
    from . import export
    out = export.write_all(args.days)
    print(f"\nExported brief.json ({out['items']} items), prices.json (as of {out['prices_as_of']}), meta.json. "
          f"LLM total: {out['llm']['calls']} requests, {out['llm']['cached']} cached.")


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
    if out.exists() and not args.force and "label" in out.read_text(encoding="utf-8-sig", errors="ignore"):
        import csv as _csv
        labelled = sum(1 for r in _csv.DictReader(out.read_text(encoding="utf-8-sig", errors="ignore").splitlines())
                       if (r.get("label") or "").strip())
        if labelled:
            sys.exit(f"{out.name} already has {labelled} labels. Not overwriting (use --force to start over).")
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "symbol", "exchange_category", "headline", "rule_category", "label"])
        w.writeheader()
        for r in rows[: args.n]:
            w.writerow({**r, "headline": r["headline"][:300], "label": ""})
    print(f"Wrote {min(args.n, len(rows))} rows to {out}. Fill the `label` column with one of the 17 categories.")


def cmd_debug_pdf(args) -> None:
    """Why did a results card fail? Prints per-page text size and keyword hits for one filing URL or symbol."""
    from .extract.results import _sq, pick_page
    from .ingest import documents
    urls = [args.target]
    if not args.target.startswith("http"):
        with db.session() as con:
            urls = [r[0] for r in con.execute("SELECT a.attachment_url FROM announcements a JOIN ann_enrichment e ON "
                                              "e.ann_id=a.id WHERE a.symbol=? AND e.category='results' ORDER BY a.filed_at DESC",
                                              (args.target.upper(),))]
    for url in urls:
        path = documents.fetch_pdf(url)
        print(f"\n{url}\n  downloaded: {bool(path)}")
        if not path:
            continue
        texts = documents.page_texts(path, 60)
        print(f"  pages: {len(texts)}, picked page: {None if pick_page(texts) is None else pick_page(texts) + 1}")
        for i, t in enumerate(texts[:12]):
            q = _sq(t)
            hits = [k for k in ("beforetax", "revenuefromoperations", "totalincome", "consolidated", "quarterended") if k in q]
            print(f"  p{i + 1:<3} {len(t):>6} chars  {hits}  {t[:80].strip()!r}")


def cmd_research(args) -> None:
    from .research import build
    db.init_db()
    symbols = config.portfolio()["research_demo"] if args.demo else [args.symbol]
    for sym in symbols:
        print(f"\n=== {sym.upper()} ===")
        try:
            pack = build.build(sym)
        except Exception as e:  # noqa: BLE001  one company failing must not stop the others
            print(f"  FAILED: {type(e).__name__}: {e}")
            continue
        pr = pack.promises
        if pr:
            for p in pr.items[:8]:
                act = "-" if p.actual is None else f"{p.actual}"
                print(f"   {p.verdict:<12} {p.said_in:<8} -> {p.target_period:<8} {p.target_text[:48]:<48} actual {act}")
            if pr.commentary:
                print(f"   commentary: {pr.commentary.text}")
        print(f"  wrote research_{pack.symbol}.json")


def cmd_export(_args) -> None:
    from . import export
    out = export.write_all()
    print(f"Exported brief.json ({out['items']} items), prices.json (as of {out['prices_as_of']}), meta.json")


def _decodes(raw: bytes, enc: str) -> bool:
    try:
        raw.decode(enc)
        return True
    except UnicodeDecodeError:
        return False


def cmd_eval_gold(_args) -> None:
    """Accuracy of FINN's categories against your hand labels in tests/gold/announcements.csv."""
    import csv
    path = config.BACKEND / "tests" / "gold" / "announcements.csv"
    if not path.exists():
        sys.exit("No gold set yet. Run `python -m finn.pipeline gold-template`, label it, then run this again.")
    raw = path.read_bytes()
    text = next((raw.decode(enc) for enc in ("utf-8-sig", "cp1252") if _decodes(raw, enc)), raw.decode("latin-1"))
    rows = [r for r in csv.DictReader(text.splitlines()) if (r.get("label") or "").strip()]   # utf-8-sig: Excel's BOM
    if not rows:
        sys.exit(f"No labels yet in {path}. Fill the `label` column first.")
    with db.session() as con:
        got = {r["ann_id"]: (r["category"], r["method"]) for r in con.execute("SELECT ann_id, category, method FROM ann_enrichment")}
    ok = by_method = 0
    stats = {"rule": [0, 0], "llm": [0, 0]}
    wrong = []
    for r in rows:
        cat, method = got.get(r["id"], (None, None))
        hit = cat == r["label"].strip()
        ok += hit
        if method in stats:
            stats[method][0] += hit
            stats[method][1] += 1
        if not hit:
            wrong.append((r["symbol"], r["label"], cat, r["headline"][:70]))
    by_method = ", ".join(f"{m}: {a}/{n}" for m, (a, n) in stats.items() if n)
    print(f"Category accuracy: {ok}/{len(rows)} = {100 * ok / len(rows):.0f}%  ({by_method})")
    for w in wrong:
        print(f"  {w[0]:<11} labelled {w[1]:<17} FINN {str(w[2]):<17} {w[3]}")


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
    pu.add_argument("--no-llm", action="store_true", help="rules + scores only")
    pu.add_argument("--skip-fetch", action="store_true", help="reuse filings already in the DB")
    pu.add_argument("--top", type=int, default=15)
    pu.add_argument("--no-cards", action="store_true", help="skip results/management card extraction")
    pu.set_defaults(fn=cmd_push)
    g = sub.add_parser("gold-template")
    g.add_argument("--n", type=int, default=60)
    g.add_argument("--force", action="store_true")
    g.set_defaults(fn=cmd_gold_template)
    sub.add_parser("export").set_defaults(fn=cmd_export)
    sub.add_parser("eval-gold").set_defaults(fn=cmd_eval_gold)
    dp = sub.add_parser("debug-pdf")
    dp.add_argument("target", help="a filing URL, or a symbol (checks its results filings)")
    dp.set_defaults(fn=cmd_debug_pdf)
    r = sub.add_parser("research")
    r.add_argument("symbol", nargs="?", default="")
    r.add_argument("--demo", action="store_true", help="build the research_demo set from portfolio.yaml")
    r.set_defaults(fn=cmd_research)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
