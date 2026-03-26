#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[*]${NC} $1"; }
ok()    { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
fail()  { echo -e "${RED}[-]${NC} $1"; }

echo ""
echo -e "${RED}╔══════════════════════════════════════╗${NC}"
echo -e "${RED}║          RedCode Setup               ║${NC}"
echo -e "${RED}║   Cybersecurity Automation Platform   ║${NC}"
echo -e "${RED}╚══════════════════════════════════════╝${NC}"
echo ""

# ── Check prerequisites ────────────────────────────────────────

info "Checking prerequisites..."

missing=0

if ! command -v opencode &>/dev/null; then
  fail "opencode not found. Install: curl -fsSL https://opencode.ai/install | bash"
  missing=1
else
  ok "opencode $(opencode --version 2>/dev/null || echo '(installed)')"
fi

if ! command -v node &>/dev/null && ! command -v bun &>/dev/null; then
  fail "node or bun required for MCP servers. Install Node.js 18+ or Bun"
  missing=1
else
  ok "node/bun found"
fi

if ! command -v npx &>/dev/null; then
  fail "npx not found. Install Node.js 18+"
  missing=1
else
  ok "npx found"
fi

if ! command -v python3 &>/dev/null; then
  fail "python3 required for HexStrike and MCP servers. Install Python 3.10+"
  missing=1
else
  ok "python3 $(python3 --version 2>&1 | awk '{print $2}')"
fi

if ! command -v git &>/dev/null; then
  fail "git not found"
  missing=1
else
  ok "git found"
fi

if [ "$missing" -eq 1 ]; then
  echo ""
  fail "Missing prerequisites. Install them and re-run setup."
  exit 1
fi

echo ""

# ── Interactive LM Studio configuration ───────────────────────

if [ ! -f .env ]; then
  info "Creating .env from template..."
  cp .env.example .env
  ok ".env created"
fi

set -a
source .env 2>/dev/null || true
set +a

if [ -z "${LM_STUDIO_URL:-}" ] || [ "${LM_STUDIO_URL}" = "http://10.10.10.55:1234/v1" ]; then
  echo ""
  echo -e "${CYAN}LM Studio Configuration${NC}"
  echo "LM Studio hosts the local AI model for PoC generation."
  echo -e "Enter the IP/host of the machine running LM Studio (default: ${YELLOW}10.10.10.55${NC}):"
  read -r lm_ip
  lm_ip="${lm_ip:-10.10.10.55}"
  LM_STUDIO_URL="http://${lm_ip}:1234/v1"
  sed -i "s|LM_STUDIO_URL=.*|LM_STUDIO_URL=${LM_STUDIO_URL}|" .env
  ok "LM_STUDIO_URL set to $LM_STUDIO_URL"
fi

if [ -z "${BRAVE_API_KEY:-}" ] || [ "${BRAVE_API_KEY}" = "your_key_here" ]; then
  echo ""
  warn "BRAVE_API_KEY not set. Brave Search MCP won't work without it."
  echo "Get a free key at: https://brave.com/search/api/"
  echo "Enter BRAVE_API_KEY (or press Enter to skip):"
  read -r brave_key
  if [ -n "$brave_key" ]; then
    sed -i "s|BRAVE_API_KEY=.*|BRAVE_API_KEY=${brave_key}|" .env
    ok "BRAVE_API_KEY saved"
  else
    warn "Skipped — you can add it later in .env"
  fi
fi

echo ""

# ── Directory structure ────────────────────────────────────────

info "Creating directory structure..."
mkdir -p output/{recon/raw,scans/raw,exploits,pocs,reports}
mkdir -p wordlists
ok "output/ directories created"

# ── HexStrike ──────────────────────────────────────────────────

if [ ! -d "hexstrike-ai" ]; then
  info "Cloning HexStrike AI..."
  if git clone https://github.com/0x4m4/hexstrike-ai.git hexstrike-ai 2>/dev/null; then
    ok "HexStrike cloned"
  else
    warn "Failed to clone HexStrike. Clone manually:"
    warn "  git clone https://github.com/0x4m4/hexstrike-ai.git hexstrike-ai"
  fi
else
  ok "hexstrike-ai/ already exists"
fi

if [ -d "hexstrike-ai" ] && [ -f "hexstrike-ai/requirements.txt" ]; then
  info "Installing HexStrike Python dependencies..."
  pip3 install -r hexstrike-ai/requirements.txt --quiet 2>/dev/null \
    && ok "HexStrike deps installed" \
    || warn "Failed — run manually: pip3 install -r hexstrike-ai/requirements.txt"
fi

# ── Python MCP servers ─────────────────────────────────────────

info "Installing Python MCP servers (fetch + sqlite)..."
pip3 install mcp-server-fetch mcp-server-sqlite --quiet 2>/dev/null \
  && ok "mcp-server-fetch and mcp-server-sqlite installed" \
  || warn "Failed to install Python MCP servers — run: pip3 install mcp-server-fetch mcp-server-sqlite"

# ── Node MCP servers ───────────────────────────────────────────

info "Pre-installing Node MCP servers..."
npx -y @modelcontextprotocol/server-filesystem --help &>/dev/null && ok "filesystem MCP ready" || warn "filesystem MCP will install on first use"
npx -y @brave/brave-search-mcp-server --help &>/dev/null && ok "brave-search MCP ready" || warn "brave-search MCP will install on first use"
npx -y @playwright/mcp@latest --help &>/dev/null && ok "playwright MCP ready" || warn "playwright MCP will install on first use"

info "Installing Playwright browser (Chromium)..."
npx -y playwright install chromium 2>/dev/null && ok "Chromium installed" || warn "Run manually: npx playwright install chromium"

# ── Patch OpenCode binary to show RedCode logo ─────────────────

info "Patching OpenCode CLI to show RedCode logo..."

OPENCODE_BIN=$(which opencode 2>/dev/null || echo "")

if [ -z "$OPENCODE_BIN" ]; then
  warn "opencode binary not found — skipping logo patch"
else
  cp "$OPENCODE_BIN" /tmp/opencode_tobepatch

  result=$(python3 - << 'PYEOF'
import os, sys

path = '/tmp/opencode_tobepatch'
data = open(path, 'rb').read()

# Row-by-row replacement: matches individual logo rows regardless of
# surrounding structure (var logo = {...} formatting differs between
# opencode v1.3.2 and v1.3.3 due to Bun bundler changes).
# Each (old, new) pair has IDENTICAL byte length — verified.

# Strategy 1: escape-sequence encoding (\u2588 = 6 ASCII bytes)
esc = [
    # Left row 1 (top): OPEN -> REDC
    (b'\\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2584',
     b'\\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2580 \\u2588\\u2580\\u2580\\u2584 \\u2588\\u2580\\u2580\\u2580'),
    # Left row 2 (mid): OPEN -> REDC
    (b'\\u2588__\\u2588 \\u2588__\\u2588 \\u2588^^^ \\u2588__\\u2588',
     b'\\u2588\\u2580_\\u2584 \\u2588^^^ \\u2588__\\u2588 \\u2588___'),
    # Left row 3 (bot): OPEN -> REDC
    (b'\\u2580\\u2580\\u2580\\u2580 \\u2588\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580~~\\u2580',
     b'\\u2580  \\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580'),
    # Right row 1 (top): CODE -> ODE+
    (b'\\u2588\\u2580\\u2580\\u2580 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588',
     b'\\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2580'),
    # Right row 2 (mid): CODE -> ODE+
    (b'\\u2588___ \\u2588__\\u2588 \\u2588__\\u2588 \\u2588^^^',
     b'\\u2588__\\u2588 \\u2588__\\u2588 \\u2588^^^ \\u2588___'),
]

# Strategy 2: raw UTF-8 encoding (fallback for future Bun versions)
utf8 = [
    ('\u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2584'.encode(),
     '\u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2580 \u2588\u2580\u2580\u2584 \u2588\u2580\u2580\u2580'.encode()),
    ('\u2588__\u2588 \u2588__\u2588 \u2588^^^ \u2588__\u2588'.encode(),
     '\u2588\u2580_\u2584 \u2588^^^ \u2588__\u2588 \u2588___'.encode()),
    ('\u2580\u2580\u2580\u2580 \u2588\u2580\u2580\u2580 \u2580\u2580\u2580\u2580 \u2580~~\u2580'.encode(),
     '\u2580  \u2580 \u2580\u2580\u2580\u2580 \u2580\u2580\u2580\u2580 \u2580\u2580\u2580\u2580'.encode()),
    ('\u2588\u2580\u2580\u2580 \u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2588'.encode(),
     '\u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2580'.encode()),
    ('\u2588___ \u2588__\u2588 \u2588__\u2588 \u2588^^^'.encode(),
     '\u2588__\u2588 \u2588__\u2588 \u2588^^^ \u2588___'.encode()),
]

# Detect already-patched binary (REDC top row present)
redc_esc = b'\\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2580 \\u2588\\u2580\\u2580\\u2584 \\u2588\\u2580\\u2580\\u2580'
redc_utf = '\u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2580 \u2588\u2580\u2580\u2584 \u2588\u2580\u2580\u2580'.encode()
if redc_esc in data or redc_utf in data:
    print("patched")
    sys.exit(0)

# Try escape-sequence patterns first
ok = 0
for old, new in esc:
    assert len(old) == len(new), f"esc length {len(old)} vs {len(new)}"
    if data.count(old) == 1:
        data = data.replace(old, new, 1)
        ok += 1

# Fallback to raw UTF-8 if no escape patterns matched
if ok == 0:
    for old, new in utf8:
        assert len(old) == len(new), f"utf8 length {len(old)} vs {len(new)}"
        if data.count(old) == 1:
            data = data.replace(old, new, 1)
            ok += 1

if ok == 0:
    print("no patterns found")
    sys.exit(1)

open(path, 'wb').write(data)
os.chmod(path, 0o755)
print(f"ok ({ok}/5 rows)")
PYEOF
  )

  case "$result" in
    ok*)
      # Backup original before replacing
      cp "$OPENCODE_BIN" "${OPENCODE_BIN}.orig" 2>/dev/null || true
      mv /tmp/opencode_tobepatch "$OPENCODE_BIN"
      ok "OpenCode binary patched — logo now shows RedCode! ($result)"
      ;;
    patched)
      ok "OpenCode binary already shows RedCode logo"
      rm -f /tmp/opencode_tobepatch
      ;;
    *)
      warn "Binary patch failed: $result"
      warn "Run: strings \$(which opencode) | grep 'u2588' | head -5"
      warn "and share the output so we can update the patch pattern"
      rm -f /tmp/opencode_tobepatch
      ;;
  esac
