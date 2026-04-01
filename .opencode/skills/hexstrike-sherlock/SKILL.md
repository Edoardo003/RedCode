---
name: "hexstrike-sherlock"
description: "Correct parameters and usage patterns for HexStrike sherlock MCP tool — username enumeration across social platforms."
---

# HexStrike sherlock — Tool Skill

Username enumeration across 300+ social media platforms. Given a username, finds all accounts associated with it across the web. Critical for OSINT — maps a person's digital footprint for social engineering and credential reuse analysis.

## Accepted Parameters

| Parameter  | Type   | Required | Description                                           |
| ---------- | ------ | -------- | ----------------------------------------------------- |
| `username` | string | **YES**  | Username to search for (e.g. `johndoe`, `admin_user`) |
| `flags`    | string | no       | Sherlock flags (e.g. `--timeout 10`)                  |

## Common Usage

```
# Search for a username across all platforms
sherlock(username="johndoe")

# With timeout (prevents hanging on slow sites)
sherlock(username="johndoe", flags="--timeout 10")

# Check multiple usernames (run separately for each)
sherlock(username="john.doe")
sherlock(username="jdoe")
sherlock(username="johndoe123")

# With specific site list
sherlock(username="johndoe", flags="--site github twitter linkedin instagram")
```

## Username Generation Strategy

From OSINT data, generate username candidates:

| Source Data            | Generated Usernames                               |
| ---------------------- | ------------------------------------------------- |
| `john.doe@example.com` | `john.doe`, `johndoe`, `jdoe`, `john_doe`, `doej` |
| `Jane Smith (CTO)`     | `janesmith`, `jsmith`, `jane.smith`, `jane_smith` |
| GitHub profile `devjd` | `devjd` (check all platforms)                     |

Run sherlock on EACH generated username. People reuse usernames across platforms.

## Proxy Configuration

Sherlock respects `http_proxy`/`https_proxy` environment variables. No explicit flag needed.

## Retry Strategy

1. **Timeout errors**: Add `--timeout 15` to increase per-site timeout
2. **Too many false positives**: Sherlock sometimes flags generic usernames. Verify top hits manually.
3. **Rate limited**: Wait 30 seconds and retry. Some platforms block rapid enumeration.
4. **Tool crashes**: Try with `--timeout 5` to fail fast on slow sites

## Output Interpretation

- **Account found on GitHub** — HIGH value. Check repos for leaked secrets, code patterns.
- **Account found on LinkedIn** — confirms identity, reveals role and connections.
- **Account found on Twitter/X** — check for security-relevant posts, complaints about work systems.
- **Account found on forum/community sites** — check for posts revealing internal info.
- **Many hits for common username** — likely false positives. Cross-reference with known target info.

## Evidence Capture

Save results to `output/{target}/osint/raw/sherlock_{username}.txt`. Link discovered profiles to the person's OSINT profile in findings.json.
