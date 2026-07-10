---
name: ctf-web
description: "Web CTF workflow for explicitly scoped local or competition challenges."
---

# CTF Web

Use only against the explicit CTF URL. Begin with the challenge description, browser inspection, routes, client JavaScript, and known test credentials if supplied.

1. Record the base URL and challenge objective in `notes.md`.
2. Use Playwright and Fetch to reproduce normal flows before testing the intended weakness.
3. Use HexStrike tools only when they fit the stated challenge and respect the CTF service limits.
4. Save relevant requests, responses, screenshots, and payloads under `evidence/`.
5. Verify the flag through the challenge response or a local checker, then document minimal reproduction steps.

For Juice Shop, treat it as a local lab service and keep all testing bound to its configured host and port.
