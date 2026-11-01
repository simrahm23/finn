import pandas as pd
import pytest

from finn.ingest.prices import normalise
from finn.signals import price_volume as pv


def test_returns():
    assert pv.daily_returns_pct([100, 110, 99]) == [None, 10.0, -10.0]


def test_volume_ratio_excludes_today():
    vols = [100] * 20 + [300]
    r = pv.volume_ratios(vols, 20)
    assert r[:20] == [None] * 20
    assert r[20] == 3.0                       # 300 / mean(prev 20 = 100)


def test_volume_ratio_rolling_window():
    vols = [100] * 20 + [300, 100]
    # session 21: previous 20 = nineteen 100s + one 300 -> mean 110
    assert pv.volume_ratios(vols, 20)[21] == pytest.approx(round(100 / 110, 2))


def test_zero_average_is_none():
    assert pv.volume_ratios([0] * 21, 20)[20] is None


def test_52w_flags():
    assert pv.is_52w_high([1, 2, 3]) and not pv.is_52w_low([1, 2, 3])
    assert pv.is_52w_low([3, 2, 1])


def test_triggers():
    assert pv.triggers(-4.5, 1.0, 4, 2) == ["price"]
    assert pv.triggers(1.0, 2.0, 4, 2) == ["volume"]           # threshold is inclusive
    assert pv.triggers(None, None, 4, 2) == []


def test_normalise_yfinance_shape():
    idx = pd.to_datetime(["2026-10-29", "2026-10-30", "2026-10-31"])
    cols = pd.MultiIndex.from_product([["LT.NS"], ["Open", "High", "Low", "Close", "Adj Close", "Volume"]])
    frame = pd.DataFrame([[1, 2, 0.5, 1.5, 1.5, 1000], [1.5, 2, 1, 1.8, 1.8, float("nan")],
                          [None, None, None, None, None, None]], index=idx, columns=cols)
    out = normalise(frame, ["LT", "INFY"])
    assert [r["date"] for r in out["LT"]] == ["2026-10-29", "2026-10-30"]   # empty session dropped
    assert out["LT"][1]["volume"] == 0                                      # NaN volume -> 0
    assert out["INFY"] == []                                                # missing ticker -> empty
