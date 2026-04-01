---
name: "hexstrike-gobuster"
description: "Correct parameters, wordlist paths, extension lists, and mode selection for HexStrike gobuster_scan and ffuf_scan MCP tools."
---

# HexStrike gobuster_scan & ffuf_scan — Tool Skill

Directory/file brute-force discovery tools. Find hidden endpoints, admin panels, backup files, config files, and unlinked content. gobuster and ffuf are alternatives — use whichever is available; prefer ffuf for parameter fuzzing.

---

## gobuster_scan — Parameters

| Parameter         | Type   | Required | Description                                                           |
| ----------------- | ------ | -------- | --------------------------------------------------------------------- |
| `target`          | string | **YES**  | Base URL (e.g. `https://example.com`)                                 |
| `mode`            | string | no       | `dir` (directory, default), `dns` (subdomain), `vhost` (virtual host) |
| `wordlist`        | string | **YES**  | Path to wordlist file                                                 |
| `additional_args` | string | no       | Extra flags                                                           |

## ffuf_scan — Parameters

| Parameter         | Type   | Required | Description                                               |
| ----------------- | ------ | -------- | --------------------------------------------------------- |
| `target`          | string | **YES**  | URL with `FUZZ` keyword (e.g. `https://example.com/FUZZ`) |
| `wordlist`        | string | **YES**  | Path to wordlist file                                     |
| `additional_args` | string | no       | Extra flags                                               |

---

## Wordlists

| Wordlist   | Path                                                                       | Size       | Use Case                    |
| ---------- | -------------------------------------------------------------------------- | ---------- | --------------------------- |
| Common     | `./wordlists/SecLists/Discovery/Web-Content/common.txt`                    | 4.7K lines | Quick first pass            |
| Medium     | `./wordlists/SecLists/Discovery/Web-Content/directory-list-2.3-medium.txt` | 220K lines | Standard scan               |
| Big        | `./wordlists/SecLists/Discovery/Web-Content/big.txt`                       | 20K lines  | Thorough without being slow |
| Raft dirs  | `./wordlists/SecLists/Discovery/Web-Content/raft-medium-directories.txt`   | 30K lines  | Good coverage               |
| Raft files | `./wordlists/SecLists/Discovery/Web-Content/raft-medium-files.txt`         | 17K lines  | File-focused                |
| DNS subs   | `./wordlists/SecLists/Discovery/DNS/subdomains-top1million-5000.txt`       | 5K lines   | DNS brute-force             |
| Params     | `./wordlists/SecLists/Discovery/Web-Content/burp-parameter-names.txt`      | 6K lines   | Parameter fuzzing           |

---

## Common Usage — gobuster_scan

### Directory discovery (default)

```
gobuster_scan(target="https://example.com", wordlist="./wordlists/SecLists/Discovery/Web-Content/common.txt", additional_args="-x php,html,txt,bak,old,conf,sql,env,log,json,xml")
```

### With proxy

```
gobuster_scan(target="https://example.com", wordlist="./wordlists/SecLists/Discovery/Web-Content/common.txt", additional_args="--proxy http://user:pass@host:port -x php,html,txt")
```

### Filter status codes

```
gobuster_scan(target="https://example.com", wordlist="./wordlists/SecLists/Discovery/Web-Content/big.txt", additional_args="-x php,html -b 404,403,500")
```

### DNS subdomain brute-force

```
gobuster_scan(target="example.com", mode="dns", wordlist="./wordlists/SecLists/Discovery/DNS/subdomains-top1million-5000.txt")
```

### Virtual host discovery

```
gobuster_scan(target="https://example.com", mode="vhost", wordlist="./wordlists/SecLists/Discovery/DNS/subdomains-top1million-5000.txt")
```

---

## Common Usage — ffuf_scan

### Directory fuzzing

```
ffuf_scan(target="https://example.com/FUZZ", wordlist="./wordlists/SecLists/Discovery/Web-Content/common.txt", additional_args="-mc 200,301,302,403 -e .php,.html,.txt,.bak")
```

### Parameter fuzzing

```
ffuf_scan(target="https://example.com/search?FUZZ=test", wordlist="./wordlists/SecLists/Discovery/Web-Content/burp-parameter-names.txt", additional_args="-mc 200 -fs 0")
```

### With proxy

```
ffuf_scan(target="https://example.com/FUZZ", wordlist="./wordlists/SecLists/Discovery/Web-Content/common.txt", additional_args="-x http://user:pass@host:port")
```

### Filter by response size (removes false positives)

```
ffuf_scan(target="https://example.com/FUZZ", wordlist="./wordlists/SecLists/Discovery/Web-Content/big.txt", additional_args="-mc all -fs 1234")
```

**Note**: `-fs 1234` filters out responses of exactly 1234 bytes (the default 404 page size). Find this size by first making a request to a known-nonexistent path.

---

## Extension Lists

Always add extensions when doing directory scans. The extensions depend on the target's technology:

```
# PHP apps (WordPress, Laravel, etc.)
-x php,php5,phps,phtml,bak,old,txt,conf,env,log,sql,xml,json

# ASP.NET apps
-x asp,aspx,ashx,asmx,config,bak,old,txt

# Java apps
-x jsp,jspx,do,action,xml,properties,bak,war

# Python apps (Django, Flask)
-x py,pyc,txt,json,yaml,yml,env,cfg,conf,bak

# General (when unsure)
-x php,html,txt,bak,old,conf,sql,env,log,json,xml
```

---

## Proxy Configuration

```
# gobuster — uses --proxy
gobuster_scan(... additional_args="--proxy http://user:pass@host:port")

# ffuf — uses -x
ffuf_scan(... additional_args="-x http://user:pass@host:port")
```

**No trailing slash on proxy URL.**

---

## Retry Strategy

1. **Too many 403s** → WAF is blocking. Try slower: gobuster `-t 5`, ffuf `-rate 10`. Try with proxy.
2. **Too many false positives** → Adjust filter: gobuster `-b 404,403`, ffuf `-fs [size]` or `-fc 404,403`.
3. **Timeout errors** → Increase timeout: gobuster `--timeout 15s`, ffuf `-timeout 15`.
4. **0 results with common.txt** → Try `big.txt` or `raft-medium-directories.txt`. Add more extensions.
5. **Tool not available** → Use the alternative (gobuster ↔ ffuf). They achieve the same goal.

---

## Output Interpretation

- **200 + meaningful content** → Discovered endpoint. Investigate further.
- **301/302** → Redirect to another path. Follow it.
- **403 on /admin, /backup, /config** → Interesting — exists but blocked. Note for auth bypass.
- **200 on .bak, .old, .env, .sql files** → HIGH value. May contain source code, credentials, database dumps.
- **200 on /robots.txt, /sitemap.xml** → Check for hidden paths listed inside.
- **Massive number of 200s with same size** → False positives. Custom 404 page. Filter by size (`-fs`).
