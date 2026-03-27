# RedCode — Cybersecurity Automation Platform

Extension di OpenCode specializzata per bug bounty, penetration testing e red teaming.

## Quick Start

```bash
# 1. Avvia HexStrike server
cd hexstrike-ai && python3 hexstrike_server.py --port 8888

# 2. Avvia LM Studio con Qwen 3.5 9B sulla macchina locale

# 3. Avvia OpenCode da questa directory
cd /opt/Progetti/redcode && opencode
```

## Architecture

```
User → OpenCode TUI → Orchestrator (redcode, Claude Sonnet 4.6)
                          ├── @recon      → Claude Haiku 4.5    → HexStrike MCP
                          ├── @scanner    → GPT-5.4-mini        → HexStrike MCP
                          ├── @exploiter  → GPT-5.4             → HexStrike MCP
                          ├── @poc        → Qwen 3.5 9B (local) → writes code
                          ├── @templates  → Claude Haiku 4.5    → Nuclei YAML
                          └── @reporter   → Claude Sonnet 4.6   → templates/
```

## Agents

| Agent        | Model               | Funzione                                      |
| ------------ | ------------------- | --------------------------------------------- |
| `redcode`    | Claude Sonnet 4.6   | Orchestratore principale, routing interattivo |
| `@recon`     | Claude Haiku 4.5    | Reconnaissance, OSINT, subdomain enum         |
| `@scanner`   | GPT-5.4-mini        | Vulnerability scanning, nuclei, nikto         |
| `@exploiter` | GPT-5.4             | Exploit research, attack chain reasoning      |
| `@poc`       | Qwen 3.5 9B (local) | PoC generation, uncensored                    |
| `@templates` | Claude Haiku 4.5    | Nuclei template creation from findings        |
| `@reporter`  | Claude Sonnet 4.6   | Report writing multi-formato                  |

## Commands

| Comando                | Descrizione                                              |
| ---------------------- | -------------------------------------------------------- |
| `/target <domain>`     | Avvia reconnaissance su un target                        |
| `/scan <target>`       | Avvia vulnerability scanning                             |
| `/exploit <vuln>`      | Ricerca exploit e tecniche di bypass                     |
| `/poc <vuln-id>`       | Genera Proof of Concept                                  |
| `/report`              | Genera report di sicurezza                               |
| `/full-chain <target>` | Pipeline completo: recon → scan → exploit → poc → report |

## Skills

Carica una skill con il tool `skill` durante la conversazione:

- `bug-bounty` — Workflow completo bug bounty
- `web-pentest` — Web application penetration testing
- `api-pentest` — API security testing
- `cloud-pentest` — Cloud infrastructure assessment
- `network-pentest` — Network penetration testing
- `osint` — Open Source Intelligence gathering
- `report-writing` — Security report writing

## Handoff Format

All agents use this JSON format when saving findings to `output/{phase}/findings.json` and to the SQLite database. This enables structured handoff between phases.

```json
{
  "target": "example.com",
  "scope": "*.example.com",
  "phase": "recon|scan|exploit|poc|report",
  "timestamp": "2025-01-15T10:30:00Z",
  "findings": [
    {
      "id": "FIND-001",
      "type": "subdomain|port|service|vuln|exploit|poc",
      "severity": "critical|high|medium|low|info",
      "title": "SQL Injection in /api/search",
      "url": "https://example.com/api/search?q=test",
      "evidence": "Response contains unescaped SQL error...",
      "cvss": 8.1,
      "cwe": "CWE-89",
      "confidence": "confirmed|likely|potential",
      "raw_path": "output/scans/raw/nuclei_001.txt",
      "next_steps": ["Attempt exploitation", "Create PoC"]
    }
  ],
  "metadata": {
    "tools_used": ["nmap", "nuclei"],
    "duration_seconds": 120
  }
}
```

Each agent:

1. Reads previous phase findings from `output/{prev_phase}/findings.json` and SQLite
2. Does its work
3. Saves structured findings to `output/{phase}/findings.json`
4. Persists each finding to the SQLite `findings` table

## SQLite Schema

The database schema is defined in `schema.sql`. Tables:

- `targets` — tracked domains/IPs with scope and status
- `findings` — all findings across all phases, linked to targets
- `scans` — tool execution history with output paths
- `credentials` — discovered credentials linked to findings

On first use, initialize the database by reading and executing `schema.sql` via the SQLite MCP.

## Wordlists

Available in `wordlists/`:

- `wordlists/SecLists/` — discovery wordlists (directories, DNS, passwords, fuzzing)
- `wordlists/PayloadsAllTheThings/` — exploit payloads (XSS, SQLi, SSRF, SSTI, command injection, etc.)

Browse via the filesystem MCP to find the right list for the task.

## Nuclei Templates

- `templates/nuclei/custom/` — RedCode custom templates created by `@templates` agent
- System templates are managed by Nuclei itself (`~/.local/nuclei-templates/`)

## Convenzioni

- L'orchestratore CHIEDE SEMPRE conferma prima di passare alla fase successiva
- I risultati vanno salvati in `output/` nel formato handoff JSON sopra definito
- Ogni finding va persistito anche nel database SQLite
- I PoC devono includere: descrizione, impatto, passi per riprodurre, codice, remediation
- I report seguono i template in `templates/`
- MAI eseguire exploit attivi senza conferma esplicita dell'utente
- Tutti i test devono essere AUTORIZZATI — mai testare target senza permesso
- All'avvio di una sessione, controllare il database SQLite per target e findings precedenti

## MCP Servers

- **HexStrike AI** — 150+ tool di sicurezza (nmap, nuclei, sqlmap, gobuster, metasploit, etc.) — timeout 1 ora
- **Filesystem** — Gestione file output, template, wordlists
- **Brave Search** — OSINT, CVE lookup, exploit research
- **Playwright** — Browser automation per verifiche web
- **Fetch** — HTTP client per testing endpoint
- **SQLite** — Persistenza findings e tracking assessment

## Provider

- **GitHub Copilot Pro** — Claude Sonnet 4.6, GPT-5.4, GPT-5.4-mini, Claude Haiku 4.5
- **LM Studio** — Qwen 3.5 9B uncensored per PoC generation
