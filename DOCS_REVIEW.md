# Documentation and Repository Review

Review date: 2026-07-11

Scope: `README.md`, `AGENTS.md`, configuration, setup and launcher scripts, agents, commands, skills, database schema, templates, and the confirmed VM runtime.

The initial documentation-only review was followed by an owner-approved control-plane implementation: MIT licensing, runtime diagnostics, database schema version 2, migrations, engagement manifests, deterministic scope preflight, and focused tests.

## Unsupported or Overstated Claims Removed

- Removed autonomous and production-ready positioning. RedCode remains an analyst-supervised, prompt-driven workspace.
- Removed the generic Ubuntu platform claim and replaced it with one confirmed development environment.
- Avoided treating the number of HexStrike MCP functions as the number of installed host tools.
- Avoided claiming that JSON and SQLite persistence are transactionally guaranteed by the launcher.
- Avoided claiming comprehensive CTF coverage, reliable autonomous exploitation, broad platform support, or complete scope enforcement.
- Avoided claiming that standard HTTP proxy variables proxy raw-socket tools.

## Confirmed Owner and Runtime Decisions

- Confirmed environment: Ubuntu 24.04.4 LTS x86_64, Proxmox `6.17.2-1-pve` kernel, Python 3.12.3, Node.js 24.18.0, OpenCode 1.3.17, and HexStrike 6.0.0.
- Model identifiers are those offered through the OpenCode Go gateway and may depend on plan availability.
- A local Juice Shop run exercised API discovery and mass assignment by registering a user with the `admin` role.
- Aggressive mode remains an intentional opt-in workflow with one initial authorization gate.
- HexStrike remains an external HTTP API backend called through its local MCP client. Compatibility should be checked rather than presented as a vendored component.
- Burp MCP remains optional and disabled until a specific server implementation is selected and tested.
- The repository uses the MIT License.
- Plaintext credential fields in local SQLite are an accepted owner decision. The database remains ignored by Git and should use restrictive local permissions.

## Inconsistencies Found

1. Several legacy agent and installer files still contain mojibake from earlier encoding conversions.
2. Agent prompts contain substantial duplicated policy and tool guidance, increasing context size and contradiction risk.
3. Phase values are singular (`scan`, `exploit`) while output directories are plural (`scans`, `exploits`). This is intentional and now documented.
4. `progress.json` creation and deletion remain prompt instructions rather than transactional application behavior.
5. `/ctf` accepts free-form arguments instead of a strict positional grammar; labeled fields are now documented.
6. `templates/nuclei/custom/` is generated and ignored, so it is absent in a fresh checkout.
7. The optional installer uses unpinned packages and several unchecked downloads, and it suppresses a number of installation failures.
8. Current HexStrike health reports 65 available host tools out of 127 detected tools. Capability varies significantly by category.

The previous `scans.phase` and `scans.subdomain` mismatch is resolved by schema version 2 and migration `002_control_plane.sql`.

## Implemented Follow-Up

- Added `./redcode doctor` for dependency, path, manifest, database, HexStrike capability, and MCP checks.
- Added versioned database initialization and migration with a timestamped backup for version 1 databases.
- Added engagement, asset, approval, evidence, and finding-relation tables.
- Added JSON engagement manifests with a tracked JSON Schema.
- Added deterministic exact-domain, wildcard, CIDR, URL-prefix, action, and out-of-scope checks.
- Added automatic manifest activation under `output/.redcode/` for the orchestrator.
- Added 13 unit tests covering schema initialization, migration, manifest activation, validation, and scope decisions.
- Added the MIT License.

## Remaining Documentation Gaps

- No broader Linux distribution or architecture support matrix exists beyond the confirmed VM.
- Assessment commands have not yet been exercised as a repeatable integration suite with machine-checked acceptance criteria.
- CTF categories beyond the local Juice Shop web workflow still lack repository fixtures.
- No tested Burp MCP implementation or version is documented.
- No formal HexStrike API compatibility range is defined.
- No data-retention, redaction, or client-evidence handling policy is documented beyond Git exclusions and local permissions.

## Screenshots and Demo Assets to Create

- A redacted terminal recording of setup, engagement initialization, doctor, and OpenCode startup.
- An orchestrator screenshot showing manifest scope and an explicit authorization gate.
- A redacted assessment output tree showing JSON findings, raw evidence, SQLite state, and a report.
- A local Juice Shop demonstration showing the API discovery, mass-assignment evidence, checkpoint, solver, and write-up.

No placeholder media files were created. The README marks the missing demo as a TODO.

## Commands and Behavior Not Fully Verified

- `sudo ./install-tools.sh` was inspected but not rerun because it modifies the host extensively.
- `/target`, `/osint`, `/scan`, `/exploit`, `/report`, `/full-chain`, and `/resume` still lack automated end-to-end acceptance tests.
- CTF categories other than the owner-reported local Juice Shop run were not exercised.
- Burp MCP and LAN-hosted HexStrike were not retested during this follow-up.
- Markdown, internal links, shell syntax, schema migration, manifest behavior, and scope matching were checked locally.

## Recommended Next Steps

1. Add a capability-aware planner that uses HexStrike `/health` before selecting tools.
2. Reduce duplicated policy text across the large agent prompts and load shared policy once.
3. Add CI for unit tests, shell syntax, schema initialization, JSON/JSONC validation, Markdown links, and agent/skill references.
4. Add a controlled Juice Shop integration test with expected finding and evidence assertions.
5. Split `install-tools.sh` into `core`, `web`, `network`, `ctf`, `cloud`, and `all` profiles with pinned versions and checksums.
6. Add deterministic finding validation and evidence hashing before report generation.
7. Add `/retest` and structured fixed/still-vulnerable/regressed outcomes.
8. Add local fixtures for pwn, reverse engineering, crypto, and forensics.
9. Introduce a policy gateway only when complete technical blocking of out-of-scope HexStrike calls becomes a requirement.
