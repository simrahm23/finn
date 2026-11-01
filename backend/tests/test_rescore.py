import json

from finn import config, db
from finn.signals import enrich


def test_boost_once_and_related_cap(tmp_path, monkeypatch):
    path = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init_db(path)
    card = {"kind": "results", "metrics": [{"name": "PAT", "yoy_pct": 8.6}], "verified": True}
    with db.session() as con:
        for d, close in (("2026-10-29", 100), ("2026-10-30", 105.4)):
            db.upsert(con, "prices_daily", {"symbol": "TRENT", "date": d, "open": 1, "high": 1, "low": 1, "close": close,
                                            "volume": 100, "source": "t"}, ["symbol", "date"])
        rows = [("a", "results", None, json.dumps(card)), ("b", "results", None, None),
                ("c", "management_change", "top_role", None), ("d", "unclassified", "routine", None)]
        for i, cat, sub, cj in rows:
            db.upsert(con, "announcements", {"id": i, "symbol": "TRENT", "exchange": "NSE", "filed_at": "2026-10-29T17:00:00+05:30",
                                             "headline": "Retirement of Chairman" if cat == "management_change" else "Results",
                                             "exchange_category": "", "attachment_url": "", "raw_json": "{}"}, ["id"])
            db.upsert(con, "ann_enrichment", {"ann_id": i, "category": cat, "method": "rule", "card_json": cj,
                                              "reasons_json": json.dumps({"sub": sub})}, ["ann_id"])
        enrich.run_materiality(con)
        got = {r["ann_id"]: (r["materiality"], r["tier"], json.loads(r["reasons_json"])["chips"])
               for r in con.execute("SELECT * FROM ann_enrichment")}
    boosted = [k for k, v in got.items() if any(c.startswith("Move") for c in v[2])]
    assert boosted == ["a"]                                   # the results filing carries the +5.4% move, alone
    assert got["b"][0] <= 55 and "Related filing" in got["b"][2]   # 2nd results filing capped
    assert got["a"][1] == "needs_you"                         # results + the move it explains
    assert got["c"][1] == "needs_you" and not any(c.startswith("Move") for c in got["c"][2])
    assert got["d"][1] == "routine"
