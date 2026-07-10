---
name: ctf-crypto
description: "Crypto CTF workflow for analyzing supplied ciphertexts, keys, protocols, and encodings."
---

# CTF Crypto

1. Identify encodings before assuming encryption: hex, base64, XOR, compressed data, and common serialization formats.
2. Record known plaintext, ciphertext length, modulus or curve parameters, and attacker-controlled inputs.
3. Write small deterministic solvers under `solver/` with comments on assumptions and complexity.
4. Validate every intermediate result against the challenge format before escalating the approach.
5. Keep private keys and flags only in ignored challenge output, never in repository files.
