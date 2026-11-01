# FINN: Financial Investment Agent

A triage inbox for an investor's portfolio. The **Brief** (push) ranks every filing and price move so only what matters surfaces. The **Promise Tracker** (pull) checks what management promised on earnings calls against what they delivered, with every number linked to its source page.

Live app: _(link after deploy)_ · Built for the ENAM Holdings AI Engineer Build Challenge, Nov 2026.

## Run locally

```bash
cd backend
pip install -r requirements.txt
python -m finn.pipeline init-db     # tables + portfolio
python -m finn.pipeline mocks       # labelled mock JSON for UI work (replaced by `export`)
python -m finn.pipeline validate    # check JSON in frontend/public/data against the contracts
pytest -q
```

Environment: `GEMINI_API_KEY`, optional `FINN_DB_PATH`, `FINN_ALLOWED_ORIGIN`, `FINN_MODEL_LITE` (default `gemini-3.5-flash-lite`), `FINN_MODEL_FLASH` (default `gemini-3.5-flash`).

## Source decisions (spikes, 1 Nov 2026 13:15–13:50 IST)

| Source | Result | Decision |
| --- | --- | --- |
| Prices: yfinance `.NS` | 18/18, last date 30 Oct 2026 | Primary. NSE bhavcopy as fallback (tested) |
| Announcements: NSE via `nse` package | PASS (LT 7, DIXON 6, INFY 11 in 10 days) | Primary. BSE not needed |
| Fundamentals: screener.in | LT, HAVELLS, CUMMINSIND, ASTRAL: all tables, 35–46 text transcripts | Research demo set |
| LLM: Gemini | `gemini-2.5-flash-lite` unavailable to new keys | `gemini-3.5-flash-lite` (bulk), `gemini-3.5-flash` (reasoning): both PASS |
| Appointment filings | Carry a "Brief profile" field, often in an annexure | Management card quotes the filing; no web scraping |

## Architecture

_(diagram and decisions: see docs/architecture.md)_

## Evaluation

_(classification accuracy, results-extraction match rate, guidance quote-match rate: filled in at D3)_
