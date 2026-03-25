---
description: "Generate proof-of-concept exploit code"
agent: poc
---

Generate a working Proof of Concept for:

$ARGUMENTS

## Instructions

1. Write clean, well-commented exploit code that demonstrates the vulnerability
2. Include in the PoC:
   - Vulnerability description and affected component
   - Prerequisites and setup instructions
   - Command-line usage (argparse or equivalent)
   - A `--check` flag for safe verification without exploitation
   - Clear output showing success/failure with evidence
   - Impact assessment
   - Remediation recommendations
3. Language preference: Python for network/web, Bash for simple chains, JavaScript for browser-based
4. Save the PoC file to `output/pocs/` with a descriptive filename

Review exploit analysis in `output/scans/` for context on the vulnerability.
