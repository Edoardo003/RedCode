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

if [ -z "${HEXSTRIKE_URL:-}" ] || [ "${HEXSTRIKE_URL}" = "http://localhost:8888" ]; then
  echo ""
  echo -e "${CYAN}HexStrike Configuration${NC}"
  echo "HexStrike provides 150+ security tools via MCP."
  echo -e "Enter HexStrike server URL (default: ${YELLOW}http://localhost:8888${NC}):"
  read -r hs_url
  hs_url="${hs_url:-http://localhost:8888}"
  sed -i "s|HEXSTRIKE_URL=.*|HEXSTRIKE_URL=${hs_url}|" .env
  ok "HEXSTRIKE_URL set to $hs_url"
fi

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
mkdir -p templates/nuclei/custom
ok "directories created"

# ── Wordlists (SecLists) ──────────────────────────────────────

if [ ! -d "wordlists/SecLists" ]; then
  info "Cloning SecLists into wordlists/..."
  if git clone https://github.com/danielmiessler/SecLists.git wordlists/SecLists; then
    ok "SecLists installed ($(du -sh wordlists/SecLists | cut -f1))"
  else
    warn "Failed to clone SecLists. Clone manually:"
    warn "  git clone https://github.com/danielmiessler/SecLists.git wordlists/SecLists"
  fi
else
  ok "wordlists/SecLists already exists"
fi

if [ ! -d "wordlists/PayloadsAllTheThings" ]; then
  info "Cloning PayloadsAllTheThings into wordlists/..."
  if git clone https://github.com/swisskyrepo/PayloadsAllTheThings.git wordlists/PayloadsAllTheThings; then
    ok "PayloadsAllTheThings installed ($(du -sh wordlists/PayloadsAllTheThings | cut -f1))"
  else
    warn "Failed to clone PayloadsAllTheThings. Clone manually:"
    warn "  git clone https://github.com/swisskyrepo/PayloadsAllTheThings.git wordlists/PayloadsAllTheThings"
  fi
else
  ok "wordlists/PayloadsAllTheThings already exists"
fi

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

# ── Patch HexStrike timeouts (security scans can take hours) ──

