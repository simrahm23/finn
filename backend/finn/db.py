"""SQLite schema and tiny helpers. One file, no ORM. Schema changes = drop and recreate (it's a demo)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
  symbol TEXT PRIMARY KEY, name TEXT, isin TEXT, bse_code TEXT, sector TEXT,
  in_portfolio INTEGER DEFAULT 0, weight REAL DEFAULT 0, lender INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prices_daily (
  symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, source TEXT,
  PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS announcements (
  id TEXT PRIMARY KEY,               -- '<exchange>:<native id>'
  symbol TEXT, exchange TEXT, filed_at TEXT,   -- ISO-8601 with +05:30
  headline TEXT, exchange_category TEXT, attachment_url TEXT, raw_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_ann_symbol_time ON announcements(symbol, filed_at);

CREATE TABLE IF NOT EXISTS ann_enrichment (
  ann_id TEXT PRIMARY KEY REFERENCES announcements(id),
  category TEXT, confidence REAL, method TEXT,         -- method: rule | llm
  materiality REAL, tier TEXT, reasons_json TEXT, summary TEXT, card_json TEXT, prompt_version TEXT
);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, symbol TEXT, kind TEXT,        -- kind: annual_report | transcript | results | filing
  period TEXT, title TEXT, url TEXT, sha256 TEXT, pages INTEGER, text_ok INTEGER
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5(doc_id UNINDEXED, page_no UNINDEXED, text);

CREATE TABLE IF NOT EXISTS facts (
  symbol TEXT, period TEXT, metric TEXT, value REAL, unit TEXT, basis TEXT,
  source_kind TEXT, doc_id TEXT, page INTEGER, method TEXT,
  PRIMARY KEY (symbol, period, metric, basis, source_kind)
);

CREATE TABLE IF NOT EXISTS guidance (
  id TEXT PRIMARY KEY, symbol TEXT, said_in_period TEXT, target_period TEXT, metric TEXT,
  target_low REAL, target_high REAL, unit TEXT, target_text TEXT, quote TEXT,
  doc_id TEXT, page INTEGER, quote_match REAL, verdict TEXT, actual_value REAL
);

CREATE TABLE IF NOT EXISTS llm_cache (
  key TEXT PRIMARY KEY, model TEXT, prompt_version TEXT, response_json TEXT,
  tokens_in INTEGER, tokens_out INTEGER, created_at TEXT
);

CREATE TABLE IF NOT EXISTS llm_calls (      -- one row per request, cached or not (feeds the ops footer)
  ts TEXT, model TEXT, purpose TEXT, cached INTEGER, tokens_in INTEGER, tokens_out INTEGER
);

CREATE TABLE IF NOT EXISTS research_jobs (
  symbol TEXT PRIMARY KEY, status TEXT, step TEXT, error TEXT, updated_at TEXT, pack_json TEXT
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  ts TEXT, source TEXT, ok INTEGER, rows INTEGER, detail TEXT
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextmanager
def session(path: Path | None = None):
    con = connect(path)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db(path: Path | None = None) -> list[str]:
    with session(path) as con:
        con.executescript(SCHEMA)
        for p in config.portfolio()["portfolio"]:
            con.execute(
                "INSERT INTO companies(symbol, sector, in_portfolio, weight, lender) VALUES (?,?,1,?,?) "
                "ON CONFLICT(symbol) DO UPDATE SET sector=excluded.sector, in_portfolio=1, "
                "weight=excluded.weight, lender=excluded.lender",
                (p["symbol"], p.get("sector"), p.get("weight", 0), int(p.get("lender", False))),
            )
        return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table') ORDER BY name")]


def upsert(con: sqlite3.Connection, table: str, row: dict, keys: list[str]) -> None:
    cols = list(row)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in keys) or f"{keys[0]}={keys[0]}"
    con.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
        f"ON CONFLICT({', '.join(keys)}) DO UPDATE SET {updates}",
        [row[c] for c in cols],
    )
