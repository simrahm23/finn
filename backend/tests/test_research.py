"""Research pipeline on a synthetic screener page (same structure as screener.in) and a fake transcript."""
from finn.ingest import screener
from finn.research import promises, snapshot

HTML = """<html><body><h1>Larsen &amp; Toubro Ltd</h1>
<ul id="top-ratios"><li><span class="name">ROCE</span><span class="nowrap value"><span class="number">15.2</span> %</span></li></ul>
<section id="quarters"><table><thead><tr><th></th><th>Sep 2025</th><th>Jun 2026</th><th>Sep 2026</th></tr></thead><tbody>
<tr><td>Sales +</td><td>68,000</td><td>63,000</td><td>78,750</td></tr>
<tr><td>OPM %</td><td>10%</td><td>10%</td><td>9%</td></tr>
<tr><td>Net Profit +</td><td>4,700</td><td>4,300</td><td>5,915</td></tr></tbody></table></section>
<section id="profit-loss"><table><thead><tr><th></th><th>Mar 2025</th><th>Mar 2026</th><th>TTM</th></tr></thead><tbody>
<tr><td>Sales +</td><td>2,55,000</td><td>2,95,000</td><td>3,05,000</td></tr>
<tr><td>Operating Profit</td><td>26,000</td><td>29,500</td><td>30,000</td></tr>
<tr><td>OPM %</td><td>10%</td><td>10%</td><td>10%</td></tr>
<tr><td>Net Profit +</td><td>15,000</td><td>17,000</td><td>18,000</td></tr></tbody></table></section>
<section id="balance-sheet"><table><thead><tr><th></th><th>Mar 2026</th></tr></thead><tbody>
<tr><td>Equity Capital</td><td>275</td></tr><tr><td>Reserves</td><td>99,725</td></tr><tr><td>Borrowings +</td><td>1,10,000</td></tr></tbody></table></section>
<section id="cash-flow"><table><thead><tr><th></th><th>Mar 2025</th><th>Mar 2026</th></tr></thead><tbody>
<tr><td>Cash from Operating Activity +</td><td>18,000</td><td>15,300</td></tr></tbody></table></section>
<section id="documents"><div class="concalls"><ul>
<li><div>Jul 2026</div><a href="https://x/t_q1fy27.pdf">Transcript</a><a href="/ppt">PPT</a></li>
<li><div>May 2026</div><a href="https://x/t_q4fy26.pdf">Transcript</a></li></ul></div>
<div class="annual-reports"><ul><li><a href="https://x/ar26.pdf">Financial Year 2026 from bse</a></li></ul></div></section>
</body></html>"""


def company():
    return screener.parse(HTML, "LT", "https://www.screener.in/company/LT/consolidated/", "consolidated")


def test_parse_tables_and_docs():
    c = company()
    assert c.name.startswith("Larsen")
    assert c.columns["quarters"] == ["Q2 FY26", "Q1 FY27", "Q2 FY27"]
    assert c.columns["profit-loss"] == ["FY25", "FY26", "TTM"]
    assert c.tables["profit-loss"]["Sales"]["FY26"] == 295000.0
    assert [t.quarter for t in c.transcripts] == ["Q1 FY27", "Q4 FY26"]
    assert c.annual_reports[0][1] == "https://x/ar26.pdf"


def test_quarter_discussed():
    assert screener.quarter_discussed("Oct 2026") == "Q2 FY27"
    assert screener.quarter_discussed("Feb 2026") == "Q3 FY26"
    assert screener.quarter_discussed("May 2026") == "Q4 FY26"


def test_snapshot_maths():
    s = snapshot.build(company())
    assert s.years == ["FY25", "FY26"]
    assert s.cash_conversion_pct == [120.0, 90.0]         # CFO / PAT
    assert s.debt_to_equity == 1.1                        # 110000 / (275 + 99725)
    assert s.kpis[0].value == 305000.0 and s.kpis[-1].label == "ROCE" and s.kpis[-1].value == 15.2


def test_actuals_and_verdicts():
    c = company()
    reported = set(c.columns["profit-loss"]) | set(c.columns["quarters"])
    assert snapshot.actual(c, "revenue_growth", "FY26") == 15.7
    assert snapshot.actual(c, "revenue_growth", "Q2 FY27") == 15.8
    assert promises.verdict("revenue_growth", "FY26", 15, 15, c, reported) == ("met", 15.7)
    assert promises.verdict("revenue_growth", "FY26", 18, 18, c, reported) == ("partly", 15.7)
    assert promises.verdict("ebitda_margin", "Q2 FY27", 12, None, c, reported) == ("missed", 9.0)
    assert promises.verdict("revenue_growth", "FY27", 12, 15, c, reported) == ("pending", None)
    assert promises.verdict("order_inflow_growth", "FY26", 10, 10, c, reported) == ("unverifiable", None)
    assert promises.verdict("revenue_growth", "H2 FY27", 10, 10, c, reported) == ("pending", None)
    assert promises.verdict("order_inflow_growth", "FY27", 10, 12, c, reported) == ("pending", None)   # not over yet
    assert promises.verdict("revenue_growth", "", 10, 10, c, reported) == ("unverifiable", None)


