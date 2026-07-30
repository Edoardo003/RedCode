# Design Notes

This document records the decisions that shape RedCode. It is intentionally narrower than a product roadmap: each section describes behavior present in the repository and the trade-off behind it.

## OpenCode Extension, Not a Fork

Early versions experimented with changing the OpenCode binary to display RedCode branding. That made upgrades fragile and mixed product identity with upstream implementation details. RedCode now uses only project-level configuration, prompts, skills, and an adaptive theme. OpenCode can be upgraded independently, subject to configuration compatibility.

## One Orchestrator, Focused Specialists

`redcode` is the only primary agent. Specialists are subagents with role-specific prompts and MCP permissions. Detailed wrapper parameters live in skills that are loaded when needed instead of being repeated in every prompt.

This keeps routing and authorization decisions in one place while reducing static context. It does not make agent output deterministic; handoffs and saved evidence still require analyst review.

## HexStrike as an External Backend

The repository does not vendor HexStrike. Setup clones it as a local dependency, and OpenCode starts a local MCP bridge that talks to the configured HexStrike HTTP endpoint. The backend can run on the same host or a trusted LAN server.

This arrangement keeps heavy security tooling away from the OpenCode process, but introduces version and availability risk. `./redcode doctor` reports the observed backend version and available capabilities; it does not guarantee compatibility with every HexStrike release.

## Standalone and Arsenal Runtime Profiles

RedCode keeps one codebase and selects its operational provider at launch. Standalone
mode exposes the existing direct HexStrike workflow. Arsenal mode first negotiates the
versioned Agent API, fixes the session to one workspace, then injects a higher-precedence
OpenCode configuration that disables direct network tooling and enables a small
workspace-bound MCP bridge.

The bridge deliberately wraps Arsenal instead of teaching every agent its REST details.
It reduces the visible tool surface, prevents arbitrary workspace IDs on job reads, and
keeps Arsenal as the source of truth. Read context, inert block proposals, and run
requests use separate protocols; draft acceptance and execution confirmation remain
Arsenal-only actions.

## Scope Preflight Instead of a False Sandbox

An engagement manifest records target rules and permitted actions. The launcher validates it, agents read the activated copy, and `./redcode scope check` provides a deterministic preflight decision.

HexStrike requests are not currently routed through an enforcing proxy, so a prompt or tool bug could still issue an invalid request. The repository states this limitation directly. A policy gateway is a future architectural option, not a capability claimed today.

## JSON Handoff and SQLite Index

Phase JSON is the complete evidence handoff. SQLite is a normalized index for cross-session queries, status, tool runs, approvals, and relationships. The two formats are deliberately not treated as identical or transactionally coupled.

This favors inspectable files and simple recovery over a larger application service. The cost is that persistence remains agent-driven and must be checked by the analyst.

## Assessment and CTF Separation

Assessment findings use target-based directories and SQLite. CTF artifacts, solvers, checkpoints, and candidate flags remain under `output/ctf/` and are not inserted into the assessment database.

The separation prevents challenge data from being mistaken for client evidence and allows local solver code in CTF workflows without normalizing that behavior into assessment tooling.

## Context Control

MCP servers are denied globally and enabled by role. OpenCode compaction prunes stale tool output, and the launcher exposes project or global usage statistics. No fixed token budget is imposed, and agent iteration limits remain role-specific.

The goal is observable context use, not an unsupported promise of a particular token saving.
