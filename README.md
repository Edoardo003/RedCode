# RedCode

Cybersecurity automation platform built on [OpenCode](https://opencode.ai). Transforms OpenCode into a full security assessment toolkit for bug bounty, penetration testing, and red teaming.

RedCode is designed to run on Ubuntu. Windows can be used to edit and manage the repository, while setup and security tooling run on the Ubuntu host or VM.

## Quick Start

```bash
git clone https://github.com/YOUR_USER/redcode
cd redcode
chmod +x setup.sh && ./setup.sh
./redcode
```

Inside OpenCode, type `/target example.com` to begin.

## Prerequisites

- [OpenCode](https://opencode.ai/docs) installed
- Node.js 18+ (for MCP servers)
- Python 3.10+ (for HexStrike)
- [Brave Search API key](https://brave.com/search/api/) (free tier, for OSINT)

## Architecture

```
opencode (runtime)
├── opencode.jsonc          ← providers, MCP servers, agent config
└── .opencode/
    ├── agent/              ← agent system prompts
    │   ├── redcode.md    ← orchestrator (routes to other agents)
    │   ├── recon.md        ← reconnaissance
    │   ├── scanner.md      ← vulnerability scanning
    │   ├── exploiter.md    ← exploit research (o3 reasoning)
    │   └── reporter.md     ← report writing
    ├── command/            ← slash commands
    │   ├── target.md       ← /target → @recon
    │   ├── scan.md         ← /scan → @scanner
    │   ├── exploit.md      ← /exploit → @exploiter
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

| Agent                      | Purpose                                                        |
| -------------------------- | -------------------------------------------------------------- |
| **redcode** (orchestrator) | Routes tasks, manages pipeline, asks for confirmation          |
| **@recon**                 | Target enumeration, OSINT, subdomain discovery, port scanning  |
| **@scanner**               | Nuclei, nikto, fuzzing, automated vulnerability detection      |
| **@exploiter**             | Exploit chains, bypass techniques, deep vulnerability analysis |
| **@reporter**              | Professional reports for HackerOne, Bugcrowd, or clients       |

Agent models come from the OpenCode Go plan and are configured only in `opencode.jsonc`.

## Commands

| Command                | Description                                   |
| ---------------------- | --------------------------------------------- |
| `/target <domain>`     | Start reconnaissance on a target              |
| `/scan`                | Run vulnerability scans on recon results      |
| `/exploit`             | Analyze vulnerabilities and research exploits |
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

The HexStrike MCP bridge runs locally beside OpenCode. Its HTTP backend can run on the same machine or on another trusted machine in the local network; `setup.sh` configures either mode.

In local mode, setup can install `redcode-hexstrike.service` so the backend starts automatically with Ubuntu and restarts after failures.

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
HEXSTRIKE_MODE=local                           # local or lan
HEXSTRIKE_URL=http://127.0.0.1:8888           # Local or LAN HexStrike backend
BRAVE_API_KEY=BSA...                           # From brave.com/search/api
REDCODE_DB=./redcode.db                        # SQLite database path
```

## Output Structure

All results are saved to `output/`:

```
output/
└── example.com/
    ├── recon/          ← Target enumeration results
    │   └── raw/        ← Raw tool output
    ├── osint/          ← Intelligence findings
    ├── scans/          ← Vulnerability scan results
    │   └── raw/        ← Raw tool output
    ├── exploits/       ← Verified exploitation evidence
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
