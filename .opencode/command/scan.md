---
description: "Run prioritized vulnerability discovery on authorized assets"
agent: scanner
---

Scan the authorized target set for:

$ARGUMENTS

1. Read the active engagement, recon, OSINT, and previous scan state.
2. Confirm scan permission, exclusions, rate limits, and availability constraints.
3. Select focused tools from observed technologies and attack surface; do not run every scanner by default.
4. Ask before intrusive techniques not already approved.
5. Reproduce material detections where permitted and separate potential, likely, and confirmed findings.
6. Preserve raw output and save `output/{target}/scans/findings.json` plus compatible SQLite records.

Return actual coverage, false positives, blocked assets, tool failures, and evidence paths.
