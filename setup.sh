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
  fail "python3 required for HexStrike. Install Python 3.10+"
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

# ── Environment file ───────────────────────────────────────────

if [ ! -f .env ]; then
  info "Creating .env from template..."
  cp .env.example .env
  ok ".env created — edit it with your values"
  warn "Set LM_STUDIO_URL and BRAVE_API_KEY in .env before running opencode"
else
  ok ".env already exists"
fi

# ── Load env vars ──────────────────────────────────────────────

set -a
source .env 2>/dev/null || true
set +a

# ── Directory structure ────────────────────────────────────────

info "Creating directory structure..."

mkdir -p output/{recon/raw,scans/raw,exploits,pocs,reports}
mkdir -p wordlists

ok "output/ directories created"

# ── HexStrike ──────────────────────────────────────────────────

if [ ! -d "hexstrike-ai" ]; then
  info "Cloning HexStrike AI..."
  if git clone https://github.com/HexStrike-AI/hexstrike-ai.git hexstrike-ai 2>/dev/null; then
    ok "HexStrike cloned"
  else
    warn "Failed to clone HexStrike. You may need to clone it manually:"
    warn "  git clone https://github.com/HexStrike-AI/hexstrike-ai.git hexstrike-ai"
  fi
else
  ok "hexstrike-ai/ already exists"
fi

# ── HexStrike dependencies ────────────────────────────────────

if [ -d "hexstrike-ai" ]; then
  if [ -f "hexstrike-ai/requirements.txt" ]; then
    info "Installing HexStrike Python dependencies..."
    pip3 install -r hexstrike-ai/requirements.txt --quiet 2>/dev/null && ok "HexStrike deps installed" || warn "Failed to install HexStrike deps. Run: pip3 install -r hexstrike-ai/requirements.txt"
  fi
fi

# ── MCP server pre-install (optional, speeds up first run) ─────

info "Pre-installing MCP servers (optional, speeds up first opencode launch)..."

npx -y @modelcontextprotocol/server-filesystem --help &>/dev/null && ok "filesystem MCP ready" || warn "filesystem MCP will install on first use"
npx -y @modelcontextprotocol/server-brave-search --help &>/dev/null && ok "brave-search MCP ready" || warn "brave-search MCP will install on first use"
npx -y @playwright/mcp@latest --help &>/dev/null && ok "playwright MCP ready" || warn "playwright MCP will install on first use"
npx -y @modelcontextprotocol/server-fetch --help &>/dev/null && ok "fetch MCP ready" || warn "fetch MCP will install on first use"
npx -y @modelcontextprotocol/server-sqlite --help &>/dev/null && ok "sqlite MCP ready" || warn "sqlite MCP will install on first use"

# ── Playwright browser ─────────────────────────────────────────

info "Installing Playwright browser (Chromium)..."
npx -y playwright install chromium 2>/dev/null && ok "Chromium installed" || warn "Run manually: npx playwright install chromium"

# ── Connectivity checks ───────────────────────────────────────

echo ""
info "Checking connectivity..."

if [ -n "${LM_STUDIO_URL:-}" ]; then
  base="${LM_STUDIO_URL%/v1}"
  base="${base%/}"
  if curl -s --connect-timeout 3 "$base/v1/models" &>/dev/null; then
    ok "LM Studio reachable at $LM_STUDIO_URL"
  else
    warn "LM Studio not reachable at $LM_STUDIO_URL — make sure it's running"
  fi
else
  warn "LM_STUDIO_URL not set in .env"
fi

if [ -n "${BRAVE_API_KEY:-}" ]; then
  ok "BRAVE_API_KEY is set"
else
  warn "BRAVE_API_KEY not set in .env — Brave Search MCP won't work"
  warn "Get a free key at https://brave.com/search/api/"
fi

# ── Summary ────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Setup Complete!             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your LM_STUDIO_URL and BRAVE_API_KEY"
echo "  2. Start LM Studio with qwen3.5-9b-uncensored-hauhaucs-aggressive loaded"
echo "  3. Run: opencode"
echo ""
echo "Quick start commands inside opencode:"
echo "  /target example.com      — Start recon on a target"
echo "  /scan                    — Run vulnerability scans"
echo "  /exploit                 — Analyze exploitation paths"
echo "  /poc                     — Generate proof-of-concept"
echo "  /report                  — Write vulnerability report"
echo "  /full-chain example.com  — Full assessment pipeline"
echo ""
