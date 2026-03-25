# HackerOne Vulnerability Report

## Title

{{VULNERABILITY_TITLE}}

## Severity

**{{SEVERITY}}** — CVSS v3.1: **{{CVSS_SCORE}}**

Vector: `{{CVSS_VECTOR}}`

## Weakness

**CWE-{{CWE_ID}}**: {{CWE_NAME}}

## Asset

| Field      | Value                 |
| ---------- | --------------------- |
| Asset      | {{ASSET_URL}}         |
| Asset Type | {{ASSET_TYPE}}        |
| Endpoint   | {{AFFECTED_ENDPOINT}} |

## Summary

{{VULNERABILITY_SUMMARY}}

Provide a clear, concise description of the vulnerability. Explain what it is, where it exists, and why it matters. 2-3 paragraphs maximum.

## Steps to Reproduce

1. Navigate to `{{TARGET_URL}}`
2. {{STEP_2}}
3. {{STEP_3}}
4. {{STEP_4}}
5. Observe: {{OBSERVATION}}

### HTTP Request (if applicable)

```http
{{HTTP_METHOD}} {{REQUEST_PATH}} HTTP/1.1
Host: {{TARGET_HOST}}
Authorization: Bearer {{TOKEN_PLACEHOLDER}}
Content-Type: {{CONTENT_TYPE}}

{{REQUEST_BODY}}
```

### HTTP Response

```http
HTTP/1.1 {{RESPONSE_CODE}}
Content-Type: {{RESPONSE_CONTENT_TYPE}}

{{RESPONSE_BODY_SNIPPET}}
```

## Supporting Material / References

- Screenshot: {{SCREENSHOT_DESCRIPTION}}
- PoC script: {{POC_FILE_REFERENCE}}
- Video demonstration: {{VIDEO_LINK}} (if applicable)

## Impact

### Technical Impact

{{TECHNICAL_IMPACT}}

Describe what an attacker can achieve: data access, code execution, privilege escalation, etc.

### Business Impact

{{BUSINESS_IMPACT}}

Describe the real-world consequences: data breach affecting N users, financial loss, regulatory implications, reputation damage.

## Remediation

### Short-term Mitigation

{{SHORT_TERM_FIX}}

### Long-term Fix

{{LONG_TERM_FIX}}

## References

- {{REFERENCE_1}}
- {{REFERENCE_2}}
- {{REFERENCE_3}}
