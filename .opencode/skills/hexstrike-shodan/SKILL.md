---
name: "hexstrike-shodan"
description: "Correct parameters and usage patterns for HexStrike shodan_search MCP tool — internet-wide device and service search."
---

# HexStrike shodan_search — Tool Skill

Internet-wide search engine for devices, services, and infrastructure. Finds exposed services, default credentials, known vulnerabilities, SSL certificates, and network topology without directly touching the target. Purely passive reconnaissance.

## Accepted Parameters

| Parameter | Type   | Required | Description                                                            |
| --------- | ------ | -------- | ---------------------------------------------------------------------- |
| `query`   | string | **YES**  | Shodan search query (e.g. `hostname:example.com`, `org:"Example Inc"`) |
| `flags`   | string | no       | Additional flags                                                       |

## Common Usage

```
# Search by hostname
shodan_search(query="hostname:example.com")

# Search by organization
shodan_search(query="org:\"Example Inc\"")

# Search by IP
shodan_search(query="net:10.10.99.0/24")

# Search by specific service
shodan_search(query="hostname:example.com port:22")

# Search for specific software
shodan_search(query="hostname:example.com product:Apache")

# SSL certificate search (finds subdomains)
shodan_search(query="ssl.cert.subject.cn:example.com")

# Search for vulnerable services
shodan_search(query="hostname:example.com vuln:CVE-2021-44228")

# Search for default credentials indicators
shodan_search(query="hostname:example.com http.title:\"Dashboard\"")
```

## Shodan Query Syntax

| Filter                 | Description          | Example                           |
| ---------------------- | -------------------- | --------------------------------- |
| `hostname:`            | Domain/subdomain     | `hostname:example.com`            |
| `org:`                 | Organization name    | `org:"Example Inc"`               |
| `net:`                 | IP range/CIDR        | `net:10.10.99.0/24`               |
| `port:`                | Specific port        | `port:3306`                       |
| `product:`             | Software name        | `product:nginx`                   |
| `version:`             | Software version     | `version:2.4.29`                  |
| `os:`                  | Operating system     | `os:"Ubuntu"`                     |
| `ssl.cert.subject.cn:` | SSL cert common name | `ssl.cert.subject.cn:example.com` |
| `http.title:`          | HTML page title      | `http.title:"login"`              |
| `vuln:`                | Known CVE            | `vuln:CVE-2021-44228`             |
| `city:`                | Geographic location  | `city:"San Francisco"`            |

## Proxy Configuration

Shodan queries go through Shodan's API — no proxy needed for the search itself. The HexStrike wrapper handles API communication.

## Retry Strategy

1. **API rate limit**: Wait and retry. Shodan limits queries per minute.
2. **No results**: Broaden the query. Try `org:` instead of `hostname:`, or search by IP range.
3. **API key errors**: Shodan requires an API key. If not configured, report TOOL FAILURE.
4. **Partial results**: Shodan free tier limits results. Note the limitation in findings.

## Output Interpretation

- **Open ports not found by nmap** — Shodan's historical data may show ports that are now filtered. Verify with nmap.
- **Software versions** — cross-reference with searchsploit for known exploits
- **SSL certificates** — may reveal internal subdomains, organization structure
- **Default pages (login, dashboard, admin)** — flag for brute-force or default credential testing
- **Known vulns listed** — HIGH priority. Verify with targeted nmap scripts or nuclei templates.
- **Historical data** — Shodan shows what was found at last scan time. Target may have changed since.

## Evidence Capture

Save raw Shodan results to `output/{target}/recon/raw/shodan.txt`. Exposed services and known vulns should be persisted as findings with confidence `likely` (Shodan data is point-in-time, needs verification).
