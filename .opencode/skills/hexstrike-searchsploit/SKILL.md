---
name: "hexstrike-searchsploit"
description: "Correct parameters, search strategies, and usage patterns for HexStrike searchsploit MCP tool - Exploit-DB search."
---

# HexStrike searchsploit - Tool Skill

Search Exploit-DB for known exploits and PoCs matching specific software, versions, and CVEs. Essential for mapping detected services to available exploits. This is your first step before running metasploit_run - find the exploit, then execute it.

## Accepted Parameters

| Parameter | Type   | Required | Description                                                            |
| --------- | ------ | -------- | ---------------------------------------------------------------------- |
| `query`   | string | **YES**  | Search terms (e.g. `Apache 2.4.29`, `CVE-2021-44228`, `WordPress 5.8`) |
| `flags`   | string | no       | Searchsploit flags (e.g. `--exact`, `-w`, `--json`)                    |

## Common Usage

```
# Search by software and version
searchsploit(query="Apache 2.4.29")

# Search by CVE
searchsploit(query="CVE-2021-44228")

# Search by CMS
searchsploit(query="WordPress 5.8")

# Exact match (more precise)
searchsploit(query="Apache 2.4.29", flags="--exact")

# Get URLs to Exploit-DB entries
searchsploit(query="Apache 2.4.29", flags="-w")

# JSON output
searchsploit(query="Apache 2.4.29", flags="--json")

# Search for specific service
searchsploit(query="OpenSSH 7.4")

# Search for specific vulnerability type
searchsploit(query="PHP file upload")

# Search for CMS plugins
searchsploit(query="WordPress plugin contact form")

# Search for protocol exploits
searchsploit(query="SMB remote code execution")
```

## Search Strategy

### Order of Searches

1. **Exact version** - `searchsploit(query="Apache 2.4.29")` - most relevant results
2. **Major version** - `searchsploit(query="Apache 2.4")` - catches version-range vulns
3. **Software name + vuln type** - `searchsploit(query="Apache RCE")` - broader search
4. **CVE number** (if known) - `searchsploit(query="CVE-2021-44228")` - specific exploit

### Search Tips

- **Be specific first, broaden later** - `Apache 2.4.29` before `Apache`
- **Include version numbers** - `OpenSSH 7.4` not just `OpenSSH`
- **Try multiple terms** - `WordPress 5.8` AND `WordPress core 5.8`
- **Use `--exact` for precision** - avoids partial matches that pollute results
- **Use `-w` for URLs** - gives direct Exploit-DB links for downloading PoCs

## Proxy Configuration

Searchsploit searches a local database - no network access needed, no proxy required.

## Retry Strategy

1. **No results**: Broaden the search. Drop version number or try different software name variant.
2. **Too many results**: Add `--exact` flag. Include full version number.
3. **Exploit not in local DB**: Run `searchsploit -u` to update the database (if available).
4. **Need the actual exploit code**: Use `-p` flag to get the file path, then read the exploit.

## Output Interpretation

- **Exploit with "Remote" in type** - HIGH priority. Can be exploited over the network.
- **Exploit with "Local" in type** - requires existing access to the target system.
- **Exploit with "DoS" in type** - Denial of Service only. Lower priority for data extraction.
- **Metasploit module referenced** - use `metasploit_run` with that module for automated exploitation.
- **Python/Ruby exploit script** - can be run via `execute_python_script` (published exploits only).
- **Multiple exploits for same version** - try the most recent one first (better reliability).

## Workflow Integration

```
# Step 1: Recon finds Apache 2.4.29
# Step 2: Search for exploits
searchsploit(query="Apache 2.4.29")

# Step 3: If Metasploit module found -> metasploit_run
# Step 4: If Python PoC found -> execute_python_script (published exploit)
# Step 5: If manual exploit -> hand to @exploiter with exploit details
```

## CVE Cross-Reference (CRITICAL)

When searchsploit returns CVE-based results:

1. **Verify the CVE is real** - check the CVE number format and description
2. **Verify the vulnerability TYPE** - do NOT misreport XSS as RCE
3. **Verify the affected version** - exploit may not work on the exact target version
4. **Note the CVSS score** - use for accurate severity classification

## Evidence Capture

Save searchsploit output to `output/{target}/scans/raw/searchsploit_*.txt`. Found exploits inform the exploitation phase - pass specific exploit IDs and paths to @exploiter.
