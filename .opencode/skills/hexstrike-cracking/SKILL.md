---
name: "hexstrike-cracking"
description: "Correct parameters, hash type selection, wordlist strategies, and usage patterns for HexStrike john_crack and hashcat_crack MCP tools."
---

# HexStrike Password Cracking - john_crack and hashcat_crack - Tool Skill

Password hash cracking tools. john_crack (John the Ripper) is CPU-based and auto-detects hash formats. hashcat_crack is GPU-accelerated for maximum speed. Use john for versatility, hashcat for speed on known hash types.

---

## john_crack - Parameters

| Parameter  | Type   | Required | Description                                                      |
| ---------- | ------ | -------- | ---------------------------------------------------------------- |
| `hashfile` | string | **YES**  | Path to file containing hashes (e.g. `output/target/hashes.txt`) |
| `flags`    | string | no       | John flags (e.g. `--wordlist=`, `--format=`, `--rules`)          |

### Common Usage

```
# Auto-detect format and crack
john_crack(hashfile="output/target/hashes.txt")

# With wordlist
john_crack(hashfile="output/target/hashes.txt", flags="--wordlist=./wordlists/SecLists/Passwords/Leaked-Databases/rockyou.txt")

# Specify format
john_crack(hashfile="output/target/hashes.txt", flags="--format=raw-md5 --wordlist=./wordlists/SecLists/Passwords/Leaked-Databases/rockyou.txt")

# With rules (mangling)
john_crack(hashfile="output/target/hashes.txt", flags="--wordlist=./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt --rules")

# Show cracked passwords
john_crack(hashfile="output/target/hashes.txt", flags="--show")

# Specific format - bcrypt
john_crack(hashfile="output/target/hashes.txt", flags="--format=bcrypt --wordlist=./wordlists/SecLists/Passwords/Common-Credentials/best1050.txt")

# /etc/shadow format
john_crack(hashfile="output/target/shadow.txt", flags="--wordlist=./wordlists/SecLists/Passwords/Leaked-Databases/rockyou.txt")

# WordPress MD5
john_crack(hashfile="output/target/wp_hashes.txt", flags="--format=phpass --wordlist=./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt")
```

---

## hashcat_crack - Parameters

| Parameter  | Type   | Required | Description                                       |
| ---------- | ------ | -------- | ------------------------------------------------- |
| `hashfile` | string | **YES**  | Path to file containing hashes                    |
| `flags`    | string | no       | Hashcat flags (e.g. `-m 0`, `-a 0`, `--wordlist`) |

### Common Usage

```
# MD5 with wordlist
hashcat_crack(hashfile="output/target/hashes.txt", flags="-m 0 -a 0 ./wordlists/SecLists/Passwords/Leaked-Databases/rockyou.txt")

# SHA-256
hashcat_crack(hashfile="output/target/hashes.txt", flags="-m 1400 -a 0 ./wordlists/SecLists/Passwords/Leaked-Databases/rockyou.txt")

# bcrypt
hashcat_crack(hashfile="output/target/hashes.txt", flags="-m 3200 -a 0 ./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt")

# NTLM (Windows)
hashcat_crack(hashfile="output/target/hashes.txt", flags="-m 1000 -a 0 ./wordlists/SecLists/Passwords/Leaked-Databases/rockyou.txt")

# MySQL
hashcat_crack(hashfile="output/target/hashes.txt", flags="-m 300 -a 0 ./wordlists/SecLists/Passwords/Leaked-Databases/rockyou.txt")

# WordPress (phpass)
hashcat_crack(hashfile="output/target/hashes.txt", flags="-m 400 -a 0 ./wordlists/SecLists/Passwords/Leaked-Databases/rockyou.txt")

# With rules
hashcat_crack(hashfile="output/target/hashes.txt", flags="-m 0 -a 0 ./wordlists/SecLists/Passwords/Leaked-Databases/rockyou.txt -r rules/best64.rule")

# Brute-force (short passwords)
hashcat_crack(hashfile="output/target/hashes.txt", flags="-m 0 -a 3 ?a?a?a?a?a?a")

# Show cracked
hashcat_crack(hashfile="output/target/hashes.txt", flags="-m 0 --show")
```

### Common Hash Modes (-m)

| Mode   | Hash Type           |
| ------ | ------------------- |
| `0`    | MD5                 |
| `100`  | SHA-1               |
| `300`  | MySQL < 4.1         |
| `400`  | phpass (WordPress)  |
| `500`  | md5crypt (Linux)    |
| `1000` | NTLM (Windows)      |
| `1400` | SHA-256             |
| `1700` | SHA-512             |
| `1800` | sha512crypt (Linux) |
| `3200` | bcrypt              |
| `5500` | NetNTLMv1           |
| `5600` | NetNTLMv2           |
| `7400` | sha256crypt (Linux) |

---

## When to Use Which

| Scenario                        | Use           | Why                        |
| ------------------------------- | ------------- | -------------------------- |
| Unknown hash format             | john_crack    | Auto-detects format        |
| Known format, large wordlist    | hashcat_crack | GPU acceleration is faster |
| /etc/shadow cracking            | john_crack    | Best shadow file support   |
| NTLM/Windows hashes             | hashcat_crack | Optimized NTLM kernel      |
| bcrypt (slow hashes)            | hashcat_crack | GPU parallelism helps      |
| Quick crack with small wordlist | john_crack    | Lower overhead to start    |

## Wordlists for Cracking

| Wordlist      | Path                                                                       | Size   | Use Case          |
| ------------- | -------------------------------------------------------------------------- | ------ | ----------------- |
| RockYou       | `./wordlists/SecLists/Passwords/Leaked-Databases/rockyou.txt`              | 14M    | Standard cracking |
| Top 10K       | `./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt`    | 10K    | Quick first pass  |
| Best 1050     | `./wordlists/SecLists/Passwords/Common-Credentials/best1050.txt`           | 1K     | Very quick pass   |
| Default creds | `./wordlists/SecLists/Passwords/Default-Credentials/default-passwords.txt` | varies | Default installs  |

**Strategy**: Start with `best1050.txt` (fast), then `10k-most-common.txt`, then `rockyou.txt` (slow but thorough).

## Retry Strategy

1. **No passwords cracked**: Try larger wordlist. Try with rules (`--rules` for john, `-r best64.rule` for hashcat).
2. **Wrong format detected**: Specify format explicitly (`--format=` for john, `-m` for hashcat).
3. **GPU not available (hashcat)**: Fall back to john_crack. Or use hashcat with `--force` for CPU mode.
4. **Out of memory**: Reduce wordlist size or use john instead.
5. **Hash format unknown**: Let john auto-detect first, then use identified format with hashcat.

## Output Interpretation

- **Password cracked** - CRITICAL finding. Persist to SQLite `credentials` table IMMEDIATELY.
- **Partial crack (some hashes)** - report cracked ones, note remaining uncracked.
- **No cracks** - passwords are strong or not in wordlist. Note in findings.
- **Session restored** - john/hashcat can resume interrupted cracking sessions.

## Evidence Capture

Save cracked passwords to `output/{target}/exploits/raw/cracked_*.txt`. IMMEDIATELY persist to SQLite:

```sql
INSERT INTO credentials (target_id, username, password, source, phase)
VALUES (?, 'admin', 'cracked_pass', 'john_crack from /etc/shadow', 'exploit');
```

Try cracked credentials immediately on login pages, SSH, FTP, databases.
