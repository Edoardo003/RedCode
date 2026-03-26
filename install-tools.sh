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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEXSTRIKE_DIR="${SCRIPT_DIR}/hexstrike-ai"

echo ""
echo -e "${RED}╔══════════════════════════════════════╗${NC}"
echo -e "${RED}║    HexStrike Tools Installer         ║${NC}"
echo -e "${RED}║    150+ Security Tools               ║${NC}"
echo -e "${RED}╚══════════════════════════════════════╝${NC}"
echo ""

if [ "$(id -u)" -ne 0 ]; then
  fail "This script must be run as root (sudo ./install-tools.sh)"
  exit 1
fi

installed=0
skipped=0
failed=0

try_install() {
  local name="$1"
  shift
  if command -v "$name" &>/dev/null; then
    ok "$name (already installed)"
    ((skipped++))
    return 0
  fi
  if "$@" &>/dev/null 2>&1; then
    ok "$name"
    ((installed++))
  else
    warn "Failed: $name"
    ((failed++))
  fi
}

go_install() {
  local name="$1"
  local pkg="$2"
  if command -v "$name" &>/dev/null; then
    ok "$name (already installed)"
    ((skipped++))
    return 0
  fi
  if ! command -v go &>/dev/null; then
    warn "Skipped $name (go not installed)"
    ((failed++))
    return 0
  fi
  if go install "$pkg" &>/dev/null 2>&1; then
    ok "$name (go install)"
    ((installed++))
  else
    warn "Failed: $name (go install $pkg)"
    ((failed++))
  fi
}

pip_install() {
  local name="$1"
  local pkg="${2:-$1}"
  if command -v "$name" &>/dev/null; then
    ok "$name (already installed)"
    ((skipped++))
    return 0
  fi
  if pip3 install "$pkg" --quiet &>/dev/null 2>&1; then
    ok "$name (pip)"
    ((installed++))
  else
    warn "Failed: $name (pip install $pkg)"
    ((failed++))
  fi
}

# ── System update ──────────────────────────────────────────────

info "Updating package lists..."
apt-get update -qq

# ── Go toolchain (needed for many security tools) ─────────────

if ! command -v go &>/dev/null; then
  info "Installing Go toolchain..."
  apt-get install -y -qq golang-go 2>/dev/null || {
    warn "Could not install Go via apt. Trying snap..."
    snap install go --classic 2>/dev/null || warn "Go not installed — Go-based tools will be skipped"
  }
fi

if command -v go &>/dev/null; then
  export GOPATH="${GOPATH:-/root/go}"
  export PATH="$PATH:$GOPATH/bin:/usr/local/go/bin"
  ok "Go $(go version 2>/dev/null | awk '{print $3}')"
fi

# ── Python toolchain ──────────────────────────────────────────

info "Ensuring pip3 and venv..."
apt-get install -y -qq python3-pip python3-venv python3-dev 2>/dev/null || true

# ── Common build dependencies ─────────────────────────────────

info "Installing build dependencies..."
apt-get install -y -qq \
  build-essential libssl-dev libffi-dev git curl wget unzip \
  libpcap-dev libxml2-dev libxslt1-dev zlib1g-dev \
  2>/dev/null || true

# ══════════════════════════════════════════════════════════════
# NETWORK RECONNAISSANCE & SCANNING (25+ tools)
# ══════════════════════════════════════════════════════════════

echo ""
info "═══ Network Reconnaissance & Scanning ═══"

try_install nmap       apt-get install -y -qq nmap
try_install masscan    apt-get install -y -qq masscan
try_install fierce     pip3 install --quiet fierce
try_install dnsenum    apt-get install -y -qq dnsenum
try_install theharvester pip3 install --quiet theHarvester
try_install arp-scan   apt-get install -y -qq arp-scan
try_install nbtscan    apt-get install -y -qq nbtscan
try_install rpcclient  apt-get install -y -qq samba-common-bin
try_install enum4linux apt-get install -y -qq enum4linux
try_install smbmap     pip3 install --quiet smbmap
try_install responder  pip3 install --quiet Responder
try_install netexec    pip3 install --quiet netexec

