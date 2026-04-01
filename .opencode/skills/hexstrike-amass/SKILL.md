---
name: "hexstrike-amass"
description: "Correct parameters, brute-force options, proxy configuration, and usage patterns for HexStrike amass_enum, amass_scan, and subfinder_scan MCP tools."
---

# HexStrike Subdomain Enumeration — amass_enum, amass_scan, subfinder_scan — Tool Skill

Subdomain discovery and DNS mapping tools. Find all subdomains of a target domain using passive sources (certificate transparency, DNS databases) and active brute-force. These are the backbone of recon — missing a subdomain means missing all vulnerabilities on it.

---

## amass_enum — Parameters

| Parameter | Type   | Required | Description                                   |
| --------- | ------ | -------- | --------------------------------------------- |
| `domain`  | string | **YES**  | Target domain (e.g. `example.com`)            |
| `flags`   | string | no       | Amass flags (e.g. `-brute`, `-active`, `-ip`) |

### Common Usage

```
# Passive enumeration (safe, no direct contact)
amass_enum(domain="example.com")

# Active + brute-force (aggressive)
amass_enum(domain="example.com", flags="-brute -active")

# With IP resolution
amass_enum(domain="example.com", flags="-ip -brute")

# Passive only (no DNS brute-force)
amass_enum(domain="example.com", flags="-passive")

# With specific DNS resolvers
amass_enum(domain="example.com", flags="-brute -active -r 8.8.8.8,1.1.1.1")
```

### Proxy Configuration

amass uses the `http_proxy` environment variable (auto-exported by the redcode launcher when `PROXY_URL` is set). No flag needed — it's automatic.

```
# No flag needed — amass reads http_proxy env var
amass_enum(domain="example.com", flags="-brute -active")
```

---

## amass_scan — Parameters

| Parameter | Type   | Required | Description                        |
| --------- | ------ | -------- | ---------------------------------- |
| `domain`  | string | **YES**  | Target domain (e.g. `example.com`) |
| `flags`   | string | no       | Amass flags for DNS mapping        |

Similar to amass_enum but oriented toward DNS infrastructure mapping. Use for mapping DNS relationships, ASN discovery, and infrastructure correlation.

### Common Usage

```
# Full DNS mapping
amass_scan(domain="example.com")

# With ASN discovery
amass_scan(domain="example.com", flags="-active")
```

---

## subfinder_scan — Parameters

| Parameter | Type   | Required | Description                        |
| --------- | ------ | -------- | ---------------------------------- |
| `domain`  | string | **YES**  | Target domain (e.g. `example.com`) |
| `flags`   | string | no       | Subfinder flags (e.g. `--proxy`)   |

Fastest passive subdomain finder. Uses 30+ sources (crt.sh, DNSdumpster, Shodan, VirusTotal, etc.). Purely passive — no direct target contact.

### Common Usage

```
# Standard passive enumeration
subfinder_scan(domain="example.com")

# With proxy
subfinder_scan(domain="example.com", flags="--proxy http://user:pass@host:port")

# Silent mode (just subdomains, no banners)
subfinder_scan(domain="example.com", flags="-silent")

# With specific sources
subfinder_scan(domain="example.com", flags="-sources crtsh,dnsdumpster,shodan")
```

### Proxy Configuration

```
subfinder_scan(domain="example.com", flags="--proxy http://user:pass@host:port")
```

**No trailing slash on proxy URL.**

---

## MANDATORY: Multi-Tool Strategy

You MUST use at least 3 subdomain enumeration methods. Each tool finds different subdomains:

1. **amass_enum** — broadest source coverage, DNS brute-force
2. **subfinder_scan** — fastest passive, good for quick baseline
3. **crt.sh** (via fetch MCP) — certificate transparency logs
4. **DNS brute-force** — amass `-brute` or gobuster dns mode
5. **theharvester** — catches subdomains from search engines

**Merge and deduplicate** results from all tools into one list. If total is under 3 subdomains, something went wrong — run more tools.

## Retry Strategy

1. **amass timeout**: Remove `-brute` flag, run passive only. Brute-force can take 30+ minutes.
2. **amass 0 results**: Check DNS resolution works for the domain. Try subfinder as fallback.
3. **subfinder 0 results**: Domain may be very new or obscure. Try amass with `-brute` and a DNS wordlist.
4. **Rate limited**: Add proxy flag. Or wait and retry.
5. **Tool not available**: Use the alternative (amass ↔ subfinder). Always have a backup.

## Output Interpretation

- **Subdomains found** — add ALL to the scanning queue. Every subdomain is a potential attack surface.
- **IP addresses** (from `-ip` flag) — check for shared hosting, CDN detection, internal IPs
- **Wildcard DNS** — if `*.domain.com` resolves, you need to filter out false positives
- **Internal-looking subdomains** (dev, staging, test, internal) — HIGH priority targets. Often less secured.

## Evidence Capture

Save subdomain lists to `output/{target}/recon/raw/subdomains.txt`. The complete list MUST be included in the handoff to @scanner — missing a subdomain means missing all its vulnerabilities.
