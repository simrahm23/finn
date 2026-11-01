"""Materiality score 0-100 + tier + reason chips. Deterministic; weights live in config/rules.yaml.

Judgment encoded here (and explained in the covering note):
- a market reaction is credited to ONE filing per stock-session (the most material), not to all of them;
- results are 'worth knowing' unless they surprise (stock reacted, or |PAT YoY| >= 20%);
- group housekeeping (new subsidiary, strike-off, letter of comfort) is not M&A-grade;
- the 2nd+ filing about the same results or the same person is capped as 'related'."""
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
MINOR_CORP = (r"incorporat|strike[- ]?off|struck off|letter of comfort|extension of (the )?timeline|step[- ]down subsidiary|"
              r"dissolution|liquidation of|name change of (the )?subsidiary|corporate guarantee")


def score(category: str, sub: Optional[str], text: str, weight_pct: float,
          ret_pct: Optional[float], vol_ratio: Optional[float],
          price_thr: Optional[float] = None, vol_thr: Optional[float] = None,
          card: Optional[dict] = None, market_boost: bool = True) -> tuple[float, str, list[str]]:
    r = config.rules()
    price_thr = price_thr if price_thr is not None else r["alert_defaults"]["price_move_pct"]
    vol_thr = vol_thr if vol_thr is not None else r["alert_defaults"]["volume_multiple"]
    m = r["modifiers"]
    reasons: list[str] = []

    if sub in ("routine", "board_meeting_notice"):
        return 5.0, "routine", ["Routine"]

    base = float(r["base_weight"].get(category, 5))
    refine = r["refine"].get(category, {})
    if sub in refine:
        base = float(refine[sub])

    label = LABEL.get(category, category)
    if category == "management_change":
        leaving = re.search(LEAVING, text or "", re.I) is not None
        label = ("Top exit" if leaving else "Top hire") if sub == "top_role" else ("Director exit" if leaving else "Board change")
        if leaving and sub == "top_role":
            base += m["negative_direction"]
    if category == "M&A" and re.search(MINOR_CORP, text or "", re.I):
        base, label = float(r["minor_corporate_action"]), "Group restructuring"
    if category == "credit_rating" and sub in ("downgrade", "upgrade", "reaffirm"):
        label = {"downgrade": "Downgrade", "upgrade": "Upgrade", "reaffirm": "Reaffirmed"}[sub]
        if sub == "downgrade":
            base += m["negative_direction"]
    if category == "earnings_call" and sub == "transcript":
        label = "Transcript"
    if category == "fund_raise" and sub == "debt":
        label = "Debt raise"
    reasons.append(label)

    if category == "results" and card and card.get("kind") == "results" and card.get("verified"):
        pat = next((x for x in card["metrics"] if x["name"] == "PAT"), None)
        yoy = pat and pat.get("yoy_pct")
        if yoy is not None:
            reasons.append(f"PAT {yoy:+.0f}% YoY")
            if abs(yoy) >= r["results"]["pat_yoy_surprise_pct"]:
                base += r["results"]["surprise_bonus"]

    if market_boost:
        if ret_pct is not None and abs(ret_pct) >= price_thr:
            base += m["price_move_beyond_threshold"]
            reasons.append(f"Move {ret_pct:+.1f}%")
        if vol_ratio is not None and vol_ratio >= vol_thr:
            base += m["volume_beyond_threshold"]
            reasons.append(f"Vol {vol_ratio:.1f}×")
    base += min(5.0, m["portfolio_weight_per_pct"] * (weight_pct or 0))
    if (weight_pct or 0) >= 7:
        reasons.append(f"{weight_pct:g}% of portfolio")
    return finish(base, reasons)


def finish(s: float, reasons: list[str]) -> tuple[float, str, list[str]]:
    s = max(0.0, min(100.0, s))
    tiers = config.rules()["tiers"]
    tier = "needs_you" if s >= tiers["needs_you"] else "worth_knowing" if s >= tiers["worth_knowing"] else "routine"
    return round(s, 1), tier, reasons


def reaction_session(filed_at: str, trading_dates: list[str]) -> Optional[str]:
    """The session whose move reflects the filing: same day if filed before the 15:30 close, else the next session."""
    day, time = filed_at[:10], filed_at[11:16]
    for d in trading_dates:
        if d > day or (d == day and time < "15:30"):
            return d
    return None
