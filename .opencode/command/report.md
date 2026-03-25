---
description: "Generate a security report from findings"
agent: reporter
---

Generate a comprehensive security report.

Format requested: $ARGUMENTS

## Instructions

1. If a format was specified (hackerone, bugcrowd, generic), read the corresponding template from `templates/`
2. If no format specified, use the generic template from `templates/generic.md`
3. Compile all findings from:
   - `output/recon/` — reconnaissance results
   - `output/scans/` — vulnerability scan results
   - `output/pocs/` — proof of concept code
4. For each finding include: title, severity, CVSS v3.1 score + vector, CWE ID, description, steps to reproduce, impact, remediation
5. Include an executive summary suitable for non-technical stakeholders
6. Include a methodology section describing tools and approach used
7. Save the report to `output/reports/`

Use professional, precise language. Every finding must have evidence.
