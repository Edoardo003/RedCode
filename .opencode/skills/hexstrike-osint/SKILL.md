---
name: "hexstrike-osint"
description: "Correct parameters and usage patterns for HexStrike bugbounty_osint_gathering MCP tool — full automated OSINT workflow."
---

# HexStrike bugbounty_osint_gathering — Tool Skill

Full automated OSINT workflow. Single-command intelligence gathering that runs domain intel, social media recon, email harvesting, technology profiling, and breach lookup. This is the **first tool to run** for any OSINT phase — it covers the broadest surface in one call.

## Accepted Parameters

| Parameter | Type   | Required | Description                        |
| --------- | ------ | -------- | ---------------------------------- |
| `domain`  | string | **YES**  | Target domain (e.g. `example.com`) |

## Common Usage

```
# Full automated OSINT workflow (START HERE for any new target)
bugbounty_osint_gathering(domain="example.com")
```

That's it. This tool runs a comprehensive workflow internally:

1. **Domain Intelligence** — WHOIS, DNS records, certificate transparency, IP ranges
2. **Social Media Intelligence** — sherlock-style username search, LinkedIn, social media
3. **Email Intelligence** — hunter.io, email validation, haveibeenpwned
4. **Technology Intelligence** — BuiltWith, Wappalyzer signatures, Shodan

## When to Use

- **ALWAYS** run this as the FIRST OSINT tool for any new target
- After recon completes and before detailed OSINT techniques
- When you need a quick intelligence baseline on a domain

## What It Does NOT Cover

Despite being comprehensive, this tool does NOT replace:

- **Deep search analysis** — use results returned by authorized HexStrike OSINT tools
- **Manual breach checks** — use authorized public breach sources when available
- **Historical URL discovery** — use `gau_discovery` and `waybackurls_discovery`
- **Detailed endpoint crawling** — use `hakrawler_crawl`
- **Username-specific enumeration** — use `sherlock` for individual usernames

**Workflow**: Run `bugbounty_osint_gathering` first → analyze gaps → run specialized tools for deeper coverage.

## Proxy Configuration

The tool respects `http_proxy`/`https_proxy` environment variables (auto-exported by the redcode launcher). No explicit flag needed.

## Retry Strategy

1. **Timeout**: This tool runs many subtasks. If it times out, results may be partial — check output for what completed.
2. **Partial results**: Some internal modules may fail (API keys missing, rate limits). Use the partial data and supplement with individual tools.
3. **No results**: Domain may be too new or obscure. Try individual HexStrike OSINT tools and public archives.
4. **MCP connection issues**: Retry once. If it fails again, run individual tools (theharvester, amass_enum, sherlock) separately.

## Output Interpretation

- **Emails found** — persist ALL to findings. Each is a phishing/brute-force/breach-lookup target.
- **Subdomains discovered** — merge with recon subdomain list. These feed the scanner.
- **Technology stack** — shapes scanning strategy (WordPress → wpscan, PHP → PHP-specific tests).
- **Social profiles** — feed to @socialeng for social engineering artifact generation.
- **Breach indicators** — flag for immediate credential exploitation by @exploiter.

## Evidence Capture

Save raw output to `output/{target}/osint/raw/bugbounty_osint.txt`. Persist structured findings to `output/{target}/osint/findings.json` and SQLite.
