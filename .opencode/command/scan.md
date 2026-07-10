---
description: "Run vulnerability scanning on a target"
agent: scanner
---

Run comprehensive vulnerability scanning on:

$ARGUMENTS

## Instructions

1. Review recon results from `output/{target}/recon/` if available
2. Run `nuclei_scan` with default + community templates
3. Run `nikto_scan` for web server misconfigurations
4. Run `gobuster_scan` or `ffuf_scan` for directory/file discovery
5. Test for common vulnerabilities: SQLi, XSS, SSRF, LFI, command injection
   - Ask my confirmation before running intrusive tests (sqlmap, brute force)
6. Correlate and deduplicate findings across tools
7. Present findings grouped by severity (Critical → High → Medium → Low → Info)
8. For each finding include: title, CVSS score, URL, evidence, confidence level

Save all results to `output/{target}/scans/`.