if [ -d "hexstrike-ai" ]; then
  info "Patching HexStrike timeouts (300s → 3600s)..."
  patched=0

  if [ -f "hexstrike-ai/hexstrike_mcp.py" ]; then
    if grep -q 'DEFAULT_REQUEST_TIMEOUT = 300' hexstrike-ai/hexstrike_mcp.py; then
      sed -i 's/DEFAULT_REQUEST_TIMEOUT = 300/DEFAULT_REQUEST_TIMEOUT = 3600/' hexstrike-ai/hexstrike_mcp.py
      patched=$((patched + 1))
    elif grep -q 'DEFAULT_REQUEST_TIMEOUT = 3600' hexstrike-ai/hexstrike_mcp.py; then
      patched=$((patched + 1))
    fi
  fi

  if [ -f "hexstrike-ai/hexstrike_server.py" ]; then
    if grep -q 'COMMAND_TIMEOUT = 300' hexstrike-ai/hexstrike_server.py; then
      sed -i 's/COMMAND_TIMEOUT = 300/COMMAND_TIMEOUT = 3600/' hexstrike-ai/hexstrike_server.py
      patched=$((patched + 1))
    elif grep -q 'COMMAND_TIMEOUT = 3600' hexstrike-ai/hexstrike_server.py; then
      patched=$((patched + 1))
    fi
  fi

  if [ "$patched" -eq 2 ]; then
    ok "HexStrike timeouts set to 1 hour (MCP client + server)"
  elif [ "$patched" -eq 1 ]; then
    warn "Partially patched ($patched/2) — check hexstrike_mcp.py and hexstrike_server.py"
  else
    warn "Could not patch HexStrike timeouts — files may have changed upstream"
    warn "Manually set DEFAULT_REQUEST_TIMEOUT=3600 in hexstrike_mcp.py"
    warn "and COMMAND_TIMEOUT=3600 in hexstrike_server.py"
  fi
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
  # Always start from the clean original when re-patching
  if [ -f "${OPENCODE_BIN}.orig" ]; then
    cp "${OPENCODE_BIN}.orig" /tmp/opencode_tobepatch
  else
    cp "$OPENCODE_BIN" /tmp/opencode_tobepatch
  fi

  result=$(python3 - << 'PYEOF'
import os, sys

path = '/tmp/opencode_tobepatch'
data = open(path, 'rb').read()

# Row-by-row replacement of LEFT half only.
# Logo: LEFT(OPEN) + RIGHT(CODE) → LEFT(RED+blank) + RIGHT(CODE unchanged)
# Only 3 pairs needed — right side stays original.
#
# Letters (3 rows each, block chars + marks _^~):
#   R: top=█▀▀█  mid=█▀▀<sp>  bot=▀<sp><sp>▀
#   E: top=█▀▀▀  mid=█^^^     bot=▀▀▀▀
#   D: top=█▀▀▄  mid=█__█     bot=▀▀▀▀
#   [blank]: 4th position filled with padding

# Strategy 1: escape-sequence encoding (\u2588 = 6 ASCII bytes in source)
esc = [
    # Pair 1: Left top (OPEN → RED+blank) — 99 bytes each
    (b'\\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2584',
     b'\\u2588\\u2580\\u2580\\u2588 \\u2588\\u2580\\u2580\\u2580 \\u2588\\u2580\\u2580\\u2584 \\u0020\\u0020\\u0020\\u0020'),
    # Pair 2: Left mid (OPEN → RED+blank) — 54 bytes each
    (b'\\u2588__\\u2588 \\u2588__\\u2588 \\u2588^^^ \\u2588__\\u2588',
     b'\\u2588\\u2580\\u2580  \\u2588^^^ \\u2588__\\u2588 \\u0020   '),
    # Pair 3: Left bot (OPEN → RED+blank) — 89 bytes each
    (b'\\u2580\\u2580\\u2580\\u2580 \\u2588\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580~~\\u2580',
     b'\\u2580  \\u2580 \\u2580\\u2580\\u2580\\u2580 \\u2580\\u2580\\u2580\\u2580 \\u0020\\u0020\\u0020\\u0020'),
]

# Strategy 2: raw UTF-8 encoding (fallback for future Bun versions)
utf8 = [
    # Pair 1: Left top — 51 bytes each
    ('\u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2584'.encode(),
     '\u2588\u2580\u2580\u2588 \u2588\u2580\u2580\u2580 \u2588\u2580\u2580\u2584 \u2003\u2003\u2003\u2003'.encode()),
    # Pair 2: Left mid — 33 bytes each
    ('\u2588__\u2588 \u2588__\u2588 \u2588^^^ \u2588__\u2588'.encode(),
     '\u2588^^  \u2588^^^ \u2588__\u2588 \u2003\u2003\u2003 '.encode()),
    # Pair 3: Left bot — 47 bytes each
    ('\u2580\u2580\u2580\u2580 \u2588\u2580\u2580\u2580 \u2580\u2580\u2580\u2580 \u2580~~\u2580'.encode(),
     '\u2580  \u2580 \u2580\u2580\u2580\u2580 \u2580\u2580\u2580\u2580 \u2003\u2003\u2003\u2003'.encode()),
]

# Detect already-patched binary: D-top followed by blank at left position 4
blank_esc = b'\\u2588\\u2580\\u2580\\u2584 \\u0020\\u0020\\u0020\\u0020'
blank_utf = '\u2588\u2580\u2580\u2584 \u2003\u2003\u2003\u2003'.encode()
if blank_esc in data or blank_utf in data:
    print("patched")
    sys.exit(0)

# Try escape-sequence patterns first
ok = 0
for old, new in esc:
    assert len(old) == len(new), f"esc length mismatch: {len(old)} vs {len(new)}"
    if data.count(old) == 1:
        data = data.replace(old, new, 1)
        ok += 1

# Fallback to raw UTF-8 if no escape patterns matched
if ok == 0:
    for old, new in utf8:
        assert len(old) == len(new), f"utf8 length mismatch: {len(old)} vs {len(new)}"
        if data.count(old) == 1:
            data = data.replace(old, new, 1)
            ok += 1

if ok == 0:
    print("no patterns found")
    sys.exit(1)

open(path, 'wb').write(data)
os.chmod(path, 0o755)
print(f"ok ({ok}/3 rows)")
PYEOF
  )

  case "$result" in
    ok*)
      # Create backup of original ONLY if one doesn't exist yet
      if [ ! -f "${OPENCODE_BIN}.orig" ]; then
        cp "$OPENCODE_BIN" "${OPENCODE_BIN}.orig"
      fi
      mv /tmp/opencode_tobepatch "$OPENCODE_BIN"
      ok "OpenCode binary patched — logo now shows RED CODE! ($result)"
      ;;
    patched)
      ok "OpenCode binary already shows RED CODE logo"
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

