# RedCode

RedCode is an Ubuntu-based OpenCode workspace for authorized security assessments and CTF challenges. It keeps an assessment workflow and a CTF workflow separate, while `redcode` remains the main orchestrator for both.

## What It Includes

- Assessment orchestration: recon, OSINT, scanning, exploitation, reporting, and resumable checkpoints.
- HexStrike backend managed locally or consumed from a trusted LAN host.
- Local MCP bridges for HexStrike, filesystem access, Playwright, Fetch, and SQLite.
- CTF specialist for web, pwn, reverse engineering, crypto, forensics, OSINT, and misc challenges.
- OpenCode Go models configured per agent in `opencode.jsonc`.

## Platform

RedCode runs on Ubuntu. Windows is suitable for editing the repository, commits, and GitHub operations; run setup, MCPs, HexStrike, and security tooling on the Ubuntu VM or server.

## Requirements

- OpenCode installed for the account that runs RedCode.
- Ubuntu with Python 3.10+, pip, Git, curl, and Node.js 22+ LTS.
- Root access only when installing the optional `systemd` service for a local HexStrike backend.

## Quick Start

On the Ubuntu host:

```bash
git clone https://github.com/Edoardo003/RedCode.git
cd RedCode
chmod +x setup.sh redcode install-tools.sh
./setup.sh
./redcode
```

`setup.sh` asks where the HexStrike HTTP backend runs:

- `local`: installs dependencies and can enable `redcode-hexstrike.service`.
- `lan`: keeps the MCP bridge local to OpenCode while connecting it to a trusted LAN backend URL.

Check runtime status with:

```bash
./redcode mcp list
systemctl status redcode-hexstrike.service
```

Run `./install-tools.sh` separately on the host that runs HexStrike when the full optional security and CTF toolset is needed.

## Configuration

Copy `.env.example` to `.env` if setup has not already created it:

```bash
HEXSTRIKE_MODE=local
HEXSTRIKE_URL=http://127.0.0.1:8888
REDCODE_DB=./redcode.db
BURP_MCP_URL=
PROXY_URL=
```

Burp is disabled by default. Enable it in `opencode.jsonc` only after configuring its trusted remote URL.

## Architecture

```text
User
  -> redcode (main orchestrator)
       -> assessment agents: recon, osint, scanner, exploiter, reporter
       -> ctf agent: challenge classification, solver workflow, write-up
       -> support agents: socialeng, templates
       -> local MCP bridges
            -> HexStrike HTTP backend
            -> filesystem, Playwright, Fetch, SQLite
```

Agent models are intentionally configured only in `opencode.jsonc`, which is the source of truth for the OpenCode Go plan.

## Assessment Commands

| Command | Purpose |
| --- | --- |
| `/target <domain>` | Start reconnaissance on a declared target. |
| `/osint <target>` | Gather authorized intelligence. |
| `/scan <target>` | Run vulnerability scanning from prior findings. |
| `/exploit <finding>` | Investigate selected, authorized findings. |
| `/report [format]` | Generate a security report from collected evidence. |
| `/full-chain <target>` | Run the five-phase assessment pipeline. |
| `/resume <target>` | Resume a checkpointed assessment phase. |

Assessment results live under:

```text
output/{target}/
  recon/
  osint/
  scans/
  exploits/
  reports/
```

## CTF Workflow

Use `/ctf` only for a named competition, local lab, supplied artifact, or explicitly provided challenge URL.

```text
/ctf web juiceshop local-lab http://127.0.0.1:3000
/ctf rev crackme local-lab ./artifacts/crackme
/ctf crypto rsa-warmup spring-ctf ./artifacts/challenge.txt
```

`@ctf` chooses the matching category skill:

- `ctf-web`
- `ctf-pwn`
- `ctf-rev`
- `ctf-crypto`
- `ctf-forensics`
- `ctf-osint`
- `ctf-misc`

CTF work is isolated from assessment data and may use local solvers and debuggers:

```text
output/ctf/{event}/{challenge}/
  artifacts/
  solver/
  evidence/
  progress.json
  writeup.md
```

Flags, attachments, solver output, and event-specific data stay inside ignored output directories. RedCode verifies flag candidates but never submits them automatically.

## Local Juice Shop Test

Juice Shop is an optional local test for the `ctf-web` workflow. With Docker installed on the Ubuntu host, bind it only to loopback:

```bash
docker run --rm --name redcode-juiceshop -p 127.0.0.1:3000:3000 bkimminich/juice-shop
```

Then use:

```text
/ctf web juiceshop local-lab http://127.0.0.1:3000
```

This tests CTF routing, local web scope, evidence storage, checkpoints, and write-up generation. It does not replace category fixtures for pwn, reverse, crypto, or forensics.

## Legal Use

Use RedCode only against authorized assessment targets, local labs, or explicitly scoped CTF challenges. Keep challenge and assessment scope separate, and never direct CTF tooling at unrelated public systems.
