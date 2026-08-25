---
name: "hexstrike-burpsuite"
description: "Correct parameters and usage patterns for HexStrike burpsuite_scan MCP tool — web application security scanning."
---

# HexStrike burpsuite_scan — Tool Skill

Web application security scanner. Performs deep crawling and active scanning of web applications for vulnerabilities including injection flaws, authentication issues, session management problems, and more. Enterprise-grade scanner that complements nuclei and nikto.

## Accepted Parameters

| Parameter | Type   | Required | Description                              |
| --------- | ------ | -------- | ---------------------------------------- |
| `target`  | string | **YES**  | URL to scan (e.g. `https://example.com`) |
| `flags`   | string | no       | Additional configuration flags           |

## Common Usage

```
# Standard web application scan
burpsuite_scan(target="https://example.com")

# Scan specific path
burpsuite_scan(target="https://example.com/api/v1")

# Scan with authentication (if supported by wrapper)
burpsuite_scan(target="https://example.com", flags="--auth-token=BEARER_TOKEN")
```

## When to Use

- **After nuclei and nikto** — Burp provides deeper application-level scanning
- **For JavaScript-heavy SPAs** — Burp's crawler handles dynamic content better
- **For complex auth flows** — Burp can navigate multi-step authentication
- **For API testing** — Burp excels at REST/GraphQL endpoint analysis

## What Burp Finds That Others Miss

| Finding Type              | Why Burp Excels                            |
| ------------------------- | ------------------------------------------ |
| Complex injection chains  | Multi-step payload delivery                |
| Workflow leads            | Crawler coverage for later manual analysis  |
| Session management issues | Cookie analysis, token prediction          |
| DOM-based XSS             | JavaScript execution and analysis          |
| Insecure deserialization  | Deep payload fuzzing                       |
| Access control issues     | Comparing authenticated vs unauthenticated |

## Proxy Configuration

Burp Suite is itself a proxy tool. The HexStrike wrapper handles configuration. If an upstream proxy is needed, it depends on the wrapper's support.

## Retry Strategy

1. **Timeout**: Burp scans can be long. Check partial results — they may already contain findings.
2. **Connection issues**: Verify target URL is accessible. Check for WAF blocking.
3. **No findings**: Not unusual for well-secured apps. Log "burpsuite clean" and rely on targeted testing.
4. **Wrapper limitations**: If the HexStrike wrapper doesn't support a feature, use nuclei + manual testing as alternative.

## Output Interpretation

- **High-confidence findings** — strong scanner leads that still require independent reproduction and demonstrated impact.
- **Tentative/informational findings** — may need manual verification. Mark as `potential`.
- **Severity mapping**: Burp uses its own severity scale. Map to standard: Critical/High/Medium/Low/Info.
- **Issue type details** — Burp provides detailed remediation advice. Include in the report.

## Evidence Capture

Save Burp scan results to `output/{target}/scans/raw/burpsuite_*.txt`. Persist findings to findings.json and SQLite with tool evidence.
