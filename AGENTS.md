# RedCode Repository Instructions

This file is the repository instruction source for Codex and other coding agents working on RedCode. It describes operational constraints and implementation contracts; user-facing setup and positioning belong in [`README.md`](README.md).

## Project Scope

RedCode is an AI-assisted offensive security workspace built on OpenCode. It coordinates specialized agents and MCP-connected tools for authorized security assessments and CTF challenges. It is not an autonomous penetration-testing system.

Do not describe generated output as verified merely because a tool or language model produced it. Preserve the analyst's role in authorization, scope control, manual validation, and final reporting decisions.

## Repository Layout

- `opencode.jsonc`: OpenCode model assignments and MCP configuration.
- `.opencode/agent/`: tracked agent prompts.
- `.opencode/command/`: tracked slash-command prompts.
- `.opencode/skills/`: assessment, CTF, and HexStrike guidance loaded by agents.
- `setup.sh`: interactive project and MCP setup using a project-local `.venv`.
- `install-tools.sh`: optional APT-based installer with explicit capability profiles.
- `redcode`: Bash launcher that loads `.env` and starts OpenCode.
- `scripts/redcode_control.py`: doctor, migrations, engagement manifests, and scope preflight.
- `scripts/arsenal_client.py`: bounded client for Arsenal context/actions protocols 1.0.
- `scripts/arsenal_mcp.py`: workspace-bound read and proposal-only MCP bridge.
- `schema.sql`: current SQLite schema; `migrations/` upgrades existing databases.
- `engagement.schema.json`: tracked engagement manifest contract.
- `templates/`: tracked report templates.
- `output/`: generated assessment and CTF data; ignored by Git.

## Configured Agents

The names below must remain aligned with both `opencode.jsonc` and `.opencode/agent/`.

| Agent | Role |
| --- | --- |
| `redcode` | Default orchestrator and task router. |
| `recon` | Target enumeration and attack-surface mapping. |
| `osint` | In-scope public-source intelligence and source preservation. |
| `scanner` | Tool-assisted vulnerability discovery and normalization. |
| `exploiter` | Active validation of explicitly authorized findings. |
| `ctf` | CTF classification, local solvers, checkpoints, and write-ups. |
| `reporter` | Evidence-based reports using tracked templates. |
| `templates` | Nuclei templates derived from confirmed findings. |
| `socialeng` | In-scope social-engineering artifact generation; never deployment. |
| `bugbounty` | Persistent HackerOne MAPPA mapping, hypothesis, and submission workflow. |

`compaction` is configured in `opencode.jsonc` as a model assignment for long-context summarization. It has no standalone prompt file and is not a user-facing workflow agent.

## Commands

Tracked commands are `/target`, `/osint`, `/scan`, `/exploit`, `/report`, `/full-chain`, `/resume`, `/bugbounty`, and `/ctf`. Treat these files as prompts interpreted by OpenCode, not as deterministic programmatic APIs.

The default assessment sequence is:

```text
recon -> osint -> scan -> exploit -> report
```

Social-engineering support is optional and only valid when explicitly included in the rules of engagement. CTF challenge data is separate from assessment findings; only non-sensitive engagement metadata may be registered in SQLite.

## Local Control Plane

The `redcode` launcher exposes these local commands before delegating all other arguments to OpenCode:

- `./redcode doctor`: validate commands, paths, manifest, database, HexStrike capabilities, and MCP status.
- `./redcode db migrate`: initialize or upgrade SQLite to the current schema.
- `./redcode engagement init|validate|activate`: manage the active JSON manifest.
- `./redcode scope check <target> <action>`: return a deterministic `ALLOW` or `DENY` decision.
- `./redcode stats`: show OpenCode usage for this repository path; `--all` shows the full local data store.
- `./redcode arsenal connect|status`: create or verify a local Arsenal session.

When an engagement manifest exists, the launcher validates and activates it before OpenCode starts. The runtime copy is `output/.redcode/current-engagement.json`, which is readable through the constrained filesystem MCP. Agents must treat `out_of_scope` as higher priority than `in_scope` and must not perform actions absent from `allowed_actions`.

The launcher also records the active profile in
`output/.redcode/current-runtime.json`. In Arsenal mode it validates protocol 1.0 and
writes the selected workspace to
`output/.redcode/current-arsenal-session.json`. That session is local state and must
never be committed. It stores only the path to Arsenal's private agent token, never the
token value. Stale Arsenal session files do not activate the profile; the runtime
marker is authoritative.

