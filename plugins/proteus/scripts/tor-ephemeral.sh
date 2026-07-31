#!/usr/bin/env bash
set -euo pipefail

TOR_SOCKS_PORT="${TOR_SOCKS_PORT:-9050}"
TOR_DATA_DIR="${TOR_DATA_DIR:-/tmp/tor-ephemeral}"
TOR_PID_FILE="${TOR_PID_FILE:-/tmp/tor-ephemeral.pid}"
PROXYCHAINS_CONF="${PROXYCHAINS_CONF:-/etc/proxychains4.conf}"

log() { printf '[tor-ephemeral] %s\n' "$*" >&2; }

install_tor() {
  if command -v tor &>/dev/null && command -v proxychains4 &>/dev/null; then
    log "tor and proxychains4 binaries found"
    return 0
  fi
  
  log "WARNING: tor or proxychains4 not found."
  log "Automatic package installation is disabled. Proceeding without attempting to install."
  return 1
}

start_ephemeral() {
  # Check if a global Tor service is already listening and working on the specified port
  if proxychains4 -q curl -s --max-time 10 https://check.torproject.org/api/ip 2>/dev/null | grep -qi '"IsTor":\s*true'; then
    log "System Tor is already active on port $TOR_SOCKS_PORT. Using global service."
    return 0
  fi

  if [ -f "$TOR_PID_FILE" ]; then
    local existing_pid
    existing_pid=$(cat "$TOR_PID_FILE" 2>/dev/null || true)
    if [ -n "$existing_pid" ] && kill -0 "$existing_pid" 2>/dev/null; then
      if grep -q "Bootstrapped 100%" "$TOR_DATA_DIR/tor.log" 2>/dev/null; then
        log "reusing active tor circuit (pid=$existing_pid) on socks5://localhost:$TOR_SOCKS_PORT"
        return 0
      fi
      log "tor process $existing_pid is still bootstrapping; waiting for the existing circuit"
      wait_for_bootstrap
      return $?
    fi
    rm -f "$TOR_PID_FILE"
  fi

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
  wait_for_bootstrap
}

wait_for_bootstrap() {
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
  log "ERROR: tor bootstrap did not complete after 30s"
  return 1
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
  # Kill only orphans we can positively attribute to THIS ephemeral instance.
  # Match the exact "--DataDirectory <dir>" argument signature (a unique path)
  # rather than a broad "tor.*PORT" regex that can match unrelated processes.
  local orphan
  for orphan in $(pgrep -f -- "--DataDirectory $TOR_DATA_DIR" 2>/dev/null || true); do
    if [ "$orphan" != "$$" ]; then
      kill "$orphan" 2>/dev/null || true
      log "orphaned tor process $orphan killed (via data-dir match)"
    fi
  done
  rm -rf "$TOR_DATA_DIR" 2>/dev/null || true
  log "tor data directory removed"
  unset ALL_PROXY HTTP_PROXY HTTPS_PROXY
}

purge_tor() {
  relax_enforcement 2>/dev/null || true
  log "purging tor package..."
  log "Automatic package removal is disabled."
}

CHAIN="PROTEUS_TOR_ENFORCE"

# Resolve the uid that the tor process runs as, so enforcement can allow tor's
# own outbound traffic (new circuits, any protocol) while dropping everything
# else. Priority: explicit override -> running tor PID owner -> known service
# users. Prints nothing if it cannot be resolved.
resolve_tor_uid() {
  if [ -n "${TOR_UID:-}" ]; then
    printf '%s' "$TOR_UID"
    return 0
  fi
  if [ -f "$TOR_PID_FILE" ]; then
    local pid uid
    pid=$(cat "$TOR_PID_FILE" 2>/dev/null || true)
    if [ -n "$pid" ] && [ -e "/proc/$pid" ]; then
      uid=$(stat -c '%u' "/proc/$pid" 2>/dev/null || true)
      if [ -n "$uid" ]; then
        printf '%s' "$uid"
        return 0
      fi
    fi
  fi
  local candidate
  for candidate in debian-tor tor; do
    if uid=$(id -u "$candidate" 2>/dev/null); then
      printf '%s' "$uid"
      return 0
    fi
  done
  return 1
}

