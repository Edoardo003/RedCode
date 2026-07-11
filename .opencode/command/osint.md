---
description: "Gather assessment-relevant public intelligence"
agent: osint
---

Gather public intelligence for:

$ARGUMENTS

1. Validate the target and collection purpose against the active engagement.
2. Read existing reconnaissance and avoid expanding to unrelated people or organizations.
3. Use only relevant public or analyst-supplied sources, preserving URL and retrieval time.
4. Minimize personal data and treat credential indicators as sensitive, unverified evidence.
5. Correlate identities and assets before assigning confidence.
6. Save the structured handoff to `output/{target}/osint/findings.json` and compatible records to SQLite.

Return confirmed intelligence, useful leads, ambiguity, unavailable sources, and evidence paths.
