---
name: "hexstrike-intelligence"
description: "Correct parameters and usage patterns for HexStrike analyze_target_intelligence MCP tool - AI-powered target analysis."
---

# HexStrike analyze_target_intelligence - Tool Skill

AI-powered target analysis and intelligence correlation tool. Synthesizes data from multiple sources to produce actionable intelligence about the target. Use after collecting raw data from other tools to get higher-level analysis and attack path recommendations.

## Accepted Parameters

| Parameter | Type   | Required | Description                                                       |
| --------- | ------ | -------- | ----------------------------------------------------------------- |
| `target`  | string | **YES**  | Target identifier (domain, IP, or organization name)              |
| `data`    | string | no       | Additional context data to analyze (findings, scan results, etc.) |
| `flags`   | string | no       | Analysis flags                                                    |

## Common Usage

```
# Analyze a target domain
analyze_target_intelligence(target="example.com")

# Analyze with context from previous phases
analyze_target_intelligence(target="example.com", data="Open ports: 22,80,443,8080. WordPress 5.8. Apache 2.4.29. 5 subdomains found. 3 employees identified.")

# Analyze specific IP
analyze_target_intelligence(target="10.10.99.120")

# Analyze with scan results
analyze_target_intelligence(target="example.com", data="nuclei found CVE-2023-1234, nikto found /admin/ with default creds, sqlmap confirmed blind SQLi on /api/search")
```

## When to Use

- **After Phase 1 (Recon)** - synthesize all recon data into an attack strategy
- **After Phase 2 (OSINT)** - correlate people, technology, and infrastructure intelligence
- **After Phase 3 (Scanning)** - prioritize findings and recommend exploitation order
- **During Phase 4 (Exploitation)** - when stuck, ask for alternative attack paths
- **Before reporting** - get a high-level risk assessment

## What It Provides

1. **Attack surface summary** - consolidated view of all discovered assets
2. **Vulnerability prioritization** - which findings to exploit first
3. **Attack path recommendations** - suggested exploitation chains
4. **Risk assessment** - overall security posture evaluation
5. **Blind spot identification** - what you might have missed

## Proxy Configuration

This tool runs AI analysis on collected data. No proxy needed as it does not contact the target directly.

## Retry Strategy

1. **Timeout**: Provide less context data. Large data inputs take longer to analyze.
2. **Unhelpful results**: Provide more specific context data. Generic inputs get generic analysis.
3. **Tool unavailable**: Skip and rely on manual analysis. This is an enhancement, not a requirement.

## Output Interpretation

- **Attack paths suggested** - validate each step. The AI may suggest paths that depend on unverified conditions.
- **Risk ratings** - use as a starting point, but validate with actual tool evidence.
- **Blind spots identified** - run additional tools to cover identified gaps.
- **Recommendations** - concrete next steps. Follow up with the appropriate tools.

## Integration with Pipeline

```
# After recon
analyze_target_intelligence(target="...", data="[recon findings summary]")
# -> Use recommendations to focus OSINT phase

# After scanning
analyze_target_intelligence(target="...", data="[scan findings summary]")
# -> Use recommendations to prioritize exploitation order

# When stuck during exploitation
analyze_target_intelligence(target="...", data="[current status, what failed, what worked]")
# -> Get alternative attack paths
```

## Evidence Capture

Intelligence analysis output supplements the final report. Save to `output/{target}/analysis/intelligence_*.txt`. Do NOT use AI analysis as evidence - it is a planning tool, not a finding source.
