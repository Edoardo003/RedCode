---
name: "hexstrike-dotdotpwn"
description: "Correct parameters, traversal modes, and exploitation patterns for HexStrike dotdotpwn_scan MCP tool."
---

# HexStrike dotdotpwn_scan - Tool Skill

Directory traversal and Local File Inclusion (LFI) exploitation tool. Tests for path traversal vulnerabilities by fuzzing file path parameters with traversal sequences (../, ..\, encoding variants). Can read arbitrary files from the server when successful.

## Accepted Parameters

| Parameter | Type   | Required | Description                                                              |
| --------- | ------ | -------- | ------------------------------------------------------------------------ |
| `target`  | string | **YES**  | URL with file parameter (e.g. `https://example.com/view?file=page.html`) |
| `flags`   | string | no       | DotDotPwn flags (e.g. `-m http`, `-d 8`, `-f /etc/passwd`)               |

## Common Usage

```
# HTTP module - test web parameter for traversal
dotdotpwn_scan(target="https://example.com/view?file=page.html", flags="-m http")

# Deep traversal (8 levels)
dotdotpwn_scan(target="https://example.com/view?file=page.html", flags="-m http -d 8")

# Target specific file
dotdotpwn_scan(target="https://example.com/view?file=page.html", flags="-m http -f /etc/passwd")

# FTP traversal
dotdotpwn_scan(target="ftp://10.10.99.120", flags="-m ftp -d 6")

# TFTP traversal
dotdotpwn_scan(target="10.10.99.120", flags="-m tftp")

# With custom keyword to find in response
dotdotpwn_scan(target="https://example.com/view?file=page.html", flags="-m http -k root:")

# Quiet mode
dotdotpwn_scan(target="https://example.com/view?file=page.html", flags="-m http -q")
```

## Modules

| Module  | Flag         | Targets                    |
| ------- | ------------ | -------------------------- |
| HTTP    | `-m http`    | Web application parameters |
| FTP     | `-m ftp`     | FTP servers                |
| TFTP    | `-m tftp`    | TFTP servers               |
| PAYLOAD | `-m payload` | Custom payload generation  |
| STDOUT  | `-m stdout`  | Output payloads to stdout  |

## Target Files for Proof of Impact

| File                                    | Platform | Why It Matters                             |
| --------------------------------------- | -------- | ------------------------------------------ |
| `/etc/passwd`                           | Linux    | Proves file read, shows users              |
| `/etc/shadow`                           | Linux    | Password hashes (requires root)            |
| `/proc/self/environ`                    | Linux    | Environment variables, may contain secrets |
| `/var/www/html/.env`                    | Linux    | Application secrets, DB credentials        |
| `C:\Windows\win.ini`                    | Windows  | Proves Windows file read                   |
| `C:\Windows\System32\drivers\etc\hosts` | Windows  | Host file, internal network info           |
| `/etc/apache2/apache2.conf`             | Linux    | Web server config                          |
| `/etc/nginx/nginx.conf`                 | Linux    | Web server config                          |

## Parameter Prioritization

Test these parameter types first (highest LFI probability):

1. **File path parameters** - `?file=`, `?page=`, `?path=`, `?template=`
2. **Include parameters** - `?include=`, `?inc=`, `?load=`, `?view=`
3. **Language/locale** - `?lang=en`, `?locale=en_US`
4. **Document parameters** - `?doc=`, `?document=`, `?pdf=`
5. **Image/resource** - `?img=`, `?src=`, `?resource=`

## Proxy Configuration

DotDotPwn does not have native HTTP proxy support. For proxied testing, rely on the `http_proxy` environment variable or use commix for file read verification.

## Retry Strategy

1. **No traversal found**: Try deeper levels (`-d 10`). Try encoding variants (double-encoding, null bytes).
2. **WAF blocking**: Traversal payloads are heavily filtered. Try encoded variants: `%2e%2e%2f`, `..%252f`, `....//`
3. **Timeout**: Reduce depth (`-d 4`). Target a specific file with `-f /etc/passwd`.
4. **False positives**: Verify by checking if the response contains actual file content (not error messages).
5. **PHP apps**: Try `php://filter/convert.base64-encode/resource=` wrapper (via manual testing or commix).

## Output Interpretation

- **"Vulnerable!" with file content** - CONFIRMED LFI. Critical/High severity depending on file accessed.
- **Traversal sequence found but no sensitive file** - still a finding. Try different target files.
- **"Not vulnerable"** - parameter is safe or properly filtered. Move to next parameter.
- **Empty responses with specific traversal strings** - may be filtered. Try encoding variants.

## LFI to RCE Escalation

When LFI is confirmed, try to escalate to RCE:

1. **Log poisoning** - include access logs with PHP payload in User-Agent
2. **PHP wrappers** - `php://input`, `php://filter`, `data://`, `expect://`
3. **Session inclusion** - include PHP session files with injected data
4. **Proc environ** - if readable, inject via User-Agent header
5. **File upload + LFI** - upload a file, include it via LFI

## Evidence Capture

Save raw output to `output/{target}/scans/raw/dotdotpwn_*.txt`. Derive severity from the confirmed files, access boundary, and impact. Preserve only the minimum necessary file evidence and request approval before further validation.
