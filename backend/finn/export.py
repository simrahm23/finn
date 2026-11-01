"""Builds the static push JSON (prices.json now; brief.json + meta.json at A7) from SQLite."""
from __future__ import annotations

from . import config, contracts, db
from .signals import price_volume as pv

SESSIONS_SHOWN = 250   # ~1 year in the file; metrics are computed on the full history first


def build_prices(con, symbols: list[str] | None = None) -> contracts.Prices:
    symbols = symbols or config.portfolio_symbols()
    names = {r["symbol"]: r["name"] for r in con.execute("SELECT symbol, name FROM companies")}
    series = {}
    for s in symbols:
        rows = con.execute("SELECT date, close, volume FROM prices_daily WHERE symbol=? ORDER BY date", (s,)).fetchall()
        if rows:
            series[s] = rows
    if not series:
        raise RuntimeError("No prices in the database. Run `python -m finn.pipeline prices` first.")
    as_of = max(r[-1]["date"] for r in series.values())
    out = {}
    for s, rows in series.items():
        dates = [r["date"] for r in rows]
        close = [r["close"] for r in rows]
        vol = [int(r["volume"] or 0) for r in rows]
        ret = pv.daily_returns_pct(close)
        vr = pv.volume_ratios(vol, 20)
        k = -SESSIONS_SHOWN
        out[s] = contracts.SymbolPrices(
            name=names.get(s) or s, dates=dates[k:], close=close[k:], volume=vol[k:], ret_pct=ret[k:],
            vol_ratio=vr[k:], high_52w=pv.is_52w_high(close), low_52w=pv.is_52w_low(close),
            stale=dates[-1] != as_of,
        )
    return contracts.Prices(as_of=as_of, lookback_sessions=20, symbols=out)


def write_prices() -> contracts.Prices:
    with db.session() as con:
        prices = build_prices(con)
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (config.EXPORT_DIR / "prices.json").write_text(prices.model_dump_json(), encoding="utf-8")
    return prices
