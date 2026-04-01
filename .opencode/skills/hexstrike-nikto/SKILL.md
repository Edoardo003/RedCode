---
name: "hexstrike-nikto"
description: "Correct parameters, proxy configuration, and scanning patterns for HexStrike nikto_scan MCP tool."
---

# HexStrike nikto_scan — Tool Skill

Web server misconfiguration and vulnerability scanner. Checks for outdated software, dangerous files, server misconfigurations, default installations, and known vulnerabilities. Complements nuclei — nikto focuses on server-level issues while nuclei focuses on application-level CVEs.

## Accepted Parameters

| Parameter | Type   | Required | Description                                                    |
| --------- | ------ | -------- | -------------------------------------------------------------- |
| `target`  | string | **YES**  | URL or IP:port (e.g. `https://example.com`, `10.10.99.120:80`) |
| `flags`   | string | no       | Nikto flags (e.g. `-Tuning 9`, `-useproxy`)                    |

## Common Usage

```
# Standard scan
nikto_scan(target="https://example.com")

# Scan specific port
nikto_scan(target="http://10.10.99.120:8080")

# With proxy
nikto_scan(target="https://example.com", flags="-useproxy http://user:pass@host:port")

# Comprehensive scan (all tuning options)
nikto_scan(target="https://example.com", flags="-Tuning 123456789abc")

# Target specific checks
nikto_scan(target="https://example.com", flags="-Tuning 9")

# Skip specific checks (speed up scan)
nikto_scan(target="https://example.com", flags="-Tuning x6")

# With SSL
nikto_scan(target="https://example.com", flags="-ssl")
```

## Tuning Reference

| Tuning | Description                            |
| ------ | -------------------------------------- |
| `1`    | Interesting file / seen in logs        |
| `2`    | Misconfiguration / default file        |
| `3`    | Information disclosure                 |
| `4`    | Injection (XSS/Script/HTML)            |
| `5`    | Remote file retrieval (inside webroot) |
| `6`    | Denial of Service                      |
| `7`    | Remote file retrieval (server-wide)    |
| `8`    | Command execution / remote shell       |
| `9`    | SQL injection                          |
| `a`    | Authentication bypass                  |
| `b`    | Software identification                |
| `c`    | Remote source inclusion                |
| `x`    | Reverse tuning (exclude instead)       |

## Proxy Configuration

```
nikto_scan(target="https://example.com", flags="-useproxy http://user:pass@host:port")
```

**Note**: nikto uses `-useproxy` (not `--proxy`). No trailing slash on the URL.

## Retry Strategy

1. **Timeout**: Nikto can be slow on large targets. Try with specific tuning (`-Tuning 2389`) to reduce checks.
2. **Connection refused**: Verify target is up. Check if correct port is specified.
3. **SSL errors**: Add `-ssl` flag. Or try with `-nossl` if the target redirects HTTP to HTTPS.
4. **WAF blocking**: Nikto is noisy. If blocked, skip nikto and rely on nuclei + manual checks.
5. **No findings**: Normal for well-configured servers. Log "nikto clean" and move on.

## Output Interpretation

- **OSVDB-xxx references** — legacy vulnerability database IDs. Cross-reference with CVE if available.
- **"Server leaks inodes via ETags"** — informational, low severity
- **"Uncommon header X-Powered-By"** — technology fingerprint, feeds exploitation strategy
- **"Default file found: /phpinfo.php"** — HIGH. Contains server config, module list, paths.
- **"Directory indexing found"** — MEDIUM. May expose sensitive files.
- **"Apache/2.4.29 appears to be outdated"** — Check specific CVEs for that version via searchsploit.
- **"TRACE method enabled"** — MEDIUM. Cross-site tracing attack vector.
- **"robots.txt contains interesting entries"** — Follow up — check the disallowed paths.

## Evidence Capture

Save raw nikto output to `output/{target}/scans/raw/nikto_*.txt`. Each finding becomes a separate entry in findings.json with appropriate severity.
