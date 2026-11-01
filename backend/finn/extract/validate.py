"""Deterministic checks used by every extractor. If these fail, the UI shows the filing, not numbers."""
from __future__ import annotations

import re
from typing import Optional

UNIT_TO_CRORE = {"crore": 1.0, "lakh": 0.01, "million": 0.1, "thousand": 0.0001, "rupees": 1e-7}


def parse_number(s: str | None) -> Optional[float]:
    """'1,23,456.78' -> 123456.78; '(12.40)' -> -12.4; '' / '-' -> None."""
    if s is None:
        return None
    t = str(s).strip().replace("₹", "").replace(" ", "")
    if t in ("", "-", "–", "—", "NA", "N.A.", "nil", "Nil"):
        return None
    neg = t.startswith("(") and t.endswith(")") or t.startswith("-")
    t = t.strip("()").lstrip("-").replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def appears_verbatim(value: str, page_text: str) -> bool:
    """The printed value occurs on the page (whitespace-insensitive). Brackets may be split across tokens."""
    v = _squash(value)
    if not v:
        return True
    page = _squash(page_text)
    return v in page or v.strip("()") in page


def close(a: Optional[float], b: Optional[float], rel: float = 0.03, abs_tol: float = 0.5) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b)))


def pct_change(cur: Optional[float], base: Optional[float]) -> Optional[float]:
    """% change; None when the base is missing, zero or negative (growth off a loss is meaningless)."""
    if cur is None or base is None or base <= 0:
        return None
    return round((cur / base - 1) * 100, 1)


def quarter_label(period_end: str) -> Optional[str]:
    """'2026-09-30' -> 'Q2 FY27 (Jul–Sep 2026)' (Indian fiscal year: Apr-Mar)."""
    m = re.match(r"(\d{4})-(\d{2})-\d{2}$", period_end or "")
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    q = {6: 1, 9: 2, 12: 3, 3: 4}.get(mo)
    if q is None:
        return None
    fy = (y + 1 if mo >= 4 else y) % 100
    months = {1: "Apr–Jun", 2: "Jul–Sep", 3: "Oct–Dec", 4: "Jan–Mar"}[q]
    return f"Q{q} FY{fy:02d} ({months} {y})"


def fuzzy_in(needle: str, haystack: str, threshold: float = 90) -> bool:
    if not needle:
        return False
    from rapidfuzz import fuzz
    return fuzz.partial_ratio(" ".join(needle.split()).lower(), " ".join(haystack.split()).lower()) >= threshold
