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

if [ -z "${LM_STUDIO_URL:-}" ] || [ "${LM_STUDIO_URL}" = "http://10.10.99.100:1234/v1" ]; then
  echo ""
  echo -e "${CYAN}LM Studio Configuration${NC}"
  echo "LM Studio hosts the local AI model for PoC generation."
  echo -e "Enter the IP/host of the machine running LM Studio (default: ${YELLOW}10.10.99.100${NC}):"
  read -r lm_ip
  lm_ip="${lm_ip:-10.10.99.100}"
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
  ORIG_MARKER='\u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2584'

  if strings "$OPENCODE_BIN" 2>/dev/null | grep -q "RedCode patched"; then
    ok "OpenCode binary already patched with RedCode logo"
  elif ! strings "$OPENCODE_BIN" 2>/dev/null | grep -q "$ORIG_MARKER"; then
    warn "Could not locate logo strings in binary — may already be patched or binary format changed"
  else
    cp "$OPENCODE_BIN" "${OPENCODE_BIN}.orig" 2>/dev/null || true
    cp "$OPENCODE_BIN" /tmp/opencode_tobepatch

    python3 - << 'PYEOF'
import os, sys

src = '/tmp/opencode_tobepatch'
data = open(src, 'rb').read()

orig = (
    b'var logo = {\n'
    b'  left: ["                   ", '
    b'"\\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2584", '
    b'"\\u2588__\\u2588 \\u2588__\\u2588 \\u2588^^^ \\u2588__\\u2588", '
    b'"\\u2580\\u2580\\u2580\\u2580 \\u2588\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580~~\\u2580"],\n'
    b'  right: ["             \\u2584     ", '
    b'"\\u2588\\u2580\\u2580\\u2580 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588", '
    b'"\\u2588___ \\u2588__\\u2588 \\u2588__\\u2588 \\u2588^^^", '
    b'"\\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580"]\n'
    b'};\nvar marks = "_^~";'
)

new = (
    b'var logo = {\n'
    b'  left: ["                   ", '
    b'"\\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2580 \\u2588\\u2580\\u2580\\u2584 \\u2588\\u2580\\u2580\\u2580", '
    b'"\\u2588\\u2580_\\u2584 \\u2588^^^ \\u2588__\\u2588 \\u2588___", '
    b'"\\u2580  \\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580"],\n'
    b'  right: ["             \\u2584     ", '
    b'"\\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2580", '
    b'"\\u2588__\\u2588 \\u2588__\\u2588 \\u2588^^^ \\u2588___", '
    b'"\\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580"]\n'
    b'};\nvar marks = "_^~";'
)

if len(orig) != len(new):
    print(f"SKIP: byte length mismatch ({len(orig)} vs {len(new)})", file=sys.stderr)
    sys.exit(1)

count = data.count(orig)
if count != 1:
    print(f"SKIP: found {count} matches (expected 1)", file=sys.stderr)
    sys.exit(1)

patched = data.replace(orig, new, 1)
open(src, 'wb').write(patched)
os.chmod(src, 0o755)
print("ok")
PYEOF

    if [ $? -eq 0 ]; then
      mv /tmp/opencode_tobepatch "${OPENCODE_BIN}.new"
      mv "${OPENCODE_BIN}.new" "$OPENCODE_BIN"
      ok "OpenCode binary patched — logo now shows RedCode!"
    else
      warn "Binary patch failed (logo strings not found — version mismatch?)"
      warn "The OpenCode logo.ts source was already patched for future rebuilds"
      rm -f /tmp/opencode_tobepatch
    fi
  fi
fi

# ── Also patch ui.ts colors if source is available ────────────

OPENCODE_UI=$(find /opt/Progetti/opencode /usr/local/lib /root -name "ui.ts" -path "*/cli/ui.ts" 2>/dev/null | head -1 || true)
if [ -n "$OPENCODE_UI" ] && ! grep -q '91m' "$OPENCODE_UI" 2>/dev/null; then
  sed -i 's/\\x1b\[90m.*left fg/\\x1b[91m/g' "$OPENCODE_UI" 2>/dev/null || true
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
