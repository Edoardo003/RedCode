---
description: "Run full security assessment pipeline: recon -> scan -> exploit -> poc -> report. Supports --aggressive for full auto mode."
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
2. All vulnerability scans
3. Active exploitation (SQLi data extraction, brute-force, RCE, SSRF probing, etc.)
4. PoC generation and execution verification
5. Final report compilation

Confirm you have WRITTEN AUTHORIZATION for aggressive testing of [target]? (yes/no)
```

After "yes": **zero more confirmations.** Every phase auto-progresses.

### Aggressive Pipeline

**Phase 1 — RECONNAISSANCE** (auto)

Delegate to @recon with: "MODE: AGGRESSIVE — run passive + active recon immediately, no confirmation needed."

- Passive: DNS, WHOIS, certificate transparency, tech fingerprinting
- Active: port scanning, subdomain enumeration, service detection
- -> Auto-progress to Phase 2 when complete

**Phase 2 — VULNERABILITY SCANNING** (auto)

Delegate to @scanner with: "MODE: AGGRESSIVE — run ALL scan types, auto-chain critical/high to exploitation."

- Nuclei, nikto, gobuster/ffuf, sqlmap detection, dalfox, commix, hydra on login pages
- ALL vulnerability classes tested — no asking
- Critical/high findings auto-chained to @exploiter
- -> Auto-progress to Phase 3 when complete

**Phase 3 — ACTIVE EXPLOITATION** (auto)

Delegate to @exploiter with: "MODE: AGGRESSIVE — exploit ALL critical/high findings without confirmation."

- SQLi: `sqlmap_scan --dump --level=5 --risk=3 --batch`
- RCE: `metasploit_run` actual exploit modules
- Brute-force: `hydra_attack` on all login pages
- XSS: `dalfox` / `xsser_scan` for session hijack proof
- Command Injection: `commix` for RCE proof
- LFI: `dotdotpwn_scan` for file extraction
- SSRF: internal network probing, cloud metadata
- Credentials found -> persist to SQLite, try immediately, trigger authenticated re-scan
- -> Auto-progress to Phase 4 when complete

**Phase 4 — PROOF OF CONCEPT** (auto)

Delegate to @poc with each exploited finding: "MODE: AGGRESSIVE — write AND execute PoC with --check flag."

- Write PoC for each confirmed exploitation
- Execute PoC in `--check` mode to verify it works
- If PoC fails, adjust and retry
- Optionally delegate to @templates for Nuclei template creation
- -> Auto-progress to Phase 5 when complete

**Phase 5 — REPORTING** (auto)

Delegate to @reporter: "Compile full report with all findings, exploitations, and PoC results."

- Ask format preference ONLY if not specified: hackerone / bugcrowd / generic
- Include all exploitation evidence, extracted data, working payloads
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

### Phase 2 — VULNERABILITY SCANNING

Use @scanner to scan discovered assets:

- Run nuclei, nikto, gobuster/ffuf
- Test for common vulnerabilities (SQLi, XSS, command injection, LFI, etc.)
- Present findings grouped by severity
- **-> Ask which vulnerabilities to exploit**

### Phase 3 — ACTIVE EXPLOITATION

Use @exploiter to attack selected vulnerabilities:

- Execute exploits using HexStrike offensive tools
- Extract data, gain access, crack credentials
- Construct and execute attack chains
- Present exploitation results with evidence
- **-> Ask which findings to create PoCs for**

### Phase 4 — PROOF OF CONCEPT

Use @poc to generate PoC code:

- Write working exploit code for confirmed exploitations
- Include verification mode (--check flag)
- Include remediation recommendations
- Present PoCs for review
- **-> Ask to approve PoCs before final reporting**

### Phase 5 — REPORTING

Use @reporter to compile the final report:

- Ask for preferred format (hackerone / bugcrowd / generic)
- Compile all findings with CVSS scoring
- Include executive summary, methodology, evidence, remediation
- Save to `output/{target}/reports/`

---

## Critical Rules

- In aggressive mode: ONE confirmation at start, then ZERO confirmations
- In normal mode: confirm before each phase
- NEVER scan or exploit outside authorized scope
- Save progress after each phase to output/ so work is not lost
- If any phase reveals scope concerns, STOP and ask regardless of mode
- ALWAYS persist findings and credentials to SQLite
- ALWAYS include exploitation evidence in the final report
