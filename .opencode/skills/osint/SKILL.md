---
name: osint
description: "Open Source Intelligence gathering. Use for target reconnaissance, employee enumeration, technology fingerprinting, and information gathering from public sources."
---

# Open Source Intelligence (OSINT)

Methodology for gathering intelligence from publicly available sources.

## Information Need Decision Tree

```
What information do I need?
├─ Domain/Infrastructure Intelligence
│   ├─ DNS records → dig, nslookup, DNSdumpster
│   ├─ WHOIS → Registration, registrar, contact info
│   ├─ Subdomains → Certificate transparency, amass_enum
│   ├─ IP ranges → ASN lookup, BGP data
│   ├─ Historical data → Wayback Machine, web cache
│   └─ Technology stack → HTTP headers, Wappalyzer, BuiltWith
├─ People/Employee Intelligence
│   ├─ Email addresses → theharvester, Hunter.io patterns
│   ├─ Social profiles → sherlock, LinkedIn
│   ├─ Organizational structure → LinkedIn, company pages
│   ├─ Published content → Blog posts, presentations, papers
│   └─ Username patterns → firstname.lastname, flast
├─ Technology Intelligence
│   ├─ CMS/Framework → nuclei fingerprinting, Wappalyzer
│   ├─ JavaScript libraries → Browser dev tools, retire.js
│   ├─ Server software → HTTP response headers, error pages
│   ├─ Cloud provider → IP ranges, DNS CNAME patterns
│   └─ Third-party services → SPF records, subresource domains
├─ Leaked/Exposed Data
│   ├─ Source code → GitHub/GitLab dorks
│   ├─ Credentials → Breach databases (ethical use only)
│   ├─ Internal documents → Paste sites, file sharing
│   ├─ API keys/secrets → GitHub search, TruffleHog
│   └─ Debug/staging environments → Subdomain patterns
└─ Network Intelligence
    ├─ Internet-facing services → shodan_search
    ├─ SSL/TLS certificates → crt.sh, Censys
    ├─ Open ports → Shodan, Censys, ZoomEye
    └─ BGP/routing → ASN lookup, PeeringDB
```

## OSINT Workflow

### Phase 1 — Passive Domain Intelligence

No direct contact with target. Entirely public sources.

1. **WHOIS** — Registration details, registrar, nameservers, dates
2. **DNS records** — All record types (A, AAAA, MX, TXT, CNAME, NS, SOA)
   - MX records reveal email infrastructure
   - TXT records reveal SPF (email senders), DKIM, DMARC, verification tokens
   - NS records reveal DNS provider
3. **Certificate transparency** — crt.sh query for all issued certificates
   - Reveals subdomains, internal hostnames, wildcard patterns
4. **Web archive** — Wayback Machine for historical content
   - Removed pages, old API endpoints, deprecated features
   - JavaScript files with hardcoded endpoints/keys
5. **ASN/IP range** — Identify all IP blocks owned by target
6. **Reverse DNS** — Map IPs back to hostnames

### Phase 2 — Technology Fingerprinting

1. **HTTP response headers** — Server, X-Powered-By, X-Generator
2. **HTML source analysis** — Meta generators, CSS/JS framework signatures
3. **robots.txt / sitemap.xml** — Reveals directory structure, hidden paths
4. **Error pages** — Framework-specific error messages
5. **Cookie names** — Session framework identification (JSESSIONID, PHPSESSID, etc.)
6. **SSL/TLS** — Certificate details, supported protocols, cipher suites

### Phase 3 — People & Organization OSINT

1. **Email harvesting** — `theharvester` for email patterns from public sources
2. **Username enumeration** — `sherlock` across social platforms
3. **LinkedIn** — Employee roles, technologies mentioned in job posts
4. **GitHub** — Employee accounts, organization repos, contribution history
5. **Social media** — Twitter/X, professional blogs, conference talks
6. **Job postings** — Technology stack revealed by job requirements

### Phase 4 — Leaked Data & Exposure

1. **GitHub dorking** — Search for exposed credentials, config files, internal docs:
   - `org:targetname password`
   - `org:targetname secret`
   - `org:targetname api_key`
   - `filename:.env org:targetname`
   - `filename:config.yml org:targetname`
2. **Google dorking** — Advanced search operators:
   - `site:target.com filetype:pdf`
   - `site:target.com inurl:admin`
   - `site:target.com intitle:"index of"`
   - `site:target.com ext:sql | ext:bak | ext:log`
   - `"target.com" password | secret | credential`
3. **Paste sites** — Search Pastebin, GitHub Gists for target references
4. **Cloud storage** — Check for public S3 buckets, Azure blobs:
   - `s3.amazonaws.com/targetname`
   - `targetname.s3.amazonaws.com`
   - `targetname.blob.core.windows.net`

### Phase 5 — Network Intelligence

1. **Shodan** — `shodan_search` for internet-facing services
   - Discover all ports, services, banners
   - Find IoT devices, industrial systems, exposed databases
2. **Censys** — Certificate and host search
3. **DNS brute force** — `amass_enum` for subdomain discovery

## Google Dork Cheatsheet

| Dork                            | Purpose             |
| ------------------------------- | ------------------- |
| `site:target.com`               | All indexed pages   |
| `site:target.com -www`          | Non-www subdomains  |
| `site:target.com filetype:pdf`  | PDF documents       |
| `site:target.com inurl:api`     | API endpoints       |
| `site:target.com intitle:login` | Login pages         |
| `"target.com" ext:env`          | Environment files   |
| `"target.com" ext:sql`          | SQL dumps           |
| `"target.com" password`         | Exposed credentials |

## GitHub Dork Cheatsheet

| Dork                                       | Purpose             |
| ------------------------------------------ | ------------------- |
| `org:target password`                      | Hardcoded passwords |
| `org:target secret_key`                    | Secret keys         |
| `org:target filename:.env`                 | Environment files   |
| `org:target filename:config extension:yml` | Config files        |
| `org:target filename:id_rsa`               | SSH private keys    |
| `"target.com" filename:credentials`        | Credential files    |

## HexStrike Tools

| Tool                        | Usage                           |
| --------------------------- | ------------------------------- |
| theharvester                | Email/subdomain harvesting      |
| sherlock                    | Username enumeration            |
| shodan_search               | Internet-wide service discovery |
| amass_enum                  | Subdomain enumeration           |
| analyze_target_intelligence | AI-powered target analysis      |

## Legal & Ethical Considerations

- ALL OSINT must use publicly available information
- Do NOT access breach databases containing stolen credentials
- Do NOT social engineer employees
- Do NOT access systems discovered through OSINT without authorization
- Document all sources for findings — reproducibility matters
- Respect robots.txt for automated crawling