# Go tools
go_install rustscan    "github.com/RustScan/RustScan@latest" 2>/dev/null || {
  if ! command -v rustscan &>/dev/null; then
    info "Installing RustScan via deb..."
    wget -q "https://github.com/RustScan/RustScan/releases/latest/download/rustscan_2.3.0_amd64.deb" -O /tmp/rustscan.deb 2>/dev/null \
      && dpkg -i /tmp/rustscan.deb 2>/dev/null \
      && ok "rustscan (deb)" && ((installed++)) \
      || { warn "Failed: rustscan"; ((failed++)); }
    rm -f /tmp/rustscan.deb
  fi
}

go_install amass       "github.com/owasp-amass/amass/v4/...@master"
go_install subfinder   "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
go_install nuclei      "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"

pip_install autorecon  "autorecon"

# enum4linux-ng
if ! command -v enum4linux-ng &>/dev/null; then
  pip_install enum4linux-ng "enum4linux-ng"
fi

# ══════════════════════════════════════════════════════════════
# WEB APPLICATION SECURITY (40+ tools)
# ══════════════════════════════════════════════════════════════

echo ""
info "═══ Web Application Security ═══"

try_install gobuster   apt-get install -y -qq gobuster
try_install dirb       apt-get install -y -qq dirb
try_install nikto      apt-get install -y -qq nikto
try_install sqlmap     apt-get install -y -qq sqlmap
try_install whatweb    apt-get install -y -qq whatweb
try_install wfuzz      pip3 install --quiet wfuzz
try_install commix     pip3 install --quiet commix

pip_install dirsearch  "dirsearch"
pip_install arjun      "arjun"
pip_install paramspider "paramspider"
pip_install wafw00f    "wafw00f"

go_install feroxbuster "github.com/epi052/feroxbuster@latest" 2>/dev/null || {
  if ! command -v feroxbuster &>/dev/null; then
    apt-get install -y -qq feroxbuster 2>/dev/null \
      && ok "feroxbuster (apt)" && ((installed++)) \
      || { warn "Failed: feroxbuster"; ((failed++)); }
  fi
}

go_install ffuf        "github.com/ffuf/ffuf/v2@latest"
go_install httpx       "github.com/projectdiscovery/httpx/cmd/httpx@latest"
go_install katana      "github.com/projectdiscovery/katana/cmd/katana@latest"
go_install dalfox      "github.com/hahwul/dalfox/v2@latest"
go_install hakrawler   "github.com/hakluke/hakrawler@latest"
go_install gau         "github.com/lc/gau/v2/cmd/gau@latest"
go_install waybackurls "github.com/tomnomnom/waybackurls@latest"
go_install anew        "github.com/tomnomnom/anew@latest"
go_install qsreplace   "github.com/tomnomnom/qsreplace@latest"
go_install uro          "github.com/s0md3v/uro@latest" 2>/dev/null || pip_install uro "uro"

# WPScan (Ruby gem)
if ! command -v wpscan &>/dev/null; then
  if command -v gem &>/dev/null; then
    gem install wpscan --quiet 2>/dev/null && ok "wpscan (gem)" && ((installed++)) || { warn "Failed: wpscan"; ((failed++)); }
  else
    apt-get install -y -qq ruby ruby-dev 2>/dev/null && gem install wpscan --quiet 2>/dev/null \
      && ok "wpscan (gem)" && ((installed++)) \
      || { warn "Failed: wpscan (needs ruby)"; ((failed++)); }
  fi
else
  ok "wpscan (already installed)"
  ((skipped++))
fi

# X8 parameter discovery
go_install x8 "github.com/Sh1Yo/x8@latest" 2>/dev/null || true

# SSL/TLS tools
try_install testssl    apt-get install -y -qq testssl.sh
try_install sslscan    apt-get install -y -qq sslscan
pip_install sslyze     "sslyze"

# JWT tool
pip_install jwt_tool   "jwt-tool" 2>/dev/null || pip_install jwt_tool "PyJWT"

