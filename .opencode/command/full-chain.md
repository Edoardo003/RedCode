---
description: "Run full security assessment pipeline: recon → scan → exploit → poc → report"
---

Run a FULL security assessment pipeline on:

$ARGUMENTS

## Pipeline Phases

Execute each phase sequentially. ASK FOR MY CONFIRMATION before proceeding to the next phase.

### Phase 1 — RECONNAISSANCE

Use @recon to enumerate the target:

- Passive recon: DNS, WHOIS, certificate transparency, technology fingerprinting
- Active recon: port scanning, subdomain enumeration (ask confirmation first)
- Present the attack surface summary
- **→ Ask me to confirm scope before proceeding to Phase 2**

### Phase 2 — VULNERABILITY SCANNING

Use @scanner to scan discovered assets:

- Run nuclei, nikto, gobuster/ffuf
- Test for common vulnerabilities
- Present findings grouped by severity
- **→ Ask me which vulnerabilities to investigate further**

### Phase 3 — EXPLOIT RESEARCH

Use @exploiter to analyze selected vulnerabilities:

- Research CVEs and public exploits
- Construct attack chains
- Identify bypass techniques
- Present exploitation analysis with confidence ratings
- **→ Ask me which vulnerabilities to create PoCs for**

### Phase 4 — PROOF OF CONCEPT

Use @poc to generate PoC code:

- Write working exploit code for confirmed vulnerabilities
- Include verification mode (--check flag)
- Include remediation recommendations
- Present PoCs for review
- **→ Ask me to approve PoCs before final reporting**

### Phase 5 — REPORTING

Use @reporter to compile the final report:

- Ask me for preferred format (hackerone / bugcrowd / generic)
- Compile all findings with CVSS scoring
- Include executive summary, methodology, evidence, remediation
- Save to output/reports/

## Critical Rules

- NEVER skip user confirmation between phases
- NEVER scan or exploit outside authorized scope
- Save progress after each phase to output/ so work is not lost
- If any phase reveals scope concerns, STOP and ask me