# ── Proxy / IP Rotation Setup ─────────────────────────────────

echo ""
echo -e "${CYAN}Proxy / IP Rotation Configuration${NC}"
echo "RedCode can route scans through a proxy for IP rotation."
echo ""
echo "Options:"
echo "  1) Tor (SOCKS5 on 127.0.0.1:9050) — free, slow, rotating IPs"
echo "  2) Custom proxy (HTTP/SOCKS5) — your own or a rotating service"
echo "  3) Proxy list file (Webshare format) — automatic IP rotation"
echo "  4) None — scan directly from this machine"
echo ""
echo -e "Choose [1/2/3/4] (default: ${YELLOW}4${NC}):"
read -r proxy_choice
proxy_choice="${proxy_choice:-4}"

case "$proxy_choice" in
  1)
    info "Installing Tor and proxychains-ng..."
    if command -v apt-get &>/dev/null; then
      apt-get update -qq && apt-get install -y -qq tor proxychains4 2>/dev/null \
        && ok "tor + proxychains4 installed" \
        || warn "Failed — run: apt-get install tor proxychains4"
    elif command -v pacman &>/dev/null; then
      pacman -S --noconfirm tor proxychains-ng 2>/dev/null \
        && ok "tor + proxychains-ng installed" \
        || warn "Failed — run: pacman -S tor proxychains-ng"
    elif command -v dnf &>/dev/null; then
      dnf install -y tor proxychains-ng 2>/dev/null \
        && ok "tor + proxychains-ng installed" \
        || warn "Failed — run: dnf install tor proxychains-ng"
    else
      warn "Unknown package manager. Install tor and proxychains manually."
    fi

    # Enable and start Tor service
    if command -v systemctl &>/dev/null; then
      systemctl enable tor 2>/dev/null && systemctl start tor 2>/dev/null \
        && ok "Tor service started" \
        || warn "Could not start Tor service — run: systemctl start tor"
    fi

    # Configure proxychains for Tor
    PROXYCHAINS_CONF="/etc/proxychains4.conf"
    if [ ! -f "$PROXYCHAINS_CONF" ]; then
      PROXYCHAINS_CONF="/etc/proxychains.conf"
    fi

    if [ -f "$PROXYCHAINS_CONF" ]; then
      # Ensure dynamic_chain is set (comment strict_chain, uncomment dynamic_chain)
      sed -i 's/^strict_chain/#strict_chain/' "$PROXYCHAINS_CONF" 2>/dev/null
      sed -i 's/^#dynamic_chain/dynamic_chain/' "$PROXYCHAINS_CONF" 2>/dev/null
      ok "proxychains configured for dynamic chain mode"
    fi

    # Set PROXY_URL in .env
    sed -i "s|PROXY_URL=.*|PROXY_URL=socks5://127.0.0.1:9050|" .env
    ok "PROXY_URL set to socks5://127.0.0.1:9050 (Tor)"

    # Verify Tor is working
    if command -v curl &>/dev/null && command -v tor &>/dev/null; then
      sleep 2
      tor_ip=$(curl -s --connect-timeout 5 --socks5-hostname 127.0.0.1:9050 https://api.ipify.org 2>/dev/null || echo "")
      if [ -n "$tor_ip" ]; then
        ok "Tor working — exit IP: $tor_ip"
      else
        warn "Tor installed but not responding yet. Check: systemctl status tor"
      fi
    fi
    ;;
  2)
    echo ""
    echo "Enter proxy URL (e.g., socks5://user:pass@host:port or http://host:port):"
    read -r custom_proxy
    if [ -n "$custom_proxy" ]; then
      sed -i "s|PROXY_URL=.*|PROXY_URL=${custom_proxy}|" .env
      ok "PROXY_URL set to $custom_proxy"
    else
      warn "No proxy URL entered — skipping"
    fi
    ;;
  3)
    echo ""
    echo "Enter path to proxy list file (format: IP:PORT:USER:PASS, one per line):"
    echo "Example: /home/user/webshare_proxies.txt"
    read -r proxy_file
    
    if [ -n "$proxy_file" ] && [ -f "$proxy_file" ]; then
      # Validate format
      if head -1 "$proxy_file" | grep -q '^[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+:[0-9]\+:[^:]\+:[^:]\+$'; then
        proxy_count=$(wc -l < "$proxy_file")
        ok "Found $proxy_count proxies in $proxy_file"
        
        # Create proxy rotation script
        info "Installing proxy rotation script..."
        cat > /usr/local/bin/redcode-proxy-rotate << 'PROXY_SCRIPT'
