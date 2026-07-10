#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

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
require_command node "Install Node.js 22 LTS or newer."
require_command npx "Install Node.js 22 LTS or newer."
require_command curl "Install curl with your system package manager."

if command -v node &>/dev/null; then
  node_major="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
  if [ "$node_major" -lt 22 ]; then
    fail "Node.js 22 or newer is required; found $(node --version)."
    missing=1
  else
    ok "Node.js $(node --version) is supported"
  fi
fi

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

if [ "$HEXSTRIKE_MODE" = "local" ]; then
  echo ""
  echo -e "${CYAN}HexStrike system service${NC}"
  echo -e "Install and start HexStrike with systemd? [${YELLOW}Y/n${NC}]"
  read -r service_choice
  service_choice="${service_choice:-y}"

  if [[ "$service_choice" =~ ^[Yy]$ ]]; then
    if [ "${EUID}" -ne 0 ]; then
      warn "Run setup as root to install the systemd service."
    elif ! command -v systemctl &>/dev/null; then
      warn "systemd is not available; start HexStrike manually."
    else
      python_bin="$(command -v python3)"
      service_file="/etc/systemd/system/redcode-hexstrike.service"

      {
        echo "[Unit]"
        echo "Description=RedCode HexStrike backend"
        echo "After=network-online.target"
        echo "Wants=network-online.target"
        echo ""
        echo "[Service]"
        echo "Type=simple"
        echo "WorkingDirectory=${PROJECT_DIR}/hexstrike-ai"
        echo "ExecStart=${python_bin} ${PROJECT_DIR}/hexstrike-ai/hexstrike_server.py --port 8888"
        echo "Restart=on-failure"
        echo "RestartSec=5"
        echo "Environment=PYTHONUNBUFFERED=1"
        echo ""
        echo "[Install]"
        echo "WantedBy=multi-user.target"
      } > "$service_file"

      systemctl daemon-reload
      systemctl enable --now redcode-hexstrike.service
      ok "HexStrike systemd service enabled and started"
    fi
  fi
fi

info "Installing local Python MCP servers..."
pip3 install mcp-server-fetch mcp-server-sqlite
ok "Python MCP servers installed"

info "Preparing local Node MCP servers..."
npx -y @modelcontextprotocol/server-filesystem --help &>/dev/null || true
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

echo ""
ok "Setup complete"
echo ""
if [ "$HEXSTRIKE_MODE" = "local" ]; then
  if command -v systemctl &>/dev/null && systemctl is-active --quiet redcode-hexstrike.service; then
    echo "1. HexStrike service is active: systemctl status redcode-hexstrike"
  else
    echo "1. Start HexStrike: cd hexstrike-ai && python3 hexstrike_server.py --port 8888"
  fi
else
  echo "1. Make sure the LAN HexStrike backend remains reachable at $HEXSTRIKE_URL"
fi
echo "2. Start RedCode from this directory: ./redcode"
echo "3. Verify MCP status: ./redcode mcp list"
echo ""
echo "For the full security toolset, run install-tools.sh separately on the machine hosting HexStrike."
