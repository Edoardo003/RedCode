---
name: "hexstrike-pacu"
description: "Correct parameters and usage patterns for HexStrike pacu_exploitation MCP tool - AWS exploitation framework."
---

# HexStrike pacu_exploitation - Tool Skill

AWS exploitation framework for cloud security assessments. Tests for IAM misconfigurations, privilege escalation paths, data exfiltration from S3/RDS/DynamoDB, and cloud-specific attack vectors. Use when the target has AWS infrastructure.

## Accepted Parameters

| Parameter | Type   | Required | Description                                                       |
| --------- | ------ | -------- | ----------------------------------------------------------------- |
| `module`  | string | **YES**  | Pacu module to run (e.g. `iam__enum_users_roles_policies_groups`) |
| `options` | string | no       | Module-specific options                                           |
| `flags`   | string | no       | Additional flags                                                  |

## Common Usage

```
# Enumerate IAM users, roles, policies
pacu_exploitation(module="iam__enum_users_roles_policies_groups")

# Check for privilege escalation
pacu_exploitation(module="iam__privesc_scan")

# Enumerate S3 buckets
pacu_exploitation(module="s3__enum")

# Download S3 bucket contents
pacu_exploitation(module="s3__download_bucket", options="--bucket target-bucket")

# Enumerate EC2 instances
pacu_exploitation(module="ec2__enum")

# Enumerate Lambda functions
pacu_exploitation(module="lambda__enum")

# Enumerate RDS databases
pacu_exploitation(module="rds__enum")

# Check for public snapshots
pacu_exploitation(module="ebs__enum_snapshots_unauth")

# Enumerate secrets
pacu_exploitation(module="secretsmanager__enum")

# Get account info
pacu_exploitation(module="iam__get_credential_report")
```

## Module Categories

| Category              | Modules                                  | Purpose                        |
| --------------------- | ---------------------------------------- | ------------------------------ |
| IAM Enumeration       | `iam__enum_*`, `iam__get_*`              | Map users, roles, permissions  |
| Privilege Escalation  | `iam__privesc_scan`                      | Find priv esc paths            |
| S3 Exploitation       | `s3__enum`, `s3__download_bucket`        | Find and exfiltrate data       |
| EC2 Exploitation      | `ec2__enum`, `ec2__startup_shell_script` | Instance access and RCE        |
| Lambda Exploitation   | `lambda__enum`, `lambda__backdoor_*`     | Function enumeration and abuse |
| Persistence           | `iam__backdoor_*`, `lambda__backdoor_*`  | Maintain access                |
| Credential Harvesting | `ssm__download_parameters`               | Extract stored credentials     |

## When to Use

- AWS credentials found (access keys, IAM keys) during OSINT or exploitation
- Target infrastructure runs on AWS (detected during recon)
- Cloud metadata endpoint accessible via SSRF (169.254.169.254)
- S3 bucket URLs discovered in source code or config files

## Prerequisites

Pacu needs AWS credentials to operate. These come from:

1. **SSRF exploitation** - cloud metadata at `http://169.254.169.254/latest/meta-data/iam/security-credentials/`
2. **Leaked AWS keys** - found in .env files, GitHub repos, config backups
3. **Compromised IAM user** - credentials from brute-force or credential stuffing

## Retry Strategy

1. **Access denied**: Current credentials may lack permissions. Try different modules that need fewer permissions.
2. **Expired credentials**: Temporary STS credentials expire. Re-fetch from metadata endpoint.
3. **Rate limited**: AWS throttles API calls. Add delays between module runs.
4. **Module error**: Check if AWS region is set correctly. Some modules are region-specific.

## Output Interpretation

- **IAM users/roles enumerated** - map the permission landscape. Look for overprivileged roles.
- **Privilege escalation path found** - record the path and request approval before changing privileges.
- **S3 bucket accessible** - check for sensitive data (backups, logs, credentials, PII).
- **Public snapshots found** - can be copied and mounted to extract data.
- **Secrets enumerated** - sensitive evidence; minimize display and validate scope before use.

## Evidence Capture

Save Pacu output to `output/{target}/exploits/raw/pacu_*.txt`. Assign severity from the affected resources, permissions, and demonstrated impact. Store only the credential metadata needed by the approved workflow.
