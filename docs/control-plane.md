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

The current schema version is 2. An existing version 1 database is backed up before migration using a name such as `redcode.db.v1-backup-YYYYMMDDHHMMSS`. Re-running the command against an up-to-date database is idempotent and does not create another backup.

Schema version 2 adds:

- engagement metadata and approvals;
- discovered assets;
- phase and subdomain tracking for scan/tool runs;
- exit codes and structured tool errors;
- evidence metadata and SHA-256 fields;
- relationships between findings.

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