# NoSQLMap
pip_install nosqlmap   "nosqlmap" 2>/dev/null || true

# Tplmap
if ! command -v tplmap &>/dev/null && [ ! -d "/opt/tplmap" ]; then
  git clone --quiet https://github.com/epinna/tplmap.git /opt/tplmap 2>/dev/null \
    && ln -sf /opt/tplmap/tplmap.py /usr/local/bin/tplmap 2>/dev/null \
    && ok "tplmap (git)" && ((installed++)) \
    || { warn "Failed: tplmap"; ((failed++)); }
elif [ -d "/opt/tplmap" ]; then
  ok "tplmap (already installed)"
  ((skipped++))
fi

# ══════════════════════════════════════════════════════════════
# PASSWORD & AUTHENTICATION (12+ tools)
# ══════════════════════════════════════════════════════════════

echo ""
info "═══ Password & Authentication ═══"

try_install hydra      apt-get install -y -qq hydra
try_install john       apt-get install -y -qq john
try_install hashcat    apt-get install -y -qq hashcat
try_install medusa     apt-get install -y -qq medusa
try_install ophcrack   apt-get install -y -qq ophcrack

pip_install patator    "patator"
pip_install hash-identifier "hash-identifier" 2>/dev/null || true

# Evil-WinRM (Ruby gem)
if ! command -v evil-winrm &>/dev/null; then
  gem install evil-winrm --quiet 2>/dev/null && ok "evil-winrm (gem)" && ((installed++)) || { warn "Failed: evil-winrm"; ((failed++)); }
else
  ok "evil-winrm (already installed)"
  ((skipped++))
fi

# CrackMapExec (legacy, netexec is successor)
pip_install crackmapexec "crackmapexec" 2>/dev/null || true

# ══════════════════════════════════════════════════════════════
# BINARY ANALYSIS & REVERSE ENGINEERING (25+ tools)
# ══════════════════════════════════════════════════════════════

echo ""
info "═══ Binary Analysis & Reverse Engineering ═══"

try_install gdb        apt-get install -y -qq gdb
try_install r2         apt-get install -y -qq radare2
try_install binwalk    apt-get install -y -qq binwalk
try_install strings    apt-get install -y -qq binutils
try_install objdump    apt-get install -y -qq binutils
try_install readelf    apt-get install -y -qq binutils
try_install xxd        apt-get install -y -qq xxd
try_install upx        apt-get install -y -qq upx-ucl
try_install foremost   apt-get install -y -qq foremost
try_install steghide   apt-get install -y -qq steghide
try_install exiftool   apt-get install -y -qq libimage-exiftool-perl
try_install checksec   apt-get install -y -qq checksec

pip_install volatility3 "volatility3"
pip_install pwntools   "pwntools"
pip_install angr       "angr"
pip_install ropper     "ropper"

# ROPgadget
pip_install ROPgadget  "ROPgadget"

# one_gadget (Ruby)
if ! command -v one_gadget &>/dev/null; then
  gem install one_gadget --quiet 2>/dev/null && ok "one_gadget (gem)" && ((installed++)) || { warn "Failed: one_gadget"; ((failed++)); }
else
  ok "one_gadget (already installed)"
  ((skipped++))
fi

# GDB plugins (PEDA, GEF)
if [ ! -d "/opt/peda" ]; then
  git clone --quiet https://github.com/longld/peda.git /opt/peda 2>/dev/null && ok "gdb-peda (git)" && ((installed++)) || { warn "Failed: gdb-peda"; ((failed++)); }
else
  ok "gdb-peda (already installed)"
  ((skipped++))
fi

if [ ! -f "/root/.gdbinit-gef.py" ] && [ ! -f "/opt/gef/gef.py" ]; then
  wget -q -O /root/.gdbinit-gef.py https://gef.blah.cat/py 2>/dev/null && ok "gdb-gef" && ((installed++)) || { warn "Failed: gdb-gef"; ((failed++)); }
else
  ok "gdb-gef (already installed)"
  ((skipped++))
