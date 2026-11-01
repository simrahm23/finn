from finn.ingest.announcements import dedupe, normalise_nse, parse_nse_time
from finn.signals.classify_rules import classify

# Shape copied from the real NSE row seen in the 13:30 spike (LT, 31 Oct 2026).
NSE_ROW = {
    "an_dt": "31-Oct-2026 13:00:35", "desc": "General Updates", "symbol": "LT", "seq_id": "123",
    "attchmntFile": "https://nsearchives.nseindia.com/corporate/AB_31102026130022_SEIntimation_ExtensionofBTAVyoma_31102026.pdf",
    "attchmntText": "Updates on the Business Transfer Agreement with Vyoma.AI Limited (Vyoma), Wholly owned Subsidiary of "
                    "the Company and Share Purchase Agreement towards sale of entire stake held in L&T Network Services "
                    "Private Limited to Vyoma   Extension of timeline of completion",
    "sm_name": "Larsen & Toubro Limited",
}


def test_time_parse():
    assert parse_nse_time("31-Oct-2026 13:00:35") == "2026-10-31T13:00:35+05:30"


def test_normalise():
    r = normalise_nse(NSE_ROW)
    assert r["id"] == "nse:123" and r["exchange_category"] == "General Updates"
    assert "  " not in r["headline"]                     # whitespace collapsed


def test_dedupe_same_attachment():
    a = normalise_nse(NSE_ROW)
    b = {**a, "id": "nse:124"}
    assert len(dedupe([a, b])) == 1


def cat(desc, text=""):
    r = classify(desc, text)
    return None if r is None else (r.category, r.sub)


def test_routine():
    assert cat("Trading Window") == ("unclassified", "routine")
    assert cat("Certificate under SEBI (Depositories and Participants) Regulations, 2018") == ("unclassified", "routine")


def test_results_and_board_meetings():
    assert cat("Financial Result Updates", "Results for quarter ended Sep 2026")[0] == "results"
    assert cat("Outcome of Board Meeting", "approved the unaudited financial results")[0] == "results"
    assert cat("Board Meeting Intimation", "meeting will be held to consider results") == ("unclassified", "board_meeting_notice")
    assert cat("Outcome of Board Meeting", "Board approved a new policy") is None          # ambiguous -> LLM


def test_management_roles():
    assert cat("Cessation", "Rajiv Lal completion of tenure as Independent Director") == ("management_change", "other_role")
    assert cat("Resignation", "Resignation of Chief Financial Officer") == ("management_change", "top_role")
    assert cat("Change in Director(s)", "Appointment of Anup Bagchi") == ("management_change", "other_role")
    assert cat("Change in Director(s)", "Appointment of statutory auditor") != ("management_change", "other_role")


def test_earnings_call_and_others():
    assert cat("Analysts/Institutional Investor Meet/Con. Call Updates", "Transcript of earnings conference call") == ("earnings_call", "transcript")
    assert cat("Analysts/Institutional Investor Meet/Con. Call Updates", "Schedule of meeting")[0] == "investor_meetings"
    assert cat("Credit Rating", "CRISIL reaffirmed AAA") == ("credit_rating", "reaffirm")
    assert cat("Credit Rating", "Rating downgraded to AA") == ("credit_rating", "downgrade")


def test_general_updates_keywords():
    assert cat("General Updates", NSE_ROW["attchmntText"])[0] == "M&A"
    assert cat("General Updates", "Clarification on news item") is None


def test_esop_and_debt():
    assert cat("Allotment of Securities", "allotment of 21098 securities pursuant to ESOP/ESPS") == ("unclassified", "routine")
    assert cat("Allotment of Securities", "allotment of 2,06,950 Non Convertible Debentures") == ("fund_raise", "debt")
    assert cat("Allotment of Securities", "allotment pursuant to Qualified Institutions Placement") == ("fund_raise", None)


def test_gold_set_patterns():
    inv = "Analysts/Institutional Investor Meet/Con. Call Updates"
    assert cat(inv, "Schedule of Conference Call to be held on 4 Nov 2026")[0] == "earnings_call"
    assert cat(inv, "Link of Recording of the earnings call")[0] == "earnings_call"
    assert cat(inv, "Investor Presentation for Q2 FY27")[0] == "results"
    assert cat(inv, "Schedule of analyst meet with Fidelity")[0] == "investor_meetings"
    assert cat("Press Release", "Press Release on the performance of the Company for the quarter ended September 30, 2026")[0] == "results"
    assert cat("Copy of Newspaper Publication", "copy of newspaper advertisement of financial results") == ("results", "routine")
    assert cat("Copy of Newspaper Publication", "notice of postal ballot") == ("unclassified", "routine")
