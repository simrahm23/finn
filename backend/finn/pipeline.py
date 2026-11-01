"""FINN command line. Run from backend/:  python -m finn.pipeline <command>

  init-db            create tables + load the portfolio into `companies`
  mocks              write clearly-labelled mock JSON into frontend/public/data (for UI work)
  validate           check every JSON file in frontend/public/data against the contracts
  push               ingest prices + announcements, classify, score, extract cards   (A1-A7)
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
    sub.add_parser("push").set_defaults(fn=_todo("A1-A7"))
    sub.add_parser("export").set_defaults(fn=_todo("A7"))
    r = sub.add_parser("research")
    r.add_argument("symbol")
    r.set_defaults(fn=_todo("A8-A11"))
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