fi

# Ghidra (headless, large download)
if ! command -v ghidra &>/dev/null && [ ! -d "/opt/ghidra" ]; then
  info "Installing Ghidra (this may take a while)..."
  apt-get install -y -qq default-jdk 2>/dev/null || true
  GHIDRA_VER="11.3.1"
  GHIDRA_DATE="20250205"
  wget -q "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_${GHIDRA_VER}_build/ghidra_${GHIDRA_VER}_PUBLIC_${GHIDRA_DATE}.zip" -O /tmp/ghidra.zip 2>/dev/null \
    && unzip -q /tmp/ghidra.zip -d /opt/ 2>/dev/null \
    && mv /opt/ghidra_${GHIDRA_VER}_PUBLIC /opt/ghidra 2>/dev/null \
    && ln -sf /opt/ghidra/ghidraRun /usr/local/bin/ghidra 2>/dev/null \
    && ok "ghidra ${GHIDRA_VER}" && ((installed++)) \
    || { warn "Failed: ghidra (manual install may be needed)"; ((failed++)); }
  rm -f /tmp/ghidra.zip
elif [ -d "/opt/ghidra" ]; then
  ok "ghidra (already installed)"
  ((skipped++))
fi

# MSFVenom (Metasploit)
if ! command -v msfvenom &>/dev/null; then
  info "Installing Metasploit Framework..."
  curl -sL https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > /tmp/msfinstall 2>/dev/null \
    && chmod +x /tmp/msfinstall \
    && /tmp/msfinstall 2>/dev/null \
    && ok "metasploit-framework" && ((installed++)) \
    || { warn "Failed: metasploit (manual install may be needed)"; ((failed++)); }
  rm -f /tmp/msfinstall
else
  ok "msfvenom (already installed)"
  ((skipped++))
fi

# ══════════════════════════════════════════════════════════════
# CLOUD & CONTAINER SECURITY (20+ tools)
# ══════════════════════════════════════════════════════════════

echo ""
info "═══ Cloud & Container Security ═══"

pip_install prowler    "prowler"
pip_install scoutsuite "scoutsuite"
pip_install checkov    "checkov"

# Trivy
if ! command -v trivy &>/dev/null; then
  wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key 2>/dev/null | gpg --dearmor -o /usr/share/keyrings/trivy.gpg 2>/dev/null
  echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb generic main" > /etc/apt/sources.list.d/trivy.list 2>/dev/null
  apt-get update -qq 2>/dev/null && apt-get install -y -qq trivy 2>/dev/null \
    && ok "trivy (apt)" && ((installed++)) \
    || { warn "Failed: trivy"; ((failed++)); }
else
  ok "trivy (already installed)"
  ((skipped++))
fi

# Kube tools
go_install kube-hunter "github.com/aquasecurity/kube-hunter@latest" 2>/dev/null || pip_install kube-hunter "kube-hunter"
if ! command -v kube-bench &>/dev/null; then
  go_install kube-bench "github.com/aquasecurity/kube-bench@latest" 2>/dev/null || { warn "Failed: kube-bench"; ((failed++)); }
fi

# Docker bench
if [ ! -d "/opt/docker-bench-security" ]; then
  git clone --quiet https://github.com/docker/docker-bench-security.git /opt/docker-bench-security 2>/dev/null \
    && ok "docker-bench-security (git)" && ((installed++)) \
    || { warn "Failed: docker-bench-security"; ((failed++)); }
else
  ok "docker-bench-security (already installed)"
  ((skipped++))
fi

# Cloud CLIs
try_install aws        apt-get install -y -qq awscli
try_install kubectl    apt-get install -y -qq kubectl 2>/dev/null || {
  if ! command -v kubectl &>/dev/null; then
    curl -sLO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
      && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
      && rm -f kubectl \
      && ok "kubectl" && ((installed++)) \
      || { warn "Failed: kubectl"; ((failed++)); }
  fi
}

# ══════════════════════════════════════════════════════════════
# CTF & FORENSICS (20+ tools)
# ══════════════════════════════════════════════════════════════