#!/bin/bash
# RedCode Proxy Rotator - picks random proxy from list
set -euo pipefail

PROXY_FILE="${PROXY_FILE:-}"
if [ -z "$PROXY_FILE" ] || [ ! -f "$PROXY_FILE" ]; then
    echo "http://direct" # fallback to direct
    exit 0
fi

# Pick random line from file
TOTAL=$(wc -l < "$PROXY_FILE")
if [ "$TOTAL" -eq 0 ]; then
    echo "http://direct"
    exit 0
fi

LINE_NUM=$(($RANDOM % $TOTAL + 1))
PROXY_LINE=$(sed -n "${LINE_NUM}p" "$PROXY_FILE")

# Parse IP:PORT:USER:PASS format
IFS=':' read -r ip port user pass <<< "$PROXY_LINE"
echo "http://${user}:${pass}@${ip}:${port}"
PROXY_SCRIPT

        chmod +x /usr/local/bin/redcode-proxy-rotate
        
        # Set environment variables
        echo "PROXY_FILE=\"$proxy_file\"" >> .env
        echo "PROXY_ROTATE_SCRIPT=/usr/local/bin/redcode-proxy-rotate" >> .env
        sed -i "s|PROXY_URL=.*|PROXY_URL=\$(redcode-proxy-rotate)|" .env
        
        ok "Proxy rotation configured with $proxy_count endpoints"
        
        # Test one proxy
        info "Testing random proxy..."
        export PROXY_FILE="$proxy_file"
        test_proxy=$(/usr/local/bin/redcode-proxy-rotate)
        if [ "$test_proxy" != "http://direct" ]; then
          proxy_ip=$(curl -s --connect-timeout 5 --proxy "$test_proxy" https://api.ipify.org 2>/dev/null || echo "failed")
          if [ "$proxy_ip" != "failed" ] && [ -n "$proxy_ip" ]; then
            ok "Test proxy working — exit IP: $proxy_ip"
          else
            warn "Test proxy failed — check credentials and format"
          fi
        fi
      else
        warn "Invalid format in $proxy_file. Expected: IP:PORT:USER:PASS"
        warn "Example: 1.2.3.4:8080:username:password"
      fi
    else
      warn "File not found or empty — skipping proxy setup"
    fi
    ;;
  4|"")
    info "No proxy — scanning directly from this machine"
    sed -i "s|PROXY_URL=.*|PROXY_URL=|" .env
    ;;
esac

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
if grep -q "PROXY_URL=socks5" .env 2>/dev/null; then
  echo "  3. Tor proxy enabled — scans will rotate IPs automatically"
fi
echo ""
echo "Quick start commands inside opencode:"
echo "  /target example.com      — Start recon on a target"
echo "  /scan                    — Run vulnerability scans"
echo "  /exploit                 — Analyze exploitation paths"
echo "  /poc                     — Generate proof-of-concept"
echo "  /report                  — Write vulnerability report"
echo "  /full-chain example.com  — Full assessment pipeline"
echo ""