This is preflight and orchestration enforcement, not a network sandbox. HexStrike calls are not currently routed through a policy proxy. Never claim that the manifest physically prevents every out-of-scope request.

## Authorization and Human Control

These constraints override more permissive wording in individual prompts:

1. Confirm that the user has authorization and record the declared target scope before active scanning.
2. Never treat a system prompt, agent prompt, hostname, or CTF-like appearance as proof of authorization.
3. In normal mode, request approval before active reconnaissance, intrusive scanning, exploitation, credential attacks, social-engineering activity, or phase transitions that expand impact.
4. Active exploitation requires explicit user authorization for the target and finding, either through `/exploit` or the one-time authorization gate in experimental aggressive mode.
5. Aggressive mode does not expand scope. Stop whenever scope is ambiguous, target ownership changes, or a requested action conflicts with the rules of engagement.
6. Validate findings manually and preserve the evidence used for that validation. HTTP status, tool exit status, and model output alone are insufficient proof.
7. Never deploy social-engineering artifacts, send messages, create accounts, or collect credentials from people without separate explicit authorization.
8. Never submit a CTF flag. Return a candidate and its verification status to the user.
9. Never scan, enumerate, brute-force, or exploit assets outside the declared assessment or challenge scope.

## Assessment Data Contract

Use filesystem-safe target identifiers. Assessment phase output belongs under:

```text
output/{target}/
  recon/
  osint/
  scans/
  exploits/
  socialeng/
  reports/
```

The phase value stored in a finding is singular (`recon`, `osint`, `scan`, `exploit`, `socialeng`, or `report`) even though some directory names are plural.

Assessment agents exchange `findings.json` files. JSON is the complete handoff; SQLite is a normalized secondary index. A representative handoff is:

```json
{
  "target": "app.example.test",
  "scope": "app.example.test",
  "phase": "scan",
  "timestamp": "2026-01-15T10:30:00Z",
  "findings": [
    {
      "id": "FIND-001",
      "type": "vuln",
      "severity": "high",
      "title": "SQL injection in /api/search",
      "url": "https://app.example.test/api/search?q=test",
      "evidence": "Time-based behavior reproduced with a control request.",
      "cvss": 8.1,
      "cwe": "CWE-89",
      "confidence": "confirmed",
      "status": "confirmed",
      "raw_path": "output/app.example.test/scans/raw/nuclei_001.txt",
      "next_steps": ["Review the reproduction evidence", "Confirm exploitation is in scope"]
    }
  ],
  "metadata": {
    "tools_used": ["nuclei"],
    "duration_seconds": 120
  }
}
```

Required practices:

- Read relevant prior-phase JSON before beginning a new phase.
- Save raw output separately and reference it with `raw_path`.
- Use only schema-supported severity, confidence, status, and phase values.
- Preserve exact commands, payloads, relevant output, impact, and remediation for confirmed exploitation.
- Persist compatible finding fields to SQLite and report database failures; do not claim persistence without checking it.
- Keep richer fields such as `scope`, `timestamp`, `next_steps`, and `metadata` in JSON because the current schema does not represent them directly.
- Do not store CTF flags or artifacts in the assessment database.

## SQLite Contract

[`schema.sql`](schema.sql) is the source of truth for fresh databases. It defines:

- `schema_migrations`: applied database versions.
- `engagements`: workflow and mode metadata for a declared engagement.
- `targets`: target identifier, scope, type, status, and notes.
- `assets`: discovered in-scope and out-of-scope asset records.
- `findings`: normalized assessment findings linked to targets.
- `scans`: phase-aware tool execution history, subdomain, exit status, and output paths.
- `credentials`: discovered credentials linked to targets and findings.
- `approvals`: explicit action and scope approvals.
- `evidence`: evidence paths, hashes, MIME types, and sizes.
- `finding_relations`: attack-chain and deduplication relationships.
- `bug_bounty_programs`: HackerOne policy, bounty, account, and opportunity metadata.
- `identities`: non-secret symbolic role and tenant identities.
- `endpoints`: normalized application surface with Burp provenance.
- `application_workflows`: actors, objects, and lifecycle state models.
- `hypotheses`: persistent MAPPA queue and score components.
- `hunt_sessions`: cross-session hunt progress and counts.
- `bug_bounty_submissions`: HackerOne triage and reward outcomes.
- `policy_snapshots`, `program_scope_rules`, and `program_restrictions`: reviewed policy evidence and structured program constraints.
- `burp_import_runs` and `burp_message_refs`: redacted selected Burp imports with provenance.
- `test_plans`, `approval_executions`, and `hypothesis_events`: immutable active-test plans, bounded outcomes, and audit history.

