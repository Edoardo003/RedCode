# Arsenal Integration

> Status: Phases 7E–7F mediated execution and provider provenance implemented
> Protocols: `arsenal-agent-context` 1.0 and `arsenal-agent-actions` 1.0

## Purpose

The Arsenal profile lets RedCode analyze the structured state of one local Arsenal
workspace without directly invoking security tools. Arsenal remains the operational
source of truth; RedCode provides reasoning and proposes the next step.

The read protocol and action protocol are deliberately separate. The only action
available to RedCode is creating an inert, Tool Contract-valid block draft and reading
its review status. RedCode cannot accept or reject drafts, create blocks, or start jobs.

## Start a Session

Start Arsenal first, then run:

```bash
./redcode --mode arsenal \
  --arsenal-url http://127.0.0.1:8000 \
  --workspace <workspace-id>
```

If `--workspace` is omitted in an interactive terminal, RedCode lists the available
workspaces. With no TTY, multiple workspaces require an explicit ID. The default origin
is `http://127.0.0.1:8000`; Phase 7C rejects non-loopback hosts.

Every Agent API request also carries a bearer token read from Arsenal's private
`agent-token` file. RedCode auto-discovers
`$XDG_DATA_HOME/arsenal/agent-token` (or `~/.local/share/arsenal/agent-token`). If
Arsenal uses a custom data directory, pass `--token-file` to `arsenal connect` or set
`ARSENAL_AGENT_TOKEN_FILE`. The token value is never copied into the RedCode session;
only its local path is stored.

The connection can be prepared or checked without opening OpenCode:

```bash
./redcode arsenal connect \
  --url http://127.0.0.1:8000 \
  --workspace <workspace-id>

./redcode arsenal status
./redcode doctor --mode arsenal
```

## Handshake

RedCode calls `GET /api/agent/v1/manifest` and requires:

- `protocol_name=arsenal-agent-context`;
- `protocol_version=1.0` and the matching response header;
- `access_mode=read_only`;
- workspace, job, result-preview, and artifact-metadata read capabilities.
- a valid local bearer token on every Agent API request.

It separately calls `GET /api/agent-actions/v1/manifest` and requires
`access_mode=proposal_only`, the matching protocol header, and the draft/run-request
proposal and status capabilities needed by the bridge.

It then reads the requested workspace context and verifies that Arsenal returns the same
workspace ID. A failed or incompatible handshake stops the launch. There is no silent
fallback to Standalone or HexStrike.

The bound session is stored in ignored local state at
`output/.redcode/current-arsenal-session.json`. The active profile is recorded separately
in `output/.redcode/current-runtime.json`, preventing a stale session from changing a
later Standalone launch.

## MCP Tools

OpenCode receives eight tools from the `arsenal` MCP server:

| Tool | Behavior |
| --- | --- |
| `arsenal_list_workspaces` | Lists local workspace summaries. |
| `arsenal_get_workspace_context` | Reads bounded resources, blocks, and recent jobs from the bound workspace. |
| `arsenal_list_jobs` | Pages through bound-workspace jobs using an opaque cursor. |
| `arsenal_get_job` | Reads one bound-workspace job, structured previews, and artifact metadata. |
| `arsenal_propose_block_draft` | Submits a validated, idempotent draft for analyst review. |
| `arsenal_get_block_draft` | Reads the review state of one bound-workspace draft. |
| `arsenal_request_block_run` | Requests confirmation for one exact block revision. |
| `arsenal_get_run_request` | Reads whether a request is pending, rejected, stale, or confirmed. |

The MCP functions do not accept a workspace ID. They always load it from the session
created by the analyst, so tool-generated content cannot redirect job reads to another
CTF.

Proposal acceptance remains an Arsenal UI action. Even an accepted draft creates only a
configurable block; it does not start execution.

Run confirmation is also an Arsenal-only action. RedCode can request a run for one exact
block revision, but only the analyst can queue the job from Arsenal's Agent Inbox.

## Runtime Isolation

The tracked Arsenal MCP is disabled by default. After the handshake, the launcher uses
OpenCode's inline runtime configuration to:

- enable the Arsenal MCP;
- deny HexStrike, Fetch, Playwright, and Burp tools globally;
- deny Bash and built-in web access globally;
- repeat those denials for every configured agent;
- enable the Arsenal tools for every agent;
- load the Arsenal-specific trust instructions.

Filesystem and SQLite remain available according to the existing role permissions, but
must not be used to bypass Arsenal or recreate direct network execution.

## Trust Boundary

Arsenal result previews, resource labels, block names, artifact metadata, and errors may
contain attacker-controlled text. RedCode treats them as untrusted data and ignores any
embedded instruction to reveal secrets, change scope, invoke tools, or alter policy.

The client also applies a four MiB response ceiling, requires the protocol header on
every response, and reloads the private token file for every request so rotation does
not require storing the secret in session JSON. It bypasses environment HTTP proxies
for the loopback connection.
Arsenal performs server-side redaction and truncation; RedCode preserves the associated
flags instead of guessing omitted values.

## Out of Scope

The integrated profile does not provide:

- direct block creation or modification;
- draft acceptance or run confirmation;
- job stopping;
- raw log or artifact content;
- event streaming;
- remote Arsenal connections.

The two-step proposal and execution gate are implemented. Raw artifacts, stop control,
remote connections, and interactive pairing remain outside this slice.
