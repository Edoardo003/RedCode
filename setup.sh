#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { echo -e "${CYAN}[*]${NC} $1"; }
ok()   { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[-]${NC} $1"; }

set_env() {
  local key="$1"
  local value="$2"

  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

require_command() {
  local command_name="$1"
  local install_hint="$2"

  if command -v "$command_name" &>/dev/null; then
    ok "$command_name found"
  else
    fail "$command_name not found. $install_hint"
    missing=1
  fi
}

echo ""
echo -e "${RED}RedCode Setup${NC}"
echo ""

missing=0
require_command opencode "Install it from https://opencode.ai/docs/."
require_command git "Install Git with your system package manager."
require_command python3 "Install Python 3.10 or newer."
require_command pip3 "Install pip for Python 3."
require_command npx "Install Node.js 18 or newer."
require_command curl "Install curl with your system package manager."

if [ "$missing" -ne 0 ]; then
  fail "Install the missing prerequisites and run setup again."
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  ok ".env created from .env.example"
fi

set -a
source .env 2>/dev/null || true
set +a

echo ""
echo -e "${CYAN}HexStrike backend${NC}"
echo "The MCP bridge runs beside OpenCode. The heavy backend can run here or on your LAN."
echo "  1) This machine"
echo "  2) Existing server on the local network"
echo -e "Choose [1/2] (default: ${YELLOW}1${NC}):"
read -r hexstrike_choice
hexstrike_choice="${hexstrike_choice:-1}"

case "$hexstrike_choice" in
  2)
    HEXSTRIKE_MODE="lan"
    echo -e "Backend URL (example: ${YELLOW}http://192.168.1.50:8888${NC}):"
    read -r HEXSTRIKE_URL
    if [ -z "$HEXSTRIKE_URL" ]; then
      fail "A backend URL is required in LAN mode."
      exit 1
    fi
    ;;
  *)
    HEXSTRIKE_MODE="local"
    HEXSTRIKE_URL="http://127.0.0.1:8888"
    ;;
esac

HEXSTRIKE_URL="${HEXSTRIKE_URL%/}"
set_env HEXSTRIKE_MODE "$HEXSTRIKE_MODE"
set_env HEXSTRIKE_URL "$HEXSTRIKE_URL"
export HEXSTRIKE_MODE HEXSTRIKE_URL
ok "HexStrike backend configured at $HEXSTRIKE_URL"

if [ -z "${BRAVE_API_KEY:-}" ]; then
  echo ""
  echo -e "${CYAN}Brave Search${NC}"
  echo "Enter BRAVE_API_KEY, or press Enter to leave Brave Search unavailable:"
  read -r brave_key
  if [ -n "$brave_key" ]; then
    set_env BRAVE_API_KEY "$brave_key"
    BRAVE_API_KEY="$brave_key"
    export BRAVE_API_KEY
    ok "BRAVE_API_KEY saved"
  fi
fi

info "Creating project directories..."
mkdir -p output wordlists templates/nuclei/custom
ok "Project directories ready"

clone_if_missing() {
  local url="$1"
  local destination="$2"

  if [ -d "$destination/.git" ]; then
    ok "$destination already present"
  else
    info "Cloning $destination..."
    git clone --depth 1 "$url" "$destination"
    ok "$destination cloned"
  fi
}

clone_if_missing https://github.com/0x4m4/hexstrike-ai.git hexstrike-ai
clone_if_missing https://github.com/danielmiessler/SecLists.git wordlists/SecLists
clone_if_missing https://github.com/swisskyrepo/PayloadsAllTheThings.git wordlists/PayloadsAllTheThings

info "Installing HexStrike bridge dependencies..."
pip3 install -r hexstrike-ai/requirements.txt
ok "HexStrike dependencies installed"

info "Installing local Python MCP servers..."
pip3 install mcp-server-fetch mcp-server-sqlite
ok "Python MCP servers installed"

info "Preparing local Node MCP servers..."
npx -y @modelcontextprotocol/server-filesystem --help &>/dev/null || true
npx -y @brave/brave-search-mcp-server --help &>/dev/null || true
npx -y @playwright/mcp@latest --help &>/dev/null || true
npx -y playwright install chromium
ok "Node MCP servers and Chromium ready"

echo ""
info "Checking HexStrike connectivity..."
if curl -fsS --connect-timeout 5 "${HEXSTRIKE_URL}/health" &>/dev/null; then
  ok "HexStrike is reachable at $HEXSTRIKE_URL"
elif [ "$HEXSTRIKE_MODE" = "local" ]; then
  warn "HexStrike is installed but not running yet."
  warn "Start it with: cd hexstrike-ai && python3 hexstrike_server.py --port 8888"
else
  warn "The LAN backend did not answer at ${HEXSTRIKE_URL}/health."
  warn "Check its bind address, firewall, and that both machines are on the trusted LAN."
fi

if [ -z "${BRAVE_API_KEY:-}" ]; then
  warn "BRAVE_API_KEY is empty; Brave Search MCP will not work until it is configured."
fi

echo ""
ok "Setup complete"
echo ""
if [ "$HEXSTRIKE_MODE" = "local" ]; then
  echo "1. Start HexStrike: cd hexstrike-ai && python3 hexstrike_server.py --port 8888"
else
  echo "1. Make sure the LAN HexStrike backend remains reachable at $HEXSTRIKE_URL"
fi
echo "2. Start RedCode from this directory: ./redcode"
echo "3. Verify MCP status: ./redcode mcp list"
echo ""
echo "For the full security toolset, run install-tools.sh separately on the machine hosting HexStrike."
