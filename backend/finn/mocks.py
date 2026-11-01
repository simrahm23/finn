"""Hand-made DEVELOPMENT data so the frontend can be built before the pipeline exists.
Every file carries mock=True and every invented number/quote is marked. Replaced by `export` at A7.
Real filings referenced here (KPIT, HDFC Bank) use only facts seen in the spike; no invented biographies."""
from __future__ import annotations

import datetime as dt
import math
import random

from . import config, contracts as c

NOW = "2026-11-01T13:55:00+05:30"
NAMES = {
    "RELIANCE": "Reliance Industries", "HDFCBANK": "HDFC Bank", "ICICIBANK": "ICICI Bank",
    "BAJFINANCE": "Bajaj Finance", "INFY": "Infosys", "PERSISTENT": "Persistent Systems",
    "KPITTECH": "KPIT Technologies", "BHARTIARTL": "Bharti Airtel", "ITC": "ITC",
    "TITAN": "Titan Company", "TRENT": "Trent", "ASIANPAINT": "Asian Paints",
    "MARUTI": "Maruti Suzuki", "SUNPHARMA": "Sun Pharmaceutical", "LT": "Larsen & Toubro",
    "POLYCAB": "Polycab India", "DIXON": "Dixon Technologies", "CDSL": "Central Depository Services",
}
# Last closes and 30-Oct volume ratios are REAL (13:25 spike); history before that is a random walk.
LAST = {"RELIANCE": (1164.9, .97), "HDFCBANK": (692.8, .67), "ICICIBANK": (1398.0, .83),
        "BAJFINANCE": (939.1, 1.14), "INFY": (1185.0, .77), "PERSISTENT": (6048.0, 1.44),
        "KPITTECH": (530.25, .46), "BHARTIARTL": (1973.7, .8), "ITC": (265.6, .7), "TITAN": (4436.5, 1.44),
        "TRENT": (3017.3, 3.86), "ASIANPAINT": (2320.0, 1.73), "MARUTI": (11397.0, .56),
        "SUNPHARMA": (1777.7, 3.43), "LT": (3871.7, .83), "POLYCAB": (7787.0, .75),
        "DIXON": (11000.0, 1.99), "CDSL": (1263.0, 1.0)}


def _trading_days(n: int, end: dt.date) -> list[str]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= dt.timedelta(days=1)
    return out[::-1]


def prices() -> c.Prices:
    rnd = random.Random(7)
    days = _trading_days(250, dt.date(2026, 10, 30))
    syms = {}
    for s, (last_close, last_ratio) in LAST.items():
        closes = [last_close]
        for _ in range(len(days) - 1):
            closes.append(closes[-1] / (1 + rnd.gauss(0.0004, 0.015)))
        closes = [round(x, 2) for x in closes[::-1]]
        base = rnd.randint(1_000_000, 8_000_000)
        vols = [int(base * math.exp(rnd.gauss(0, 0.25))) for _ in days]
        vols[-1] = int(sum(vols[-21:-1]) / 20 * last_ratio)
        ret = [None] + [round((closes[i] / closes[i - 1] - 1) * 100, 2) for i in range(1, len(days))]
        vr = [None] * 20 + [round(vols[i] / (sum(vols[i - 20:i]) / 20), 2) for i in range(20, len(days))]
        syms[s] = c.SymbolPrices(name=NAMES[s], dates=days, close=closes, volume=vols, ret_pct=ret,
                                 vol_ratio=vr, high_52w=closes[-1] >= max(closes), low_52w=closes[-1] <= min(closes))
    return c.Prices(as_of=days[-1], symbols=syms)


