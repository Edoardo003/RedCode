# Bug-Bounty Assistant

RedCode's bug-bounty assistant is a persistent, analyst-controlled workspace.
It helps turn selected Burp traffic into a map, coverage gaps, a ranked MAPPA
queue, narrowly approved test plans, evidence bundles, and report drafts. It
does not submit findings and does not make active requests by itself.

## Operating Model

```text
Reviewed policy + manifest
  -> selected Burp export
  -> redacted persistent map
  -> MAPPA hypothesis queue
  -> one immutable approved test plan
  -> reviewed evidence
  -> confirmed finding and manual-submission draft
```

The reviewed program policy narrows the active engagement manifest. A target
must be allowed by both. A program restriction also wins over a more permissive
manifest. This is a local preflight and audit gate, not a network sandbox: a
Burp MCP server must still be configured and used responsibly.

## First Run

Create an assessment manifest that includes `hunt`; add `scan` or `exploit`
only if the program policy permits those actions. Then save a local copy of the
program policy and onboard it:

```bash
./redcode engagement init \
  --name example-program \
  --workflow assessment \
  --scope app.example.test \
  --allow hunt \
  --allow exploit

./redcode bugbounty onboard \
  --program-name "Example" \
  --platform hackerone \
  --policy-file ./example-policy.md \
  --scope app.example.test \
  --reviewed-by analyst
```

The policy file is copied into ignored `output/` storage and hashed. Re-run
`onboard` whenever the policy changes; old active policy data is superseded and
any open test-plan approval is cancelled before it can be used again.

Add only symbolic identities, never credentials or cookies:

```bash
./redcode bugbounty identity add --label user-a --role member
./redcode bugbounty identity add --label user-b --role member
```

## Burp Intake

First check that the configured remote MCP endpoint implements standard
streamable HTTP and exposes the tools you expect:

```bash
./redcode bugbounty burp probe
```

The exact history and site-map tool names vary between Burp MCP servers. Rather
than silently assuming a proprietary tool contract, export only the selected,
in-scope messages to JSON or JSONL and import them through the deterministic
redactor:

```bash
./redcode bugbounty ingest \
  --file ./selected-burp-history.json \
  --identity user-a \
  --source-kind history \
  --include-bodies
```

Accepted records contain `id` (or `message_id`), `url`, `method`, `headers`,
and optional `body`; a nested `request` or `response` object is also accepted.
URLs may be represented by `scheme`, `host`, and `path`. The importer removes
values from query strings, redacts sensitive headers and body values, derives
path templates such as `/api/orders/{id}`, and skips out-of-scope messages. It
also correlates structural identifiers from path/query/request/response data
using a local HMAC key and stores only fingerprints plus field/path context in
`identifier_registry`; raw
Burp exports are never copied into RedCode output. A source-aware Burp
reference and a redacted-request fingerprint make re-importing the same selected
traffic idempotent without assuming that two Burp projects use globally unique
message IDs.

## Add Business Context Before Testing

The first `map` is an evidence-based structural map, not a claim that RedCode
understands the application's business rules. Add the small amount of analyst
context that materially changes a test decision: symbolic actors, object type,
lifecycle state, and sensitivity.

```bash
./redcode bugbounty workflow annotate \
  --host api.example.test \
  --name api \
  --actor user-a \
  --actor user-b \
  --object order \
  --state paid \
  --sensitivity 5 \
  --notes "Orders can change state after payment."
```

`--name` is the first mapped path segment (for example `api` for
`/api/orders/{id}`). Re-running `map` preserves these annotations.

### Confirm workflow semantics

The structural map deliberately does not guess business meaning from endpoint
names or redacted request values. Confirm the lifecycle graph that matters to
the hunt, then let MAPPA derive proposals from it:

```bash
./redcode bugbounty workflow state set --host api.example.test --name invites \
  --state accepted --terminal
./redcode bugbounty workflow transition add \
  --host api.example.test --name invites --from-state pending --to-state accepted \
  --endpoint-id 42 --actor user-a --sensitive
./redcode bugbounty workflow invariant add \
  --host api.example.test --name invites \
  --statement "An accepted invite cannot be accepted again" \
  --state accepted --transition TRANSITION_KEY \
  --endpoint-id 42 --assumption "The server rejects terminal-state replay"
```

Transitions preserve order and metadata (actor, endpoint, prerequisites,
postconditions, authorization effect, capabilities, trust boundary, sensitivity,
and confidence). Invariants preserve the expected property and the assumptions
that may explain a violation. `workflow learn --observation ...` appends an
analyst-reviewed observation after a test, so the next queue generation can
continue the observe → model → test → learn loop. The semantics are versioned
JSON inside `application_workflows`; no parallel table is needed.

