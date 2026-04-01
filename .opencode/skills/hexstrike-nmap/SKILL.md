---
name: "hexstrike-nmap"
description: "Correct parameters, scan types, proxy configuration, and retry strategies for HexStrike nmap_scan, rustscan_scan, and masscan_scan MCP tools."
---

# HexStrike Port Scanning — nmap_scan, rustscan_scan, masscan_scan — Tool Skill

Port scanning and service detection tools. Discover open ports, running services, OS fingerprints, and network topology. nmap is the primary scanner; rustscan is the fast alternative; masscan covers large IP ranges.

---

## nmap_scan — Parameters

| Parameter | Type   | Required | Description                                                         |
| --------- | ------ | -------- | ------------------------------------------------------------------- |
| `target`  | string | **YES**  | IP, hostname, or CIDR range (e.g. `10.10.99.120`, `example.com/24`) |
| `flags`   | string | no       | Nmap flags (e.g. `-sV -O -p-`)                                      |

### Common Flag Combinations

```
# Service version + OS detection (standard)
nmap_scan(target="10.10.99.120", flags="-sV -O")

# Full TCP port scan + service detection
nmap_scan(target="10.10.99.120", flags="-p- -sV")

# Quick top 1000 ports
nmap_scan(target="10.10.99.120", flags="-sV --top-ports 1000")

# Aggressive scan (OS, version, scripts, traceroute)
nmap_scan(target="10.10.99.120", flags="-A")

# Stealth SYN scan
nmap_scan(target="10.10.99.120", flags="-sS -sV")

# UDP scan (slow but finds SNMP, DNS, TFTP)
nmap_scan(target="10.10.99.120", flags="-sU --top-ports 100")

# Script scan for specific vulns
nmap_scan(target="10.10.99.120", flags="-sV --script=vuln")

# Scan specific ports
nmap_scan(target="10.10.99.120", flags="-p 80,443,8080,8443 -sV")
```

### Proxy Configuration

nmap does NOT support HTTP proxies natively. For TCP-level proxying:

```
# Use proxychains (configured in the environment)
nmap_scan(target="10.10.99.120", flags="--proxies socks4://127.0.0.1:9050")
```

For most assessments, nmap runs direct (no proxy) since it needs raw socket access for SYN scans. The `http_proxy` env var does NOT affect nmap.

---

## rustscan_scan — Parameters

| Parameter | Type   | Required | Description                              |
| --------- | ------ | -------- | ---------------------------------------- |
| `target`  | string | **YES**  | IP or hostname (e.g. `10.10.99.120`)     |
| `flags`   | string | no       | RustScan flags (e.g. `--ulimit 5000 -a`) |

Fast port scanner — scans all 65535 ports in seconds. Use as a first pass, then follow up with nmap for service detection on discovered ports.

### Common Usage

```
# Fast full port scan
rustscan_scan(target="10.10.99.120")

# With ulimit for speed
rustscan_scan(target="10.10.99.120", flags="--ulimit 5000")

# Scan specific port range
rustscan_scan(target="10.10.99.120", flags="-r 1-10000")

# Pass results to nmap for service detection
# Step 1: rustscan finds open ports
# Step 2: nmap_scan with -p <ports> -sV on discovered ports
```

### When to Use rustscan vs nmap

- **rustscan**: fast initial port discovery (all 65535 ports)
- **nmap**: service detection, OS fingerprinting, script scans on known-open ports

**Ideal workflow**: rustscan first (find ports) → nmap second (enumerate services on those ports).

---

## masscan_scan — Parameters

| Parameter | Type   | Required | Description                                   |
| --------- | ------ | -------- | --------------------------------------------- |
| `target`  | string | **YES**  | IP range or CIDR (e.g. `10.10.99.0/24`)       |
| `flags`   | string | no       | Masscan flags (e.g. `-p 0-65535 --rate 1000`) |

Mass-scale port scanner for large IP ranges. No proxy support.

### Common Usage

```
# Scan entire /24 subnet for common ports
masscan_scan(target="10.10.99.0/24", flags="-p 80,443,8080,22,21,3306,5432")

# Full port range on single host (very fast)
masscan_scan(target="10.10.99.120", flags="-p 0-65535 --rate 1000")

# Scan multiple hosts with rate limiting
masscan_scan(target="10.10.99.0/24", flags="-p 1-1024 --rate 500")
```

### Limitations

- **No proxy support** — masscan sends raw packets, bypasses the network stack
- **No service detection** — only finds open ports, not what's running
- **Rate-sensitive** — high rates can crash network equipment. Start with `--rate 500`

---

## Retry Strategy

1. **nmap timeout**: Reduce scope — scan specific ports (`-p 80,443`) instead of full range
2. **nmap "host seems down"**: Add `-Pn` to skip host discovery
3. **rustscan connection refused**: Lower ulimit (`--ulimit 1000`), target may be rate-limiting
4. **masscan 0 results**: Ensure target is reachable. Try nmap first — masscan needs raw sockets
5. **Tool not available**: Use alternative (nmap ↔ rustscan ↔ masscan)

## Output Interpretation

- **Open ports** — service is listening, investigate further
- **Filtered ports** — firewall is blocking, note for bypass attempts
- **Closed ports** — service not running (expected)
- **Service versions** (from nmap -sV) — cross-reference with searchsploit for known CVEs
- **OS detection** — helps target exploit selection (Linux vs Windows, version)

## Evidence Capture

Save raw output to `output/{target}/recon/raw/nmap_*.txt` for the final report. Port scan results are foundational evidence for the attack surface map.