def brief() -> c.Brief:
    nse = "https://nsearchives.nseindia.com/corporate/"
    items = [
        c.BriefItem(
            id="nse:mock-lt-results", symbol="LT", company=NAMES["LT"], filed_at="2026-10-30T17:40:00+05:30",
            headline="[MOCK] Financial results for the quarter ended September 30, 2026",
            exchange_category="Financial Result Updates", category="results", category_method="rule",
            materiality=88, tier="needs_you", reasons=["Results", "7% of portfolio"],
            summary="[MOCK] Revenue up, margin down; numbers below are invented for UI work.",
            filing_url=nse + "MOCK_LT_results.pdf", price_reaction_pct=None,
            card=c.ResultsCard(
                period="Q2 FY27 (Jul–Sep 2026) [MOCK NUMBERS]", basis="consolidated",
                metrics=[
                    c.ResultsMetric(name="Revenue", current=67000, prev_q=63000, year_ago=60000, qoq_pct=6.3, yoy_pct=11.7),
                    c.ResultsMetric(name="EBITDA", current=6600, prev_q=6300, year_ago=6200, qoq_pct=4.8, yoy_pct=6.5),
                    c.ResultsMetric(name="PBT", current=5400, prev_q=5000, year_ago=4900, qoq_pct=8.0, yoy_pct=10.2),
                    c.ResultsMetric(name="PAT", current=4000, prev_q=3700, year_ago=3600, qoq_pct=8.1, yoy_pct=11.1),
                ],
                checks=c.ResultsChecks(verbatim=True, identities=True, cross_check=None), verified=True,
                source=c.Source(label="Results filing p.2", kind="filing", url=nse + "MOCK_LT_results.pdf", page=2),
            ),
        ),
        c.BriefItem(
            id="nse:mock-kpit-cessation", symbol="KPITTECH", company=NAMES["KPITTECH"],
            filed_at="2026-10-31T18:25:33+05:30", headline="Cessation: Rajiv Lal, completion of tenure",
            exchange_category="Cessation", category="management_change", category_method="rule",
            materiality=52, tier="worth_knowing", reasons=["Director exit", "Completion of tenure"],
            summary=None, filing_url=nse + "KPITTECH_31102026182503_KPIT_Rajiv_Lal_Completion_of_Tenure-S.pdf",
            card=c.ManagementCard(
                direction="leaving", person="Rajiv Lal", role="[MOCK] Director (role to be extracted)",
                reason="Completion of tenure",
                source=c.Source(label="Filing p.1", kind="filing", page=1,
                                url=nse + "KPITTECH_31102026182503_KPIT_Rajiv_Lal_Completion_of_Tenure-S.pdf"),
            ),
        ),
        c.BriefItem(
            id="nse:mock-hdfc-director", symbol="HDFCBANK", company=NAMES["HDFCBANK"],
            filed_at="2026-10-01T18:23:52+05:30", headline="Change in Director(s): Anup Bagchi",
            exchange_category="Change in Director(s)", category="management_change", category_method="rule",
            materiality=78, tier="needs_you", reasons=["Board change", "8% of portfolio"],
            filing_url=nse + "HDFCBANK3_01102026182319_SE_Intimation-_Anup_Bagchi.pdf",
            card=c.ManagementCard(
                direction="joining", person="Anup Bagchi", role="[MOCK] Role to be extracted",
                profile="[MOCK] The brief profile will be quoted from Annexure I of this filing.",
                source=c.Source(label="Filing, Annexure I", kind="filing",
                                url=nse + "HDFCBANK3_01102026182319_SE_Intimation-_Anup_Bagchi.pdf"),
            ),
        ),
        c.BriefItem(
            id="nse:mock-lt-vyoma", symbol="LT", company=NAMES["LT"], filed_at="2026-10-31T13:00:35+05:30",
            headline="Extension of timeline: business transfer to Vyoma.AI and sale of L&T Network Services stake",
            exchange_category="General Updates", category="M&A", category_method="llm",
            materiality=62, tier="worth_knowing", reasons=["Subsidiary deal", "Timeline extended"],
            summary="[MOCK] Completion deadline extended for an intra-group transfer; no new deal terms.",
            filing_url=nse + "AB_31102026130022_SEIntimation_ExtensionofBTAVyoma_31102026.pdf",
        ),
    ]
    routine = [
        ("INFY", "Trading Window", "Closure of trading window"),
        ("INFY", "Copy of Newspaper Publication", "Newspaper advertisement of results"),
        ("DIXON", "Certificate under SEBI (Depositories and Participants) Regulations, 2018", "Reg 74(5) certificate"),
        ("RELIANCE", "Analysts/Institutional Investor Meet/Con. Call Updates", "Schedule of analyst meet"),
        ("TITAN", "ESOP/ESOS/ESPS", "Allotment of shares under ESOP"),
        ("ITC", "Trading Window", "Closure of trading window"),
    ]
    cats = {"Analysts/Institutional Investor Meet/Con. Call Updates": "investor_meetings"}
    for i, (s, ex, head) in enumerate(routine):
        items.append(c.BriefItem(
            id=f"nse:mock-routine-{i}", symbol=s, company=NAMES[s], filed_at=f"2026-10-3{i % 2}T1{i}:00:00+05:30",
            headline=head, exchange_category=ex, category=cats.get(ex, "unclassified"), category_method="rule",
            materiality=8 + i, tier="routine", reasons=["Routine"], filing_url=nse + f"MOCK_{i}.pdf"))
    items.sort(key=lambda x: x.filed_at, reverse=True)
    return c.Brief(generated_at=NOW, window_max_days=10, items=items)


