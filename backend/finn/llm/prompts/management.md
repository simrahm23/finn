# version: management-v1
You read an Indian listed company's stock-exchange filing about a change in its directors or key managerial
personnel. Use only the text given. Do not use outside knowledge about any person or company.

Return:
- `person`: the full name of the person joining or leaving, exactly as written
- `role`: their position, as written (e.g. "Chief Financial Officer", "Independent Director")
- `direction`: "joining" (appointment, re-appointment) or "leaving" (resignation, cessation, retirement, end of tenure)
- `effective_date`: YYYY-MM-DD if stated, else ""
- `reason`: for leaving, the stated reason in a few words (e.g. "Completion of tenure"), else ""
- `profile`: for joining, copy the brief-profile paragraph VERBATIM from the text (often in an annexure), at most
  600 characters, cut at a sentence end. If there is no profile text, or the profile says "Not applicable", use "".

If several people are named, pick the most senior role. If the text is not about a management change, set
`person` to "".
