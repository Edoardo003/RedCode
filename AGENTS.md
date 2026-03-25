# RedCode — Cybersecurity Automation Platform

Extension di OpenCode specializzata per bug bounty, penetration testing e red teaming.

## Quick Start

```bash
# 1. Avvia HexStrike server
cd hexstrike-ai && python3 hexstrike_server.py --port 8888

# 2. Avvia LM Studio con Qwen 3.5 9B sulla macchina locale (10.10.99.100)

# 3. Avvia OpenCode da questa directory
cd /opt/Progetti/redcode && opencode
```

## Architecture

```
User → OpenCode TUI → Orchestrator (build agent, Claude Sonnet 4.6)
                          ├── @recon    → Claude Sonnet 4.6  → HexStrike MCP
                          ├── @scanner  → Claude Sonnet 4.6  → HexStrike MCP
                          ├── @exploiter → o3 (deep reason)  → HexStrike MCP
                          ├── @poc      → Qwen 3.5 9B local → writes code
                          └── @reporter → Claude Sonnet 4.6  → templates/
```

## Agents

| Agent        | Model               | Funzione                                      |
| ------------ | ------------------- | --------------------------------------------- |
| `build`      | Claude Sonnet 4.6   | Orchestratore principale, routing interattivo |
| `@recon`     | Claude Sonnet 4.6   | Reconnaissance, OSINT, subdomain enum         |
| `@scanner`   | Claude Sonnet 4.6   | Vulnerability scanning, nuclei, nikto         |
| `@exploiter` | o3                  | Exploit research, attack chain reasoning      |
| `@poc`       | Qwen 3.5 9B (local) | PoC generation, uncensored                    |
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

## Convenzioni

- L'orchestratore CHIEDE SEMPRE conferma prima di passare alla fase successiva
- I risultati degli scan vanno salvati in `output/`
- I PoC devono includere: descrizione, impatto, passi per riprodurre, codice, remediation
- I report seguono i template in `templates/`
- MAI eseguire exploit attivi senza conferma esplicita dell'utente
- Tutti i test devono essere AUTORIZZATI — mai testare target senza permesso

## MCP Servers

- **HexStrike AI** — 150+ tool di sicurezza (nmap, nuclei, sqlmap, gobuster, metasploit, etc.)
- **Filesystem** — Gestione file output, template, wordlists

## Provider

- **GitHub Copilot Pro** — Claude Sonnet 4.6, o3, GPT-4o per agenti cloud
- **LM Studio** — Qwen 3.5 9B uncensored su `http://10.10.99.100:1234` per PoC
