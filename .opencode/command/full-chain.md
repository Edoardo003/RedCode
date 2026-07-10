---
description: "Run full security assessment pipeline: recon -> osint -> scan -> exploit -> report. Supports --aggressive for full auto mode."
---

Run a FULL security assessment pipeline on:

$ARGUMENTS

## Mode Detection

- If `--aggressive` is present in arguments: **AGGRESSIVE MODE** — one confirmation, then full auto
- Otherwise: **NORMAL MODE** — confirm before each phase

---

## AGGRESSIVE MODE (--aggressive flag present)

### One-Time Authorization

Ask ONCE:

```
AGGRESSIVE MODE requested for [target].

This will automatically execute:
1. Full recon (passive + active)
2. OSINT intelligence gathering (email harvesting, breach lookup, dorking, social media)
3. All vulnerability scans
4. Active exploitation (SQLi data extraction, brute-force, RCE, SSRF probing, etc.)
   — includes social engineering artifact generation (phishing, pretexting, credential harvesting)
5. Final report compilation

Confirm you have WRITTEN AUTHORIZATION for aggressive testing of [target]? (yes/no)
```

After "yes": **zero more confirmations.** Every phase auto-progresses.

### Aggressive Pipeline

**Phase 1 — RECONNAISSANCE** (auto)

Delegate to @recon with: "MODE: AGGRESSIVE — run passive + active recon immediately, no confirmation needed. Use AT LEAST 3 subdomain enumeration methods (amass, subfinder/crt.sh, theharvester/dns-brute). Report ALL discovered subdomains."

- Passive: DNS, WHOIS, certificate transparency, tech fingerprinting
- Active: port scanning, subdomain enumeration (3+ tools), service detection
- **VERIFY**: recon must return a COMPLETE subdomain list
- If fewer than 3 subdomains found, send @recon back for additional enumeration
- -> Auto-progress to Phase 2 when complete, passing FULL subdomain list + org context

**Phase 2 — OSINT INTELLIGENCE** (auto)

Delegate to @osint with: "MODE: AGGRESSIVE — run ALL OSINT techniques on [target]. Domains: [full subdomain list]. Org info from recon: [WHOIS data, registrant, tech stack]. Read recon data from output/{target}/recon/findings.json. Execute ALL techniques without confirmation."

- Email harvesting: HexStrike `bugbounty_osint_gathering`, theHarvester, and public sources
- Username enumeration: social media profiling, platform searches
- Breach/credential lookup: authorized public breach sources and HexStrike OSINT tools
- Metadata extraction: document harvesting, EXIF, exposed files
- Technology intelligence: tech stack enrichment, vendor identification
- **VERIFY**: @osint ran at least 3 OSINT techniques and produced actionable intelligence
- If leaked credentials found, persist to SQLite immediately
- If new subdomains/endpoints discovered via dorking, add to scan target list
- -> Auto-progress to Phase 3 when complete, passing OSINT findings + enriched target list

**Phase 3 — VULNERABILITY SCANNING** (auto)

Delegate to @scanner with: "MODE: AGGRESSIVE — scan ALL of these subdomains: [full list from recon + OSINT additions]. Run ALL scan types on EVERY subdomain. If blocked on one, pivot to the next immediately. Auto-chain critical/high to exploitation. OSINT data available at output/{target}/osint/findings.json — check for new endpoints, exposed panels, technology intel."

- Scan EVERY subdomain, not just the first one
- Nuclei, nikto, gobuster/ffuf, sqlmap detection, dalfox, commix, hydra on login pages
- ALL vulnerability classes tested — no asking, no option menus
- If blocked on a subdomain → pivot immediately, come back later
- Critical/high findings auto-chained to @exploiter
- **VERIFY**: scanner must report findings across ALL subdomains, not just one
- -> Auto-progress to Phase 4 when complete

**Phase 4 — ACTIVE EXPLOITATION** (auto)

Delegate to @exploiter with: "MODE: AGGRESSIVE — exploit ALL critical/high findings across ALL subdomains without confirmation. Pivot when blocked. Cover every subdomain."

- SQLi: `sqlmap_scan --dump --level=5 --risk=3 --batch`
- RCE: `metasploit_run` actual exploit modules
- Brute-force: `hydra_attack` on all login pages
- XSS: `dalfox` / `xsser_scan` for session hijack proof
- Command Injection: `commix` for RCE proof
- LFI: `dotdotpwn_scan` for file extraction
- SSRF: internal network probing, cloud metadata
- Exploit findings across ALL subdomains, not just one
- Credentials found -> persist to SQLite, try immediately, trigger authenticated re-scan

**Social Engineering** (within Phase 4, auto):

If @osint produced actionable people intelligence, also delegate to @socialeng: "MODE: AGGRESSIVE — generate ALL social engineering artifacts. OSINT data at output/{target}/osint/findings.json. Key targets: [names, emails, roles]. Generate: spear phishing emails, pretexting scripts, credential harvesting pages, payloads. Full auto — no per-artifact confirmation."

- @socialeng generates ALL artifact types without confirmation
- @socialeng does NOT deploy — artifacts are generated for user to review and decide
- -> Auto-progress to Phase 5 when complete, optionally creating Nuclei templates for confirmed findings