fi

# ── Connectivity checks ───────────────────────────────────────

echo ""
info "Checking connectivity..."

set -a
source .env 2>/dev/null || true
set +a

if [ -n "${LM_STUDIO_URL:-}" ]; then
  base="${LM_STUDIO_URL%/v1}"
  base="${base%/}"
  if curl -s --connect-timeout 3 "${base}/v1/models" &>/dev/null; then
    ok "LM Studio reachable at $LM_STUDIO_URL"
  else
    warn "LM Studio not reachable at $LM_STUDIO_URL — make sure it's running"
  fi
fi

if [ -n "${BRAVE_API_KEY:-}" ] && [ "${BRAVE_API_KEY}" != "your_key_here" ]; then
  ok "BRAVE_API_KEY is set"
else
  warn "BRAVE_API_KEY not set — Brave Search MCP won't work"
  warn "Get a free key at https://brave.com/search/api/"
fi

# ── Done ───────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Setup Complete!             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. Make sure LM Studio is running with qwen3.5-9b-uncensored-hauhaucs-aggressive"
echo "  2. Run: opencode"
echo ""
echo "Quick start commands inside opencode:"
echo "  /target example.com      — Start recon on a target"
echo "  /scan                    — Run vulnerability scans"
echo "  /exploit                 — Analyze exploitation paths"
echo "  /poc                     — Generate proof-of-concept"
echo "  /report                  — Write vulnerability report"
echo "  /full-chain example.com  — Full assessment pipeline"
echo ""
