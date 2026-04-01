---
name: "hexstrike-httpx"
description: "Correct parameters, probe strategies, and output interpretation for HexStrike httpx probe/scan MCP tool."
---

# HexStrike httpx — Tool Skill

HTTP toolkit for probing live web servers. Takes a list of subdomains/IPs and identifies which ones have active web servers, their status codes, titles, technologies, and response sizes. Usually the FIRST tool run after recon to filter live hosts.

---

## Accepted Parameters

| Parameter         | Type   | Required | Description                                                  |
| ----------------- | ------ | -------- | ------------------------------------------------------------ |
| `target`          | string | **YES**  | Single URL, domain, IP, or path to file with list of targets |
| `additional_args` | string | no       | Extra httpx flags                                            |

**Note**: The HexStrike MCP wrapper for httpx may have specific parameter names. If the tool is called `httpx_scan`, `httpx_probe`, or similar, use the correct function name. Check available MCP tools if unsure.

---

## Common Usage Patterns

### Probe subdomains for live web servers

```
httpx(target="subdomains.txt", additional_args="-sc -title -tech-detect -follow-redirects")
```

### Single domain probe

```
httpx(target="https://example.com", additional_args="-sc -title -server -tech-detect")
```

### With proxy

```
httpx(target="subdomains.txt", additional_args="-sc -title -tech-detect -http-proxy http://user:pass@host:port")
```

### Filter live hosts by status code

```
httpx(target="subdomains.txt", additional_args="-sc -mc 200,301,302,403 -title")
```

---

## Useful Flags for `additional_args`

| Flag                | Description                                         |
| ------------------- | --------------------------------------------------- |
| `-sc`               | Show status code                                    |
| `-title`            | Show page title                                     |
| `-tech-detect`      | Detect technologies (Wappalyzer-style)              |
| `-server`           | Show server header                                  |
| `-follow-redirects` | Follow HTTP redirects                               |
| `-mc 200,301,302`   | Match only these status codes                       |
| `-fc 404,503`       | Filter OUT these status codes                       |
| `-cl`               | Show content length                                 |
| `-method GET`       | HTTP method                                         |
| `-http-proxy URL`   | Proxy (use `-http-proxy`, not `--proxy`)            |
| `-threads 10`       | Concurrency (default 50, reduce if getting blocked) |
| `-timeout 10`       | Request timeout in seconds                          |
| `-retries 2`        | Number of retries                                   |

---

## COMMON ERRORS AND FIXES

### Wrong proxy flag

```
# WRONG — double dash
httpx(target="example.com", additional_args="--proxy http://user:pass@host:port")

# CORRECT — httpx uses -http-proxy
httpx(target="example.com", additional_args="-http-proxy http://user:pass@host:port")
```

### Port confusion

httpx probes port 80 (HTTP) and 443 (HTTPS) by default. If a service runs on a non-standard port:

```
httpx(target="example.com:8080", additional_args="-sc -title")
```

### Target format

```
# GOOD — domain only, httpx adds http/https
httpx(target="example.com")

# GOOD — explicit scheme
httpx(target="https://example.com")

# GOOD — file with one target per line
httpx(target="/path/to/subdomains.txt")

# BAD — multiple targets in one string
httpx(target="example.com,sub.example.com")  # Use a file instead
```

---

## Retry Strategy

1. **Connection timeout** → Increase timeout: `-timeout 15`. Try with proxy for IP rotation.
2. **Too many errors** → Reduce threads: `-threads 5`. Target may be rate-limiting.
3. **No results** → Verify targets are correct. Try with `-follow-redirects`. Check if targets are behind a VPN/firewall.
4. **Wrong results (all 403/503)** → WAF or CDN blocking. Try with `-method HEAD`. Use proxy rotation.

---

## Output Interpretation

- **`200 [Title]`** → Live web server. Note title for technology hints.
- **`301/302`** → Redirect. Follow it (`-follow-redirects`) to see real destination.
- **`401/403`** → Access restricted. Still alive — note for auth bypass testing.
- **`404`** → Usually not interesting unless the 404 page leaks info.
- **`500/503`** → Server error or WAF block. Try later or with proxy.
- **`[tech: WordPress, PHP, Apache]`** → Technology stack. Feed to @scanner for targeted scans.

---

## Workflow Integration

1. **After recon**: Run httpx on all discovered subdomains to identify live web servers
2. **Feed results to @scanner**: Only scan live hosts (saves time on dead subdomains)
3. **Technology detection**: Use `-tech-detect` output to choose appropriate nuclei tags and templates
4. **Screenshot** (if needed): Use Playwright instead of httpx screenshots for better quality
