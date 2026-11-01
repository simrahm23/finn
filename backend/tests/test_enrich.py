import json
import sys
import types

from finn.signals.enrich import numbers_grounded
from finn.signals.materiality import reaction_session, score


def test_ordering():
    cfo_exit = score("management_change", "top_role", "Resignation of CFO", 5, None, None)
    results = score("results", None, "Q2 results", 7, None, None)
    esop = score("unclassified", "routine", "ESOP allotment", 8, 9.0, 5.0)
    indep = score("management_change", "other_role", "Cessation of independent director", 4, None, None)
    assert cfo_exit[0] > indep[0] > esop[0]
    assert cfo_exit[1] == "needs_you"
    assert results[1] == "worth_knowing"                          # in-line results are not urgent
    assert esop[1] == "routine"                                   # routine never escalates
    assert "Top exit" in cfo_exit[2]


def test_price_and_volume_chips():
    s, tier, chips = score("press_release", None, "Order win", 5, 5.4, 3.86)
    assert "Move +5.4%" in chips and "Vol 3.9×" in chips
    assert s == 40 + 10 + 5 + 2.5


def test_results_surprise_and_minor_ma():
    card = {"kind": "results", "verified": True, "metrics": [{"name": "PAT", "yoy_pct": 26.2}]}
    s, tier, chips = score("results", None, "Q2 results", 7, None, 3.2, card=card)
    assert tier == "needs_you" and "PAT +26% YoY" in chips          # 70 + 10 surprise + 5 vol + 3.5
    s2, tier2, chips2 = score("M&A", None, "incorporated a wholly owned subsidiary in Canada", 5, None, None)
    assert tier2 == "worth_knowing" and chips2[0] == "Group restructuring"
    s3, *_ = score("press_release", None, "Order win", 5, 5.4, 3.86, market_boost=False)
    assert s3 == 42.5


def test_reaction_session():
    dates = ["2026-10-29", "2026-10-30"]
    assert reaction_session("2026-10-29T10:00:00+05:30", dates) == "2026-10-29"      # before close
    assert reaction_session("2026-10-29T17:40:00+05:30", dates) == "2026-10-30"      # after close -> next
    assert reaction_session("2026-10-31T13:00:00+05:30", dates) is None              # weekend, no session yet


def test_numbers_grounded():
    assert numbers_grounded("Order worth 1,250 crore won", "received an order of Rs 1250 crore")
    assert not numbers_grounded("Profit up 18%", "profit increased")
    assert numbers_grounded("New CFO appointed", "")


def test_llm_cache_second_call_free(tmp_path, monkeypatch):
    from finn import config, db
    from finn.llm import client
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "x")
    monkeypatch.setattr(client, "RPM", 6000)
    db.init_db(tmp_path / "t.db")
    calls = []

    class Models:
        def generate_content(self, model, contents, config):
            calls.append(model)
            return types.SimpleNamespace(text=json.dumps({"results": []}),
                                         usage_metadata=types.SimpleNamespace(prompt_token_count=10, candidates_token_count=2))

    genai = types.ModuleType("google.genai")
    genai.Client = lambda api_key: types.SimpleNamespace(models=Models())
    gtypes = types.ModuleType("google.genai.types")
    gtypes.GenerateContentConfig = lambda **k: k
    genai.types = gtypes
    google = types.ModuleType("google")
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", gtypes)

    client.generate_json("classify", {"items": [1]}, {"type": "object"})
    client.generate_json("classify", {"items": [1]}, {"type": "object"})
    assert len(calls) == 1
    u = client.usage()
    assert u["calls"] == 2 and u["cached"] == 1 and u["tokens_in"] == 10


def test_unverified_card_gives_no_surprise():
    card = {"kind": "results", "verified": False, "metrics": [{"name": "PAT", "yoy_pct": 538.0}]}
    s, tier, chips = score("results", None, "Q2 results", 0, None, None, card=card)
    assert s == 70 and not any("PAT" in c for c in chips)


def test_morning_note_numbers_must_come_from_the_cards():
    from finn.signals.note import numbers_ok
    src = '{"chips": ["PAT +26% YoY", "Vol 3.2×"], "results": {"Revenue": {"current_cr": 78749.94, "yoy_pct": 15.8}}}'
    assert numbers_ok("L&T profit rose 26% on 3.2× volume; revenue +15.8%.", src)
    assert not numbers_ok("L&T profit rose 30%.", src)
    assert numbers_ok("Trent's chairman retires.", src)


def test_note_ignores_period_labels_and_years():
    from finn.signals.note import numbers_ok
    src = '{"chips": ["PAT +26% YoY"]}'
    assert numbers_ok("In Q2 FY27, L&T's profit rose 26%; results for September 2026.", src)
    assert not numbers_ok("In Q2 FY27, profit rose 31%.", src)
