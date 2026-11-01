import datetime as dt

from finn import contracts, db, export


def test_build_prices_end_to_end(tmp_path):
    path = tmp_path / "t.db"
    db.init_db(path)
    start = dt.date(2026, 9, 1)
    with db.session(path) as con:
        for i in range(30):
            d = (start + dt.timedelta(days=i)).isoformat()
            db.upsert(con, "prices_daily", {"symbol": "LT", "date": d, "open": 1, "high": 1, "low": 1,
                                            "close": 100 + i, "volume": 300 if i == 29 else 100,
                                            "source": "test"}, ["symbol", "date"])
            if i < 29:   # INFY misses the last session -> stale
                db.upsert(con, "prices_daily", {"symbol": "INFY", "date": d, "open": 1, "high": 1, "low": 1,
                                                "close": 50, "volume": 10, "source": "test"}, ["symbol", "date"])
    with db.session(path) as con:
        p = export.build_prices(con, ["LT", "INFY", "TCS"])
    contracts.Prices.model_validate(p.model_dump())
    assert p.as_of == "2026-09-30"
    assert set(p.symbols) == {"LT", "INFY"}                 # no data -> left out, not faked
    assert p.symbols["LT"].vol_ratio[-1] == 3.0
    assert p.symbols["LT"].high_52w is True
    assert p.symbols["INFY"].stale is True and p.symbols["LT"].stale is False
