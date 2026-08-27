# RedCode Control Plane

The local control plane provides runtime diagnostics, database migrations, engagement manifests, and deterministic scope preflight checks. It is implemented by `scripts/redcode_control.py` and exposed through the `redcode` launcher.

## Runtime Doctor

Run:

```bash
./redcode doctor
```

The doctor checks:

- required commands and supported Python and Node.js versions;
- required repository paths;
- engagement manifest validity and local file permissions;
- SQLite schema version, required tables, and resume columns;
- HexStrike health, backend version, host-tool availability, and capability profiles;
- OpenCode MCP startup status.

Use `--mode arsenal` after connecting a workspace to validate Arsenal instead of
HexStrike:

```bash
./redcode arsenal connect --url http://127.0.0.1:8000 --workspace <workspace-id>
./redcode doctor --mode arsenal
```

The connect command auto-discovers Arsenal's private `agent-token`. With a custom
Arsenal data directory, set `ARSENAL_AGENT_TOKEN_FILE` or add
`--token-file /absolute/path/to/agent-token`.

Use `--skip-mcp` when only local files, the database, and HexStrike should be checked:

```bash
./redcode doctor --skip-mcp
```

Warnings do not make the command fail. Configuration, database, HexStrike, or MCP errors produce a non-zero exit code.

## Database Migrations

`setup.sh` initializes or upgrades the configured database automatically. It can also be run directly:

```bash
./redcode db migrate
```

The current schema version is 8. Existing version 1–7 databases are backed up before migration using a name such as `redcode.db.v7-backup-YYYYMMDDHHMMSS`. Migration 008 adds the redacted identifier registry and is independent of workflow migration 007. Re-running the command against an up-to-date database is idempotent and does not create another backup.

Schema version 2 adds:

- engagement metadata and approvals;
- discovered assets;
- phase and subdomain tracking for scan/tool runs;
- exit codes and structured tool errors;
- evidence metadata and SHA-256 fields;
- relationships between findings.

Schema version 3 adds persistent bug-bounty state:

- HackerOne program and policy metadata;
- symbolic identities without live secrets;
- normalized endpoints with Burp history provenance;
- application workflows and lifecycle states;
- ranked MAPPA hypotheses;
- hunt sessions and submission outcomes.

Schema version 4 turns that state into a guided assistant workflow:

- reviewed policy snapshots plus structured program scope and restrictions;
- audited, redacted Burp import runs and message provenance;
- immutable test plans, tied approvals, and execution records;
- append-only hypothesis events for resume and review.

Schema version 5 binds every test plan to its reviewed policy snapshot. Version 6
adds source-aware Burp provenance plus redacted-request fingerprints, so selected
exports can be re-imported idempotently without treating two Burp projects' local
message IDs as the same record. Updating
the policy supersedes drafts and cancels active approvals before a new plan can
be approved.

Schema version 7 adds the MAPPA workflow-semantic model. Each application
workflow can persist analyst-confirmed states, ordered transitions, invariants,
assumptions, and reviewed observations. Generated semantic hypotheses receive a
stable key and reasoning JSON for explainability and deduplication; existing
generic ownership hypotheses remain compatible.

Schema version 8 adds the identifier-semantics extension. Selected path,
query, request-body, and response-body identifiers are correlated with a local
engagement-scoped HMAC fingerprint. Endpoint metadata stores generic and
semantic display templates plus candidate roles, while workflow JSON stores
relationship leads and analyst confirmations. Raw identifier values and the
HMAC key remain local and are never committed.

JSON findings remain the richer agent-to-agent handoff. SQLite provides normalized state and indexing.

## Engagement Manifests

Create an assessment manifest:

```bash
./redcode engagement init \
  --name example-assessment \
  --workflow assessment \
  --mode normal \
  --scope example.test \
  --scope '*.example.test' \
  --out-of-scope admin.example.test
```

Create a local CTF manifest:

```bash
./redcode engagement init \
  --name juice-shop-local \
  --workflow ctf \
  --scope http://127.0.0.1:3000
```

By default, the manifest is written to the path in `REDCODE_ENGAGEMENT`, or `engagement.json`. The local manifest is ignored by Git. `engagement.example.json` and `engagement.schema.json` document the tracked format.

Validate or activate a manifest explicitly:

```bash
./redcode engagement validate
./redcode engagement activate
```

Activation writes a runtime copy to `output/.redcode/current-engagement.json`. The normal launcher performs this activation automatically before starting OpenCode, allowing the filesystem MCP and the `redcode` orchestrator to read the current boundaries.

The manifest fields are:

| Field | Purpose |
| --- | --- |
| `name` | Filesystem-safe engagement identifier. |
| `workflow` | `assessment` or `ctf`. |
| `mode` | `normal` or `aggressive`. |
| `in_scope` | Allowed domains, wildcard domains, IP addresses, CIDRs, or URL prefixes. |
| `out_of_scope` | Explicit exclusions; these take precedence. |
| `allowed_actions` | Maximum permitted RedCode actions for the engagement. |
| `rate_limit_per_second` | Analyst-declared rate ceiling for agent and tool context. |
| `notes` | Rules-of-engagement context that should be preserved. |

`allowed_actions` is a scope ceiling. Including `exploit` does not replace the explicit authorization gates required by the selected workflow mode.

## Scope Preflight

Check a target and action before starting work:

```bash
./redcode scope check api.example.test scan
./redcode scope check https://api.example.test/v1 exploit
```

The command returns `ALLOW` with exit code 0 or `DENY` with exit code 1. Matching behavior is deterministic:

- explicit out-of-scope rules take precedence;
- exact domains do not include subdomains;
- wildcard domains use shell-style matching;
- CIDR rules match IP literals;
- URL rules require the same scheme, host, port, and path prefix;
- the requested action must be listed in `allowed_actions`.

## Enforcement Boundary

The manifest, launcher activation, orchestrator instructions, and scope command provide a concrete preflight and a shared scope source. They do not intercept every HexStrike API call. Complete technical enforcement would require a policy gateway that validates every target-bearing MCP request before forwarding it to HexStrike.

Do not describe the current control plane as a sandbox or absolute network boundary. The analyst must still review tool targets and generated commands.

## Runtime Profiles

The launcher writes `output/.redcode/current-runtime.json` on every start so an old
session file cannot silently select a profile.

- `standalone` activates the local engagement manifest and uses the normal MCP set;
- `arsenal` performs a live protocol handshake, binds one workspace, and applies a
  high-precedence OpenCode runtime override.

The Arsenal override enables only the mediated Arsenal bridge for bounded context,
inert proposals, and run requests. It disables HexStrike, Fetch, Playwright, Burp, Bash,
and built-in web access for every configured agent. The tracked Arsenal MCP entry
remains disabled when OpenCode is started outside the launcher or when the Standalone
profile is selected.
