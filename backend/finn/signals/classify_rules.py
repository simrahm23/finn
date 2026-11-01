"""Tier-0 classification: NSE's own category ('desc') + keywords -> the 17 reference categories.
Returns None when unsure, so the LLM (A4) only sees the genuinely ambiguous filings."""
from __future__ import annotations

import re
from typing import NamedTuple, Optional


class Rule(NamedTuple):
    category: str
    confidence: float
    sub: Optional[str] = None      # refines materiality: top_role, transcript, downgrade...


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.I) is not None


TOP_ROLE = r"\b(ceo|chief executive|managing director|\bmd\b|cfo|chief financial|chairman|chairperson|whole[- ]?time director|executive director)\b"

# Exchange categories that are routine whatever the text says.
ROUTINE_DESC = [
    r"trading window", r"newspaper publication", r"certificate under sebi \(depositories", r"reg\.? ?74",
    r"esop|esos|esps", r"loss of share certificate|duplicate share certificate", r"compliance certificate",
    r"statement of investor complaints", r"book closure", r"closure of trading", r"monitoring agency",
    r"business responsibility|brsr|esg", r"secretarial compliance", r"change in registered office",
    r"appointment of (statutory|secretarial|internal|cost) auditor", r"reg\.? ?39", r"reg\.? ?40",
]

# (pattern on desc, category, confidence, sub) - checked in order.
DESC_RULES = [
    (r"financial result", "results", 0.95, None),
    (r"integrated filing.?-?\s*financ", "results", 0.9, None),
    (r"analysts?/institutional investor meet|investor meet|con\.? call", "investor_meetings", 0.85, None),
    (r"credit rating", "credit_rating", 0.95, None),
    (r"insider trading|sebi \(pit\)|\bpit\b", "insider_trading", 0.9, None),
    (r"pledge|encumbrance", "pledging", 0.95, None),
    (r"dividend", "dividend", 0.9, None),
    (r"bonus|split|sub-?division", "bonus_split", 0.9, None),
    (r"buy ?back|rights issue|qip|qualified institutions|preferential|allotment of (securities|shares)|"
     r"commercial paper|non-convertible|\bncd", "fund_raise", 0.85, None),
    (r"acquisition|amalgamation|merger|scheme of arrangement|demerger|joint venture|takeover", "M&A", 0.85, None),
    (r"litigation|action\(s\) initiated|orders? passed|penalt|show cause|insolvency|nclt", "litigation", 0.85, None),
    (r"postal ballot", "postal_ballot", 0.95, None),
    (r"shareholders? meeting|\bagm\b|\begm\b|general meeting", "agm_egm", 0.9, None),
    (r"press release|bagging|receiving of orders|order win", "press_release", 0.8, None),
]


def classify(exchange_category: str, headline: str) -> Optional[Rule]:
    desc, text = exchange_category or "", headline or ""
    both = f"{desc} {text}"

    if any(_has(p, desc) for p in ROUTINE_DESC) or _has(r"\b(esop|esos|esps|employee stock option)", both):
        return Rule("unclassified", 0.95, "routine")

    # Earnings call: transcript beats notice/recording.
    if _has(r"transcript", both) and _has(r"call|conference|earnings", both):
        return Rule("earnings_call", 0.95, "transcript")
    if _has(r"audio|video recording|earnings call|conference call", text) and not _has(r"investor meet", desc):
        return Rule("earnings_call", 0.85, None)

    if _has(r"record date", desc):
        if _has(r"dividend", text):
            return Rule("dividend", 0.9, None)
        if _has(r"bonus|split|sub-?division", text):
            return Rule("bonus_split", 0.9, None)
        return None
    if _has(r"other restructuring", desc):
        return Rule("M&A", 0.7, None)

    # Management change: exchange categories are explicit; the role decides weight.
    if _has(r"change in (director|management|key managerial)|cessation|resignation|retirement|appointment|re-?appointment", desc) \
            or _has(r"\b(resign|appointed|appointment of|cessation|completion of (his|her)? ?tenure)\b", text):
        if not _has(r"auditor|scrutini[sz]er|registrar|share transfer agent", both):
            return Rule("management_change", 0.9, "top_role" if _has(TOP_ROLE, both) else "other_role")

    # Board meeting outcomes are ambiguous: decide only on clear words, else leave for the LLM.
    if _has(r"outcome of board meeting|board meeting", desc):
        if _has(r"financial results?|quarter(ly)? results|un-?audited|audited", text):
            return Rule("results", 0.85, None)
        if _has(r"intimation|to consider|will be held|scheduled", text):
            return Rule("unclassified", 0.8, "board_meeting_notice")
        return None

    for pattern, cat, conf, sub in DESC_RULES:
        if _has(pattern, desc):
            if cat == "credit_rating":
                sub = "downgrade" if _has(r"downgrad|negative", text) else "upgrade" if _has(r"upgrad", text) \
                    else "reaffirm" if _has(r"reaffirm|retain", text) else None
            if cat == "fund_raise" and _has(r"non[- ]convertible|\bncds?\b|commercial paper|debenture|bonds?", text):
                sub = "debt"
            return Rule(cat, conf, sub)

    # Generic NSE buckets ("General Updates", "Updates") - only clear keywords, else LLM.
    for pattern, cat in [(r"investor presentation", "results"), (r"capex|capacity expansion|new plant|greenfield", "capex"),
                         (r"acqui|merger|stake (sale|purchase)|subsidiary", "M&A"), (r"order", "press_release")]:
        if _has(pattern, text):
            return Rule(cat, 0.7, None)
    return None
