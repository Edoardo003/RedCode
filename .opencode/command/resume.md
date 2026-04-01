---
description: "Resume an interrupted assessment phase from the last checkpoint. Reads progress.json and scans table to skip completed work."
---

Resume an interrupted security assessment for:

$ARGUMENTS

## Instructions

### Step 1 — Detect Interrupted Phase

Check for `progress.json` files across all phase directories:

```
output/{target}/recon/progress.json
output/{target}/osint/progress.json
output/{target}/scans/progress.json
output/{target}/exploits/progress.json
```

Also query SQLite for the current state:

```sql
SELECT * FROM targets WHERE status = 'active';
SELECT phase, tool, subdomain, status FROM scans WHERE target_id = ? ORDER BY started_at DESC;
SELECT COUNT(*) as total, status FROM scans WHERE target_id = ? GROUP BY status;
```

### Step 2 — Show Resume Summary

Present the user a summary of what was completed vs what's pending:

```
RESUME for [target]:

Phase: [interrupted phase name]
Completed: N/M tool runs (X%)
Last activity: [timestamp from progress.json]

Completed tools:
  ✓ nuclei on api.example.com
  ✓ nikto on api.example.com
  ✓ nuclei on www.example.com

Pending:
  ○ nikto on www.example.com
  ○ gobuster on api.example.com
  ○ gobuster on www.example.com
  ○ sqlmap on api.example.com (from scan findings)

Resume from [phase]? (y/n)
```

### Step 3 — Re-Delegate with Resume Context

After confirmation, delegate to the correct agent with explicit resume instructions:

**For @scanner**: "@scanner RESUME MODE — continue scanning [target]. Read checkpoint from output/{target}/scans/progress.json. Skip all completed tool+subdomain combinations. Start with the first pending item. MODE: [AGGRESSIVE/NORMAL as per original run]."

**For @exploiter**: "@exploiter RESUME MODE — continue exploitation for [target]. Read checkpoint from output/{target}/exploits/progress.json. Skip already-exploited findings. Start with the first pending finding. MODE: [AGGRESSIVE/NORMAL]."

**For @osint**: "@osint RESUME MODE — continue OSINT gathering for [target]. Read checkpoint from output/{target}/osint/progress.json. Skip completed techniques. Start with the first pending technique. MODE: [AGGRESSIVE/NORMAL]."

### Step 4 — If No progress.json Found

If no progress.json exists in any phase directory:

1. Check SQLite `scans` table for completed entries
2. If completed scans exist → reconstruct resume state from SQLite and present summary
3. If no data at all → inform user: "No interrupted assessment found for [target]. Use `/full-chain` or `/scan` to start a new assessment."

## Rules

- ALWAYS show the resume summary before re-delegating
- ALWAYS include "RESUME MODE" in the handoff to tell the agent to check its RESUME PROTOCOL
- ALWAYS preserve the original mode (aggressive/normal) from the interrupted run
- If multiple phases have progress.json files, resume the EARLIEST incomplete phase
- If the user specifies a phase override in arguments, use that instead
