"""Snapshot metrics, all computed in code from the screener tables. No model involved."""
from __future__ import annotations

from typing import Optional

from .. import contracts as c
from ..ingest.screener import Company

REVENUE_ROWS = ("Sales", "Revenue", "Total Income")         # banks show 'Revenue'
PROFIT_ROWS = ("Net Profit", "Profit after tax")
OP_ROWS = ("Operating Profit", "Financing Profit")


def row(company: Company, section: str, names: tuple[str, ...]) -> dict[str, Optional[float]]:
    t = company.tables.get(section, {})
    for n in names:
        if n in t:
            return t[n]
    return {}


def ratio_value(company: Company, *names: str) -> Optional[float]:
    for k, v in company.ratios.items():
        if any(k.strip().lower() == n.lower() for n in names):
            try:
                return float(v.replace(",", "").replace("%", "").replace("₹", "").replace("Cr.", "").split()[0])
            except (ValueError, IndexError):
                return None
    return None


def build(company: Company) -> c.Snapshot:
    src = c.Source(label="screener.in tables", kind="screener", url=company.url)
    missing = []
    years = [p for p in company.columns.get("profit-loss", []) if p.startswith("FY")][-10:]
    rev, opm, pat = row(company, "profit-loss", REVENUE_ROWS), row(company, "profit-loss", ("OPM %",)), \
        row(company, "profit-loss", PROFIT_ROWS)
    op = row(company, "profit-loss", OP_ROWS)
    cfo = row(company, "cash-flow", ("Cash from Operating Activity",))
    if not rev:
        missing.append("revenue")
    if not cfo:
        missing.append("cash flow")

    def margin(y):
        if opm.get(y) is not None:
            return opm[y]
        if op.get(y) is not None and rev.get(y):
            return round(op[y] / rev[y] * 100, 1)
        return None

    conv = []
    for y in years:
        a, b = cfo.get(y), pat.get(y)
        conv.append(round(a / b * 100, 0) if a is not None and b and b > 0 else None)

    bs = company.tables.get("balance-sheet", {})
    last_bs = (company.columns.get("balance-sheet") or [None])[-1]
    de = None
    if last_bs and "Borrowings" in bs:
        eq = (bs.get("Equity Capital", {}).get(last_bs) or 0) + (bs.get("Reserves", {}).get(last_bs) or 0)
        de = round(bs["Borrowings"][last_bs] / eq, 2) if eq > 0 and bs["Borrowings"].get(last_bs) is not None else None
    else:
        missing.append("debt to equity")

    last_fy = years[-1] if years else "FY"
    kpis = [
        c.Kpi(label="Revenue (TTM)", value=rev.get("TTM", rev.get(last_fy)), unit="₹ cr",
              period="TTM" if "TTM" in rev else last_fy, source=src),
        c.Kpi(label="Operating margin", value=margin(last_fy), unit="%", period=last_fy, source=src),
        c.Kpi(label="Net profit (TTM)", value=pat.get("TTM", pat.get(last_fy)), unit="₹ cr",
              period="TTM" if "TTM" in pat else last_fy, source=src),
    ]
    roce = ratio_value(company, "ROCE")
    roe = ratio_value(company, "ROE")
    if roce is not None:
        kpis.append(c.Kpi(label="ROCE", value=roce, unit="%", period="latest", source=src))
    elif roe is not None:
        kpis.append(c.Kpi(label="ROE", value=roe, unit="%", period="latest", source=src))

    return c.Snapshot(
        kpis=kpis, years=years, revenue=[rev.get(y) for y in years], ebitda_margin_pct=[margin(y) for y in years],
        cfo=[cfo.get(y) for y in years], pat=[pat.get(y) for y in years], cash_conversion_pct=conv,
        debt_to_equity=de, business=None, business_source=None, missing=missing,
    )


def actual(company: Company, metric: str, period: str) -> Optional[float]:
    """Delivered value for a promise, computed from reported numbers. None = can't verify from the tables."""
    if period.startswith("FY"):
        sec, cols = "profit-loss", company.columns.get("profit-loss", [])
    elif period.startswith("Q"):
        sec, cols = "quarters", company.columns.get("quarters", [])
    else:
        return None
    if period not in cols:
        return None
    prev = _prior(period)
    if metric == "revenue_growth":
        r = row(company, sec, REVENUE_ROWS)
        return _growth(r.get(period), r.get(prev))
    if metric == "pat_growth":
        r = row(company, sec, PROFIT_ROWS)
        return _growth(r.get(period), r.get(prev))
    if metric == "ebitda_margin":
        m = row(company, sec, ("OPM %",)).get(period)
        if m is not None:
            return m
        op, rv = row(company, sec, OP_ROWS).get(period), row(company, sec, REVENUE_ROWS).get(period)
        return round(op / rv * 100, 1) if op is not None and rv else None
    return None


def _prior(period: str) -> str:
    """Same period one year earlier: FY27 -> FY26, Q2 FY27 -> Q2 FY26."""
    if period.startswith("FY"):
        return f"FY{int(period[2:]) - 1:02d}"
    q, fy = period.split()
    return f"{q} FY{int(fy[2:]) - 1:02d}"


def _growth(cur, base):
    if cur is None or base is None or base <= 0:
        return None
    return round((cur / base - 1) * 100, 1)


def ytd(company: Company, metric: str, fy: str) -> tuple[Optional[str], Optional[float]]:
    """Year-to-date for an open fiscal year from the reported quarters, vs the same quarters a year earlier.
    Returns (through-label, value): ('H1 FY27', 15.8). Growth for revenue/PAT; margin = sum(op profit)/sum(sales)."""
    cols = company.columns.get("quarters", [])
    k = 0
    while k < 3 and f"Q{k + 1} {fy}" in cols:
        k += 1
    if k == 0:
        return None, None
    prior = f"FY{int(fy[2:]) - 1:02d}"
    cur_q = [f"Q{i} {fy}" for i in range(1, k + 1)]
    pri_q = [f"Q{i} {prior}" for i in range(1, k + 1)]
    through = {1: f"Q1 {fy}", 2: f"H1 {fy}", 3: f"9M {fy}"}[k]

    def total(rows, qs):
        vals = [rows.get(q) for q in qs]
        return None if any(v is None for v in vals) else sum(vals)

    if metric in ("revenue_growth", "pat_growth"):
        rows = row(company, "quarters", REVENUE_ROWS if metric == "revenue_growth" else PROFIT_ROWS)
        return through, _growth(total(rows, cur_q), total(rows, pri_q))
    if metric == "ebitda_margin":
        op, rv = total(row(company, "quarters", OP_ROWS), cur_q), total(row(company, "quarters", REVENUE_ROWS), cur_q)
        if op is not None and rv:
            return through, round(op / rv * 100, 1)
        opm = [row(company, "quarters", ("OPM %",)).get(q) for q in cur_q]
        return (through, round(sum(opm) / len(opm), 1)) if all(v is not None for v in opm) else (None, None)
    return None, None
