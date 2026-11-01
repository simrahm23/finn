"""The mocks must satisfy the contracts, and the TS mirror must name every Python field."""
import re

from finn import config, contracts, mocks


def test_mocks_validate():
    contracts.Brief.model_validate(mocks.brief().model_dump())
    contracts.Prices.model_validate(mocks.prices().model_dump())
    contracts.ResearchPack.model_validate(mocks.research_lt().model_dump())


def test_prices_arrays_aligned():
    for s, p in mocks.prices().symbols.items():
        n = len(p.dates)
        assert len(p.close) == len(p.volume) == len(p.ret_pct) == len(p.vol_ratio) == n, s


def test_ts_mirror_has_every_field():
    ts = (config.ROOT / "frontend" / "src" / "lib" / "types.ts").read_text(encoding="utf-8")
    for model in (contracts.BriefItem, contracts.ResultsCard, contracts.ManagementCard, contracts.SymbolPrices,
                  contracts.Snapshot, contracts.Promise, contracts.ResearchPack, contracts.Meta):
        for field in model.model_fields:
            assert re.search(rf"\b{field}\??:", ts), f"{model.__name__}.{field} missing from types.ts"