def test_guidance_quotes_must_exist(monkeypatch, tmp_path):
    pages = ["Moderator: welcome", "CFO: We expect revenue growth of 15% for FY26 and margins of about 10%. Thank you.",
             "Analyst question"]
    monkeypatch.setattr(promises.documents, "fetch_pdf", lambda url, folder="_filings": tmp_path / "t.pdf")
    monkeypatch.setattr(promises.documents, "page_texts", lambda path, n=None: pages * 30)
    monkeypatch.setattr(promises.llm, "generate_json", lambda *a, **k: {"items": [
        {"metric": "revenue_growth", "target_period": "FY26", "target_low": 15, "target_high": 15, "unit": "%",
         "target_text": "15% revenue growth", "quote": "We expect revenue growth of 15% for FY26", "page": 3, "measurable": True},
        {"metric": "pat_growth", "target_period": "FY26", "target_low": 30, "target_high": 30, "unit": "%",
         "target_text": "invented", "quote": "Profit will double next year, guaranteed", "page": 2, "measurable": True}]})
    kept, _, note = promises.extract_from_transcript(screener.Transcript("May 2025", "Q4 FY25", "https://x/t.pdf"), "LT")
    assert len(kept) == 1 and kept[0]["page"] == 2            # wrong page corrected; invented quote dropped
    assert note == "1/2 statements kept"


def test_segment_promises_are_not_checked_against_company_totals():
    c = company()
    reported = set(c.columns["profit-loss"]) | set(c.columns["quarters"])
    assert promises.is_segment("company", "Core P&M margin of 8.5% for FY26")
    assert promises.is_segment("segment", "anything")
    assert not promises.is_segment("company", "Group revenue growth of 15% in FY26")
    assert promises.verdict("ebitda_margin", "FY26", 8.5, 8.5, c, reported, segment=True) == ("unverifiable", None)


def test_reported_actuals_fill_and_verify(monkeypatch):
    from finn import contracts as c
    src = c.Source(label="x", kind="transcript", url="u", page=1)
    mk = lambda i, lo: c.Promise(id=i, said_in="Q4 FY25", target_period="FY26", metric="order_inflow_growth",  # noqa: E731
                                 target_text="Order inflow growth 10%", target_low=lo, target_high=lo, verdict="unverifiable",
                                 quote="q", source=src)
    items = [mk("p1", 10), mk("p2", 10), mk("p3", 10)]
    pages = ["intro", "Group order inflow for FY26 grew 14.2% to a record level.", "Q&A"] * 2
    monkeypatch.setattr(promises.llm, "generate_json", lambda *a, **k: {"results": [
        {"id": "p1", "found": True, "value": 14.2, "quote": "Group order inflow for FY26 grew 14.2% to a record level.", "page": 2},
        {"id": "p2", "found": True, "value": 18.0, "quote": "Group order inflow for FY26 grew 14.2% to a record level.", "page": 2},
        {"id": "p3", "found": True, "value": 14.2, "quote": "Order inflow grew 14.2% as promised, a fabricated sentence.", "page": 2}]})
    n = promises.fill_reported_actuals(items, [screener.Transcript("May 2026", "Q4 FY26", "https://x/q4.pdf")],
                                       {"Q4 FY26": pages}, lambda *a: None)
    assert n == 1
    assert items[0].verdict == "met" and items[0].actual == 14.2 and items[0].actual_source.page == 2
    assert items[1].verdict == "unverifiable"        # number not in its quote -> rejected
    assert items[2].verdict == "unverifiable"        # quote not in the transcript -> rejected


def test_repeated_promises_count_once():
    from finn import contracts as c
    src = c.Source(label="x", kind="transcript", url="u", page=1)
    mk = lambda q: c.Promise(id=q, said_in=q, target_period="FY26", metric="revenue_growth", target_text="Double-digit",  # noqa: E731
                             target_low=10, target_high=None, verdict="met", actual=16.9, quote="q", source=src)
    out = promises.merge_repeats([mk("Q3 FY26"), mk("Q4 FY25"), mk("Q1 FY26"), mk("Q2 FY26")])
    assert len(out) == 1 and out[0].said_in == "Q4 FY25"
    assert out[0].repeated_in == ["Q1 FY26", "Q2 FY26", "Q3 FY26"]


def test_same_measure_guards():
    assert not promises.same_measure("revenue_growth", "Revenue growth of 3% to 3.5% in constant currency for FY26")
    assert not promises.same_measure("ebitda_margin", "Operating margin guidance of 20% to 22% for FY26")
    assert promises.same_measure("ebitda_margin", "EBITDA margin of 21% for the full year")
    assert not promises.same_measure("pat_growth", "Effective tax rate for FY26 likely to remain around 23%")
    assert promises.same_measure("revenue_growth", "Group revenues to grow at 15% in FY26")


def test_tracking_for_open_full_year_promise():
    c = company()          # quarters: Q2 FY26, Q1 FY27, Q2 FY27 -> FY27 Q1 present, Q1 FY26 missing
    through, val = snapshot.ytd(c, "revenue_growth", "FY27")
    assert val is None and promises.track(c, "revenue_growth", "FY27", 10) is None   # no prior-year Q1 -> say nothing
    c.tables["quarters"]["Sales"]["Q1 FY26"] = 58000.0
    c.columns["quarters"].insert(0, "Q1 FY26")
    through, val = snapshot.ytd(c, "revenue_growth", "FY27")
    assert through == "H1 FY27" and val == round((63000 + 78750) / (58000 + 68000) * 100 - 100, 1)
    t = promises.track(c, "revenue_growth", "FY27", 10)
    assert t.status == "on_track" and t.through == "H1 FY27"
    assert promises.track(c, "revenue_growth", "FY27", 20).status == "behind"
