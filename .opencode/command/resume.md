---
description: "Resume an assessment from reliable saved state"
---

Resume work for:

$ARGUMENTS

1. Validate the active engagement and requested target.
2. Inspect phase `findings.json` files, any `progress.json` files, and SQLite tool-run state.
3. Distinguish completed evidence from prompt-managed checkpoints that may be stale.
4. Present the last reliable state, incomplete actions, changed scope, and required approval.
5. Delegate only the next incomplete authorized task to the appropriate agent.
6. Preserve previous evidence and record new tool runs separately.

Never claim exactly-once execution or automatic checkpoint deletion; resume behavior is agent-managed.
