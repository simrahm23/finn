# FINN decision log

What we tested, what broke, what we changed, and why. Kept as we built on 1 Nov 2026 (IST).

## 13:15–13:50: source tests and go/no-go

| Source | Result | Decision |
| --- | --- | --- |
| Prices (yfinance, 18 × .NS, 400 days) | 18/18 OK, last date 2026-10-30 | GO: yfinance primary |
| Prices fallback (NSE bhavcopy via `nse`) | PASS | Keep as fallback |
| Announcements (NSE via `nse` 5.1.x) | PASS: LT 7, DIXON 6, INFY 11 in 10 days | GO: NSE primary; BSE not needed |
| Fundamentals (screener.in) | LT, HAVELLS, CUMMINSIND, ASTRAL: all 4 tables, 35–46 transcripts each, text PDFs | GO: research set |
| Gemini | `gemini-2.5-flash-lite` → 404 "no longer available to new users" | `gemini-3.5-flash-lite` (bulk), `gemini-3.5-flash` (reasoning); both PASS |
| Appointment filings | 21 management-change filings with PDFs in 90 days; appointments carry a "Brief profile", often in an annexure | Management card quotes the filing; no web scraping |

## 14:00–17:35: build decisions (and why)

| When | Decision | Why |
| --- | --- | --- |
| 16:10 | Force IPv4 and a 10 s connect timeout for every HTTP call (`finn/net.py`) | `push` hung twice while connecting (NSE PDFs, Gemini); IPv6 routes on the home network were silently failing |
| 16:15 | Commit after each model batch; never retry database errors | A dry run deadlocked: the pipeline held a write lock while the model client wrote its cache |
| 16:25 | Ranking: a price move is credited to one filing per stock-session (results first); results are "worth knowing" unless they surprise (stock reacted, or verified PAT YoY ≥ 20%); group housekeeping capped at 40; 2nd+ filing on the same results or person capped at 55 | First real run put 40 of 120 filings in "Needs you", which defeats the point. After: 19, then 15 |
| 16:30 | ESOP allotments = routine; NCDs / commercial paper = "debt raise"; an unverified results card gives no surprise bonus | L&T ESOP and Bajaj Finance NCDs ranked as fund raises; Sun Pharma's "PAT +538%" was a bad extraction the checks had already flagged |
| 16:45 | Research pre-built to static JSON for 4 companies; a live research API deferred | Removes the riskiest deploy. `research SYMBOL` still works for any NSE ticker |
| 17:00 | Every promise carries a scope (company or segment); segment targets are never checked against company totals | First L&T run said "met the 8.5% core margin target by delivering 13.0%": a segment target against company operating margin |
| 17:10 | "Reported actuals": for ended periods, read the call that reported the period for management's stated figure; the quote must be on the page and contain the number; verdict still computed in code | Order-inflow and segment targets are not in the financial tables |
| 17:15 | Period not over → "pending" first; read 6 calls (adds the year-start call where full-year guidance is set); judged promises shown first | Most promises in the last 5 calls were for FY27 and were mislabelled "can't check" |
| 17:30 | The same target restated on several calls counts once ("reiterated on N later calls") | Cummins showed "4 met" for one promise repeated on 4 calls |
| 17:35 | "Partly" tolerance: 1 pp for margins, 3 pp for growth | A 3 pp margin miss is a large miss |

## Measured results

- Filings: 120 in 10 days across 18 holdings; rules classified 95 (79%) with no model; 25 went to Flash-Lite in one batch.
- Brief: 15 "Needs you" (from 40 before the ranking rules).
- Summaries: 53/60 written; 2 dropped because a number was not in the filing.
- Results cards: 7 built; 5 verified (LT, TRENT, KPITTECH, CDSL, DIXON); 2 correctly flagged not verified (SUNPHARMA, RELIANCE); INFY scanned; MARUTI no table found.
- Management cards: 10, e.g. HDFC Bank's new MD & CEO, Trent's chairman retiring.
- Guidance quotes kept after the verbatim check: 65/66.
- L&T Promise Tracker: "order inflow +10% in FY26" met (10.0%, reported on the Q4 FY26 call); "revenue +15% in FY26" missed (11.8%). Cummins: "double-digit revenue growth in FY26" met (16.9%), reiterated on 3 later calls.
- Cost: ₹0 (Gemini free tier).
