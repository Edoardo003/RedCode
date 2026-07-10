---
name: ctf-forensics
description: "Forensics CTF workflow for disk images, memory captures, media, archives, and packet captures."
---

# CTF Forensics

1. Hash originals and copy them to `artifacts/original/` before extraction.
2. Identify format, archive layers, timestamps, metadata, and embedded content.
3. Use binwalk, exiftool, strings, foremost, Volatility, Wireshark, or file-system tools according to artifact type.
4. Store extracted data under `artifacts/work/` and document every transformation.
5. Verify the final flag from artifact evidence, not from filename guesses or tool speculation.
