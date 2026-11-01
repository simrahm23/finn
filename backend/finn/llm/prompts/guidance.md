# version: guidance-v2
You read one earnings-call transcript of an Indian listed company. Pages are marked like [[p7]].
Extract management's FORWARD-LOOKING GUIDANCE: statements by the company's own executives (not analysts) about what
they expect for a future period. Use only this transcript. Do not use outside knowledge.

For each statement return:
- `metric`: one of revenue_growth, ebitda_margin, pat_growth, order_inflow_growth, capex, volume_growth, other
  (EBITDA / operating / core margin all map to ebitda_margin; sales or topline growth to revenue_growth)
- `target_period`: the period it is about, as "FY27", "Q3 FY27", or "H2 FY27" (Indian fiscal year Apr-Mar;
  "this year" in a call held in FY27 means FY27; "next year" means FY28). Use "" if no period is clear.
- `target_low`, `target_high`: the numeric target. A single number -> both equal. "12-15%" -> 12 and 15.
  "Double-digit" -> 10 and null. Use null when there is no number.
- `unit`: "%" for growth rates and margins, "₹ cr" for amounts
- `target_text`: the promise in at most 10 words, e.g. "Revenue growth of 12-15% in FY27"
- `quote`: the speaker's words, copied EXACTLY from the transcript, 1-2 sentences, at most 300 characters
- `page`: the page number where the quote appears
- `scope`: "company" if it is about the whole company / group (consolidated revenue, group order inflow, company
  margin); "segment" if it is about one business, segment, division, subsidiary or portfolio (e.g. "core P&M margin",
  "IT services revenue", "projects portfolio margin")
- `measurable`: true only if there is a number AND a period

Return at most 12 statements, the most specific first. Skip generic optimism with no target ("we remain confident").
If the call gives no guidance, return an empty list.
