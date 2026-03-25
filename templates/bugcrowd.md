# Bugcrowd Vulnerability Report

## Title

{{VULNERABILITY_TITLE}}

## VRT Classification

**Category**: {{VRT_CATEGORY}}
**Subcategory**: {{VRT_SUBCATEGORY}}
**Variant**: {{VRT_VARIANT}}

## Severity

**{{BUGCROWD_PRIORITY}}** ({{SEVERITY_LABEL}})

| Priority | Description                              |
| -------- | ---------------------------------------- |
| P1       | Critical — Immediate risk to production  |
| P2       | High — Significant security impact       |
| P3       | Medium — Moderate security impact        |
| P4       | Low — Minor security impact              |
| P5       | Informational — Best practice suggestion |

**CVSS v3.1**: {{CVSS_SCORE}} — `{{CVSS_VECTOR}}`

## Target / Asset

| Field       | Value                 |
| ----------- | --------------------- |
| Target      | {{TARGET_URL}}        |
| Asset       | {{ASSET_IDENTIFIER}}  |
| Endpoint    | {{AFFECTED_ENDPOINT}} |
| Environment | {{ENVIRONMENT}}       |

## Description

{{VULNERABILITY_DESCRIPTION}}

Provide a clear explanation of the vulnerability, its root cause, and the affected component. Include technical details about why the vulnerability exists.

## Steps to Reproduce

1. {{STEP_1}}
2. {{STEP_2}}
3. {{STEP_3}}
4. {{STEP_4}}
5. Observe: {{OBSERVATION}}

### Request Details

```http
{{HTTP_METHOD}} {{REQUEST_PATH}} HTTP/1.1
Host: {{TARGET_HOST}}
{{REQUEST_HEADERS}}

{{REQUEST_BODY}}
```

### Response Details

```http
HTTP/1.1 {{RESPONSE_CODE}}
{{RESPONSE_HEADERS}}

{{RESPONSE_BODY_SNIPPET}}
```

## Proof of Concept

{{POC_DESCRIPTION}}

**PoC File**: {{POC_FILE_REFERENCE}}

**PoC Command** (if applicable):

```bash
{{POC_COMMAND}}
```

**Expected Output**:

```
{{EXPECTED_OUTPUT}}
```

## Impact

{{IMPACT_DESCRIPTION}}

### Attack Scenario

1. Attacker {{ATTACK_STEP_1}}
2. This allows {{ATTACK_STEP_2}}
3. Resulting in {{ATTACK_OUTCOME}}

### Affected Users/Data

- Users affected: {{AFFECTED_USERS}}
- Data exposed: {{AFFECTED_DATA}}

## Remediation

### Suggested Fix

{{REMEDIATION_DESCRIPTION}}

### Code Example (if applicable)

```{{LANGUAGE}}
{{REMEDIATION_CODE}}
```

## References

- CWE: CWE-{{CWE_ID}} — {{CWE_NAME}}
- {{REFERENCE_1}}
- {{REFERENCE_2}}

## VRT Taxonomy Reference

Common VRT categories for reference:

- Server-Side Injection → SQL Injection, Command Injection, SSRF
- Cross-Site Scripting (XSS) → Reflected, Stored, DOM
- Broken Authentication and Session Management
- Insecure Direct Object Reference (IDOR)
- Server Security Misconfiguration
- Sensitive Data Exposure
- Broken Access Control → Privilege Escalation
- Application-Level Denial of Service
- Insufficient Security Configurability
