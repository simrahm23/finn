"""Price and volume maths. Pure functions, no network, no LLM. Every alert number comes from here."""
from __future__ import annotations

from typing import Optional, Sequence


def daily_returns_pct(closes: Sequence[float]) -> list[Optional[float]]:
    """% change close-to-close. First value is None (no previous close)."""
    out: list[Optional[float]] = [None]
    for prev, cur in zip(closes, closes[1:]):
        out.append(None if not prev else round((cur / prev - 1) * 100, 2))
    return out


def volume_ratios(volumes: Sequence[float], lookback: int = 20) -> list[Optional[float]]:
    """Today's volume / mean of the previous `lookback` sessions (today excluded).
    None until `lookback` previous sessions exist, or when the average is zero."""
    out: list[Optional[float]] = []
    running = 0.0
    for i, v in enumerate(volumes):
        if i >= lookback:
            avg = running / lookback
            out.append(round(v / avg, 2) if avg > 0 else None)
            running -= volumes[i - lookback]
        else:
            out.append(None)
        running += v
    return out


def is_52w_high(closes: Sequence[float], window: int = 250) -> bool:
    w = closes[-window:]
    return bool(w) and closes[-1] >= max(w)


def is_52w_low(closes: Sequence[float], window: int = 250) -> bool:
    w = closes[-window:]
    return bool(w) and closes[-1] <= min(w)


def triggers(ret_pct: Optional[float], vol_ratio: Optional[float],
             price_threshold_pct: float, volume_multiple: float) -> list[str]:
    """Which alerts fire for one session. Mirrors frontend/src/lib/rules.ts; keep them identical."""
    fired = []
    if ret_pct is not None and abs(ret_pct) >= price_threshold_pct:
        fired.append("price")
    if vol_ratio is not None and vol_ratio >= volume_multiple:
        fired.append("volume")
    return fired
