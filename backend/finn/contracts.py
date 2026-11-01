"""JSON contracts between backend and frontend. Mirrored by hand in frontend/src/lib/types.ts.
Change one, change the other. `python -m finn.pipeline validate` checks the files in public/data."""
from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

Category = Literal[
    "results", "M&A", "fund_raise", "management_change", "litigation", "insider_trading",
    "earnings_call", "investor_meetings", "credit_rating", "dividend", "bonus_split", "capex",
    "press_release", "postal_ballot", "agm_egm", "pledging", "unclassified",
]
Tier = Literal["needs_you", "worth_knowing", "routine"]
Verdict = Literal["met", "partly", "missed", "pending", "unverifiable"]


class Source(BaseModel):
    label: str                      # "Results filing p.2", "Q1 FY27 transcript p.7", "screener.in"
    kind: Literal["filing", "transcript", "annual_report", "screener"]
    url: str
    page: Optional[int] = None      # frontend opens url#page=N


# ---------- meta.json ----------
class LlmUsage(BaseModel):
    calls: int = 0
    cached: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_inr: float = 0.0


class Meta(BaseModel):
    generated_at: str               # ISO-8601 +05:30
    prices_as_of: Optional[str]     # last trading date in prices.json
    filings_as_of: Optional[str]
    mock: bool = False              # True only for hand-made development data
    sources: dict[str, str] = {}    # {"prices": "yfinance", "announcements": "nse"}
    llm: LlmUsage = LlmUsage()


# ---------- brief.json ----------
class ResultsMetric(BaseModel):
    name: Literal["Revenue", "EBITDA", "PBT", "PAT"]
    applicable: bool = True         # False for EBITDA at lenders
    current: Optional[float] = None
    prev_q: Optional[float] = None
    year_ago: Optional[float] = None
    qoq_pct: Optional[float] = None
    yoy_pct: Optional[float] = None


class ResultsChecks(BaseModel):
    verbatim: bool                  # every value found on the cited page
    identities: bool                # PAT ~ PBT - tax, etc.
    cross_check: Optional[bool]     # matches screener quarterly table (None = not available)


class ResultsCard(BaseModel):
    kind: Literal["results"] = "results"
    period: str                     # "Q2 FY27 (Jul-Sep 2026)"
    basis: Literal["consolidated", "standalone"]
    unit: str = "₹ crore"
    metrics: list[ResultsMetric]
    ebitda_formula: str = "PBT + finance costs + depreciation − other income"
    checks: ResultsChecks
    verified: bool                  # verbatim and identities both pass
    source: Source


class ManagementCard(BaseModel):
    kind: Literal["management"] = "management"
    direction: Literal["joining", "leaving"]
    person: str
    role: str
    effective_date: Optional[str] = None
    reason: Optional[str] = None    # leaving: resignation, completion of tenure...
    profile: Optional[str] = None   # joining: quoted from the filing / its annexure
    source: Source


class BriefItem(BaseModel):
    id: str
    symbol: str
    company: str
    filed_at: str
    headline: str
    exchange_category: str
    category: Category
    category_method: Literal["rule", "llm"]
    materiality: float = Field(ge=0, le=100)
    tier: Tier
    reasons: list[str]              # chips, e.g. ["CFO exit", "Vol 3.1×"]
    summary: Optional[str] = None
    filing_url: str
    price_reaction_pct: Optional[float] = None
    card: Optional[Union[ResultsCard, ManagementCard]] = Field(default=None, discriminator="kind")


class Brief(BaseModel):
    generated_at: str
    window_max_days: int            # how far back the file reaches; the UI filters inside it
    items: list[BriefItem]          # newest first


# ---------- prices.json ----------
class SymbolPrices(BaseModel):
    name: str
    dates: list[str]                # oldest -> newest, trading days only
    close: list[float]
    volume: list[int]
    ret_pct: list[Optional[float]]  # daily % change; first is None
    vol_ratio: list[Optional[float]]  # volume / mean(previous 20 sessions); None until 20 exist
    high_52w: bool
    low_52w: bool
    stale: bool = False


class Prices(BaseModel):
    as_of: str
    lookback_sessions: int = 20
    symbols: dict[str, SymbolPrices]


# ---------- research pack (GET /api/research/{symbol}) ----------
class Kpi(BaseModel):
    label: str
    value: Optional[float]
    unit: str
    period: str
    source: Source


class Snapshot(BaseModel):
    kpis: list[Kpi]
    years: list[str]                # "FY17".."FY26" (+ "TTM")
    revenue: list[Optional[float]]
    ebitda_margin_pct: list[Optional[float]]
    cfo: list[Optional[float]]
    pat: list[Optional[float]]
    cash_conversion_pct: list[Optional[float]]   # CFO / PAT
    debt_to_equity: Optional[float]
    business: Optional[str] = None
    business_source: Optional[Source] = None
    missing: list[str] = []         # tables or fields we could not get


class Promise(BaseModel):
    id: str
    said_in: str                    # quarter the statement was made, "Q1 FY27"
    target_period: str              # "FY27", "Q2 FY27", "H2 FY27"
    metric: str
    target_text: str                # "12-15% revenue growth"
    target_low: Optional[float] = None
    target_high: Optional[float] = None
    unit: str = "%"
    actual: Optional[float] = None
    verdict: Verdict
    quote: str
    source: Source


class Scorecard(BaseModel):
    met: int = 0
    partly: int = 0
    missed: int = 0
    pending: int = 0
    unverifiable: int = 0


class Commentary(BaseModel):
    text: str
    cites: list[str]                # Promise ids


class Promises(BaseModel):
    scorecard: Scorecard
    items: list[Promise]
    qualitative: list[Promise] = []   # no measurable target; shown separately, never scored
    commentary: Optional[Commentary] = None


class DocumentRef(BaseModel):
    id: str
    kind: Literal["annual_report", "transcript", "results", "filing"]
    period: str
    title: str
    url: str
    pages: Optional[int] = None


class BuildStep(BaseModel):
    ts: str
    step: str
    status: Literal["running", "done", "failed", "skipped"]
    detail: Optional[str] = None


class ResearchPack(BaseModel):
    symbol: str
    name: str
    sector: Optional[str] = None
    status: Literal["building", "ready", "failed"]
    built_at: Optional[str] = None
    mock: bool = False
    snapshot: Optional[Snapshot] = None
    promises: Optional[Promises] = None
    documents: list[DocumentRef] = []
    build_log: list[BuildStep] = []
