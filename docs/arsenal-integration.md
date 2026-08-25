# Arsenal Integration

> Status: Phase 8 embedded chat gateway and mediated execution implemented
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

OpenCode receives nine tools from the `arsenal` MCP server:

| Tool | Behavior |
| --- | --- |
| `arsenal_list_workspaces` | Lists local workspace summaries. |
| `arsenal_get_workspace_context` | Reads bounded resources, blocks, and recent jobs from the bound workspace. |
| `arsenal_list_jobs` | Pages through bound-workspace jobs using an opaque cursor. |
| `arsenal_get_job` | Reads one bound-workspace job, structured previews, and artifact metadata. |
| `arsenal_get_operation_schema` | Reads exact Tool Contract parameter IDs, constraints, options, presets, and runtime metadata. |
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

Before proposing a block, RedCode must read `arsenal_get_operation_schema` and use only
the returned parameter IDs. A validation failure permits one schema-based correction;
after a second failure the agent stops and reports the contract error. This prevents
loops caused by guessed aliases such as `host`, `target`, `ip`, or `address`.

## Embedded Chat Gateway

Arsenal can host the RedCode conversation directly in its workspace drawer. Start the
gateway on the RedCode host:

```bash
./redcode gateway start
```

The gateway is a small authenticated process in front of `opencode run --format json`.
It creates one OpenCode provider session per Arsenal chat, relays assistant text as
NDJSON, exposes only tool name/state activity, and supports cancellation. Conversations,
message state, and replayable UI events are persisted by Arsenal. Hidden reasoning,
gateway bearer tokens, MCP payloads, and raw tool output are not relayed to the browser.

The default topology is same-host loopback. For a Kali VM running Arsenal and an Ubuntu
server running RedCode, use one SSH process from Kali:

```bash
ssh -N \
  -L 8765:127.0.0.1:8765 \
  -R 18000:127.0.0.1:8000 \
  redcode-user@ubuntu-server
```

The local forward carries Arsenal-to-gateway traffic; the reverse forward lets the
gateway call the bounded Arsenal Agent APIs. Copy the two private tokens once, without
printing them to the terminal:

```bash
# Kali: copy the gateway credential from Ubuntu and keep it private.
mkdir -p ~/.local/share/redcode
scp redcode-user@ubuntu-server:.local/share/redcode/chat-gateway-token \
  ~/.local/share/redcode/chat-gateway-token
chmod 600 ~/.local/share/redcode/chat-gateway-token

# Kali: copy Arsenal's agent credential to the path the Ubuntu gateway will read.
ssh redcode-user@ubuntu-server mkdir -p .local/share/arsenal
scp ~/.local/share/arsenal/agent-token \
  redcode-user@ubuntu-server:.local/share/arsenal/agent-token
ssh redcode-user@ubuntu-server chmod 600 .local/share/arsenal/agent-token
```

Configure Arsenal's backend `.env` on Kali:

```dotenv
ARSENAL_REDCODE_GATEWAY_URL=http://127.0.0.1:8765
ARSENAL_REDCODE_ARSENAL_CALLBACK_URL=http://127.0.0.1:18000
ARSENAL_REDCODE_ARSENAL_TOKEN_FILE=/home/redcode-user/.local/share/arsenal/agent-token
```

Restart Arsenal, open a workspace, and select **RedCode**. The OpenCode TUI remains
optional. If the SSH tunnel or gateway stops, Arsenal preserves the conversation and
shows the gateway as unavailable.

Direct LAN exposure is not the recommended topology. It requires explicit remote flags,
TLS certificate/key on the gateway, HTTPS for non-loopback Arsenal origins, and a CA
file configured in Arsenal. Plain HTTP is accepted only on loopback/tunneled endpoints.

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
- direct raw MCP payload streaming to the browser;
- interactive token pairing and coordinated token rotation.

The two-step proposal and execution gate are implemented. Raw artifacts, stop control,
interactive pairing and coordinated rotation remain outside this slice.
