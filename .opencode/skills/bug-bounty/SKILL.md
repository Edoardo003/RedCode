---
name: bug-bounty
description: "Scope and submission decisions for an authorized bug-bounty program."
---

# Bug-Bounty Workflow

Use this skill when the engagement is governed by a public or private program policy.

1. Record the program URL, eligible assets, exclusions, prohibited tests, rate limits, safe-harbor terms, and disclosure channel in the engagement notes.
2. Convert only explicit assets into manifest scope. Do not infer that related domains, vendors, or employee accounts are eligible.
3. Prefer low-impact validation and stop when program rules are narrower than the technical capability available.
4. Check likely duplicates and known exclusions before spending time on deeper validation.
5. Preserve request/response evidence, timestamps, affected account role, and a minimal reproduction path.
6. Create one platform submission per root cause unless the program requests grouping.
7. Use the tracked HackerOne or Bugcrowd template and leave final submission to the analyst.

The program policy overrides generic methodology and aggressive mode.
