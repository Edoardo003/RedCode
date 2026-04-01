---
name: "hexstrike-xss"
description: "Correct parameters, scanning modes, proxy configuration, and exploitation patterns for HexStrike dalfox and xsser_scan MCP tools."
---

# HexStrike XSS Tools - dalfox and xsser_scan - Tool Skill

Cross-Site Scripting (XSS) detection and exploitation tools. dalfox is the primary XSS scanner (faster, more accurate); xsser_scan is the automated alternative. Use both for comprehensive XSS coverage.

---

## dalfox - Parameters

| Parameter | Type   | Required | Description                                                           |
| --------- | ------ | -------- | --------------------------------------------------------------------- |
| `target`  | string | **YES**  | URL with parameter to test (e.g. `https://example.com/search?q=test`) |
| `flags`   | string | no       | Dalfox flags (e.g. `--proxy`, `--blind`, `--custom-payload`)          |

### Common Usage

```
# Scan a URL with parameter
dalfox(target="https://example.com/search?q=test")

# Scan with proxy
dalfox(target="https://example.com/search?q=test", flags="--proxy http://user:pass@host:port")

# Blind XSS with callback
dalfox(target="https://example.com/search?q=test", flags="--blind https://your-callback.xss.ht")

# Custom payload file
dalfox(target="https://example.com/search?q=test", flags="--custom-payload ./wordlists/PayloadsAllTheThings/XSS_Injection/payload.txt")

# Scan with specific parameter
dalfox(target="https://example.com/page", flags="--param q")

# Output format
dalfox(target="https://example.com/search?q=test", flags="--format json")

# WAF bypass mode
dalfox(target="https://example.com/search?q=test", flags="--waf-evasion")

# Scan from URL list (pipe mode)
dalfox(target="https://example.com/search?q=test", flags="--pipe")
```

### Scan Modes

| Mode     | Flag       | Use Case                   |
| -------- | ---------- | -------------------------- |
| URL mode | (default)  | Single URL with parameters |
| Pipe     | `--pipe`   | Read URLs from stdin/pipe  |
| Server   | `--server` | Run as API server          |

---

## xsser_scan - Parameters

| Parameter | Type   | Required | Description                                            |
| --------- | ------ | -------- | ------------------------------------------------------ |
| `target`  | string | **YES**  | URL to test (e.g. `https://example.com/search?q=test`) |
| `flags`   | string | no       | XSSer flags                                            |

### Common Usage

```
# Automated XSS scan
xsser_scan(target="https://example.com/search?q=test")

# With automatic payload generation
xsser_scan(target="https://example.com/search?q=test", flags="--auto")

# With proxy
xsser_scan(target="https://example.com/search?q=test", flags="--proxy http://user:pass@host:port")

# Target specific parameter
xsser_scan(target="https://example.com/page", flags="-p q=test")
```

---

## When to Use Which

| Tool   | Best For                                           |
| ------ | -------------------------------------------------- |
| dalfox | Fast scanning, WAF bypass, blind XSS, pipe mode    |
| xsser  | Automated multi-vector testing, payload generation |

**Recommended**: Run dalfox first (faster), then xsser on interesting endpoints.

## XSS Parameter Prioritization

Test these parameter types first (highest XSS probability):

1. **Search parameters** - `?q=`, `?search=`, `?query=`
2. **User input displayed** - `?name=`, `?message=`, `?comment=`
3. **Error messages** - `?error=`, `?msg=`, `?redirect=`
4. **URL/path parameters** - `?url=`, `?next=`, `?return=`
5. **AJAX/API parameters** - POST body fields, JSON values

## Proxy Configuration

```
# dalfox
dalfox(target="...", flags="--proxy http://user:pass@host:port")

# xsser
xsser_scan(target="...", flags="--proxy http://user:pass@host:port")
```

**No trailing slash on proxy URL.**

## Retry Strategy

1. **WAF blocking**: Use dalfox `--waf-evasion`. Try encoding payloads.
2. **No XSS found**: Try different parameters. Use custom payloads from PayloadsAllTheThings.
3. **False positives**: Dalfox may flag reflected content as XSS. Verify with Playwright browser rendering.
4. **Timeout**: Large parameter lists take time. Test high-priority parameters first.
5. **Tool not available**: Use the alternative (dalfox <-> xsser). They overlap in capability.

## Output Interpretation

- **Confirmed XSS with payload** - REAL finding. Report with the working payload and severity medium/high.
- **Reflected parameter** - needs verification. May be reflected but filtered/encoded.
- **DOM-based XSS** - dalfox detects some DOM XSS. Verify with Playwright if flagged.
- **Blind XSS callback** - if your callback server receives a hit, XSS is confirmed. HIGH severity.
- **No findings** - target may be properly encoding output. Not a false negative guarantee.

## Exploitation After Detection

When XSS is confirmed:

1. **Craft cookie-stealing payload** - prove session hijack is possible
2. **Test for stored XSS** - if reflected works, try stored (POST to comment/profile fields)
3. **Check CSP headers** - CSP may prevent actual exploitation even if injection works
4. **Document the full chain** - injection point, payload, impact proof

## Evidence Capture

Save raw output to `output/{target}/scans/raw/dalfox_*.txt` and `output/{target}/scans/raw/xsser_*.txt`. Working XSS payloads go directly to @exploiter for exploitation and @poc for PoC generation.
