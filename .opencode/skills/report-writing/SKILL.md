---
name: report-writing
description: "Security report writing skill. Use for creating professional vulnerability reports, CVSS scoring guidance, and bug bounty submissions."
---

# Security Report Writing

Methodology for creating professional vulnerability reports and bug bounty submissions.

## Report Type Decision Tree

```
What type of report?
├─ Bug Bounty Submission
│   ├─ HackerOne → Use templates/hackerone.md
│   ├─ Bugcrowd → Use templates/bugcrowd.md
│   └─ Key: One vuln per report, concise, reproducible
├─ Penetration Test Report
│   ├─ Full report → Use templates/generic.md
│   ├─ Executive summary → Non-technical, business impact
│   ├─ Technical report → All findings with evidence
│   └─ Key: Comprehensive, structured, remediation roadmap
├─ Vulnerability Advisory
│   ├─ CVE format → Standardized disclosure
│   └─ Key: Technical accuracy, affected versions, patches
└─ Quick Finding
    └─ Single finding write-up for internal tracking
```

## CVSS v3.1 Scoring Guide

### Base Metrics

```
Attack Vector (AV)
├─ Network (N) — Exploitable remotely via network
├─ Adjacent (A) — Requires same network segment
├─ Local (L) — Requires local access
└─ Physical (P) — Requires physical access

Attack Complexity (AC)
├─ Low (L) — No special conditions needed
└─ High (H) — Requires specific configuration or race condition

Privileges Required (PR)
├─ None (N) — No authentication needed
├─ Low (L) — Requires basic user account
└─ High (H) — Requires admin/privileged account

User Interaction (UI)
├─ None (N) — No user action needed
└─ Required (R) — Victim must perform action (click link, visit page)

Scope (S)
├─ Unchanged (U) — Impact limited to vulnerable component
└─ Changed (C) — Impact extends beyond vulnerable component

Impact: Confidentiality (C), Integrity (I), Availability (A)
├─ None (N) — No impact
├─ Low (L) — Limited impact
└─ High (H) — Total impact
```

### Common Vulnerability CVSS Scores

| Vulnerability                   | CVSS | Vector                              |
| ------------------------------- | ---- | ----------------------------------- |
| Unauthenticated RCE             | 9.8  | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H |
| SQL Injection (data extraction) | 8.6  | AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N |
| Stored XSS (admin context)      | 8.0  | AV:N/AC:L/PR:L/UI:R/S:C/C:H/I:L/A:N |
| SSRF to internal services       | 7.5  | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N |
| IDOR (data access)              | 6.5  | AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N |
| Reflected XSS                   | 6.1  | AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N |
| CSRF (state changing)           | 4.3  | AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:L/A:N |
| Information disclosure (minor)  | 3.1  | AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:N/A:N |
| Missing security headers        | 0.0  | Informational — no CVSS             |

### Severity Ranges

| Severity      | CVSS Score | Color     |
| ------------- | ---------- | --------- |
| Critical      | 9.0 - 10.0 | 🔴 Red    |
| High          | 7.0 - 8.9  | 🟠 Orange |
| Medium        | 4.0 - 6.9  | 🟡 Yellow |
| Low           | 0.1 - 3.9  | 🔵 Blue   |
| Informational | 0.0        | ⚪ Gray   |

## Finding Write-Up Structure

### Title

Specific and descriptive. Include the vulnerability type and affected component.

- Good: "Stored XSS in User Profile Bio Field via Markdown Rendering"
- Bad: "XSS Vulnerability Found"

### Severity

CVSS v3.1 score with full vector string. Justify any non-obvious metric choices.

### CWE Classification

Map to the most specific CWE:

- XSS → CWE-79
- SQLi → CWE-89
- SSRF → CWE-918
- IDOR → CWE-639
- Command Injection → CWE-78
- Path Traversal → CWE-22
- Deserialization → CWE-502
- XXE → CWE-611
- CSRF → CWE-352
- Open Redirect → CWE-601
- Broken Auth → CWE-287
- Information Exposure → CWE-200

### Steps to Reproduce

Numbered steps that another person can follow exactly:

1. Navigate to [URL]
2. Log in as [role] with credentials [method to obtain]
3. Navigate to [specific page/endpoint]
4. Enter [specific payload] in [specific field]
5. Click [specific button] / Submit the form
6. Observe [specific evidence of vulnerability]

Include: HTTP requests (cURL or raw), screenshots, video if complex.

### Impact

Two perspectives:

- **Technical impact**: What does the attacker gain? (data access, code execution, session hijack)
- **Business impact**: What does this mean for the company? (data breach, regulatory fines, reputation damage, financial loss)

### Remediation

Be specific:

- **Short-term**: Immediate mitigation (WAF rule, disable feature, IP restriction)
- **Long-term**: Proper fix (input validation, parameterized queries, access control refactor)
- Include code examples when possible

## Report Quality Checklist

- [ ] Title is specific and descriptive
- [ ] Severity has CVSS score AND vector string
- [ ] CWE classification is accurate
- [ ] Steps to reproduce are numbered and exact
- [ ] Evidence includes raw HTTP requests/responses
- [ ] Impact covers both technical and business perspectives
- [ ] Remediation is specific with short-term and long-term suggestions
- [ ] No speculation — all claims backed by evidence
- [ ] Professional language — no filler, no exaggeration
- [ ] Tested against latest version / production environment
- [ ] All testing was within authorized scope

## Platform-Specific Tips

### HackerOne

- Markdown supported — use code blocks for payloads
- One vulnerability per report
- Include impact aligned to their taxonomy
- Use structured format matching their template
- Respond to triage questions within 7 days

### Bugcrowd

- Map findings to VRT (Vulnerability Rating Taxonomy)
- P1-P5 severity scale
- Submission form has specific fields — fill all
- Attach reproducible requests, responses, screenshots, and tool evidence

## Templates

Available in `templates/` directory:

- `templates/hackerone.md` — HackerOne submission format
- `templates/bugcrowd.md` — Bugcrowd VRT format
- `templates/generic.md` — Full pentest report format
