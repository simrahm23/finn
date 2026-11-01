"""screener.in company page -> standardised tables + document links (annual reports, concall transcripts).
The tables are screener's standardisation of the company's own filings; transcripts link to the exchange PDFs."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

from .. import net

BASE = "https://www.screener.in"


@dataclass
class Transcript:
    call_month: str               # "Jul 2026" (month of the call)
    quarter: Optional[str]        # quarter discussed, e.g. "Q1 FY27"
    url: str


@dataclass
class Company:
    symbol: str
    name: str
    url: str
    basis: str                                        # consolidated | standalone
    tables: dict[str, dict[str, dict[str, Optional[float]]]] = field(default_factory=dict)  # section -> row -> col -> v
    columns: dict[str, list[str]] = field(default_factory=dict)
    ratios: dict[str, str] = field(default_factory=dict)
    transcripts: list[Transcript] = field(default_factory=list)
    annual_reports: list[tuple[str, str]] = field(default_factory=list)   # (title, url)


def num(s: str | None) -> Optional[float]:
    if s is None:
        return None
    t = s.strip().replace(",", "").replace("%", "").replace("₹", "").replace("Cr.", "").strip()
    if t in ("", "-", "--"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def quarter_discussed(call_month: str) -> Optional[str]:
    """A call in Jul/Aug/Sep discusses Q1 of the fiscal year starting that April, etc. (Indian FY = Apr-Mar)."""
    m = re.match(r"([A-Z][a-z]{2})\w*\s+(\d{4})", call_month.strip())
    if not m or m.group(1) not in MONTHS:
        return None
    mo, y = MONTHS[m.group(1)], int(m.group(2))
    if mo <= 3:
        return f"Q3 FY{y % 100:02d}"
    if mo <= 6:
        return f"Q4 FY{y % 100:02d}"
    if mo <= 9:
        return f"Q1 FY{(y + 1) % 100:02d}"
    return f"Q2 FY{(y + 1) % 100:02d}"


def col_period(col: str, section: str) -> Optional[str]:
    """'Mar 2026' in annual tables -> 'FY26'; 'Sep 2026' in quarters -> 'Q2 FY27'; 'TTM' stays."""
    if col.strip().upper() == "TTM":
        return "TTM"
    m = re.match(r"([A-Z][a-z]{2})\s+(\d{4})", col.strip())
    if not m or m.group(1) not in MONTHS:
        return None
    mo, y = MONTHS[m.group(1)], int(m.group(2))
    if section == "quarters":
        q = {6: 1, 9: 2, 12: 3, 3: 4}.get(mo)
        fy = y + 1 if mo >= 4 else y
        return f"Q{q} FY{fy % 100:02d}" if q else None
    fy = y + 1 if mo >= 4 else y      # annual columns are usually Mar (FY end)
    return f"FY{fy % 100:02d}"


def parse(html: str, symbol: str, url: str, basis: str) -> Company:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    c = Company(symbol=symbol, name=h1.get_text(" ", strip=True) if h1 else symbol, url=url, basis=basis)

    for sec in ("quarters", "profit-loss", "balance-sheet", "cash-flow"):
        node = soup.find("section", id=sec)
        table = node.find("table") if node else None
        if not table or not table.find("thead"):
            continue
        heads = [th.get_text(" ", strip=True) for th in table.find("thead").find_all("th")][1:]
        periods = [col_period(h, sec) or h for h in heads]
        c.columns[sec] = periods
        rows = {}
        for tr in table.find("tbody").find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            name = re.sub(r"\s*\+\s*$", "", tds[0].get_text(" ", strip=True)).strip()
            rows[name] = {p: num(td.get_text(" ", strip=True)) for p, td in zip(periods, tds[1:])}
        c.tables[sec] = rows

    for li in soup.select("#top-ratios li"):
        n, v = li.select_one(".name"), li.select_one(".value") or li.select_one(".number")
        if n and v:
            c.ratios[n.get_text(" ", strip=True)] = v.get_text(" ", strip=True)

    docs = soup.find("section", id="documents")
    if docs:
        for li in docs.select(".concalls li") or []:
            link = next((a for a in li.find_all("a") if re.search(r"transcript", a.get_text(" ", strip=True), re.I)), None)
            if not link or not link.get("href"):
                continue
            label = li.get_text(" ", strip=True)
            m = re.search(r"([A-Z][a-z]{2})\w*\s+(\d{4})", label)
            month = f"{m.group(1)} {m.group(2)}" if m else ""
            c.transcripts.append(Transcript(month, quarter_discussed(month) if month else None, _abs(link["href"])))
        if not c.transcripts:   # fallback: any link whose text mentions a transcript
            for a in docs.find_all("a"):
                if re.search(r"transcript", a.get_text(" ", strip=True), re.I) and a.get("href"):
                    c.transcripts.append(Transcript("", None, _abs(a["href"])))
        for a in docs.select(".annual-reports a") or []:
            if a.get("href"):
                c.annual_reports.append((a.get_text(" ", strip=True), _abs(a["href"])))
    return c


def _abs(href: str) -> str:
    return href if href.startswith("http") else BASE + href


def fetch(symbol: str) -> Company:
    """Consolidated first; standalone if the consolidated page has no P&L (companies without subsidiaries)."""
    symbol = symbol.upper()
    last_err = None
    for basis, path in (("consolidated", f"/company/{symbol}/consolidated/"), ("standalone", f"/company/{symbol}/")):
        url = BASE + path
        try:
            r = net.client().get(url)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
        if r.status_code == 404:
            raise LookupError(f"{symbol} not found on screener.in")
        if r.status_code != 200:
            last_err = f"HTTP {r.status_code}"
            continue
        c = parse(r.text, symbol, url, basis)
        if c.tables.get("profit-loss", {}).get("Sales") or c.tables.get("profit-loss", {}).get("Revenue"):
            return c
    raise RuntimeError(f"screener.in: could not read {symbol} ({last_err})")


def fetch_basis(symbol: str, basis: str) -> Company:
    """The page for one basis only (consolidated | standalone), for like-for-like cross-checks."""
    symbol = symbol.upper()
    path = f"/company/{symbol}/consolidated/" if basis == "consolidated" else f"/company/{symbol}/"
    r = net.client().get(BASE + path)
    if r.status_code != 200:
        raise RuntimeError(f"screener {symbol} {basis}: HTTP {r.status_code}")
    return parse(r.text, symbol, BASE + path, basis)
