---
name: "hexstrike-python"
description: "Correct usage rules, allowed vs forbidden use cases, and safety constraints for HexStrike execute_python_script MCP tool."
---

# HexStrike execute_python_script - Tool Skill

Execute Python scripts on the HexStrike server. **RESTRICTED** - this tool is ONLY for running existing, published exploit scripts (Exploit-DB, GitHub PoCs, CVE-specific scripts). It is NOT a general-purpose scripting tool.

## Accepted Parameters

| Parameter | Type   | Required | Description                              |
| --------- | ------ | -------- | ---------------------------------------- |
| `script`  | string | **YES**  | Python script content or path to execute |
| `flags`   | string | no       | Additional execution flags               |

## ALLOWED Uses (Published Exploits ONLY)

```
# Run a public CVE exploit from Exploit-DB
execute_python_script(script="/path/to/exploit-db-12345.py")

# Run an existing, reviewed exploit script
execute_python_script(script="/path/to/verified-poc.py")

# Run a published GitHub exploit
execute_python_script(script="import requests; # [published exploit code from GitHub]")

# Run a verified exploit script
execute_python_script(script="/path/to/cve-2024-xxxx.py")
```

## FORBIDDEN Uses (WILL BE REJECTED BY ORCHESTRATOR)

The following uses will cause the orchestrator (@redcode) to **REJECT your findings** as unreliable:

```
# FORBIDDEN: Custom brute-force script
execute_python_script(script="import requests; for pw in passwords: requests.post(login_url, data={'password': pw})")
# USE INSTEAD: hydra_attack

# FORBIDDEN: Custom SQLi testing script
execute_python_script(script="import requests; r = requests.get(url + \"' OR 1=1--\")")
# USE INSTEAD: sqlmap_scan

# FORBIDDEN: Custom XSS scanner
execute_python_script(script="import requests; for payload in xss_payloads: test(url, payload)")
# USE INSTEAD: dalfox or xsser_scan

# FORBIDDEN: Custom directory fuzzer
execute_python_script(script="import requests; for path in wordlist: check(url + path)")
# USE INSTEAD: gobuster_scan or ffuf_scan

# FORBIDDEN: Custom login tester
execute_python_script(script="import requests; s = requests.Session(); s.post(login_url, data=creds)")
# USE INSTEAD: hydra_attack

# FORBIDDEN: Any script using 'import requests' for scanning/fuzzing/brute-force
# USE INSTEAD: The dedicated HexStrike tool for that task
```

## The Test

Before using `execute_python_script`, ask yourself:

> "Does a dedicated HexStrike tool already do what this script does?"

If YES (brute-force, SQLi, XSS, directory fuzzing, port scanning, etc.) - **USE THE DEDICATED TOOL**.
If NO (published CVE exploit, custom protocol, unique vulnerability) - proceed with the script.

## Why Custom Scripts Are Forbidden

1. **False positives** - HTTP 200 does not mean login success. Custom scripts misparse responses.
2. **Missing CSRF handling** - scripts don't handle anti-CSRF tokens, breaking form submissions.
3. **Missing session management** - scripts don't handle cookies, redirects, multi-step auth.
4. **Orchestrator rejection** - @redcode will reject ANY finding produced by a custom script when a dedicated tool exists.
5. **Report credibility** - professional reports cite tool output, not custom scripts.

## Retry Strategy

1. **Script fails**: Check Python syntax and dependencies. The HexStrike server may not have all libraries.
2. **Module not found**: The server environment may lack the library. Check what's available.
3. **Connection errors**: Verify target is reachable from the HexStrike server.
4. **Permission denied**: Script may need elevated privileges not available in the execution context.

## Evidence Capture

When running published exploits, save the script source and output to `output/{target}/exploits/raw/python_*.txt`. Document which Exploit-DB ID or GitHub repo the script came from.