echo ""
info "═══ CTF & Forensics ═══"

try_install scalpel    apt-get install -y -qq scalpel
try_install testdisk   apt-get install -y -qq testdisk
try_install photorec   apt-get install -y -qq testdisk

# Steg tools
if ! command -v zsteg &>/dev/null; then
  gem install zsteg --quiet 2>/dev/null && ok "zsteg (gem)" && ((installed++)) || { warn "Failed: zsteg"; ((failed++)); }
else
  ok "zsteg (already installed)"
  ((skipped++))
fi

pip_install stegsolve  "stegsolve" 2>/dev/null || true
pip_install outguess   "outguess" 2>/dev/null || {
  try_install outguess apt-get install -y -qq outguess
}

# Bulk extractor
try_install bulk_extractor apt-get install -y -qq bulk-extractor

# Sleuth Kit / Autopsy
try_install fls        apt-get install -y -qq sleuthkit
try_install autopsy    apt-get install -y -qq autopsy

# ══════════════════════════════════════════════════════════════
# BUG BOUNTY & OSINT (20+ tools)
# ══════════════════════════════════════════════════════════════

echo ""
info "═══ Bug Bounty & OSINT ═══"

pip_install sherlock   "sherlock-project"
pip_install social-analyzer "social-analyzer"
pip_install recon-ng   "recon-ng"
pip_install spiderfoot "spiderfoot"
pip_install trufflehog "trufflehog" 2>/dev/null || go_install trufflehog "github.com/trufflesecurity/trufflehog@latest"

go_install subjack     "github.com/haccer/subjack@latest"
go_install aquatone    "github.com/michenriksen/aquatone@latest" 2>/dev/null || true

# ══════════════════════════════════════════════════════════════
# BROWSER AGENT REQUIREMENTS
# ══════════════════════════════════════════════════════════════

echo ""
info "═══ Browser Agent (Chromium) ═══"

try_install chromium-browser apt-get install -y -qq chromium-browser
if ! command -v chromium-browser &>/dev/null; then
  try_install chromium apt-get install -y -qq chromium
fi
try_install chromedriver apt-get install -y -qq chromium-chromedriver

pip_install selenium   "selenium"

# ══════════════════════════════════════════════════════════════
# HEXSTRIKE PYTHON DEPENDENCIES
# ══════════════════════════════════════════════════════════════

echo ""
info "═══ HexStrike Python Dependencies ═══"

if [ -d "$HEXSTRIKE_DIR" ]; then
  if [ -f "$HEXSTRIKE_DIR/requirements.txt" ]; then
    pip3 install -r "$HEXSTRIKE_DIR/requirements.txt" --quiet 2>/dev/null \
      && ok "hexstrike-ai requirements.txt" \
      || warn "Some HexStrike deps failed — run: pip3 install -r hexstrike-ai/requirements.txt"
  fi
else
  warn "hexstrike-ai/ not found — run setup.sh first to clone it"
fi

# ══════════════════════════════════════════════════════════════
# NUCLEI TEMPLATES
# ══════════════════════════════════════════════════════════════

echo ""
info "═══ Updating Nuclei Templates ═══"

if command -v nuclei &>/dev/null; then
  nuclei -update-templates -silent 2>/dev/null && ok "nuclei templates updated" || warn "nuclei template update failed"
fi

# ══════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════

total=$((installed + skipped + failed))
echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║    Installation Complete!            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}Installed:${NC} $installed"
echo -e "  ${CYAN}Already OK:${NC} $skipped"
echo -e "  ${YELLOW}Failed:${NC}    $failed"
echo -e "  Total:     $total"
echo ""

if [ "$failed" -gt 0 ]; then
  warn "Some tools failed to install. Check output above for details."
  warn "Many tools have special requirements (Kali repos, manual builds, etc.)"
  echo ""
fi

echo "Start HexStrike server:  python3 hexstrike-ai/hexstrike_server.py"
echo "Launch RedCode:          ./redcode"
echo ""
