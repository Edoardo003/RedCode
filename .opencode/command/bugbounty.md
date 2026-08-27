---
description: "Start or resume a persistent HackerOne MAPPA hunt"
agent: bugbounty
---

Start or resume the authorized bug-bounty hunt for:

$ARGUMENTS

1. Read the active manifest and require the `hunt` action. Explain that program-policy scope must also be reviewed and saved before work begins.
2. Use `./redcode bugbounty status` to resume structured state. If the program is not onboarded, guide the analyst through `./redcode bugbounty onboard`; require a local policy snapshot, explicit policy scopes/exclusions, and a reviewer name. Do not infer policy from marketing text or a hostname.
3. Treat Burp as the traffic source. First run `./redcode bugbounty burp probe` to verify the configured MCP endpoint. Export only selected, in-scope messages into the documented JSON/JSONL interchange format, then use `./redcode bugbounty ingest`. Do not persist raw Authorization, Cookie, CSRF, bearer-token, or personal-data values.
4. Run `map`, inspect `identifier list` and `identifier relationship list`, then use the dedicated confirmation commands for any role or relationship the analyst accepts. Run `queue --generate`, then return the map deltas, coverage gaps, and at most three ranked hypotheses with their MAPPA score components. `queue --generate` retains the generic ownership/tenant seeds and also derives proposals only from analyst-confirmed workflow transitions, invariants, authorization changes, terminal states, trust boundaries, and identifier relationships. Show each semantic proposal's invariant, assumption, control, single-variable change, and expected result.
5. For a selected hypothesis, create a minimal `plan create` record. Present its control, one permitted change, expected result, proof, stop condition, cleanup, request cap, and immutable hash. Wait for explicit analyst approval before `approve` and `begin-test`. This agent must not delegate active work to `scanner`/`exploiter` or use Repeater itself; give the approved plan to the analyst for manual, bounded execution instead.
6. After an approved analyst-reviewed test, require a redacted evidence file under `output/`, run `record`, and keep the result as candidate unless minimum reproducible impact is established. `confirm` needs an analyst review. `report` creates a draft only; never submit it.
7. Persist every state transition and return the next highest-value approved or approval-ready action.

Do not restart mapping from scratch when reliable state exists. Do not treat model output, scanner confidence, HTTP status, a successful command, or the existence of a plan as proof.
