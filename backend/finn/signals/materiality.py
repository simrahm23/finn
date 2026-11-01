"""Materiality score 0-100 + tier + reason chips. Deterministic; weights live in config/rules.yaml."""
from __future__ import annotations

import re
from typing import Optional

from .. import config

LABEL = {
    "results": "Results", "M&A": "M&A", "fund_raise": "Fund raise", "management_change": "Mgmt change",
    "litigation": "Litigation", "insider_trading": "Insider trade", "earnings_call": "Earnings call",
    "investor_meetings": "Investor meet", "credit_rating": "Credit rating", "dividend": "Dividend",
    "bonus_split": "Bonus/split", "capex": "Capex", "press_release": "Update", "postal_ballot": "Postal ballot",
    "agm_egm": "AGM/EGM", "pledging": "Pledge", "unclassified": "Routine",
}
LEAVING = r"\b(resign|cessation|retire|completion of (his|her)? ?tenure|step(ping)? down)"


def score(category: str, sub: Optional[str], headline: str, weight_pct: float,
          ret_pct: Optional[float], vol_ratio: Optional[float],
          price_thr: Optional[float] = None, vol_thr: Optional[float] = None) -> tuple[float, str, list[str]]:
    r = config.rules()
    price_thr = price_thr if price_thr is not None else r["alert_defaults"]["price_move_pct"]
    vol_thr = vol_thr if vol_thr is not None else r["alert_defaults"]["volume_multiple"]
    m = r["modifiers"]
    reasons: list[str] = []

    if sub == "routine" or sub == "board_meeting_notice":
        return 5.0, "routine", ["Routine"]

    base = float(r["base_weight"].get(category, 5))
    refine = r["refine"].get(category, {})
    if sub in refine:
        base = float(refine[sub])

    label = LABEL.get(category, category)
    if category == "management_change":
        leaving = re.search(LEAVING, headline or "", re.I) is not None
        label = ("Top exit" if leaving else "Top hire") if sub == "top_role" else ("Director exit" if leaving else "Board change")
        if leaving and sub == "top_role":
            base += m["negative_direction"]
    if category == "credit_rating" and sub in ("downgrade", "upgrade", "reaffirm"):
        label = {"downgrade": "Downgrade", "upgrade": "Upgrade", "reaffirm": "Reaffirmed"}[sub]
        if sub == "downgrade":
            base += m["negative_direction"]
    if category == "earnings_call" and sub == "transcript":
        label = "Transcript"
    reasons.append(label)

    if ret_pct is not None and abs(ret_pct) >= price_thr:
        base += m["price_move_beyond_threshold"]
        reasons.append(f"Move {ret_pct:+.1f}%")
    if vol_ratio is not None and vol_ratio >= vol_thr:
        base += m["volume_beyond_threshold"]
        reasons.append(f"Vol {vol_ratio:.1f}×")
    base += min(5.0, m["portfolio_weight_per_pct"] * (weight_pct or 0))
    if (weight_pct or 0) >= 7:
        reasons.append(f"{weight_pct:g}% of portfolio")

    s = max(0.0, min(100.0, base))
    tiers = r["tiers"]
    tier = "needs_you" if s >= tiers["needs_you"] else "worth_knowing" if s >= tiers["worth_knowing"] else "routine"
    return round(s, 1), tier, reasons


def reaction_session(filed_at: str, trading_dates: list[str]) -> Optional[str]:
    """The session whose move reflects the filing: same day if filed before the 15:30 close, else the next session."""
    day, time = filed_at[:10], filed_at[11:16]
    for d in trading_dates:
        if d > day or (d == day and time < "15:30"):
            return d
    return None
