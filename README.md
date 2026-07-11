# RedCode

RedCode is an AI-assisted offensive security workspace built on [OpenCode](https://opencode.ai/) for authorized assessments and CTF workflows.

It coordinates specialized agents, connects security tools through MCP, and keeps findings and evidence organized between phases. RedCode assists an analyst; it is not an autonomous penetration-testing system, and its output requires manual review.

> Use RedCode only on systems and challenges you are explicitly authorized to test.

## Key Capabilities

- Routes assessment work across reconnaissance, OSINT, scanning, exploitation, reporting, social-engineering support, and Nuclei template agents.
- Connects OpenCode to HexStrike, a constrained project filesystem, Playwright, Fetch, and SQLite through MCP.
- Preserves assessment findings in per-target JSON files and provides a SQLite schema for cross-session tracking.
- Separates assessment data from CTF artifacts, solver code, checkpoints, and write-ups.
- Supports a local HexStrike backend or a backend hosted on a trusted local network.
- Provides report templates for generic assessments, HackerOne, and Bugcrowd formats.

## Why RedCode?

Offensive security work often involves moving the same context between discovery tools, notes, verification steps, and reports. RedCode gives OpenCode a security-focused workspace in which agents share a target-specific evidence structure instead of starting each phase from an empty conversation. The goal is to reduce repetitive coordination and evidence handling while leaving scope decisions, intrusive actions, validation, and reporting judgment with the analyst.

## Human-in-the-Loop Design

- The analyst declares the target and confirms that the requested activity is authorized and in scope.
- The default assessment workflow asks before active reconnaissance, intrusive tests, exploitation, and phase transitions where appropriate.
- `/exploit` is an active command and must be used only after explicit authorization for the selected finding and target.
- `/full-chain --aggressive` is an experimental opt-in mode. It asks for one explicit authorization before automatically advancing; it should not be used when the rules of engagement require approval per action.
- Tool output is evidence, not proof by itself. Findings and credentials require analyst validation before they are treated as confirmed or included in a deliverable.
- CTF agents may verify candidate flags against a supplied format or local checker, but they do not submit flags or operate outside the declared challenge scope.

## Architecture

```text
Analyst
  -> OpenCode
       -> redcode (main orchestrator)
            -> assessment: recon -> osint -> scanner -> exploiter -> reporter
            -> CTF: ctf -> category skill -> solver and write-up
            -> support: socialeng, templates
       -> MCP connections
            -> HexStrike HTTP backend
            -> filesystem, Playwright, Fetch, SQLite
            -> Burp MCP (optional, disabled by default)
```

Agent prompts live in [`.opencode/agent/`](.opencode/agent/), command prompts in [`.opencode/command/`](.opencode/command/), and model assignments in [`opencode.jsonc`](opencode.jsonc). The `redcode` agent is the default orchestrator.

## Quick Start

Install the requirements listed below, then run on a Linux host with Bash:

```bash
git clone https://github.com/Edoardo003/RedCode.git
cd RedCode
chmod +x setup.sh redcode install-tools.sh
./setup.sh
./redcode mcp list
./redcode
```

`setup.sh` is interactive. It creates `.env`, clones HexStrike and the configured wordlist repositories, installs MCP dependencies, installs Playwright Chromium, and asks whether HexStrike runs locally or on a trusted LAN host. In local mode it can install a `systemd` service when run as root.

The large optional tool installer is separate:

```bash
sudo ./install-tools.sh
```

`install-tools.sh` uses `apt-get`, writes to system locations, and is intended for a disposable or dedicated Debian/Ubuntu-style security host. Review it before running it.

## Example Workflow

The commands below are entered inside OpenCode:

```text
/target app.example.test
```

1. Confirm the authorized scope, then review passive reconnaissance before approving active enumeration.
2. Inspect `output/app.example.test/recon/findings.json` and remove any out-of-scope assets.
3. Continue with `/osint app.example.test` or `/scan app.example.test` after analyst review.
4. Validate scanner results manually. Use `/exploit <selected finding>` only when active exploitation is explicitly permitted.
5. Preserve raw output and reproduction evidence under the relevant target phase.
6. Generate a report with `/report generic` and review it under `output/app.example.test/reports/`.

The commands are OpenCode prompts, not a deterministic pipeline API. The analyst should review each handoff and verify that generated files and database records are complete.

## Assessment Commands

| Command | Purpose | Status |
| --- | --- | --- |
| `/target <target>` | Start passive reconnaissance and request approval before active reconnaissance. | Core |
| `/osint <target>` | Gather in-scope public intelligence and preserve sources. | Core |
| `/scan <target>` | Run tool-assisted vulnerability discovery from available context. | Core |
| `/exploit <finding>` | Actively investigate an explicitly authorized finding. | Core, high impact |
| `/report [generic\|hackerone\|bugcrowd]` | Build a report from collected evidence and templates. | Core |
| `/full-chain <target>` | Orchestrate the five assessment phases with confirmations. | Experimental |
| `/full-chain <target> --aggressive` | Use one authorization gate, then auto-advance within scope. | Experimental |
| `/resume <target>` | Resume from prompt-managed checkpoints. | Experimental; see limitations |

## CTF Workflow

Use `/ctf` only for a named competition, local lab, supplied artifact, or explicitly provided challenge service:

```text
/ctf category=web event=local-lab challenge=juiceshop url=http://127.0.0.1:3000
/ctf category=rev event=spring-ctf challenge=crackme artifact=./artifacts/crackme
/ctf category=crypto event=spring-ctf challenge=rsa-warmup artifact=./artifacts/challenge.txt flag_format=FLAG{...}
```

`/ctf` currently accepts free-form arguments rather than enforcing a positional grammar, so labeled fields are the least ambiguous form. The CTF agent routes to one of the tracked `ctf-web`, `ctf-pwn`, `ctf-rev`, `ctf-crypto`, `ctf-forensics`, `ctf-osint`, or `ctf-misc` skills.

CTF work is kept under `output/ctf/` and is not written to the assessment database. A local Juice Shop run has been used during development to exercise the web workflow, but the repository does not yet contain automated CTF fixtures or test results for every category.

## Structured Findings and Evidence

Assessment agents are instructed to exchange `findings.json` files and persist compatible records to SQLite. The handoff includes target, scope, phase, confidence, evidence paths, and next steps; the complete contract is documented in [`AGENTS.md`](AGENTS.md), and the database tables are defined in [`schema.sql`](schema.sql).

JSON remains the richer evidence handoff. SQLite stores normalized target, finding, scan, and credential records, but does not contain every JSON field. Persistence is agent-driven and must be checked by the analyst; it is not transactionally enforced by the launcher.

## Optional Integrations

### HexStrike Deployment

The HexStrike MCP client is local to OpenCode. Its HTTP backend may run on the same machine or at `HEXSTRIKE_URL` on a trusted LAN. The repository clones HexStrike during setup rather than vendoring or pinning it.

### Burp MCP

The `burp` remote MCP entry in [`opencode.jsonc`](opencode.jsonc) is disabled by default. When an analyst supplies a trusted `BURP_MCP_URL` and enables the entry, it is intended for proxy-history or request analysis and analyst-reviewed Repeater workflows. RedCode does not claim reliable autonomous exploitation through Burp.

### Proxy Environment

When `PROXY_URL` is set, the [`redcode`](redcode) launcher exports standard HTTP proxy environment variables. Support still depends on each underlying tool; raw-socket tools such as Nmap do not become proxied automatically.

## Output Structure

Generated output is excluded from Git by default.

```text
output/
  {target}/
    recon/findings.json
    osint/findings.json
    scans/findings.json
    exploits/findings.json
    socialeng/
    reports/
  ctf/{event}/{challenge}/
    artifacts/
    solver/
    evidence/
    progress.json
    writeup.md
```

Custom Nuclei templates are generated under `templates/nuclei/custom/`, which is also ignored. Reusable report templates are tracked in [`templates/`](templates/).

## Project Status and Limitations

RedCode is a personal, experimental security workspace, not a production-ready platform.

- **Implemented core:** OpenCode agent and command definitions, MCP configuration, local/LAN HexStrike setup, launcher environment handling, report templates, structured assessment handoff, and isolated CTF workspaces.
- **Experimental:** full-chain orchestration, aggressive mode, checkpoint/resume behavior, social-engineering artifact generation, generated Nuclei templates, and CTF categories beyond the locally exercised web workflow.
- **Optional:** the large security-tool installer, Burp MCP, proxy configuration, LAN-hosted HexStrike, and downloaded wordlists.
- **Known limitation:** resume-related prompts reference `phase` and `subdomain` fields that are not currently present in the `scans` table. SQLite-assisted resume should not be treated as reliable until the schema and prompts are aligned.
- There is no automated test suite, CI workflow, release process, supported-platform matrix, or pinned HexStrike revision.
- MCP packages invoked through `npx ...@latest` and OpenCode Go model availability may change independently of this repository.
- No license file is currently included.

See [`DOCS_REVIEW.md`](DOCS_REVIEW.md) for the documentation audit and prioritized follow-up work.

> **TODO:** Add a terminal recording of setup and a redacted end-to-end local-lab demonstration. No screenshot or demo asset is currently tracked.

## Requirements

- OpenCode installed and authenticated for the account running RedCode.
- Linux with Bash, Git, `curl`, Python 3 with `pip3`, and Node.js 22 or newer with `npx`.
- Network access during setup to clone repositories and install Python, Node, browser, and wordlist dependencies.
- Root access for the optional `systemd` service and `install-tools.sh`. Python package installation may also require an appropriate virtual environment or package-manager policy on the host.
- An OpenCode provider plan that can access the model identifiers configured in [`opencode.jsonc`](opencode.jsonc).

`setup.sh` checks command availability and enforces Node.js 22+, but it does not currently enforce a Python version or detect a supported Linux distribution.

## Legal Use

Use RedCode only under explicit authorization and documented scope. Respect rules of engagement, rate limits, privacy obligations, and service availability. Never use assessment or CTF workflows against unrelated systems, and never treat generated findings as validated client results without manual review.

## Documentation

- [`AGENTS.md`](AGENTS.md): repository instructions, safety boundaries, agents, and the assessment handoff contract.
- [`DOCS_REVIEW.md`](DOCS_REVIEW.md): audit findings, unresolved gaps, and recommended next steps.
- [`opencode.jsonc`](opencode.jsonc): MCP and model configuration.
- [`.opencode/agent/`](.opencode/agent/): specialized agent prompts.
- [`.opencode/skills/`](.opencode/skills/): assessment, CTF, and HexStrike tool guidance.
- [`schema.sql`](schema.sql): SQLite schema.
- [`templates/`](templates/): report templates.
