---
name: ctf-rev
description: "Reverse engineering CTF workflow for supplied executables and bytecode."
---

# CTF Reverse Engineering

1. Identify file type, architecture, packing, imports, strings, and input format.
2. Use Ghidra or Radare2 for static analysis, then local tracing or a debugger only when needed.
3. Rename recovered functions and variables in notes so the write-up remains understandable.
4. Keep deobfuscators, patches, and extractors in `solver/`.
5. Preserve an evidence trail from validation logic to the recovered flag candidate.
