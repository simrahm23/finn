"""Corporate announcements from NSE (via the `nse` package; confirmed in the 13:30 spike).
Network + normalising + storage only. Classification lives in signals/."""
from __future__ import annotations

import datetime as dt
import json

from .. import config, db

# NSE row fields seen in the spike: an_dt, desc, attchmntText, attchmntFile, symbol, sm_name, sm_isin, seq_id ...


def parse_nse_time(s: str) -> str:
    """'31-Oct-2026 13:00:35' -> '2026-10-31T13:00:35+05:30'"""
    return dt.datetime.strptime(s.strip(), "%d-%b-%Y %H:%M:%S").isoformat() + config.IST_OFFSET


def normalise_nse(row: dict) -> dict:
    text = " ".join(str(row.get("attchmntText") or "").split())
    return {
        "id": f"nse:{row.get('seq_id') or row.get('dt') or hash(text)}",
        "symbol": row["symbol"],
        "exchange": "NSE",
        "filed_at": parse_nse_time(row["an_dt"]),
        "headline": text or str(row.get("desc") or ""),
        "exchange_category": str(row.get("desc") or "").strip(),
        "attachment_url": row.get("attchmntFile") or "",
        "raw_json": json.dumps(row, default=str),
    }


def dedupe(rows: list[dict]) -> list[dict]:
    """Same filing can appear twice (re-uploads). Key on symbol + attachment, else symbol + headline + minute."""
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: x["filed_at"]):
        key = (r["symbol"], r["attachment_url"]) if r["attachment_url"] else (r["symbol"], r["headline"], r["filed_at"][:16])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def run(symbols: list[str] | None = None, days: int = 10, today: dt.date | None = None) -> dict:
    from nse import NSE
    symbols = symbols or config.portfolio_symbols()
    today = today or dt.date.today()
    frm = today - dt.timedelta(days=days)
    rows, names, errors = [], {}, {}
    (config.DATA_DIR / "cache").mkdir(parents=True, exist_ok=True)
    with NSE(download_folder=config.DATA_DIR / "cache") as n:
        for s in symbols:
            try:
                for raw in n.announcements(symbol=s, from_date=frm, to_date=today):
                    rows.append(normalise_nse(raw))
                    if raw.get("sm_name"):
                        names[s] = (raw["sm_name"], raw.get("sm_isin"))
            except Exception as e:  # noqa: BLE001
                errors[s] = f"{type(e).__name__}: {e}"
    rows = dedupe(rows)
    with db.session() as con:
        for r in rows:
            db.upsert(con, "announcements", r, ["id"])
        for s, (name, isin) in names.items():
            con.execute("UPDATE companies SET name=?, isin=? WHERE symbol=?", (name, isin, s))
        con.execute("INSERT INTO ingest_runs VALUES (?,?,?,?,?)",
                    (dt.datetime.now().isoformat(timespec="seconds"), "announcements:nse", int(not errors),
                     len(rows), json.dumps({"errors": errors, "from": frm.isoformat()})))
    per = {s: sum(r["symbol"] == s for r in rows) for s in symbols}
    return {"rows": len(rows), "per_symbol": per, "errors": errors, "from": frm.isoformat(), "to": today.isoformat()}