**Phase 5 — REPORTING** (auto)

Delegate to @reporter: "Compile full report with all findings, exploitations, OSINT intelligence, and social engineering artifacts across ALL subdomains."

- Ask format preference ONLY if not specified: hackerone / bugcrowd / generic
- Include all exploitation evidence, extracted data, working payloads
- Include OSINT summary: emails, leaked credentials, exposed intelligence
- Include social engineering artifacts summary (if generated)
- Include coverage summary: which subdomains were tested, what was found on each
- Save to `output/{target}/reports/`

---

## NORMAL MODE (no --aggressive flag)

Execute each phase sequentially. ASK FOR CONFIRMATION before proceeding to the next phase.

### Phase 1 — RECONNAISSANCE

Use @recon to enumerate the target:

- Passive recon: DNS, WHOIS, certificate transparency, technology fingerprinting
- Active recon: port scanning, subdomain enumeration (ask confirmation first)
- Present the attack surface summary
- **-> Ask to confirm scope before proceeding to Phase 2**

### Phase 2 — OSINT INTELLIGENCE

Use @osint to gather intelligence:

- Email harvesting, username enumeration, breach/credential lookup
- Google dorking for exposed files, panels, sensitive data
- Social media profiling, metadata extraction
- Present OSINT findings grouped by intelligence type
- **-> Ask which OSINT avenues to pursue further, or proceed to Phase 3**

### Phase 3 — VULNERABILITY SCANNING

Use @scanner to scan discovered assets:

- Run nuclei, nikto, gobuster/ffuf
- Test for common vulnerabilities (SQLi, XSS, command injection, LFI, etc.)
- Incorporate OSINT-discovered endpoints and technology intel
- Present findings grouped by severity
- **-> Ask which vulnerabilities to exploit**

### Phase 4 — ACTIVE EXPLOITATION

Use @exploiter to attack selected vulnerabilities:

- Execute exploits using HexStrike offensive tools
- Extract data, gain access, crack credentials
- Construct and execute attack chains
- If scope includes social engineering, offer to invoke @socialeng for artifact generation
- Present exploitation results with evidence
- **-> Ask whether to proceed to final reporting**

### Phase 5 — REPORTING

Use @reporter to compile the final report:

- Ask for preferred format (hackerone / bugcrowd / generic)
- Compile all findings with CVSS scoring
- Include executive summary, methodology, evidence, remediation
- Include OSINT and social engineering sections if applicable
- Save to `output/{target}/reports/`

---

## Critical Rules

- In aggressive mode: ONE confirmation at start, then ZERO confirmations — NO EXCEPTIONS
- In aggressive mode: NEVER present option menus or ask questions after initial authorization
- In aggressive mode: if an agent asks a question or presents options, REJECT and send back with "AGGRESSIVE MODE. Execute without questions."
- In normal mode: confirm before each phase
- ALWAYS scan and exploit ALL subdomains, not just the main domain
- ALWAYS verify each phase covered ALL subdomains before advancing
- ALWAYS run @osint between recon and scanning — OSINT enriches the target list and provides exploitation intel
- NEVER accept "blocked" or "auth required" as a reason to stop the entire pipeline — agents must PIVOT
- NEVER scan or exploit outside authorized scope
- Save progress after each phase to output/ so work is not lost
- If any phase reveals scope concerns, STOP and ask regardless of mode
- ALWAYS persist findings and credentials to SQLite
- ALWAYS include exploitation evidence in the final report
- @socialeng generates but does NOT deploy — artifacts are for user review

## Checkpoint & Resume

Each long-running phase (Scanning, Exploitation, OSINT) maintains a `progress.json` checkpoint file:

- **Location**: `output/{target}/{phase}/progress.json` (e.g. `output/example.com/scans/progress.json`)
- **Written by**: The phase agent (@scanner, @exploiter, @osint) after each tool completes
- **Read by**: The same agent on RESUME to skip already-completed work
- **Deleted**: Automatically when the phase completes successfully — `progress.json` is a transient checkpoint, NOT a permanent artifact

If the pipeline is interrupted (crash, timeout, user stop):

1. `progress.json` persists with the last checkpoint state
2. User can run `/resume` to detect the interrupted phase and continue
3. The agent reads `progress.json` + SQLite `scans` table to determine what's done
4. Only remaining work is executed — no re-running completed tools

**In aggressive mode**: resume is automatic if the orchestrator detects `progress.json` on pipeline start.
**In normal mode**: the orchestrator informs the user and offers `/resume`.

## Nuclei Scan Rules (CRITICAL — agents MUST follow)

The `nuclei_scan` MCP tool accepts ONLY: `target`, `severity`, `tags`, `template`, and `additional_args` (proxy only).

**BANNED `additional_args`:** `-k`, `-no-verify`, `-no-color`, `-duc`, `-rl`, `-timeout`, `-retries`, `-sk`, `-stats`, `-silent`, `-json`, `-o`, `-rate-limit`, `-concurrency`, `-ni`

If nuclei scans fail with "flag provided but not defined", tell @scanner: "Remove ALL additional_args. Retry with just target, severity, tags."

Do NOT fire more than 2 nuclei scans in parallel — the HexStrike MCP crashes under heavy load.
