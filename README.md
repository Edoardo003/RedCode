# RedCode

Cybersecurity automation platform built on [OpenCode](https://opencode.ai). Transforms OpenCode into a full security assessment toolkit for bug bounty, penetration testing, and red teaming.

## Quick Start

```bash
git clone https://github.com/YOUR_USER/redcode
cd redcode
chmod +x setup.sh && ./setup.sh
opencode
```

Inside OpenCode, type `/target example.com` to begin.

## Prerequisites

- [OpenCode](https://opencode.ai/docs) installed
- Node.js 18+ (for MCP servers)
- Python 3.10+ (for HexStrike)
- [LM Studio](https://lmstudio.ai) running `qwen3.5-9b-uncensored-hauhaucs-aggressive` (for PoC generation)
- [Brave Search API key](https://brave.com/search/api/) (free tier, for OSINT)

## Architecture

```
opencode (runtime)
├── opencode.jsonc          ← providers, MCP servers, agent config
└── .opencode/
    ├── agent/              ← agent system prompts
    │   ├── build.md        ← orchestrator (routes to other agents)
    │   ├── recon.md        ← reconnaissance
    │   ├── scanner.md      ← vulnerability scanning
    │   ├── exploiter.md    ← exploit research (o3 reasoning)
    │   ├── poc.md          ← PoC code generation (local model)
    │   └── reporter.md     ← report writing
    ├── command/            ← slash commands
    │   ├── target.md       ← /target → @recon
    │   ├── scan.md         ← /scan → @scanner
    │   ├── exploit.md      ← /exploit → @exploiter
    │   ├── poc.md          ← /poc → @poc
    │   ├── report.md       ← /report → @reporter
    │   └── full-chain.md   ← /full-chain → full pipeline
    └── skills/             ← loadable skill packs
        ├── bug-bounty/
        ├── web-pentest/
        ├── api-pentest/
        ├── cloud-pentest/
        ├── network-pentest/
        ├── osint/
        └── report-writing/
```

## Agents

| Agent                    | Model              | Purpose                                                        |
| ------------------------ | ------------------ | -------------------------------------------------------------- |
| **build** (orchestrator) | claude-sonnet-4-6  | Routes tasks, manages pipeline, asks for confirmation          |
| **@recon**               | claude-sonnet-4-6  | Target enumeration, OSINT, subdomain discovery, port scanning  |
| **@scanner**             | claude-sonnet-4-6  | Nuclei, nikto, fuzzing, automated vulnerability detection      |
| **@exploiter**           | o3                 | Exploit chains, bypass techniques, deep vulnerability analysis |
| **@poc**                 | qwen3.5-9b (local) | Proof-of-concept exploit code — runs on uncensored local model |
| **@reporter**            | claude-sonnet-4-6  | Professional reports for HackerOne, Bugcrowd, or clients       |

## Commands

| Command                | Description                                   |
| ---------------------- | --------------------------------------------- |
| `/target <domain>`     | Start reconnaissance on a target              |
| `/scan`                | Run vulnerability scans on recon results      |
| `/exploit`             | Analyze vulnerabilities and research exploits |
| `/poc`                 | Generate proof-of-concept code                |
| `/report`              | Write vulnerability report                    |
| `/full-chain <domain>` | Run the full assessment pipeline end-to-end   |

## MCP Servers

| Server           | Purpose                                                                |
| ---------------- | ---------------------------------------------------------------------- |
| **HexStrike**    | 150+ security tools (nmap, nuclei, sqlmap, gobuster, metasploit, etc.) |
| **Filesystem**   | Read/write output directory, templates, wordlists                      |
| **Brave Search** | OSINT, CVE lookup, exploit research, bug bounty write-ups              |
| **Playwright**   | Browser automation — verify XSS, take screenshot evidence              |
| **Fetch**        | HTTP client — test API endpoints, custom requests                      |
| **SQLite**       | Persist findings across sessions, track assessment progress            |

## Skills

Skills auto-load based on context. Available skill packs:

- **bug-bounty** — Platform rules, scope management, submission best practices
- **web-pentest** — OWASP Top 10, injection techniques, auth testing
- **api-pentest** — REST/GraphQL testing, auth bypass, rate limiting
- **cloud-pentest** — AWS/GCP/Azure misconfigurations, IAM, storage exposure
- **network-pentest** — Service exploitation, lateral movement, protocol attacks
- **osint** — Intelligence gathering, source prioritization, OPSEC
- **report-writing** — Professional formatting, evidence standards, CVSS methodology

## Configuration

Copy `.env.example` to `.env` and set:

```bash
LM_STUDIO_URL=http://10.10.99.100:1234/v1   # Your LM Studio endpoint
BRAVE_API_KEY=BSA...                          # From brave.com/search/api
REDCODE_DB=./redcode.db                       # SQLite database path
```

## Output Structure

All results are saved to `output/`:

```
output/
├── recon/          ← Target enumeration results
│   └── raw/        ← Raw tool output
├── scans/          ← Vulnerability scan results
│   └── raw/        ← Raw tool output
├── exploits/       ← Exploit analysis documents
├── pocs/           ← Generated PoC code
└── reports/        ← Final vulnerability reports
```

## How It Works

1. **You** open `opencode` in the redcode directory
2. **Build agent** greets you, asks about the target and scope
3. **You** type `/target example.com` or describe what you want
4. **Orchestrator** proposes a plan and asks for confirmation
5. **Specialized agents** execute each phase, reporting back
6. **You** confirm before each phase transition
7. **Reporter** generates platform-ready reports

The entire flow is interactive — nothing runs without your approval.

## Legal

This tool is for **authorized security testing only**. Always ensure you have written permission before testing any target. Unauthorized access to computer systems is illegal.
