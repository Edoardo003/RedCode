# RedCode

[![CI](https://github.com/Edoardo003/RedCode/actions/workflows/ci.yml/badge.svg)](https://github.com/Edoardo003/RedCode/actions/workflows/ci.yml)

RedCode is an OpenCode workspace for authorized security assessments and CTFs. It coordinates focused agents, exposes local security tooling through MCP, and keeps scope, findings, and evidence available between phases.

It is not an autonomous penetration-testing system. The analyst approves active work, validates findings, and owns the final report.

## What It Adds

- A primary `redcode` orchestrator with recon, OSINT, scanning, validation, CTF, reporting, template, and simulation subagents.
- A local control plane for engagement manifests, deterministic scope checks, database migrations, and runtime diagnostics.
- MCP connections to HexStrike, a constrained filesystem, Fetch, Playwright, and SQLite, with access enabled by agent role.
- JSON evidence handoffs plus a SQLite index for targets, findings, approvals, tool runs, credentials, and evidence metadata.
- Separate assessment and CTF workspaces.
- A project-local RedCode theme with light and dark variants, without modifying the OpenCode binary.

## Why I Built It

During an assessment, useful context is repeatedly moved between reconnaissance output, scanners, manual verification, notes, and reports. RedCode experiments with keeping that context structured while leaving security decisions with the analyst.

The project originally tried broader platform integrations and binary-level branding. Those approaches were removed because they increased maintenance cost without improving the core workflow. The current design favors a small launcher, explicit configuration, inspectable files, and an external HexStrike backend. The trade-offs are documented in [`docs/design.md`](docs/design.md).

## Architecture

```text
Analyst
  -> OpenCode TUI
       -> redcode orchestrator
            -> recon -> osint -> scanner -> exploiter -> reporter
            -> ctf -> category skill -> solver/write-up
            -> socialeng / templates (optional support)
       -> MCP
            -> HexStrike HTTP backend
            -> filesystem / Fetch / Playwright / SQLite
            -> Burp (optional, disabled)
  -> redcode launcher
       -> engagement manifest / scope preflight / doctor / migrations
```

`redcode` is the only primary agent. Specialist prompts are deliberately short and load detailed tool guidance from `.opencode/skills/` only when required.

## Quick Start

RedCode currently targets a Linux host with Bash. The interactive setup requires Git, Python 3.10+, Node.js 22+, `curl`, and an authenticated OpenCode installation.

```bash
git clone https://github.com/Edoardo003/RedCode.git
cd RedCode
chmod +x setup.sh redcode install-tools.sh
./setup.sh

./redcode engagement init \
  --name local-lab \
  --workflow ctf \
  --scope http://127.0.0.1:3000

./redcode doctor
./redcode
```

`setup.sh` creates local configuration, initializes SQLite, clones HexStrike and wordlists, installs the configured MCP dependencies, and optionally creates a local `systemd` service. It can instead point the MCP bridge at a HexStrike backend on a trusted LAN.

`install-tools.sh` is optional. It installs small `core`, `web`, `network`, or `ctf` profiles from the host's configured APT repositories. It does not add third-party repositories or execute remote install scripts.

```bash
sudo ./install-tools.sh core web
```

## Control Plane

```bash
./redcode engagement init --name demo --scope app.example.test
./redcode engagement validate
./redcode scope check app.example.test scan
./redcode db migrate
./redcode doctor
```

The engagement manifest is the source of target and action scope. `out_of_scope` rules take precedence. This is a deterministic preflight, not a network sandbox: HexStrike requests are not yet forced through an enforcing policy proxy.

Usage can be inspected without imposing a fixed token budget:

```bash
./redcode stats          # sessions associated with this repository path
./redcode stats --all    # all sessions in the OpenCode data store
```

Automatic compaction prunes stale tool output. Existing per-agent iteration limits remain unchanged.

## Workflows

Commands are OpenCode prompts, not deterministic APIs.

| Command | Purpose |
| --- | --- |
| `/target <target>` | Map the declared attack surface. |
| `/osint <target>` | Gather relevant public intelligence with source attribution. |
| `/scan <target>` | Run prioritized vulnerability discovery. |
| `/exploit <finding>` | Validate one explicitly authorized finding. |
| `/report [generic\|hackerone\|bugcrowd]` | Generate an evidence-based report. |
| `/full-chain <target>` | Coordinate the applicable assessment phases. |
| `/full-chain <target> --aggressive` | Execute one approved plan without routine phase prompts. |
| `/resume <target>` | Resume from reliable saved state. |
| `/ctf ...` | Start or resume a named challenge or local lab. |

Normal mode requests approval before consequential active phases. Aggressive mode does not expand scope and stops on ambiguity, instability, destructive impact, or a material plan change.

CTF commands accept labeled free-form arguments:

```text
/ctf category=web event=local-lab challenge=juice-shop url=http://127.0.0.1:3000
/ctf category=rev event=demo challenge=crackme artifact=./artifacts/crackme
```

RedCode never submits a flag. It returns a candidate and its verification status.

## Data Layout

```text
output/
  {target}/
    recon/findings.json
    osint/findings.json
    scans/findings.json
    exploits/findings.json
    reports/
  ctf/{event}/{challenge}/
    artifacts/
    solver/
    evidence/
    progress.json
    writeup.md
```

JSON is the complete phase handoff. SQLite is a normalized secondary index; persistence is agent-driven and should be checked by the analyst. Generated output, databases, manifests, wordlists, downloaded HexStrike code, and custom Nuclei templates are excluded from Git.

## Project Status

Implemented and tested in the repository:

- engagement validation, activation, and exact/wildcard/CIDR/URL scope decisions;
- schema initialization and version 1 to version 2 migration with backup;
- runtime and MCP diagnostics;
- agent/configuration/link contract checks;
- shell syntax checks through CI;
- a loopback-only Juice Shop integration test and a sanitized evidence fixture derived from two clean-container runs.

Current limitations:

- Agent workflows and evidence persistence are prompt-driven, not transactional.
- HexStrike is cloned without a pinned compatibility version; Node MCP entry points are pinned in the repository.
- Burp MCP is disabled until a specific implementation is selected and tested.
- Tool profiles are limited to packages available from the host's configured APT repositories; additional HexStrike capabilities require separate, reviewed installation.
- The confirmed development environment is Ubuntu 24.04.4 LTS x86_64 with OpenCode 1.3.17 and HexStrike 6.0.0; this is not a support matrix.

Run the local suite with:

```bash
python3 -m unittest discover -s tests -v
bash -n redcode setup.sh install-tools.sh
```

## Legal Boundary

Use RedCode only with explicit authorization and documented scope. Respect rules of engagement, rate limits, privacy obligations, and service availability. Tool or model output is not a validated finding by itself.

## Documentation

- [`docs/design.md`](docs/design.md): architectural decisions and trade-offs.
- [`docs/control-plane.md`](docs/control-plane.md): manifests, migrations, doctor, and scope matching.
- [`docs/juice-shop-e2e.md`](docs/juice-shop-e2e.md): local reproduction and the sanitized CTF fixture.
- [`examples/juice-shop-e2e/`](examples/juice-shop-e2e/): redacted evidence from the validated run.
- [`AGENTS.md`](AGENTS.md): repository contracts for coding agents.
- [`opencode.jsonc`](opencode.jsonc): models, MCP servers, compaction, and permissions.
- [`schema.sql`](schema.sql): current SQLite schema.
- [`templates/`](templates/): tracked report templates.
- [`LICENSE`](LICENSE): MIT license.
