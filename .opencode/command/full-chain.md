---
description: "Coordinate an authorized assessment from reconnaissance to reporting"
---

Coordinate an assessment for:

$ARGUMENTS

## Preconditions

1. Read `output/.redcode/current-engagement.json` and reject targets or actions outside it.
2. Read existing SQLite and phase state before starting new work.
3. Identify normal or `--aggressive` mode from the arguments.

## Normal Mode

Coordinate only the phases relevant to the engagement:

1. Delegate scoped discovery to `@recon`; request approval before active enumeration.
2. Present the attack surface and obtain analyst review.
3. Delegate relevant public-source enrichment to `@osint`.
4. Obtain scan approval, then delegate prioritized vulnerability discovery to `@scanner`.
5. Present candidate findings. Delegate only analyst-selected, explicitly authorized validation to `@exploiter`.
6. Review evidence and delegate the requested report to `@reporter`.

Ask before consequential phase transitions. Record why a phase is skipped.

## Aggressive Mode

Aggressive mode uses one approval for a concrete plan; it does not expand scope.

Before execution, show:

- exact targets and exclusions;
- planned phases and tools;
- permitted active actions;
- expected load and stop conditions;
- findings eligible for active validation, if already known.

After explicit approval, advance through that plan without routine phase prompts. Stop for scope ambiguity, service instability, destructive impact, sensitive evidence requiring analyst handling, or a material plan change. Do not automatically exploit every scanner result or generate social-engineering artifacts unless those actions were included in the approved plan.

Aggressive mode never authorizes denial of service, persistence, uncontrolled propagation, unrelated assets, credential reuse outside scope, social-engineering delivery, or CTF flag submission.

## State and Output

Use the handoff contract in `AGENTS.md` and phase paths under `output/{target}/`. Preserve raw evidence by path, persist schema-compatible records to SQLite, and summarize coverage gaps and tool failures.

If prior state is incomplete, resume from reliable saved evidence. Do not claim transactional checkpoint behavior that the files do not demonstrate.
