#!/usr/bin/env bash
set -euo pipefail

TOR_SOCKS_PORT="${TOR_SOCKS_PORT:-9050}"
TOR_DATA_DIR="${TOR_DATA_DIR:-/tmp/tor-ephemeral-$$}"
TOR_PID_FILE="${TOR_PID_FILE:-/tmp/tor-ephemeral-$$.pid}"
PROXYCHAINS_CONF="${PROXYCHAINS_CONF:-/etc/proxychains4.conf}"

log() { printf '[tor-ephemeral] %s\n' "$*" >&2; }

install_tor() {
  if command -v tor &>/dev/null; then
    log "tor binary found at $(command -v tor)"
    return 0
  fi
  log "tor not found, installing temporarily..."
  local installed=0
  if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y -qq tor proxychains4 && installed=1
  elif command -v dnf &>/dev/null; then
    sudo dnf install -y tor proxychains && installed=1
  elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm tor proxychains-ng && installed=1
  elif command -v brew &>/dev/null; then
    brew install tor proxychains-ng && installed=1
  fi
  if [ "$installed" -eq 0 ]; then
    log "ERROR: failed to install tor. Check sudo/package manager."
    return 1
  fi
  # Kill any systemd service that may have auto-started
  sudo systemctl stop tor 2>/dev/null || true
  sudo systemctl disable tor 2>/dev/null || true
  if ! command -v tor &>/dev/null; then
    log "ERROR: tor binary still not found after install attempt"
    return 1
  fi
}

start_ephemeral() {
  mkdir -p "$TOR_DATA_DIR"
  nohup tor --SocksPort "$TOR_SOCKS_PORT" \
     --DataDirectory "$TOR_DATA_DIR" \
     --Log "notice file $TOR_DATA_DIR/tor.log" \
     --RunAsDaemon 0 \
     --PidFile "$TOR_PID_FILE" \
     > "$TOR_DATA_DIR/nohup.out" 2>&1 &
  local tor_pid=$!
  echo "$tor_pid" > "$TOR_PID_FILE"
  log "tor starting (pid=$tor_pid)..."
  # Wait for tor to bootstrap
  local attempts=0
  while [ $attempts -lt 30 ]; do
    sleep 1
    if grep -q "Bootstrapped 100%" "$TOR_DATA_DIR/tor.log" 2>/dev/null; then
      log "tor circuit established on socks5://localhost:$TOR_SOCKS_PORT"
  log "use: proxychains4 <command>  (ALL_PROXY is deliberately NOT set)"
      return 0
    fi
    attempts=$((attempts + 1))
  done
  log "WARNING: tor bootstrap may not be complete after 30s. Continuing anyway."
}

check_ip() {
  log "verifying exit IP through Tor..."
  local ip
  ip=$(proxychains4 -q curl -s --max-time 15 https://check.torproject.org/api/ip 2>/dev/null || true)
  if echo "$ip" | grep -qi '"IsTor":\s*true'; then
    log "confirmed: traffic is routed through Tor"
  else
    log "WARNING: could not confirm Tor exit. Check result: ${ip:-timeout}"
  fi
}

stop_ephemeral() {
  relax_enforcement 2>/dev/null || true
  # Kill by PID file first
  if [ -f "$TOR_PID_FILE" ]; then
    local pid
    pid=$(cat "$TOR_PID_FILE" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      log "tor process $pid killed (via PID file)"
    fi
    rm -f "$TOR_PID_FILE"
  fi
  # Kill any orphaned tor processes using this data dir
  pkill -f "tor.*$TOR_SOCKS_PORT" 2>/dev/null || true
  pkill -f "tor.*$TOR_DATA_DIR" 2>/dev/null || true
  # Clean up temp data directories
  rm -rf /tmp/tor-ephemeral-* 2>/dev/null || true
  log "tor data directory removed"
  unset ALL_PROXY HTTP_PROXY HTTPS_PROXY
}

purge_tor() {
  relax_enforcement 2>/dev/null || true
  log "purging tor package..."
  if command -v apt-get &>/dev/null; then
    sudo apt-get purge -y -qq tor proxychains4 2>/dev/null || true
    sudo apt-get autoremove -y -qq 2>/dev/null || true
  elif command -v dnf &>/dev/null; then
    sudo dnf remove -y tor proxychains 2>/dev/null || true
  elif command -v pacman &>/dev/null; then
    sudo pacman -Rns --noconfirm tor proxychains-ng 2>/dev/null || true
  elif command -v brew &>/dev/null; then
    brew uninstall tor proxychains-ng 2>/dev/null || true
  fi
}

CHAIN="PROTEUS_TOR_ENFORCE"

enforce_kernel() {
  require_root "enforce"
  # Idempotent: flush chain if it exists, then recreate
  sudo iptables -D OUTPUT -j "$CHAIN" 2>/dev/null || true
  sudo iptables -F "$CHAIN" 2>/dev/null || true
  sudo iptables -X "$CHAIN" 2>/dev/null || true
  sudo iptables -N "$CHAIN"
  # Allow loopback unconditionally
  sudo iptables -A "$CHAIN" -o lo -j ACCEPT
  # Allow established/related (tor's ongoing circuits survive)
  sudo iptables -A "$CHAIN" -m state --state ESTABLISHED,RELATED -j ACCEPT
  # Allow local SOCKS port so proxychains can reach tor
  sudo iptables -A "$CHAIN" -p tcp --dport "$TOR_SOCKS_PORT" -d 127.0.0.0/8 -j ACCEPT
  # Drop everything else new going to external networks
  sudo iptables -A "$CHAIN" -p tcp -j DROP
  # Insert as first OUTPUT rule
  sudo iptables -I OUTPUT 1 -j "$CHAIN"
  log "iptables enforcement ON — all non-Tor outbound TCP is DROPped"
  log "  (webfetch, direct curl, and any host-level HTTP will fail)"
}

relax_enforcement() {
  require_root "relax"
  sudo iptables -D OUTPUT -j "$CHAIN" 2>/dev/null || true
  sudo iptables -F "$CHAIN" 2>/dev/null || true
  sudo iptables -X "$CHAIN" 2>/dev/null || true
  log "iptables enforcement OFF — outbound traffic unrestricted"
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    log "ERROR: '$1' requires root (iptables). Use sudo."
    return 1
  fi
}

bootstrap() {
  install_tor && start_ephemeral
}

teardown() {
  stop_ephemeral
}

full_teardown() {
  stop_ephemeral
  purge_tor
}

case "${1:-}" in
  bootstrap) bootstrap ;;
  start)     start_ephemeral ;;
  stop)      teardown ;;
  purge)     full_teardown ;;
  check)     check_ip ;;
  enforce)   enforce_kernel ;;
  relax)     relax_enforcement ;;
  *)
    echo "Usage: $0 {bootstrap|start|stop|purge|check|enforce|relax}"
    echo ""
    echo "  bootstrap  install tor if missing and start ephemeral circuit"
    echo "  start      start ephemeral tor (assumes binary exists)"
    echo "  stop       kill tor process and delete temp data directory"
    echo "  purge      stop + remove tor and proxychains packages from system"
    echo "  check      verify exit IP is routed through Tor"
    echo "  enforce    iptables DROP all non-Tor outbound TCP (kernel-level lockdown)"
    echo "  relax      remove iptables enforcement rules"
    exit 1
    ;;
esac
