---
description: "Run a focused bug bounty hunt against a HackerOne program: fetch scope, recon, quick scan, and produce a shortlist of testable opportunities."
agent: redcode
---

Run a focused bug bounty hunt on HackerOne program:

$ARGUMENTS

## Prerequisites

1. **Extract the HackerOne handle** from `$ARGUMENTS`. If missing, ask the user: "Which HackerOne program handle? (e.g., `security`, `verizon-media`, `shopify`)"
2. Register the target in SQLite using the existing `targets` table:
   ```sql
   INSERT OR IGNORE INTO targets (domain, scope, type, notes)
   VALUES ('{handle}.hackerone.com', '*.{handle}.hackerone.com', 'bug-bounty', 'HackerOne handle: {handle}');
   ```
3. Create output directory: `output/bounty-hunt/{handle}/`

## Phase 1 — Program Intelligence

Call `hackerone.get_program(handle)` and `hackerone.get_program_scope(handle)`.

From the responses, extract:
- Program name, policy URL, and safe-harbor status
- In-scope assets: domains, wildcards, URLs, CIDR blocks, mobile apps
- Out-of-scope exclusions
- Bounty table and severity payouts (if available)

**VERIFY**: scope response contains at least one asset. If empty, warn the user and stop.

Save raw program data to `output/bounty-hunt/{handle}/raw/program.json` and `scope.json`.

## Phase 2 — Focused Recon

Delegate to @recon with: "MODE: FOCUSED BUG BOUNTY — Run quick recon on HackerOne program {handle}. In-scope assets: [list from Phase 1]. Save raw outputs to `output/bounty-hunt/{handle}/raw/`."

Run these tools sequentially (do NOT overwhelm the HexStrike MCP):

1. **Subdomain enumeration** — `amass_enum` and `subfinder` on every wildcard domain
2. **Live host probing** — `httpx_scan` on all discovered subdomains to find live hosts
3. **Technology detection** — `whatweb` + `httpx` headers on live hosts to fingerprint stack
4. **Endpoint discovery** — `gau` + `waybackurls` on live hosts to collect historical endpoints
5. **Parameter discovery** — `arjun` or `paramspider` on key endpoints to find hidden params
6. **Quick vulnerability scan** — `nuclei_scan` with `severity: critical,high,medium` on live hosts (max 2 parallel scans)
7. **Manual verification via Burp** — for the most promising endpoints, use the `burp` MCP server to send requests, inspect responses, and create Repeater tabs instead of writing custom scripts

**Rules for this phase:**
- Respect out-of-scope exclusions from Phase 1 — NEVER scan excluded assets
- Do NOT run active exploitation or brute-force — this is a quick hunt, not full exploitation
- If a tool fails, log it and continue with the next tool
- Save raw tool outputs to `output/bounty-hunt/{handle}/raw/{tool}_{timestamp}.txt`

## Phase 3 — Findings Synthesis

Compile structured findings into `output/bounty-hunt/{handle}/findings.json` using the existing handoff JSON format:

```json
{
  "target": "{handle}",
  "scope": "*.example.com",
  "phase": "scan",
  "timestamp": "2025-01-15T10:30:00Z",
  "findings": [
    {
      "id": "FIND-BH-001",
      "type": "vuln",
      "severity": "high",
      "title": "Reflected XSS on /search",
      "url": "https://example.com/search?q=test",
      "evidence": "nuclei output: reflected-xss template matched",
      "cvss": 6.1,
      "cwe": "CWE-79",
      "confidence": "likely",
      "raw_path": "output/bounty-hunt/{handle}/raw/nuclei_001.txt",
      "next_steps": ["Verify with dalfox", "Write PoC"]
    }
  ],
  "metadata": {
    "tools_used": ["amass", "httpx", "nuclei", "gau"],
    "duration_seconds": 600
  }
}
```

Persist each finding to SQLite:
```sql
INSERT INTO findings (target_id, finding_id, phase, type, severity, title, url, evidence, cvss, cwe, confidence, raw_path)
VALUES (?, 'FIND-BH-001', 'scan', 'vuln', 'high', 'Reflected XSS on /search', 'https://example.com/search?q=test', 'nuclei matched', 6.1, 'CWE-79', 'likely', 'output/bounty-hunt/{handle}/raw/nuclei_001.txt');
```

## Phase 4 — Opportunity Shortlist

Produce a final shortlist of **3-5 concrete, manually-testable opportunities** with reasoning for each:

For each opportunity, include:
1. **Title** — specific and descriptive
2. **Asset** — exact URL/subdomain
3. **Type** — vulnerability class (XSS, IDOR, SSRF, etc.)
4. **Severity** — estimated CVSS
5. **Why it's promising** — what the recon/scan revealed
6. **Manual test steps** — 3-5 concrete steps to verify
7. **Confidence** — high / medium / low

Example:
```
1. Reflected XSS on https://api.example.com/search?q=
   - Type: XSS | CVSS: 6.1
   - Why: nuclei reflected-xss template fired; parameter is reflected unescaped
   - Test: Inject <img src=x onerror=alert(1)> in q param; check if script executes
   - Confidence: high
```

Present the shortlist to the user. Offer to:
- Deep-dive any opportunity with `/exploit`
- Generate a PoC with `/poc`
- Write a HackerOne report with `/report hackerone`

## Critical Rules

- NEVER scan out-of-scope assets
- NEVER run active exploitation (sqlmap --dump, brute-force, RCE) during a bounty hunt — this is recon + quick scan only
- Do NOT fire more than 2 nuclei scans in parallel
- ALWAYS save raw tool outputs to `output/bounty-hunt/{handle}/raw/`
- ALWAYS persist findings to SQLite `findings` table linked to `targets`
- If the program has no in-scope assets, STOP and warn the user
- Respect rate limits — bug bounty programs are live production systems
- Include the HackerOne handle in the `targets.notes` field for tracking
