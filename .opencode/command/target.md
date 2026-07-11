---
description: "Map the authorized attack surface"
agent: recon
---

Map the attack surface for:

$ARGUMENTS

1. Read and validate the active engagement manifest.
2. Normalize the declared domains, hosts, IPs, CIDRs, URLs, and exclusions.
3. Begin with relevant passive DNS, certificate, archive, and public-source discovery.
4. Present passive results and request approval before active enumeration unless already approved.
5. Resolve and deduplicate assets, identify wildcard DNS and scope drift, and prioritize reachable services.
6. Save `output/{target}/recon/findings.json`, raw evidence, and compatible SQLite records.

Return asset counts, sources, confidence, coverage gaps, and exact saved paths.