def research_lt() -> c.ResearchPack:
    scr = c.Source(label="screener.in", kind="screener", url="https://www.screener.in/company/LT/consolidated/")
    tr = lambda q, p: c.Source(label=f"{q} transcript p.{p}", kind="transcript", url="https://example.invalid/mock.pdf", page=p)  # noqa: E731
    years = [f"FY{y}" for y in range(17, 27)]
    rev = [round(100000 * 1.1 ** i) for i in range(10)]
    return c.ResearchPack(
        symbol="LT", name=NAMES["LT"], sector="Capital Goods", status="ready", built_at=NOW, mock=True,
        snapshot=c.Snapshot(
            kpis=[c.Kpi(label="Revenue (TTM)", value=260000, unit="₹ cr", period="TTM [MOCK]", source=scr),
                  c.Kpi(label="EBITDA margin", value=10.4, unit="%", period="FY26 [MOCK]", source=scr),
                  c.Kpi(label="PAT (TTM)", value=16000, unit="₹ cr", period="TTM [MOCK]", source=scr),
                  c.Kpi(label="ROCE", value=15.0, unit="%", period="FY26 [MOCK]", source=scr)],
            years=years, revenue=rev, ebitda_margin_pct=[11.5, 11.2, 11.8, 11.0, 10.5, 10.9, 10.6, 10.3, 10.2, 10.4],
            cfo=[r * 0.06 for r in rev], pat=[r * 0.055 for r in rev], cash_conversion_pct=[109.1] * 10,
            debt_to_equity=1.1, business="[MOCK] Business description will be quoted from the annual report.",
        ),
        promises=c.Promises(
            scorecard=c.Scorecard(met=2, partly=1, missed=1, pending=1),
            items=[
                c.Promise(id="p1", said_in="Q4 FY26", target_period="FY27", metric="order_inflow_growth",
                          target_text="[MOCK] ~10% order inflow growth", target_low=10, target_high=10,
                          actual=None, verdict="pending", quote="[MOCK QUOTE] ...", source=tr("Q4 FY26", 6)),
                c.Promise(id="p2", said_in="Q4 FY25", target_period="FY26", metric="revenue_growth",
                          target_text="[MOCK] 15% revenue growth", target_low=15, target_high=15, actual=15.8,
                          verdict="met", quote="[MOCK QUOTE] ...", source=tr("Q4 FY25", 5)),
                c.Promise(id="p3", said_in="Q4 FY25", target_period="FY26", metric="ebitda_margin",
                          target_text="[MOCK] core margin ~8.5%", target_low=8.5, target_high=8.5, actual=7.9,
                          verdict="partly", quote="[MOCK QUOTE] ...", source=tr("Q4 FY25", 9)),
                c.Promise(id="p4", said_in="Q2 FY26", target_period="FY26", metric="order_inflow_growth",
                          target_text="[MOCK] 10% order inflow growth", target_low=10, target_high=10, actual=4.0,
                          verdict="missed", quote="[MOCK QUOTE] ...", source=tr("Q2 FY26", 4)),
                c.Promise(id="p5", said_in="Q1 FY27", target_period="FY27", metric="capex",
                          target_text="[MOCK] capex in line with plan", verdict="met", actual=None,
                          quote="[MOCK QUOTE] ...", source=tr("Q1 FY27", 11)),
            ],
            commentary=c.Commentary(text="[MOCK] Delivered on revenue; margin and order-inflow guidance slipped.",
                                    cites=["p2", "p3", "p4"]),
        ),
        documents=[c.DocumentRef(id="mock-doc", kind="transcript", period="Q1 FY27",
                                 title="[MOCK] Q1 FY27 earnings call transcript", url="https://example.invalid/mock.pdf")],
        build_log=[c.BuildStep(ts=NOW, step="mock data", status="done", detail="Hand-made for UI work")],
    )


def write_all() -> list[str]:
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    meta = c.Meta(generated_at=NOW, prices_as_of="2026-10-30", filings_as_of=NOW, mock=True,
                  sources={"prices": "mock (real last close)", "announcements": "mock"},
                  llm=c.LlmUsage(calls=0, cached=0))
    out = {"meta.json": meta, "brief.json": brief(), "prices.json": prices(), "research_LT.json": research_lt()}
    for name, model in out.items():
        (config.EXPORT_DIR / name).write_text(model.model_dump_json(indent=1 if name != "prices.json" else None),
                                              encoding="utf-8")
    return list(out)
