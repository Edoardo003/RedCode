---
description: "Generate an evidence-based security report"
agent: reporter
---

Generate the requested report for:

$ARGUMENTS

1. Read the active engagement and all relevant JSON, SQLite, and raw evidence paths.
2. Select `templates/generic.md`, `templates/hackerone.md`, or `templates/bugcrowd.md` from the requested format.
3. Include only findings supported by preserved evidence; separate unverified leads.
4. Verify severity, CVSS vector, CWE, affected asset, reproduction steps, impact, and remediation.
5. Redact secrets and unnecessary personal data.
6. Save the report under `output/{target}/reports/` and record reported status where supported.

Return the report path and a short list of evidence gaps requiring analyst review.
