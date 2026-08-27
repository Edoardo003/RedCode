# RedCode

[![CI](https://github.com/Edoardo003/RedCode/actions/workflows/ci.yml/badge.svg)](https://github.com/Edoardo003/RedCode/actions/workflows/ci.yml)

RedCode is an OpenCode workspace for authorized security assessments and CTFs. It coordinates focused agents, exposes local security tooling through MCP, and keeps scope, findings, and evidence available between phases.

It is not an autonomous penetration-testing system. The analyst approves active work, validates findings, and owns the final report.

## What It Adds

- A primary `redcode` orchestrator with recon, OSINT, scanning, validation, persistent bug-bounty hunting, CTF, reporting, template, and simulation subagents.
- A local control plane for engagement manifests, deterministic scope checks, database migrations, and runtime diagnostics.
- An optional Arsenal profile with separate read-only and proposal-only protocols, a
  workspace-bound MCP bridge, and analyst-gated execution.
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
            -> Arsenal Agent APIs (read-only context + proposal-only actions)
            -> filesystem / Fetch / Playwright / SQLite
            -> Burp MCP (enabled, remote trusted VLAN)
  -> redcode launcher
       -> engagement manifest / scope preflight / doctor / migrations
```

`redcode` is the only primary agent. Specialist prompts are deliberately short and load detailed tool guidance from `.opencode/skills/` only when required.

## Quick Start

RedCode currently targets a Linux host with Bash. The interactive setup requires Git, Python 3.10+ with the `venv` module, Node.js 22+, `curl`, and an authenticated OpenCode installation.

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

To connect RedCode to a locally running Arsenal workspace instead of exposing direct
security execution tools:

```bash
./redcode --mode arsenal \
  --arsenal-url http://127.0.0.1:8000 \
  --workspace <workspace-id>
```

To use the embedded chat inside Arsenal, start the authenticated gateway on the RedCode
host. OpenCode is launched on demand for each persisted conversation; the OpenCode TUI
does not need to be open:

```bash
./redcode gateway start
```

The gateway binds to `127.0.0.1:8765`, creates a private `0600` bearer token under
`~/.local/share/redcode/`, streams assistant text and bounded tool activity, and keeps
all proposal and run confirmation gates in Arsenal. See
[`docs/arsenal-integration.md`](docs/arsenal-integration.md) for the Kali/Ubuntu tunnel.

Running `./redcode` interactively offers Standalone and Arsenal profiles. In the Arsenal
profile, RedCode negotiates protocol 1.0, binds the session to one workspace, disables
direct HexStrike/Fetch/Playwright/Burp access, and exposes bounded reads plus inert
proposal/status operations. The Agent APIs require Arsenal's private local token;
RedCode auto-discovers it without copying the secret into session state.

`setup.sh` creates local configuration, installs Python dependencies in an ignored project `.venv`, initializes SQLite, clones HexStrike and wordlists, installs the configured MCP dependencies, and optionally creates a local `systemd` service. It can instead point the MCP bridge at a HexStrike backend on a trusted LAN.

`install-tools.sh` is optional. It installs small `core`, `web`, `network`, or `ctf` profiles from the host's configured APT repositories. It does not add third-party repositories or execute remote install scripts.

```bash
sudo ./install-tools.sh core web
```

### Proxychains

Every process launched through `./redcode` receives the configured
`REDCODE_COMMAND_PREFIX`, which defaults to `proxychains4 -q`; the local
HexStrike service also uses the same prefix for its child commands. Install it
through the `core` profile (or install `proxychains4` separately) and set up
its system configuration before starting RedCode. The launcher fails closed if
the prefix executable is unavailable. The prefix is configurable through
`REDCODE_COMMAND_PREFIX` in `.env`.

`setup.sh` adds direct `localnet` exclusions for IPv4/IPv6 loopback and for the
exact numeric host and port in `BURP_MCP_URL`. This keeps local HexStrike and
the trusted Burp MCP hop reachable without bypassing Proxychains for unrelated
targets. It creates a one-time `.redcode-backup` beside the system Proxychains
configuration before changing it; without write access, setup prints the exact
rules for the operator to review and add manually. Existing proxy-list entries
and credentials are left unchanged.

After changing this value, restart the local service with
`sudo systemctl restart redcode-hexstrike`.

If `HEXSTRIKE_URL` points to a LAN backend, run the same tracked runner on the
host that runs HexStrike; a local RedCode launcher cannot prefix processes on a
remote machine.

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
| `/bugbounty <target>` | Start or resume a HackerOne MAPPA hunt from Burp and SQLite. |
| `/ctf ...` | Start or resume a named challenge or local lab. |

Normal mode requests approval before consequential active phases. Aggressive mode does not expand scope and stops on ambiguity, instability, destructive impact, or a material plan change.

CTF commands accept labeled free-form arguments:

```text
/ctf category=web event=local-lab challenge=juice-shop url=http://127.0.0.1:3000
/ctf category=rev event=demo challenge=crackme artifact=./artifacts/crackme
```

RedCode never submits a flag. It returns a candidate and its verification status.

## Bug-Bounty Assistant

`/bugbounty` is backed by a local, persistent control workflow for reviewed
program policies, selected Burp exports, application mapping, MAPPA hypotheses,
one-time test-plan approvals, evidence hashes, and draft reports. It is built
to guide an analyst through the next useful action, not to autonomously test or
submit against a program.

Use `./redcode bugbounty --help` for the local workflow and read
[`docs/bugbounty-assistant.md`](docs/bugbounty-assistant.md) before first use.
Implementation progress and verified limits are tracked in
[`docs/implementation-status.md`](docs/implementation-status.md).
The policy scope and the engagement manifest are intersected; the stricter rule
wins. Burp traffic is imported from selected JSON/JSONL exports after local
redaction rather than copying an entire proxy history into the workspace.

MAPPA extends endpoint heuristics with an analyst-confirmed application model:
workflow states and ordered transitions produce explicit invariants,
implementation assumptions, and explainable single-variable hypotheses. It
augments analyst reasoning; it does not replace approval or manual validation.
The identifier-semantics extension keeps the generic endpoint key while adding
redacted, engagement-scoped HMAC correlation for path/query/request/response
identifiers. It can propose semantic roles and co-occurrence relationships,
but only explicit analyst confirmation makes them eligible for relationship-
derived hypotheses.

The dedicated `bugbounty` agent has no direct HexStrike, Fetch, Playwright, or
Burp MCP permissions. It prepares and audits bounded plans; any approved Burp
request remains a manual analyst action.

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

Bug-bounty hunts additionally persist program metadata, symbolic identities, normalized endpoints with Burp references, application workflows (including versioned semantic state/transition/invariant JSON), redacted identifier fingerprints and semantic path metadata, ranked hypotheses with stable semantic keys and reasoning, hunt sessions, and HackerOne outcomes. Live cookies, bearer tokens, and raw identifier values do not belong in these mapping tables.

## Project Status

Implemented and tested in the repository:

- schema version 8 with backwards-compatible workflow-semantics and identifier-semantics migrations;

- engagement validation, activation, and exact/wildcard/CIDR/URL scope decisions;
- schema initialization and version 1–7 to version 8 migration with backup;
- runtime and MCP diagnostics;
- agent/configuration/link contract checks;
- shell syntax checks through CI;
- a loopback-only Juice Shop integration test and a sanitized evidence fixture derived from two clean-container runs.
- Arsenal protocol 1.0 clients, workspace handshake, runtime isolation policy, five
  bounded read tools, four proposal/status tools, and the authenticated chat gateway.

Current limitations:

- Agent workflows and evidence persistence are prompt-driven, not transactional.
- HexStrike is cloned without a pinned compatibility version; Node MCP entry points are pinned in the repository.
- Burp MCP is enabled and configured through `BURP_MCP_URL`; the external server address and VLAN path must be reachable, and the selected Burp-side implementation must expose the tools expected by the agent.
- Tool profiles are limited to packages available from the host's configured APT repositories; additional HexStrike capabilities require separate, reviewed installation.
- The confirmed development environment is Ubuntu 24.04.4 LTS x86_64 with OpenCode 1.3.17 and HexStrike 6.0.0; this is not a support matrix.
- The Arsenal integration can create inert block proposals and run requests. It cannot
  accept drafts, confirm execution, stop jobs, or read raw artifact content; those
  operational decisions remain in Arsenal.

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
- [`docs/arsenal-integration.md`](docs/arsenal-integration.md): profile selection, handshake, MCP tools, and trust boundary.
- [`docs/juice-shop-e2e.md`](docs/juice-shop-e2e.md): local reproduction and the sanitized CTF fixture.
- [`examples/juice-shop-e2e/`](examples/juice-shop-e2e/): redacted evidence from the validated run.
- [`AGENTS.md`](AGENTS.md): repository contracts for coding agents.
- [`opencode.jsonc`](opencode.jsonc): models, MCP servers, compaction, and permissions.
- [`schema.sql`](schema.sql): current SQLite schema.
- [`templates/`](templates/): tracked report templates.
- [`LICENSE`](LICENSE): MIT license.