# Build DROP-by-default egress rules on the given iptables/ip6tables binary.
# Everything except loopback, tor's own traffic, and already-established flows
# is dropped — including UDP (so DNS cannot leak outside Tor).
apply_enforcement_rules() {
  local ipt="$1"
  local tor_uid="$2"
  sudo "$ipt" -D OUTPUT -j "$CHAIN" 2>/dev/null || true
  sudo "$ipt" -F "$CHAIN" 2>/dev/null || true
  sudo "$ipt" -X "$CHAIN" 2>/dev/null || true
  sudo "$ipt" -N "$CHAIN"
  # Allow loopback unconditionally (proxychains -> local tor SOCKS).
  sudo "$ipt" -A "$CHAIN" -o lo -j ACCEPT
  # Allow already-established/related flows so live circuits survive.
  sudo "$ipt" -A "$CHAIN" -m state --state ESTABLISHED,RELATED -j ACCEPT
  # Allow the tor process itself to open NEW outbound connections (any proto).
  if [ -n "$tor_uid" ]; then
    sudo "$ipt" -A "$CHAIN" -m owner --uid-owner "$tor_uid" -j ACCEPT
  fi
  # Drop everything else new going to external networks: TCP *and* UDP.
  # This is what stops direct HTTP, curl/webfetch, and plaintext DNS leaks.
  sudo "$ipt" -A "$CHAIN" -j DROP
  # Insert as first OUTPUT rule.
  sudo "$ipt" -I OUTPUT 1 -j "$CHAIN"
}

enforce_kernel() {
  require_root "enforce" || return 1
  local tor_uid
  tor_uid=$(resolve_tor_uid || true)
  if [ -n "$tor_uid" ]; then
    log "tor traffic will be allowed by owner uid=$tor_uid"
  else
    log "WARNING: could not resolve tor uid; set TOR_UID=<uid> so tor can build"
    log "         new circuits. Proceeding with established-only tor allowance."
  fi

  apply_enforcement_rules iptables "$tor_uid"
  log "iptables (IPv4) enforcement ON — all non-Tor outbound TCP/UDP is DROPped"

  # IPv6 must be locked down too, otherwise dual-stack hosts leak around IPv4.
  if command -v ip6tables &>/dev/null; then
    apply_enforcement_rules ip6tables "$tor_uid"
    log "ip6tables (IPv6) enforcement ON — non-Tor outbound IPv6 is DROPped"
  else
    # No ip6tables tooling: at least try to disable IPv6 egress via sysctl so it
    # cannot bypass the IPv4 rules. Best-effort; logged either way.
    if sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1 \
       && sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1 >/dev/null 2>&1; then
      log "ip6tables missing — IPv6 disabled via sysctl to prevent leaks"
    else
      log "WARNING: ip6tables missing and IPv6 could not be disabled — IPv6 may leak"
    fi
  fi

  log "  (webfetch, direct curl, plaintext DNS, and host-level HTTP will fail)"
}

relax_enforcement() {
  require_root "relax" || return 1
  sudo iptables -D OUTPUT -j "$CHAIN" 2>/dev/null || true
  sudo iptables -F "$CHAIN" 2>/dev/null || true
  sudo iptables -X "$CHAIN" 2>/dev/null || true
  if command -v ip6tables &>/dev/null; then
    sudo ip6tables -D OUTPUT -j "$CHAIN" 2>/dev/null || true
    sudo ip6tables -F "$CHAIN" 2>/dev/null || true
    sudo ip6tables -X "$CHAIN" 2>/dev/null || true
  else
    # Mirror of the sysctl fallback in enforce_kernel: re-enable IPv6 egress.
    sudo sysctl -w net.ipv6.conf.all.disable_ipv6=0 >/dev/null 2>&1 || true
    sudo sysctl -w net.ipv6.conf.default.disable_ipv6=0 >/dev/null 2>&1 || true
  fi
  log "iptables/ip6tables enforcement OFF — outbound traffic unrestricted"
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
    echo "  enforce    DROP all non-Tor outbound TCP/UDP over IPv4 and IPv6"
    echo "             (kernel-level lockdown; set TOR_UID=<uid> if tor runs"
    echo "             under a user this script cannot auto-detect)"
    echo "  relax      remove iptables/ip6tables enforcement rules"
    exit 1
    ;;
esac