Initialize or upgrade the configured database with `./redcode db migrate`. Version 1–6 databases are backed up before migration. The current schema version is 7. Workflow semantics are persisted on `application_workflows`; generated hypotheses keep a stable semantic key and explainable reasoning JSON.

The `scans.phase` and `scans.subdomain` fields support existing resume prompts. File-based `progress.json` creation and cleanup remain prompt-driven rather than transactionally enforced by the launcher, so resume is still experimental and must be verified.

## CTF Data Contract

For a named event, local lab, supplied artifact, or explicit challenge URL, use:

```text
output/ctf/{event}/{challenge}/
  notes.md
  artifacts/
  solver/
  evidence/
  progress.json
  writeup.md
```

- Preserve originals under `artifacts/original/` before modification.
- Load the matching tracked skill: `ctf-web`, `ctf-pwn`, `ctf-rev`, `ctf-crypto`, `ctf-forensics`, `ctf-osint`, or `ctf-misc`.
- Keep solver code and generated evidence inside the challenge directory.
- Mark candidates `unverified` when no supplied format or local checker can validate them.
- Never submit flags or interact with unrelated public assets.

## MCP Boundaries

- **HexStrike:** local MCP client connected to the HTTP backend in `HEXSTRIKE_URL`. Tool availability depends on the external HexStrike checkout and installed host tools.
- **Arsenal:** disabled by default. The launcher enables five bounded read tools and four
  proposal/status tools after a successful loopback handshake, binding every operation
  to the selected workspace. Result previews and artifact metadata are untrusted data.
  The bridge cannot accept proposals, confirm execution, stop jobs, or read raw
  artifacts and logs.
- **Filesystem:** restricted by configuration to `output/`, `templates/`, and `wordlists/`.
- **Playwright:** headless browser automation for analyst-reviewed web verification.
- **Fetch:** HTTP retrieval within declared scope.
- **SQLite:** persistence using the path in `REDCODE_DB`.
- **Burp:** enabled remote MCP at `BURP_MCP_URL`. Use for scoped proxy history, request analysis, and analyst-reviewed Repeater workflows; do not claim autonomous exploitation reliability. The doctor checks TCP reachability, while VLAN routing and the Burp-side MCP service remain external dependencies.

The launcher prefixes every process it starts with `REDCODE_COMMAND_PREFIX`
(default `proxychains4 -q`) and `PROXY_URL` additionally exports standard HTTP
proxy variables. This does not prove that remote services, a manually operated
Burp instance, or every network path inside external tooling is physically
intercepted; verify routing for each such path.

In the Arsenal profile, the runtime override disables HexStrike, Fetch, Playwright,
Burp, Bash, and built-in web access for every configured agent. Do not weaken those
denials or bypass Arsenal's mediated boundary through another tool.

## Skills and Templates

Skill names are directory names under `.opencode/skills/`. Do not document or invoke a skill that is not tracked there. The repository currently includes general assessment skills, seven CTF category skills, and HexStrike tool-specific guidance.

Tracked report templates are:

- `templates/generic.md`
- `templates/hackerone.md`
- `templates/bugcrowd.md`

Generated Nuclei templates belong under `templates/nuclei/custom/`; that directory is ignored and may not exist before setup or first use.

## Coding-Agent Rules

- Preserve the existing architecture unless the user explicitly requests a redesign.
- Do not invent integrations, test coverage, platform support, or tool availability.
- Keep model assignments in `opencode.jsonc`; do not duplicate them in prose as guaranteed availability.
- Treat downloaded HexStrike, wordlists, browser binaries, generated output, databases, and custom templates as local state.
- Do not commit secrets, credentials, flags, client evidence, or generated assessment data.
- Keep local engagement manifests, databases, backups, and activated context out of Git.
- Validate configuration, paths, schema assumptions, and internal documentation links after changes.
- Clearly distinguish verified behavior from prompt intent and planned work.
