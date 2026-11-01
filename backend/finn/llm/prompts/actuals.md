# version: actuals-v1
You read one earnings-call transcript of an Indian listed company. Pages are marked like [[p7]].
INPUT.promises lists targets management gave earlier. For each one, find what management SAYS was actually achieved
for that same metric, scope and period, in THIS transcript. Use only this transcript.

For each promise return:
- `id`: the promise id
- `found`: true only if the transcript states the achieved figure for that exact metric, scope and period
- `value`: the achieved figure as a number in the same unit as the promise (e.g. growth 14.2 for "grew 14.2%",
  margin 8.3 for "8.3% margin"). Do not calculate: only copy a figure management states.
- `quote`: the sentence stating it, copied EXACTLY, at most 300 characters
- `page`: the page number of the quote

If the figure is not stated, return found=false, value=0, quote="", page=0.
