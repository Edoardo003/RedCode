---
name: bug-bounty
description: "Bug bounty workflow and methodology. Use for any bug bounty engagement, program rules, scope management, and submission workflows."
---

# Bug Bounty Methodology

Comprehensive workflow for bug bounty engagements on platforms like HackerOne, Bugcrowd, and private programs.

## Quick Decision Tree

```
Starting a bug bounty?
├─ Read program policy first → Scope, rules, exclusions
├─ What program type?
│   ├─ Public → Open to all, higher competition, faster dupes
│   ├─ Private → Invite-only, less competition, higher expectations
│   └─ VDP → No bounty, disclosure only, good for reputation
├─ What target type?
│   ├─ Web application → web-pentest skill
│   ├─ API → api-pentest skill
│   ├─ Mobile app → Decompile, proxy traffic, test API
│   ├─ Cloud/Infra → cloud-pentest skill
│   └─ Network → network-pentest skill
└─ What to look for first?
    ├─ Low-hanging fruit → Misconfigs, exposed panels, default creds
    ├─ Business logic → Payment bypass, access control, race conditions
    └─ Deep bugs → SQLi, RCE, SSRF, deserialization
```

## Phase Workflow

### Phase 1 — Scope Review

Before ANY testing:

1. Read the full program policy
2. Identify in-scope domains, IPs, applications
3. Note exclusions — out-of-scope assets, forbidden test types
4. Check for wildcard scope (`*.example.com`) — enum subdomains
5. Note safe harbor provisions and disclosure rules
6. Check bounty table — understand payout ranges per severity

### Phase 2 — Reconnaissance

Use @recon agent or `/target` command:

1. Subdomain enumeration — `amass_enum`, certificate transparency
2. Port scanning — `nmap_scan` on in-scope IPs
3. Technology fingerprinting — CMS, frameworks, WAF detection
4. OSINT — employee emails, GitHub repos, leaked credentials

### Phase 3 — Vulnerability Discovery

Use @scanner agent or `/scan` command:

1. Automated scanning — `nuclei_scan` with community templates
2. Directory discovery — `gobuster_scan`, `ffuf_scan`
3. Manual testing — focus on business logic, access control, auth
4. Parameter fuzzing — hidden params, debug endpoints

### Phase 4 — Exploitation & PoC

Use @exploiter for analysis, @poc for code:

1. Validate findings — confirm exploitability
2. Assess impact — what can an attacker actually do?
3. Write minimal PoC — demonstrate the bug, don't destroy
4. Document reproduction steps clearly

### Phase 5 — Reporting & Submission

Use @reporter or `/report hackerone|bugcrowd`:

1. One vulnerability per report
2. Clear title — specific, descriptive
3. Detailed reproduction steps — copy-paste reproducible
4. Impact statement — technical AND business impact
5. CVSS score with justification
6. Remediation suggestions

## Severity Rating (Bug Bounty Platforms)

| Rating | CVSS    | Examples                                       | Typical Bounty |
| ------ | ------- | ---------------------------------------------- | -------------- |
| P1     | 9.0-10  | RCE, auth bypass, full DB dump                 | $5,000-50,000+ |
| P2     | 7.0-8.9 | Stored XSS (admin), SSRF (internal), SQLi      | $2,000-10,000  |
| P3     | 4.0-6.9 | Reflected XSS, IDOR, info disclosure (PII)     | $500-3,000     |
| P4     | 0.1-3.9 | Self-XSS, low-impact info leak, CSRF           | $100-500       |
| P5     | Info    | Missing headers, verbose errors, best practice | $0-100         |

## Duplicate Avoidance

1. Search existing reports before submitting
2. Focus on UNIQUE attack surfaces — recently deployed features, new endpoints
3. Test edge cases that scanners miss — business logic, multi-step flows
4. Move fast on new program launches — first 48 hours have lowest dupe rate
5. If unsure, submit anyway — worst case is a dupe, not a miss

## Report Quality Checklist

- [ ] Clear, specific title
- [ ] Correct severity with CVSS score
- [ ] Step-by-step reproduction (numbered)
- [ ] Evidence: screenshots, HTTP requests, tool output
- [ ] Impact statement (business perspective)
- [ ] Remediation recommendation
- [ ] All testing was in-scope
- [ ] No destructive actions taken

## HexStrike Tools by Phase

| Phase        | Tools                                              |
| ------------ | -------------------------------------------------- |
| Recon        | amass_enum, nmap_scan, theharvester, shodan_search |
| Scanning     | nuclei_scan, nikto_scan, gobuster_scan, ffuf_scan  |
| Exploitation | searchsploit, sqlmap_scan, metasploit              |
| Analysis     | analyze_target_intelligence, select_tools          |
