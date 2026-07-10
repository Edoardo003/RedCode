---
name: ctf-pwn
description: "Binary exploitation CTF workflow for supplied local binaries and challenge endpoints."
---

# CTF Pwn

1. Preserve the original binary and run `file`, `checksec`, `strings`, and dependency inspection.
2. Use GDB and local execution to establish the crash or primitive before writing a solver.
3. Keep exploit code in `solver/` and parameterize host and port instead of embedding secrets.
4. Test first against the local binary; use a supplied remote challenge endpoint only after local behavior is understood.
5. Record mitigations, offsets, payload structure, and output required to verify the result.
