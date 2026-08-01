#!/usr/bin/env bash
# verify-tor-enforce.sh — verifica o recurso `enforce` do tor-ephemeral.sh
#
# Testa: bootstrap do Tor, baseline direto, enforce (drop de TCP/UDP nao-Tor),
# proxychains sob enforce, DNS UDP externo (leak), IPv6 direto (leak) e
# relax automatico via trap EXIT (a rede volta SEMPRE, mesmo com erro/Ctrl-C).
#
# Avisos:
#   - Use uma VM descartavel: o enforce derruba todo trafego nao-Tor da maquina.
#   - Nao rode via SSH sem acesso ao console: se a conexao cair, so o relax restaura.
#
# Uso: sudo -v && scripts/verify-tor-enforce.sh
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$SCRIPT_DIR/tor-ephemeral.sh"
pass(){ echo "  OK  $1"; }
fail(){ echo "  FALHOU  $1"; }

echo "== 1. subindo Tor =="
sudo bash "$SCRIPT" bootstrap

echo "== 2. circuito ativo? (espera IsTor:true) =="
proxychains4 -q curl -s --max-time 20 https://check.torproject.org/api/ip; echo

echo "== 3. baseline ANTES do enforce: curl direto deve FUNCIONAR =="
curl -s --max-time 8 -o /dev/null -w "http=%{http_code}\n" https://example.com \
  && pass "curl direto funciona (esperado antes do enforce)" || fail "curl direto falhou cedo demais"

# rede volta SEMPRE, mesmo com erro ou Ctrl-C:
trap 'echo "== relax (teardown) =="; sudo bash "$SCRIPT" relax' EXIT

echo "== 4. ENFORCE =="
sudo bash "$SCRIPT" enforce

echo "== 5. testes COM enforce ativo =="
# a) curl direto TCP deve FALHAR
curl -s --max-time 8 -o /dev/null https://example.com \
  && fail "curl direto passou (nao deveria)" || pass "curl direto bloqueado (TCP drop OK)"

# b) proxychains ainda deve passar por Tor
proxychains4 -q curl -s --max-time 25 https://check.torproject.org/api/ip | grep -q '"IsTor":true' \
  && pass "proxychains ainda roteia por Tor" || fail "Tor quebrou sob enforce (ver TOR_UID)"

# c) DNS direto a resolver externo deve FALHAR (prova anti-leak de DNS/UDP)
if command -v dig >/dev/null; then
  dig +time=3 +tries=1 @8.8.8.8 example.com >/dev/null 2>&1 \
    && fail "DNS UDP externo passou (LEAK)" || pass "DNS UDP externo bloqueado (sem leak)"
fi

# d) IPv6 direto deve FALHAR
curl -s -6 --max-time 8 -o /dev/null https://example.com 2>/dev/null \
  && fail "IPv6 direto passou (LEAK)" || pass "IPv6 direto bloqueado"

echo "== 6. relax dispara automatico no EXIT =="
