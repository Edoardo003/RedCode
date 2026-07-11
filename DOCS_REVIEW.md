# Documentation Review

Review date: 2026-07-11

Scope: `README.md`, `AGENTS.md`, `opencode.jsonc`, `.env.example`, `setup.sh`, `redcode`, `.opencode/agent/`, `.opencode/command/`, `.opencode/skills/`, `schema.sql`, and `templates/`.

No runtime behavior was changed during this documentation review.

## Unsupported or Overstated Claims Removed

- Removed the description of RedCode as an Ubuntu-based platform. The core setup is Bash-based; only the optional tool installer clearly depends on an `apt-get` environment.
- Removed the sentence recommending Windows for editing and Git operations.
- Removed the unverified Python 3.10+ support claim. `setup.sh` checks for `python3` and `pip3` but does not inspect the Python version.
- Avoided repeating the `150+ tools` metric. The number belongs to an external HexStrike checkout and is not verified or pinned by this repository.
- Replaced autonomous or production-style positioning with prompt-driven, analyst-supervised workspace positioning.
- Removed any implication that all handoffs and SQLite writes are automatically enforced. Persistence is performed by agents and requires validation.
- Avoided claiming reliable checkpoint resume, broad platform support, comprehensive CTF coverage, automated exploitation reliability, or automated testing.
- Avoided claiming that standard HTTP proxy variables proxy Nmap, Hydra, or other raw-socket traffic.

## Inconsistencies Found

1. `AGENTS.md`, comments in `opencode.jsonc`, `.env.example`, and several existing prompt files contained mojibake caused by encoding errors.
2. The repository uses `.opencode/skills/` (plural), while the requested review path and some informal references used `.opencode/skill/`.
3. The `scans` table in `schema.sql` has neither `phase` nor `subdomain`, but `/resume`, `scanner`, `osint`, and `exploiter` prompts query or insert those columns.
4. Assessment phase values are singular (`scan`, `exploit`) while output directories are plural (`scans`, `exploits`). This is valid but was not explained consistently.
5. The normal workflow requests approval between phases, while `--aggressive` explicitly uses one authorization gate and then auto-progresses. Documentation now treats aggressive mode as experimental and opt-in.
6. Individual agent prompts often assert that written authorization already exists. Repository-level instructions now require the coding agent to confirm user-declared authorization and scope rather than treating prompt text as evidence.
7. `progress.json` creation, use, and deletion are prompt instructions; no launcher or application code enforces checkpoint consistency.
8. The CTF command asks the agent to parse free-form arguments but does not implement a strict argument grammar. The README now uses labeled fields to avoid implying positional parsing.
9. `templates/nuclei/custom/` is ignored and created by setup, so it is not present in a fresh checkout.
10. `examples/`, `docs/`, screenshots, demo assets, a license file, automated tests, and CI configuration are absent.

## Documentation Gaps Requiring Owner Input

- Which Linux distributions and host architectures have actually completed `setup.sh` successfully?
- Which OpenCode Go model identifiers are currently available to the intended plan, and should users be expected to replace them?
- Which assessment commands have been exercised end to end against a controlled lab, and with what acceptance criteria?
- Beyond the reported local Juice Shop run, which CTF categories have been tested with reproducible fixtures?
- Is aggressive mode intended to remain a public feature, or should it be narrowed before the repository is presented professionally?
- What HexStrike revision or compatibility range should be supported?
- Which Burp MCP server implementation and version is expected?
- What license should govern the repository and generated templates?
- Should sensitive credentials remain in the current SQLite schema as plaintext, or should storage guidance and controls be added?

## Screenshots and Demo Assets to Create

- A redacted terminal recording covering `./setup.sh`, `./redcode mcp list`, and OpenCode startup.
- A screenshot of the orchestrator showing an explicit scope confirmation and agent handoff.
- A redacted assessment output tree showing JSON findings, raw evidence, and a generated report.
- A local Juice Shop CTF demonstration showing challenge declaration, evidence, checkpoint, solver, and write-up without exposing reusable credentials.
- An architecture image only if it adds value beyond the README text diagram.

No placeholder media files were created. The README marks the missing demo as a TODO.

## Commands and Behavior Not Verified in This Review

- `./setup.sh` was inspected but not executed because this review ran in a Windows workspace and setup performs network installs and clones.
- `sudo ./install-tools.sh` was not executed because it is a root-level, system-modifying installer.
- `/target`, `/osint`, `/scan`, `/exploit`, `/report`, `/full-chain`, and `/resume` were inspected as prompts but not run end to end during this review.
- CTF categories other than the owner-reported local Juice Shop web run were not exercised.
- Burp MCP connectivity and Repeater integration were not tested.
- LAN-hosted HexStrike setup was not retested.
- Markdown was checked structurally and internal repository links were resolved locally; no external link checker was run.

## Recommended Next Steps

1. **Align `schema.sql` and resume prompts.** Decide whether to add `phase` and `subdomain` columns with a migration or remove those fields from prompt SQL, then add a resume fixture.
2. **Review high-impact agent prompts.** Remove unconditional authorization assumptions and reconcile aggressive-mode wording with the intended human-in-the-loop policy.
3. **Add controlled integration tests.** Start with configuration parsing, schema initialization, MCP startup checks, and a local Juice Shop workflow that asserts output paths without attacking external systems.
4. **Pin external dependencies.** Record a tested HexStrike revision and reconsider `@latest` MCP dependencies for reproducibility.
5. **Create a minimal test matrix.** Document the exact Linux distribution, architecture, Python, Node.js, OpenCode, and Docker versions used in successful runs.
6. **Add a license and security/data-handling guidance.** Address credential storage, evidence retention, redaction, and responsible disclosure.
7. **Add redacted portfolio media.** Capture the setup, scope gate, structured handoff, and final report workflow after the underlying schema issue is fixed.
8. **Add category-specific CTF fixtures.** Use small local artifacts for pwn, reverse engineering, crypto, and forensics before describing those workflows as validated.
