"""Single place for paths, environment, model IDs and the yaml configs."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]          # repo root
BACKEND = ROOT / "backend"
CONFIG_DIR = ROOT / "config"
DATA_DIR = BACKEND / "data"
DOCS_DIR = DATA_DIR / "docs"                         # downloaded PDFs (gitignored)
EXPORT_DIR = ROOT / "frontend" / "public" / "data"   # static push JSON for the frontend

DB_PATH = Path(os.environ.get("FINN_DB_PATH", DATA_DIR / "finn.db"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ALLOWED_ORIGIN = os.environ.get("FINN_ALLOWED_ORIGIN", "http://localhost:5173")

# Model routing (confirmed PASS in the 13:50 spike). Tier 0 = no model (rules + code).
MODEL_LITE = os.environ.get("FINN_MODEL_LITE", "gemini-3.5-flash-lite")   # tier 1: bulk extraction
MODEL_FLASH = os.environ.get("FINN_MODEL_FLASH", "gemini-3.5-flash")      # tier 2: reasoning

IST_OFFSET = "+05:30"


@lru_cache
def portfolio() -> dict:
    return yaml.safe_load((CONFIG_DIR / "portfolio.yaml").read_text(encoding="utf-8"))


@lru_cache
def rules() -> dict:
    return yaml.safe_load((CONFIG_DIR / "rules.yaml").read_text(encoding="utf-8"))


def portfolio_symbols() -> list[str]:
    return [p["symbol"] for p in portfolio()["portfolio"]]
