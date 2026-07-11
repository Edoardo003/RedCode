---
name: "hexstrike-wpscan"
description: "Correct parameters, enumeration modes, brute-force configuration, and usage patterns for HexStrike wpscan_analyze MCP tool."
---

# HexStrike wpscan_analyze - Tool Skill

WordPress vulnerability scanner and exploitation tool. Enumerates users, plugins, themes, and WordPress-specific vulnerabilities. Can brute-force discovered usernames. The go-to tool when WordPress is detected on a target.

## Accepted Parameters

| Parameter | Type   | Required | Description                                      |
| --------- | ------ | -------- | ------------------------------------------------ |
| `target`  | string | **YES**  | WordPress URL (e.g. `https://example.com`)       |
| `flags`   | string | no       | WPScan flags (e.g. `--enumerate`, `--passwords`) |

## Common Usage

```
# Full enumeration (users, plugins, themes)
wpscan_analyze(target="https://example.com", flags="--enumerate u,p,t")

# User enumeration only
wpscan_analyze(target="https://example.com", flags="--enumerate u")

# Plugin enumeration (aggressive)
wpscan_analyze(target="https://example.com", flags="--enumerate ap --plugins-detection aggressive")

# Theme enumeration
wpscan_analyze(target="https://example.com", flags="--enumerate t")

# Config backup detection
wpscan_analyze(target="https://example.com", flags="--enumerate cb")

# Brute-force with wordlist
wpscan_analyze(target="https://example.com", flags="--enumerate u --passwords ./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt")

# Full aggressive scan
wpscan_analyze(target="https://example.com", flags="--enumerate u,ap,at,cb --plugins-detection aggressive --passwords ./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt")

# With proxy
wpscan_analyze(target="https://example.com", flags="--proxy http://user:pass@host:port --enumerate u,p,t")

# With API token (for vulnerability data)
wpscan_analyze(target="https://example.com", flags="--enumerate u,p,t --api-token YOUR_TOKEN")

# Stealthy mode
wpscan_analyze(target="https://example.com", flags="--enumerate u,p,t --stealthy")
```

## Enumeration Modes

| Flag  | What It Enumerates                           |
| ----- | -------------------------------------------- |
| `u`   | Users (via author archives, login, REST API) |
| `p`   | Popular plugins                              |
| `ap`  | All plugins (aggressive)                     |
| `t`   | Popular themes                               |
| `at`  | All themes (aggressive)                      |
| `cb`  | Config backups (wp-config.php~, .bak, etc.)  |
| `dbe` | Database exports                             |

## Plugin Detection Modes

| Mode       | Flag                             | Description              |
| ---------- | -------------------------------- | ------------------------ |
| Passive    | `--plugins-detection passive`    | Fast, checks known paths |
| Mixed      | `--plugins-detection mixed`      | Balanced (default)       |
| Aggressive | `--plugins-detection aggressive` | Slow but thorough        |

## Brute-Force Configuration

```
# Brute-force with common passwords
wpscan_analyze(target="...", flags="--passwords ./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt")

# Brute-force specific user
wpscan_analyze(target="...", flags="--passwords ./wordlists/SecLists/Passwords/Common-Credentials/best1050.txt --usernames admin")

# Limit threads
wpscan_analyze(target="...", flags="--passwords ./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt --max-threads 5")
```

### Wordlists for WordPress

| Wordlist      | Path                                                                       | Use Case             |
| ------------- | -------------------------------------------------------------------------- | -------------------- |
| Top 10K       | `./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt`    | Standard brute-force |
| Best 1050     | `./wordlists/SecLists/Passwords/Common-Credentials/best1050.txt`           | Quick first pass     |
| Default creds | `./wordlists/SecLists/Passwords/Default-Credentials/default-passwords.txt` | Default installs     |

## Proxy Configuration

```
wpscan_analyze(target="...", flags="--proxy http://user:pass@host:port")
```

**No trailing slash on proxy URL.**

## Retry Strategy

1. **Rate limited / blocked**: Add `--stealthy` flag. Reduce threads with `--max-threads 2`.
2. **No users found**: Try REST API enumeration manually (`/wp-json/wp/v2/users`). WP may hide author archives.
3. **Plugin detection misses**: Use `--plugins-detection aggressive` for thorough scanning.
4. **API token errors**: Skip the `--api-token` flag. WPScan works without it, just fewer vuln details.
5. **Timeout**: Split enumeration into separate calls (users first, then plugins, then themes).

## Output Interpretation

- **Users enumerated** - each user is a brute-force target. Admin users are highest priority.
- **Vulnerable plugins** - cross-reference with searchsploit for public exploits.
- **Outdated WordPress core** - check specific CVEs for the detected version.
- **Config backups found** - sensitive evidence; preserve the minimum necessary content and derive severity from confirmed exposure.
- **XML-RPC enabled** - can be used for brute-force amplification and SSRF.
- **Debug log found** - may contain errors with file paths, credentials, internal info.
- **Brute-force success** - VERIFY by actually logging in. WPScan uses response analysis, not 100% reliable.

## Post-Exploitation (Admin Access Gained)

1. **Theme editor** - edit theme PHP files to inject a web shell
2. **Plugin upload** - upload a malicious plugin for RCE
3. **Database access** - wp-config.php contains DB credentials
4. **User data** - dump all user accounts and password hashes
5. **Pivot** - WordPress server may have access to internal network

## Evidence Capture

Save raw WPScan output to `output/{target}/scans/raw/wpscan_*.txt`. Persist users, plugins, and vulnerabilities as separate findings. Cracked credentials go immediately to SQLite `credentials` table.
