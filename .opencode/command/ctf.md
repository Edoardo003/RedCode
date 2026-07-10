---
description: "Start or resume an authorized CTF challenge"
agent: ctf
---

Work on this authorized CTF challenge:

$ARGUMENTS

## Instructions

1. Parse event, challenge name, category, supplied artifact path or challenge URL, and expected flag format.
2. Use `output/ctf/{event}/{challenge}/` for every generated file, note, checkpoint, and write-up.
3. If `progress.json` exists, summarize completed attempts and resume from the next unresolved step.
4. Load the matching category skill before starting specialized analysis.
5. Use scripts and local tooling only for challenge artifacts or the explicitly supplied CTF service.
6. Present verified flags as candidates for the user to submit; never submit them automatically.
