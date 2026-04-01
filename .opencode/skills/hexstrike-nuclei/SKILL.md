---
name: "hexstrike-nuclei"
description: "Correct parameters, banned flags, retry strategies, and scanning patterns for HexStrike nuclei_scan MCP tool."
---

# HexStrike nuclei_scan — Tool Skill

Template-based vulnerability scanner. Detects CVEs, misconfigurations, exposures, and default credentials across web services using Nuclei's template engine via the HexStrike MCP wrapper.

## Accepted Parameters

| Parameter         | Type   | Required | Description                                                     |
| ----------------- | ------ | -------- | --------------------------------------------------------------- |
| `target`          | string | **YES**  | URL or IP to scan (e.g. `https://example.com`)                  |
| `severity`        | string | no       | Comma-separated: `critical,high,medium,low,info`                |
| `tags`            | string | no       | Comma-separated: `cve,rce,sqli,xss,lfi,ssrf,misconfig,exposure` |
| `template`        | string | no       | Path to a specific template file                                |
| `additional_args` | string | no       | **ONLY for proxy** — nothing else                               |

## BANNED FLAGS (WILL CRASH — DO NOT USE)

These flags in `additional_args` cause "flag provided but not defined" errors. The MCP wrapper builds the CLI command itself — extra flags get appended raw and break it.

**NEVER put ANY of these in `additional_args`:**

`-k`, `-no-verify`, `-no-color`, `-duc`, `-rl`, `-timeout`, `-retries`, `-sk`, `-stats`, `-si`, `-silent`, `-nc`, `-disable-update-check`, `-json`, `-jsonl`, `-o`, `-output`, `-rate-limit`, `-bulk-size`, `-concurrency`, `-headless`, `-system-resolvers`, `-r`, `-interactsh-url`, `-iserver`, `-ni`, `-no-interactsh`

**Why**: The HexStrike wrapper handles output format, rate limiting, and interactsh internally. Passing these flags duplicates or conflicts with the wrapper's own configuration.

## Correct Usage Examples

```
# Broad scan — all severities, common tags
nuclei_scan(target="https://example.com", severity="critical,high,medium,low,info", tags="cve,rce,sqli,xss,lfi,ssrf")

# Targeted — critical/high only
nuclei_scan(target="https://api.example.com", severity="critical,high", tags="cve,rce,sqli")

# With proxy
nuclei_scan(target="https://example.com", severity="critical,high,medium", tags="cve,rce,sqli,xss", additional_args="--proxy http://user:pass@host:port")

# Specific template
nuclei_scan(target="https://example.com", template="/path/to/custom-template.yaml")

# XSS/SSRF focused
nuclei_scan(target="https://example.com", severity="medium,high,critical", tags="xss,ssrf,redirect")

# Minimal — just target (runs all templates)
nuclei_scan(target="https://example.com")
```

## WRONG Usage Examples (WILL FAIL)

```
# WRONG: banned flags in additional_args
nuclei_scan(target="https://example.com", additional_args="-k -no-color -duc")
# Error: "flag provided but not defined: -k"

# WRONG: output flags
nuclei_scan(target="https://example.com", additional_args="-json -o results.json")
# Error: wrapper handles output format internally

# WRONG: rate limiting flags
nuclei_scan(target="https://example.com", additional_args="-rl 10 -timeout 30 -retries 3")
# Error: multiple "flag provided but not defined" errors

# WRONG: interactsh flags
nuclei_scan(target="https://example.com", additional_args="-ni -no-interactsh")
# Error: wrapper manages interactsh configuration
```

## MCP Throttling (CRITICAL)

**Max 2 nuclei scans in parallel.** The HexStrike MCP server crashes with "Connection closed" (MCP error -32000) when overloaded with 3+ simultaneous nuclei processes.

Scan subdomains **sequentially** or in **batches of 2**:

```
# Batch 1: scan sub1 and sub2 in parallel
nuclei_scan(target="https://sub1.example.com", severity="critical,high,medium", tags="cve,rce,sqli,xss")
nuclei_scan(target="https://sub2.example.com", severity="critical,high,medium", tags="cve,rce,sqli,xss")
# Wait for both to complete

# Batch 2: scan sub3 and sub4
nuclei_scan(target="https://sub3.example.com", ...)
nuclei_scan(target="https://sub4.example.com", ...)
```

## Retry Strategy

1. **First failure**: Remove ALL `additional_args`. Retry with just `target`, `severity`, `tags`
2. **Second failure**: Simplify severity to `critical,high` only
3. **Third failure**: Try with just `target` (no severity, no tags — full default scan)
4. **Still failing**: Report TOOL FAILURE. Do NOT add more flags — adding flags makes it worse

## Common Failure Patterns

| Error                            | Cause                              | Fix                                             |
| -------------------------------- | ---------------------------------- | ----------------------------------------------- |
| `flag provided but not defined`  | Banned flag in additional_args     | Remove ALL additional_args, retry               |
| `Connection closed` / MCP -32000 | Too many parallel scans            | Reduce to max 2 parallel, wait between batches  |
| Empty results                    | Target may be down or WAF blocking | Verify target is live first, try with proxy     |
| Timeout                          | Large scan scope                   | Narrow severity to `critical,high`, narrow tags |

## Proxy Configuration

```
additional_args="--proxy http://user:pass@host:port"
```

**No trailing slash.** Use `http://user:pass@host:port` not `http://user:pass@host:port/`.

The proxy flag is the ONLY acceptable use of `additional_args`.

## Output Interpretation

- **Template matches with severity** = real finding, report it
- **`[info]` severity matches** = informational, group separately
- **No matches** = target clean for tested templates (not necessarily vuln-free)
- **Verify CVE matches**: cross-check the CVE number, affected software, and version against the actual target before reporting

## Scanning Strategy

1. **First pass** — broad: `severity="critical,high,medium"`, `tags="cve,rce,sqli,xss,lfi,ssrf"`
2. **Second pass** — targeted: based on detected tech stack (e.g., `tags="wordpress"` if WP detected)
3. **Third pass** — custom templates from `templates/nuclei/custom/` if they exist
