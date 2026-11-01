"""End-of-day prices: yfinance (primary), NSE bhavcopy for the latest day (fallback).
Talks to the network and writes `prices_daily`. No scoring here."""
from __future__ import annotations

import datetime as dt
import json
import math
import time

import pandas as pd

from .. import config, db

SOURCE = "yfinance"


def normalise(frame: pd.DataFrame, symbols: list[str]) -> dict[str, list[dict]]:
    """yf.download(group_by='ticker') frame -> {symbol: [row, ...]} oldest first.
    Drops sessions with no close. Volume NaN -> 0."""
    out: dict[str, list[dict]] = {}
    for s in symbols:
        t = f"{s}.NS"
        if t not in frame.columns.get_level_values(0):
            out[s] = []
            continue
        sub = frame[t].dropna(subset=["Close"])
        rows = []
        for idx, r in sub.iterrows():
            vol = r.get("Volume")
            rows.append({
                "symbol": s, "date": pd.Timestamp(idx).date().isoformat(),
                "open": _f(r.get("Open")), "high": _f(r.get("High")), "low": _f(r.get("Low")),
                "close": round(float(r["Close"]), 2),
                "volume": 0 if vol is None or (isinstance(vol, float) and math.isnan(vol)) else int(vol),
                "source": SOURCE,
            })
        out[s] = rows
    return out


def _f(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 2)


def fetch_yfinance(symbols: list[str], days: int = 400, retries: int = 3) -> pd.DataFrame:
    import warnings
    warnings.filterwarnings("ignore", module="yfinance")   # pandas deprecation noise from inside yfinance
    import yfinance as yf
    last_err = None
    for attempt in range(retries):
        try:
            df = yf.download([f"{s}.NS" for s in symbols], period=f"{days}d", interval="1d",
                             group_by="ticker", auto_adjust=False, progress=False, threads=True)
            if not df.empty:
                return df
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(2 ** attempt)
    raise RuntimeError(f"yfinance failed after {retries} tries: {last_err}")


def fetch_bhavcopy_day(day: dt.date, symbols: list[str]) -> dict[str, dict]:
    """Fallback for one session from NSE's daily bhavcopy CSV. Column names vary across NSE's
    formats, so we look for them by candidates."""
    from nse import NSE
    with NSE(download_folder=config.DATA_DIR / "cache") as n:
        path = n.equity_bhavcopy(day)
    df = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in df.columns}
    pick = lambda *names: next((cols[n] for n in names if n in cols), None)  # noqa: E731
    sym_c, ser_c = pick("tckrsymb", "symbol"), pick("sctysrs", "series")
    close_c, vol_c = pick("clspric", "close"), pick("ttltradgvol", "tottrdqty")
    o_c, h_c, l_c = pick("opnpric", "open"), pick("hghpric", "high"), pick("lwpric", "low")
    if ser_c:
        df = df[df[ser_c].astype(str).str.strip() == "EQ"]
    out = {}
    for _, r in df[df[sym_c].isin(symbols)].iterrows():
        out[r[sym_c]] = {"symbol": r[sym_c], "date": day.isoformat(), "open": _f(r[o_c]), "high": _f(r[h_c]),
                         "low": _f(r[l_c]), "close": round(float(r[close_c]), 2), "volume": int(r[vol_c]),
                         "source": "nse_bhavcopy"}
    return out


def run(symbols: list[str] | None = None, days: int = 400) -> dict:
    """Ingest prices for the portfolio. Returns a summary; also logged to `ingest_runs`."""
    symbols = symbols or config.portfolio_symbols()
    summary = {"ok": [], "empty": [], "fallback": [], "error": None}
    by_symbol: dict[str, list[dict]] = {s: [] for s in symbols}
    try:
        by_symbol = normalise(fetch_yfinance(symbols, days), symbols)
    except Exception as e:  # noqa: BLE001
        summary["error"] = str(e)

    # Fallback: any symbol with no rows, or missing the latest session, gets the bhavcopy day.
    latest = max((r[-1]["date"] for r in by_symbol.values() if r), default=None)
    need = [s for s, r in by_symbol.items() if not r or r[-1]["date"] != latest]
    if need:
        day = dt.date.fromisoformat(latest) if latest else _last_weekday(dt.date.today())
        try:
            for s, row in fetch_bhavcopy_day(day, need).items():
                by_symbol[s].append(row)
                summary["fallback"].append(s)
        except Exception as e:  # noqa: BLE001
            summary["error"] = (summary["error"] or "") + f" | bhavcopy: {e}"

    with db.session() as con:
        for s, rows in by_symbol.items():
            for row in rows:
                db.upsert(con, "prices_daily", row, ["symbol", "date"])
            (summary["ok"] if rows else summary["empty"]).append(s)
        con.execute("INSERT INTO ingest_runs VALUES (?,?,?,?,?)",
                    (dt.datetime.now().isoformat(timespec="seconds"), "prices", int(not summary["empty"]),
                     sum(len(r) for r in by_symbol.values()), json.dumps(summary)))
    summary["latest"] = latest
    return summary


def _last_weekday(d: dt.date) -> dt.date:
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d
