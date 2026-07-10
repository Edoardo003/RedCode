---
description: "Run OSINT intelligence gathering on a target"
agent: osint
---

Run comprehensive OSINT intelligence gathering on:

$ARGUMENTS

## Instructions

1. Review recon results from `output/{target}/recon/` if available — ingest subdomains, WHOIS, tech stack
2. Run `bugbounty_osint_gathering` for full-spectrum domain/org intelligence
3. Email harvesting: Google dorking via Brave Search (`site:target.com "@target.com"`, `intext:"@target.com" filetype:pdf`)
4. Username enumeration: search social platforms, code repos, forums for employees
5. Breach/credential lookup: Brave Search for paste sites, breach databases, exposed credentials
6. Google dorking: exposed panels, sensitive files, directory listings, backup files
7. Metadata extraction: harvest documents, analyze EXIF/metadata for internal paths, usernames, software
8. Persist leaked credentials to SQLite immediately
9. Flag new subdomains/endpoints discovered via dorking for scanner
10. Present findings grouped by intelligence type (email, username, credential, profile, breach, document, exposure)
11. For each finding include: type, confidence, source, raw evidence, actionable next steps

Save all results to `output/{target}/osint/`.
