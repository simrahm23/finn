from finn.extract import validate as v
from finn.extract.management import relevant_text
from finn.extract.results import build_card, pick_page

# A synthetic page in SEBI layout (invented numbers, Rs in lakh).
PAGE = """STATEMENT OF CONSOLIDATED UNAUDITED FINANCIAL RESULTS FOR THE QUARTER ENDED 30 SEPTEMBER 2026
(Rs in lakh)  Quarter ended 30.09.2026  30.06.2026  30.09.2025  Half year ended
1 Revenue from operations 1,20,000.00 1,10,000.00 1,00,000.00 2,30,000.00
2 Other income 2,000.00 1,500.00 1,000.00
Finance costs 3,000.00 3,000.00 2,500.00
Depreciation and amortisation expense 5,000.00 4,800.00 4,500.00
Profit before tax 20,000.00 18,000.00 15,000.00
Total tax expense 5,000.00 4,500.00 3,750.00
Profit for the period 15,000.00 13,500.00 11,250.00"""

RAW = {"found": True, "basis": "consolidated", "unit": "lakh", "current_period_end": "2026-09-30", "lines": {
    "revenue": {"cur": "1,20,000.00", "prev": "1,10,000.00", "yago": "1,00,000.00"},
    "other_income": {"cur": "2,000.00", "prev": "1,500.00", "yago": "1,000.00"},
    "finance_costs": {"cur": "3,000.00", "prev": "3,000.00", "yago": "2,500.00"},
    "depreciation": {"cur": "5,000.00", "prev": "4,800.00", "yago": "4,500.00"},
    "pbt": {"cur": "20,000.00", "prev": "18,000.00", "yago": "15,000.00"},
    "tax": {"cur": "5,000.00", "prev": "4,500.00", "yago": "3,750.00"},
    "pat": {"cur": "15,000.00", "prev": "13,500.00", "yago": "11,250.00"}}}


def test_parse_number():
    assert v.parse_number("1,23,456.78") == 123456.78
    assert v.parse_number("(12.40)") == -12.4
    assert v.parse_number("-") is None and v.parse_number("") is None


def test_quarter_label():
    assert v.quarter_label("2026-09-30") == "Q2 FY27 (Jul–Sep 2026)"
    assert v.quarter_label("2027-03-31") == "Q4 FY27 (Jan–Mar 2027)"
    assert v.quarter_label("2026-12-31") == "Q3 FY27 (Oct–Dec 2026)"


def test_pct_change_guards():
    assert v.pct_change(110, 100) == 10.0
    assert v.pct_change(10, -5) is None and v.pct_change(10, 0) is None


def test_pick_page():
    assert pick_page(["Cover letter to exchange", PAGE, "Notes"]) == 1
    assert pick_page(["Newspaper advertisement only"]) is None


def test_card_values_and_checks():
    card = build_card(RAW, PAGE, "https://x/r.pdf", 2, lender=False)
    m = {x.name: x for x in card.metrics}
    assert m["Revenue"].current == 1200.0                       # 1,20,000 lakh = 1,200 crore
    assert m["Revenue"].qoq_pct == 9.1 and m["Revenue"].yoy_pct == 20.0
    assert m["EBITDA"].current == 260.0                         # (20000 + 3000 + 5000 - 2000) lakh
    assert card.verified and card.period.startswith("Q2 FY27")
    assert card.source.page == 2


def test_card_rejects_numbers_not_on_page():
    bad = {**RAW, "lines": {**RAW["lines"], "pat": {"cur": "99,999.00", "prev": "13,500.00", "yago": "11,250.00"}}}
    card = build_card(bad, PAGE, "u", 2, lender=False)
    assert card.checks.verbatim is False and card.checks.identities is False and card.verified is False


def test_lender_has_no_ebitda():
    card = build_card(RAW, PAGE, "u", 2, lender=True)
    assert [x for x in card.metrics if x.name == "EBITDA"][0].applicable is False


def test_management_annexure_page_kept():
    texts = ["Intimation of appointment", "Details as per SEBI circular", "Notice of AGM", "Annexure I Brief profile of Mr X"]
    text, page = relevant_text(texts)
    assert "Brief profile" in text and page == 4


def test_cross_check_catches_misread_columns():
    from finn.extract.cards import cross_check
    card = {"period": "Q2 FY27 (Jul–Sep 2026)", "metrics": [{"name": "Revenue", "current": 25483.0, "year_ago": 45000.0}]}
    assert cross_check(card, {"Q2 FY27": 46000.0, "Q2 FY26": 44000.0}) is False      # passes page checks, fails source 2
    ok = {"period": "Q2 FY27 (Jul–Sep 2026)", "metrics": [{"name": "Revenue", "current": 21793.64, "year_ago": 14855.0}]}
    assert cross_check(ok, {"Q2 FY27": 21794.0, "Q2 FY26": 14855.0}) is True
    assert cross_check(ok, {"Q1 FY27": 1.0}) is None                                  # not posted yet: unknown, not failed
