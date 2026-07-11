#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: sudo ./install-tools.sh [profile ...]

Install security tools available from the host's configured APT repositories.

Profiles:
  core      Basic discovery and data-processing tools
  web       Web discovery and validation tools
  network   Network and SMB enumeration tools
  ctf       Local binary, password, and artifact-analysis tools
  all       Every profile above

With no arguments, the script installs the core and web profiles.
It does not add third-party repositories or execute remote install scripts.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "error: run this installer as root" >&2
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1 || ! command -v apt-cache >/dev/null 2>&1; then
  echo "error: this installer requires an APT-based Linux distribution" >&2
  exit 1
fi

declare -A PROFILE_PACKAGES=(
  [core]="nmap dnsutils whois jq curl git"
  [web]="gobuster ffuf nikto sqlmap hydra whatweb"
  [network]="masscan arp-scan smbclient enum4linux"
  [ctf]="gdb binutils checksec radare2 binwalk foremost steghide libimage-exiftool-perl john hashcat"
)

profiles=("$@")
if [ "${#profiles[@]}" -eq 0 ]; then
  profiles=(core web)
fi

expanded=()
for profile in "${profiles[@]}"; do
  if [ "$profile" = "all" ]; then
    expanded=(core web network ctf)
    break
  fi
  if [ -z "${PROFILE_PACKAGES[$profile]+x}" ]; then
    echo "error: unknown profile '$profile'" >&2
    usage >&2
    exit 2
  fi
  expanded+=("$profile")
done

packages=()
for profile in "${expanded[@]}"; do
  read -r -a profile_packages <<< "${PROFILE_PACKAGES[$profile]}"
  packages+=("${profile_packages[@]}")
done

mapfile -t packages < <(printf '%s\n' "${packages[@]}" | sort -u)

echo "Updating APT metadata..."
apt-get update

installed=()
unavailable=()
failed=()

for package in "${packages[@]}"; do
  if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q "ok installed"; then
    installed+=("$package (already present)")
    continue
  fi
  if ! apt-cache show "$package" >/dev/null 2>&1; then
    unavailable+=("$package")
    continue
  fi
  echo "Installing $package..."
  if apt-get install -y "$package"; then
    installed+=("$package")
  else
    failed+=("$package")
  fi
done

echo
echo "Profiles: ${expanded[*]}"
echo "Installed or present: ${#installed[@]}"
echo "Unavailable in configured repositories: ${#unavailable[@]}"
echo "Failed: ${#failed[@]}"

if [ "${#unavailable[@]}" -gt 0 ]; then
  printf 'Unavailable: %s\n' "${unavailable[*]}"
fi
if [ "${#failed[@]}" -gt 0 ]; then
  printf 'Failed: %s\n' "${failed[*]}" >&2
  exit 1
fi

echo
echo "Run './redcode doctor' to inspect the capabilities visible to HexStrike."
