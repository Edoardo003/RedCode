---
name: "hexstrike-theharvester"
description: "Correct parameters, source selection, and usage patterns for HexStrike theharvester MCP tool."
---

# HexStrike theharvester — Tool Skill

Email, subdomain, and metadata harvesting tool. Gathers emails, names, subdomains, IPs, and URLs from public search engines and databases. Critical for building target profiles — every email found is a potential credential attack vector.

## Accepted Parameters

| Parameter | Type   | Required | Description                                  |
| --------- | ------ | -------- | -------------------------------------------- |
| `domain`  | string | **YES**  | Target domain (e.g. `example.com`)           |
| `flags`   | string | no       | TheHarvester flags (e.g. `-b all`, `-l 500`) |

## Common Usage

```
# Harvest from all sources
theharvester(domain="example.com", flags="-b all")

# Specific sources (faster)
theharvester(domain="example.com", flags="-b google,linkedin,dnsdumpster,crtsh")

# Limit results
theharvester(domain="example.com", flags="-b all -l 500")

# With DNS brute-force
theharvester(domain="example.com", flags="-b all -c")

# Specific source — LinkedIn (employee emails)
theharvester(domain="example.com", flags="-b linkedin")

# Specific source — search engines
theharvester(domain="example.com", flags="-b google,bing,yahoo")
```

## Source Reference

| Source        | Finds                                    |
| ------------- | ---------------------------------------- |
| `google`      | Emails, subdomains from search results   |
| `bing`        | Emails, subdomains from search results   |
| `linkedin`    | Employee names, emails                   |
| `dnsdumpster` | Subdomains, DNS records                  |
| `crtsh`       | Subdomains from certificate transparency |
| `shodan`      | IPs, banners, open ports                 |
| `all`         | All available sources                    |

## Proxy Configuration

TheHarvester respects `http_proxy`/`https_proxy` environment variables (auto-exported by the redcode launcher). No explicit flag needed.

## Retry Strategy

1. **Timeout with `-b all`**: Narrow to specific sources (`-b google,linkedin,crtsh`)
2. **Source blocked**: Try different sources. Google/Bing rate-limit aggressively — try `crtsh,dnsdumpster`
3. **0 results**: Domain may be too new or obscure. Cross-check with `amass_enum` and `subfinder_scan`
4. **API key errors**: Some sources (Shodan, Hunter) need API keys. Skip those sources if keys aren't configured.

## Output Interpretation

- **Emails found** — persist to findings. Each is a credential attack vector (brute-force, phishing, breach lookup)
- **Subdomains found** — merge with amass/subfinder results. Add to scanning queue.
- **Employee names** — use for username enumeration (firstname.lastname, f.lastname patterns)
- **IPs found** — cross-reference with port scan data
- **No results** — does NOT mean the target is clean. TheHarvester depends on public indexing; newer targets have less data.

## Evidence Capture

Save raw output to `output/{target}/recon/raw/theharvester.txt`. Harvested emails should also be persisted to `output/{target}/osint/findings.json` for OSINT correlation.
