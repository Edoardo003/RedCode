---
name: "hexstrike-hydra"
description: "Correct parameters, service syntax, false positive detection, and wordlist paths for HexStrike hydra_attack MCP tool."
---

# HexStrike hydra_attack — Tool Skill

Network login brute-forcer. Tests credentials against login pages, SSH, FTP, databases, and other services. Uses wordlists to systematically test username+password combinations.

---

## Accepted Parameters

| Parameter         | Type   | Required | Description                                                                                                |
| ----------------- | ------ | -------- | ---------------------------------------------------------------------------------------------------------- |
| `target`          | string | **YES**  | IP or hostname (e.g. `example.com` or `10.10.99.120`)                                                      |
| `service`         | string | **YES**  | Protocol: `http-post-form`, `https-post-form`, `ssh`, `ftp`, `mysql`, `rdp`, `smb`, `smtp`, `pop3`, `imap` |
| `username`        | string | varies   | Single username to test                                                                                    |
| `userlist`        | string | varies   | Path to username wordlist                                                                                  |
| `passwordlist`    | string | **YES**  | Path to password wordlist                                                                                  |
| `additional_args` | string | no       | Extra flags                                                                                                |

---

## HTTP Form Brute-Force (Most Common)

The `http-post-form` syntax is **the #1 source of errors**. Get this right:

```
hydra_attack(
  target="example.com",
  service="http-post-form",
  username="admin",
  passwordlist="./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt",
  additional_args="/login:username=^USER^&password=^PASS^:F=incorrect"
)
```

### Syntax Breakdown

The `additional_args` for `http-post-form` uses colon-separated fields:

```
/path:POST_BODY:FAILURE_STRING
```

- **`/path`** — login endpoint path (e.g. `/login`, `/wp-login.php`, `/admin/login`)
- **`POST_BODY`** — form data with `^USER^` and `^PASS^` placeholders
- **`FAILURE_STRING`** — `F=text` that appears on FAILED login (hydra looks for this to identify failures)

### Common Services

```
# WordPress
additional_args="/wp-login.php:log=^USER^&pwd=^PASS^&wp-submit=Log+In:F=incorrect"

# Generic login form
additional_args="/login:username=^USER^&password=^PASS^:F=invalid"

# With cookies/headers
additional_args="/login:username=^USER^&password=^PASS^:F=failed:H=Cookie: session=abc123"
```

### SSH / FTP / Database

```
# SSH brute-force
hydra_attack(target="10.10.99.120", service="ssh", username="root", passwordlist="./wordlists/SecLists/Passwords/Common-Credentials/best1050.txt")

# FTP
hydra_attack(target="10.10.99.120", service="ftp", userlist="./wordlists/SecLists/Usernames/top-usernames-shortlist.txt", passwordlist="./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt")

# MySQL
hydra_attack(target="10.10.99.120", service="mysql", username="root", passwordlist="./wordlists/SecLists/Passwords/Common-Credentials/best1050.txt")
```

---

## FALSE POSITIVE DETECTION (CRITICAL)

**HTTP 200 does NOT mean login success.** This is the most common hydra false positive.

### How to Validate

1. **Check the hydra output carefully**: `[80][http-post-form] host: X login: Y password: Z` — this is a HIT, but may be false positive
2. **Verify post-auth content**: After hydra reports a password, use Fetch/Playwright to login and check for dashboard/inbox/admin content
3. **First-attempt success = suspicious**: If hydra finds a password on the very first try on a production server, it's almost certainly a false positive
4. **Compare responses**: If the "success" response is identical to a known failure response, it's a false positive
5. **Session cookie trap**: Many apps set session cookies BEFORE auth — cookie presence ≠ login success

### Getting the Failure String Right

The `F=` failure string is crucial. Get it wrong → every attempt looks like success → massive false positives.

```
# GOOD — specific failure text
F=Invalid username or password
F=Login failed
F=incorrect credentials

# BAD — too generic, might match success pages too
F=error
F=login
```

**How to find the right failure string**: Make one manual login attempt with wrong credentials (via Fetch), note the EXACT error message text, use that as your `F=` value.

---

## Wordlists

| Wordlist          | Path                                                                    | Use Case                 |
| ----------------- | ----------------------------------------------------------------------- | ------------------------ |
| Top 10k passwords | `./wordlists/SecLists/Passwords/Common-Credentials/10k-most-common.txt` | Default for web logins   |
| Top 1050          | `./wordlists/SecLists/Passwords/Common-Credentials/best1050.txt`        | Quick scan, SSH/FTP      |
| Top usernames     | `./wordlists/SecLists/Usernames/top-usernames-shortlist.txt`            | When username is unknown |
| Default creds     | `./wordlists/SecLists/Passwords/Default-Credentials/`                   | IoT, admin panels        |

---

## Proxy Configuration

Hydra has **no native proxy flag**. Two options:

1. **Environment variable** (auto-set by redcode launcher): `http_proxy` and `https_proxy` env vars
2. **Proxychains**: `proxychains hydra ...` — for full TCP proxying

For HTTP form attacks, the proxy env vars usually work. For SSH/FTP, use proxychains.

---

## Retry Strategy

1. **"Connection refused"** → Service not running on target. Check port first.
2. **All attempts show as "valid"** → Wrong failure string. Fix `F=` value.
3. **0 valid passwords** → Not a failure. Brute-force didn't work. Move on.
4. **Rate limited / blocked** → Reduce threads: `additional_args="-t 4"`. Use proxy rotation.
5. **Timeout** → Increase wait: `additional_args="-w 10"`.

---

## Output Interpretation

- **`[80][http-post-form] host: X login: admin password: secret123`** → Potential hit. MUST verify with post-auth content.
- **`0 valid passwords found`** → Clean result. Brute-force failed. Report as attempted, not as vulnerability.
- **`[ERROR] target is not a valid`** → Wrong target format or service string.
- **Multiple valid passwords found** → Almost certainly false positives. Wrong failure string.
