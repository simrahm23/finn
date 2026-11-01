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


def build_brief(con, window_days: int = 10) -> contracts.Brief:
    import json
    names = {r["symbol"]: r["name"] for r in con.execute("SELECT symbol, name FROM companies")}
    rows = con.execute("SELECT a.*, e.category, e.method, e.materiality, e.tier, e.reasons_json, e.summary, e.card_json "
                       "FROM announcements a JOIN ann_enrichment e ON e.ann_id=a.id WHERE e.tier IS NOT NULL "
                       "ORDER BY a.filed_at DESC").fetchall()
    items = []
    for r in rows:
        meta = json.loads(r["reasons_json"] or "{}")
        card = json.loads(r["card_json"]) if r["card_json"] else None
        items.append(contracts.BriefItem(
            id=r["id"], symbol=r["symbol"], company=_short(names.get(r["symbol"]) or r["symbol"]),
            filed_at=r["filed_at"], headline=r["headline"], exchange_category=r["exchange_category"] or "",
            category=r["category"], category_method=r["method"], materiality=r["materiality"] or 0,
            tier=r["tier"], reasons=meta.get("chips", []), summary=r["summary"], filing_url=r["attachment_url"] or "",
            price_reaction_pct=meta.get("reaction_pct"), card=card,
        ))
    return contracts.Brief(generated_at=_now(), window_max_days=window_days, items=items)


def build_meta(con, prices: contracts.Prices | None) -> contracts.Meta:
    from .llm import client as llm
    last = con.execute("SELECT MAX(filed_at) FROM announcements").fetchone()[0]
    return contracts.Meta(generated_at=_now(), prices_as_of=prices.as_of if prices else None, filings_as_of=last,
                          mock=False, sources={"prices": "yfinance (NSE bhavcopy fallback)", "announcements": "NSE",
                                               "models": f"{config.MODEL_LITE} / {config.MODEL_FLASH}"},
                          llm=contracts.LlmUsage(**llm.usage()))


def _short(name: str) -> str:
    for suffix in (" Limited", " Ltd.", " Ltd"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _now() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds")


def write_all(window_days: int = 10) -> dict:
    """prices.json + brief.json + meta.json. research_*.json mocks stay until the live API replaces them (A12)."""
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    with db.session() as con:
        prices = build_prices(con)
        brief = build_brief(con, window_days)
        meta = build_meta(con, prices)
    (config.EXPORT_DIR / "prices.json").write_text(prices.model_dump_json(), encoding="utf-8")
    (config.EXPORT_DIR / "brief.json").write_text(brief.model_dump_json(indent=1), encoding="utf-8")
    (config.EXPORT_DIR / "meta.json").write_text(meta.model_dump_json(indent=1), encoding="utf-8")
    return {"items": len(brief.items), "prices_as_of": prices.as_of, "llm": meta.llm.model_dump()}


def write_prices() -> contracts.Prices:
    with db.session() as con:
        prices = build_prices(con)
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (config.EXPORT_DIR / "prices.json").write_text(prices.model_dump_json(), encoding="utf-8")
    return prices
