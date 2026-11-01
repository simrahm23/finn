**To:** assessment@enam.com
**Subject:** ENAM - IIT screening - 2027

Hello ENAM team,

Please find my submission for the FINN build challenge.

- **Live app (open on a phone):** [LIVE LINK]
- **Repository:** https://github.com/simrahm23/finn
- **AI build history:** [LINKS]

**What I built.** FINN is a triage inbox for a portfolio, not a dashboard. Across 18 holdings, 120 NSE filings came in over the last 10 days; FINN puts 15 in "Needs you", explains each with reason chips ("Results · PAT +26% YoY · Vol 3.2×"), and folds the routine paperwork into one line. Results filings open as a first-cut card (Revenue, EBITDA, PBT, PAT, QoQ and YoY), and management changes show who is joining or leaving, with the incoming person's profile quoted from the filing's own annexure. You set what "unusual" means for price and volume, and see how many alerts your settings would have produced.

The push side hands off to the pull side: "Dig in: did they deliver?" opens a **Promise Tracker** built from the last six earnings calls. For L&T, "group order inflows to grow 10% in FY26" is **met** (10.0%, as reported on the Q4 FY26 call) and "group revenues to grow 15% in FY26" is **missed** (11.8%). Every verdict carries the promise quote and the source of the delivered figure.

**Key decisions.**
- **Code decides, models read.** Gemini turns text into typed JSON and writes short summaries. Every number, score and verdict is computed in code.
- **Nothing unverified is shown as fact.** Quotes must appear on the cited page (65 of 66 did); results must pass PAT = PBT − tax; a summary with a number not in its source is dropped. The checks flagged two bad extractions (a "PAT +538%" for Sun Pharma among them), and FINN shows "open the filing" instead.
- **Cost.** Rules classify 79% of filings with no model; Flash-Lite handles bulk extraction in batches; Flash only writes commentary; everything is cached. Total spend: ₹0.
- **Push is batch, pull is pre-built.** Both produce static JSON, so the app loads instantly on a phone and doesn't depend on a live scraper during review.

**Judgment calls I'd point to.** The first ranking put 40 of 120 filings in "Needs you", so I added rules: a price move is credited to one filing per stock and session, and results only "need you" when they surprise. The first Promise Tracker said L&T "met" an 8.5% segment margin target by delivering 13% company-wide; promises now carry a scope, and segment targets are never checked against company totals. The full log of what broke and why I changed it is in `docs/decision-log.md`.

**Left out on purpose.** Real push notifications (they add setup without adding signal to a demo), login, voice, LinkedIn scraping, and a balance-sheet deep-dive (related parties, contingent liabilities). Research is pre-built for four companies; the same command builds any NSE ticker, but a live "type any ticker" server was the riskiest deploy, so I left it out.

**Next.** Scheduled ingestion from an allowed IP, materiality weights learned from what the investor opens and dismisses, segment-level actuals from annual reports, and a short spoken brief for the commute.

Thank you for the interesting problem.

Simrah