### Review identifier semantics

Identifier roles are deliberately proposals, not facts inferred from a URL.
Inspect the redacted candidates and co-occurrence leads, then confirm only the
semantics supported by application context:

```bash
./redcode bugbounty identifier list
./redcode bugbounty identifier confirm --endpoint-id 42 --position 3 \
  --role segment_id --confirmed-by analyst
./redcode bugbounty identifier relationship list
./redcode bugbounty identifier relationship confirm --workflow-id 7 \
  --from-role segment_id --to-role app_group_id --relation scoped-by \
  --confirmed-by analyst
```

Use `identifier reject` with a reason when a candidate is wrong. Confirmed
relationships can add a single-variable relationship hypothesis to the queue;
unreviewed leads never do. The generic endpoint template remains authoritative
for deduplication, while the semantic display template improves explainability.

`queue --generate` keeps the baseline ownership/state hypothesis for eligible
endpoints. Its score uses actual imported symbolic identities and tenants,
workflow sensitivity, number of observations, endpoint coverage, and the
program's duplicate-risk value. It also creates deduplicated semantic proposals
for confirmed transition, invariant, terminal-state, authorization-change,
trust-boundary, and identifier-relationship cases. Each proposal is explainable
and includes a suggested control request, a single-variable change, and an
expected secure result. If a
workflow has no confirmed semantics, generation degrades to the existing
generic baseline rather than fabricating business meaning. The queue remains a
prioritization aid, not proof.

For a business-logic idea that is more specific than the baseline, add a
contextual hypothesis instead of forcing it into a generic URL heuristic:

```bash
./redcode bugbounty hypothesis add \
  --endpoint-id 42 \
  --actor user-a \
  --object-owner tenant-b \
  --object-state paid \
  --statement "A member cannot update a paid order from another tenant." \
  --created-by analyst
```

Optional `--*-score` flags (0–5) override only the relevant MAPPA component;
the resulting priority and its components remain visible in `queue` output.

## Guided Daily Loop

```bash
./redcode bugbounty status
./redcode bugbounty map
./redcode bugbounty queue --generate
```

For the selected hypothesis, create a minimal plan with a control request, one
permitted change, expected result, proof, stop condition, and cleanup:

```bash
./redcode bugbounty plan create \
  --hypothesis HYP-... \
  --identity user-a \
  --control "Request an object owned by user-a" \
  --single-change "Use the pre-authorized cross-identity object reference" \
  --expected-result "Server rejects the request" \
  --minimum-proof "A redacted authorization decision" \
  --stop-condition "Stop after the first unexpected authorization result" \
  --cleanup "No state change; stop immediately if one occurs" \
  --created-by analyst
```

Review the returned SHA-256 hash. Only an analyst should run `approve` with the
exact hash. `begin-test` records the bounded testing window; it does not add
permission to perform another kind of request. Save redacted evidence under
`output/`, record the result, and confirm it only after reviewing minimal,
reproducible impact.

```bash
./redcode bugbounty approve PLAN_ID --approved-by analyst --confirm PLAN_SHA256
./redcode bugbounty begin-test PLAN_ID --operator analyst
./redcode bugbounty record PLAN_ID --outcome candidate --request-count 1 \
  --evidence output/example-program/scans/mappa/evidence.md \
  --summary "Control and one approved variation differ" --operator analyst
```

`confirm` creates a RedCode finding; `report` creates an ignored draft only.
Submission to HackerOne, Bugcrowd, or another platform remains manual.

## Guarantees and Limits

- Policy snapshots, scope rules, imports, hypotheses, plans, approvals, test
  outcomes, evidence hashes, and report drafts are persisted in SQLite/output.
- A direct command through this control plane fails closed for missing policy,
  out-of-scope targets, prohibited actions, expired approvals, excess request
  counts, altered policy snapshots, altered evidence, or evidence saved outside
  `output/`.
- The controller deliberately does not proxy or execute Burp requests. The
  `bugbounty` agent is also denied HexStrike, Fetch, Playwright, and Burp MCP
  permissions, so it cannot make target requests itself; its workflow prompt
  also prohibits delegating active work. This does not restrict actions in
  Burp's human UI or other RedCode agents; an MCP server invoked outside this
  controller is not physically intercepted. Keep active Burp actions
  analyst-reviewed and use the approval record as their required operational
  gate.
- Do not store live credentials, cookies, bearer tokens, CSRF tokens, or
  personal data in SQLite, evidence, prompts, or report drafts.
