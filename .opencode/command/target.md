---
description: "Start reconnaissance on a target"
agent: recon
---

Perform full reconnaissance on the following target:

$ARGUMENTS

## Instructions

### Phase 1 — Passive Recon (start immediately)

1. DNS records (A, AAAA, MX, TXT, CNAME, NS, SOA)
2. WHOIS lookup — registrar, dates, registrant info
3. Certificate transparency — discover subdomains via crt.sh
4. Web archive — check Wayback Machine for historical pages and removed endpoints
5. Technology fingerprinting — detect CMS, frameworks, server software, WAF

### Phase 2 — Active Recon (ask my confirmation first)

1. Port scanning with `nmap_scan` — service detection, OS detection
2. Subdomain enumeration with `amass_enum`
3. Web technology detection via HTTP headers and responses
4. Virtual host discovery

### Phase 3 — Summary

Compile a structured attack surface summary with:

- All discovered subdomains
- Open ports and services with versions
- Technologies and frameworks detected
- WAF/CDN identification
- Potential entry points rated by severity (HIGH/MEDIUM/LOW)

Save all results to `output/{target}/recon/`.
