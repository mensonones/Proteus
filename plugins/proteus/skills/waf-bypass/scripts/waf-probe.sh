#!/usr/bin/env bash
# waf-probe.sh — calibrated WAF block/pass matrix probe.
#
# Learns how an edge filter (Akamai, Cloudflare, AWS WAF, F5, ModSecurity,
# generic) discriminates benign from suspect input by running ONE mutation per
# request against a baseline block fingerprint, then prints a block/pass matrix.
# Designed for the Proteus base research contract: bounded budgets, explicit
# rate limiting, negative controls, and artifacts that survive as evidence.
#
# Usage:
#   waf-probe.sh -u <url> [-p <payload>] [-k <param>] [-b <body>] [-n <budget>]
#                [-r <rate>] [-o <outdir>] [-A <ua>] [-P <proxychains-conf>]
#                [--xff] [--no-proxy] [--tag <tag>] [-h]
#
# Semantics:
#   - Baseline request fingerprints the deny layer (Server header, deny-body
#     tokens, bot-manager cookies). Every later response is classified BLOCK
#     when it matches any fingerprint token; PASS = 2xx app response;
#     REDIR = 3xx; APP-ERR = 4xx/5xx without the deny fingerprint (reached the
#     application — the strongest bypass signal); FAIL = transport error.
#   - Without -p/-k the probe uses a harmless marker value (zqx17) so the
#     matrix measures the filter's normalization parity, not a payload.
#   - With -p payload and -k param, the payload is inserted into the URL as
#     <param>=<mutated-variant> and the marker is appended as a second param
#     so classifications stay comparable. Setting -k also activates the body
#     families (form/JSON/multipart/charset/multiline/chunked smuggling), HPP
#     duplicates, and unicode homoglyph variants — these are the payload-sink
#     probes and cost ~12 extra requests.
#   - -b <body> sends a request body (form-urlencoded) for POST/PUT method
#     differential probes; the payload variants apply to the body param too.
#
# Exit codes: 0 = app-level responses observed despite a blocked baseline
#                 (bypass candidate), 1 = no bypass, 2 = usage/error.
set -euo pipefail

URL=""
PAYLOAD=""
KEY=""
BODY=""
BUDGET=24
RATE=0.5
OUTDIR=""
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"
PX_CONF="${PROXYCHAINS_CONF:-}"
USE_PROXY=1
XFF=0
TAG="$(date +%H%M%S)"
MARKER="zqx17"

usage() { sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    -u) URL="$2"; shift 2 ;;
    -p) PAYLOAD="$2"; shift 2 ;;
    -k) KEY="$2"; shift 2 ;;
    -b) BODY="$2"; shift 2 ;;
    -n) BUDGET="$2"; shift 2 ;;
    -r) RATE="$2"; shift 2 ;;
    -o) OUTDIR="$2"; shift 2 ;;
    -A) UA="$2"; shift 2 ;;
    -P) PX_CONF="$2"; shift 2 ;;
    --xff) XFF=1; shift ;;
    --no-proxy) USE_PROXY=0; shift ;;
    --tag) TAG="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$URL" ]; then
  echo "error: -u <url> is required" >&2
  usage >&2
  exit 2
fi

if [ -z "$OUTDIR" ]; then
  OUTDIR="/tmp/waf-probe-$TAG"
fi
mkdir -p "$OUTDIR"

PV_RAW="${PAYLOAD:-$MARKER}"

CURL_BIN=(curl -sk)
if [ "$USE_PROXY" = "1" ]; then
  if [ -n "$PX_CONF" ]; then
    CURL_BIN=(proxychains4 -f "$PX_CONF" curl -sk)
  else
    CURL_BIN=(proxychains4 curl -sk)
  fi
fi

COUNTER_FILE="$OUTDIR/.count"
next_index() { # persists across subshells via the counter file, always advances
  local n
  n="$(cat "$COUNTER_FILE" 2>/dev/null || echo 1)"
  echo "$((n + 1))" > "$COUNTER_FILE"
  echo "$n"
}

req() { # label url method extra_args... writes OUTDIR/NN_label.hdr/.body,
        # prints "status|server|size|url" and returns 0 (1 = budget exhausted)
  local n
  n="$(next_index)"
  local label="$1" u="$2" m="$3"
  shift 3
  local hdr="$OUTDIR/$(printf '%02d' "$n")_${label}.hdr"
  local body="$OUTDIR/$(printf '%02d' "$n")_${label}.body"
  "${CURL_BIN[@]}" -A "$UA" -X "$m" -D "$hdr" -o "$body" --max-time 20 "$@" "$u" || true
  local status server size loc
  status=$(grep -aoE '^HTTP/[0-9.]+\s+[0-9]{3}' "$hdr" | tail -1 | grep -aoE '[0-9]{3}$' || echo "000")
  server=$(grep -ai '^server:' "$hdr" | head -1 | tr -d '\r' | cut -c1-48 || true)
  loc=$(grep -ai '^location:' "$hdr" | head -1 | tr -d '\r' | cut -c1-90 || true)
  if [ -f "$body" ]; then
    size=$(wc -c < "$body" | tr -d ' ')
  else
    size="-"
  fi
  printf '%s|%s|%s|%s|%s\n' "$status" "$server" "$size" "$u" "$loc"
}

req_stdin() { # label url body method extra... — feeds body via stdin so curl
              # cannot precompute Content-Length (chunked TE probe)
  local n
  n="$(next_index)"
  local label="$1" u="$2" body="$3" m="$4"
  shift 4
  local hdr="$OUTDIR/$(printf '%02d' "$n")_${label}.hdr"
  local out="$OUTDIR/$(printf '%02d' "$n")_${label}.body"
  printf '%s' "$body" | "${CURL_BIN[@]}" -A "$UA" -X "$m" -D "$hdr" -o "$out" --max-time 20 "$@" --http1.1 -H "Transfer-Encoding: chunked" --data-binary @- "$u" || true
  local status server size loc
  status=$(grep -aoE '^HTTP/[0-9.]+\s+[0-9]{3}' "$hdr" | tail -1 | grep -aoE '[0-9]{3}$' || echo "000")
  server=$(grep -ai '^server:' "$hdr" | head -1 | tr -d '\r' | cut -c1-48 || true)
  loc=$(grep -ai '^location:' "$hdr" | head -1 | tr -d '\r' | cut -c1-90 || true)
  if [ -f "$out" ]; then
    size=$(wc -c < "$out" | tr -d ' ')
  else
    size="-"
  fi
  printf '%s|%s|%s|%s|%s\n' "$status" "$server" "$size" "$u" "$loc"
}

log() { printf '[waf-probe] %s\n' "$*" >&2; }

urlencode() { # ascii-safe urlencode
  local s="$1" out="" c h
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:i:1}"
    case "$c" in
      [a-zA-Z0-9_.~-]) out+="$c" ;;
      *) printf -v h '%%%02X' "'$c"; out+="$h" ;;
    esac
  done
  printf '%s' "$out"
}

double_encode() { urlencode "$(urlencode "$1")"; }

case_mix() {
  local s="$1" out="" c n=0
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:i:1}"
    if [[ "$c" =~ [a-zA-Z] ]]; then
      n=$((n + 1))
      if [ $((n % 2)) -eq 1 ]; then c="${c^^}"; else c="${c,,}"; fi
    fi
    out+="$c"
  done
  printf '%s' "$out"
}

comment_spaces() { printf '%s' "$1" | sed 's/ /\/*\*\*\//g'; }
plus_spaces() { printf '%s' "$1" | sed 's/ /+/g'; }

json_escape() { # minimal JSON string escaping
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

raw_quote() { # make a payload URL-safe while keeping its raw form: only
              # encode the bytes curl rejects (space, tab, newline)
  printf '%s' "$1" | sed -e 's/ /%20/g' -e 's/\t/%09/g' -e 's/\n/%0A/g'
}

homoglyph() { # dangerous ASCII -> fullwidth/ideographic Unicode lookalikes
  printf '%s' "$1" | sed \
    -e "s/'/\xef\xbc\x87/g" \
    -e 's/"/\xef\xbc\x82/g' \
    -e 's/</\xef\xbc\x9c/g' \
    -e 's/>/\xef\xbc\x9e/g' \
    -e 's/ /\xe3\x80\x80/g' \
    -e 's/=/\xef\xbc\x9d/g'
}

to_utf7() { # UTF-8 -> UTF-7 (iconv); falls back to identity
  if command -v iconv >/dev/null 2>&1; then
    printf '%s' "$1" | iconv -f UTF-8 -t UTF-7 2>/dev/null || printf '%s' "$1"
  else
    printf '%s' "$1"
  fi
}

to_utf16le() { # UTF-8 -> UTF-16LE (iconv); falls back to identity
  if command -v iconv >/dev/null 2>&1; then
    printf '%s' "$1" | iconv -f UTF-8 -t UTF-16LE 2>/dev/null || printf '%s' "$1"
  else
    printf '%s' "$1"
  fi
}

to_utf16le_pct() { # UTF-8 -> UTF-16LE bytes as %XX (null-safe, for URL values)
  if command -v xxd >/dev/null 2>&1 && command -v iconv >/dev/null 2>&1; then
    printf '%s' "$1" | iconv -f UTF-8 -t UTF-16LE 2>/dev/null | xxd -p | tr -d '\n' | sed 's/../%&/g'
  else
    urlencode "$1"
  fi
}

# probe URL with value v as the probe value for key k (or marker param)
probe_url() {
  local v
  v="$(raw_quote "$1")"
  if [ -n "$KEY" ]; then
    local kenc
    kenc=$(urlencode "$KEY")
    local base="$URL"
    if [[ "$base" == *"?$kenc="* ]] || [[ "$base" == *"&$kenc="* ]]; then
      base=$(printf '%s' "$base" | sed "s/\([?&]$kenc=\)[^&]*/\1$v/")
      printf '%s&wafprobe=%s' "$base" "$MARKER"
    else
      if [[ "$base" == *"?"* ]]; then
        printf '%s&%s=%s&wafprobe=%s' "$base" "$kenc" "$v" "$MARKER"
      else
        printf '%s?%s=%s&wafprobe=%s' "$base" "$kenc" "$v" "$MARKER"
      fi
    fi
  else
    if [[ "$URL" == *"?"* ]]; then
      printf '%s&wafprobe=%s' "$URL" "$v"
    else
      printf '%s?wafprobe=%s' "$URL" "$v"
    fi
  fi
}

echo "=== [1/3] baseline fingerprints ==="
BENIGN="$(req benign "$URL" GET)"
IFS='|' read -r BN_BCK BN_SRV BN_SIZE BN_URL <<< "$BENIGN"
log "benign baseline: HTTP $BN_BCK server='$BN_SRV' size=$BN_SIZE"
log "artifacts: $OUTDIR"

FP_FILE="$OUTDIR/fingerprint.txt"
: > "$FP_FILE"
if [ -n "$BN_SRV" ]; then
  echo "server:${BN_SRV#Server: }" >> "$FP_FILE"
fi
awk 'NF && !seen[$0]++ { print substr($0,1,80); n++ } n>=4 { exit }' "$OUTDIR/01_benign.body" >> "$FP_FILE" || true
grep -ai '^set-cookie:' "$OUTDIR/01_benign.hdr" | sed 's/^[Ss]et-[Cc]ookie:\s*\([^=;]*\).*/\1/' | tr -d '\r' >> "$FP_FILE" || true

SUSPECT_FP_FILE="$OUTDIR/suspect-fingerprint.txt"
BLOCKED_BASE=0
if [ -n "$PAYLOAD" ]; then
  SUSPECT="$(req suspect "$(probe_url "$PV_RAW")" GET)"
  IFS='|' read -r SP_BCK SP_SRV SP_SIZE SP_URL <<< "$SUSPECT"
  log "suspect baseline (raw payload): HTTP $SP_BCK server='$SP_SRV' size=$SP_SIZE"
  : > "$SUSPECT_FP_FILE"
  if [ -n "$SP_SRV" ]; then
    echo "server:${SP_SRV#Server: }" >> "$SUSPECT_FP_FILE"
  fi
  awk 'NF && !seen[$0]++ { print substr($0,1,80); n++ } n>=4 { exit }' "$OUTDIR/02_suspect.body" >> "$SUSPECT_FP_FILE" || true
  grep -ai '^set-cookie:' "$OUTDIR/02_suspect.hdr" | sed 's/^[Ss]et-[Cc]ookie:\s*\([^=;]*\).*/\1/' | tr -d '\r' >> "$SUSPECT_FP_FILE" || true
  if [ "$SP_BCK" != "000" ] && [ "$SP_BCK" -ge 400 ]; then
    BLOCKED_BASE=1
  else
    log "WARNING: suspect baseline PASSED (HTTP $SP_BCK) — no active filter on this payload. Matrix measures parity, not bypass."
  fi
elif [ "$BN_BCK" != "000" ] && [ "$BN_BCK" -ge 400 ]; then
  BLOCKED_BASE=1
  cp "$FP_FILE" "$SUSPECT_FP_FILE"
  log "benign baseline blocked (HTTP $BN_BCK) — treating it as the deny fingerprint."
else
  log "WARNING: benign baseline PASSED and no -p payload given — nothing to bypass."
fi
log "fingerprint tokens: $(wc -l < "$FP_FILE" | tr -d ' ') (benign), $(wc -l < "$SUSPECT_FP_FILE" 2>/dev/null | tr -d ' ') (suspect)"

classify() { # label -> BLOCK|PASS|REDIR|APP-ERR|FAIL (uses exact files of that label)
  local label="$1"
  local idx
  idx="$(($(cat "$COUNTER_FILE") - 1))" # counter already advanced past this request
  local hf="$OUTDIR/$(printf '%02d' "$idx")_${label}.hdr"
  local bf="$OUTDIR/$(printf '%02d' "$idx")_${label}.body"
  local st="$2" srv="$3"
  if [ "$st" = "000" ]; then echo "FAIL"; return; fi
  # WAF-vendor server + deny status + deny-ish body = filter block, regardless
  # of what the fingerprints looked like.
  if [[ "$srv" =~ AkamaiGHost|cloudflare|BigIP|Sucuri|imperva|ModSecurity|FortiWeb|NSFocus|Citrix ]] \
     && { [ "$st" = "403" ] || [ "$st" = "429" ] || [ "$st" = "503" ]; }; then
    if grep -qaiE 'access denied|request blocked|security check|denied|challenge|forbidden|not acceptable' "$bf" 2>/dev/null; then echo "BLOCK"; return; fi
  fi
  if [ "$st" -ge 400 ]; then
    # suspect-fingerprint match (the payload-block reference) is a BLOCK.
    # Server token only counts at the suspect's own status, so shared app/WAF
    # server headers (e.g. nginx+ModSecurity) don't false-positive on other
    # app statuses.
    if [ -f "$SUSPECT_FP_FILE" ] && [ -s "$SUSPECT_FP_FILE" ]; then
      local srv_tok
      srv_tok=$(grep '^server:' "$SUSPECT_FP_FILE" | head -1 | sed 's/^server://')
      if [ -n "$srv_tok" ] && [ "$st" = "$SP_BCK" ] && grep -qaiF "Server: $srv_tok" "$hf" 2>/dev/null; then echo "BLOCK"; return; fi
      while IFS= read -r tok; do
        [ -z "$tok" ] && continue
        case "$tok" in
          server:*) continue ;;
          Set-Cookie:*|set-cookie:*) continue ;;
          *)
            if grep -qaiF -- "${tok:0:60}" "$bf" 2>/dev/null; then echo "BLOCK"; return; fi
            ;;
        esac
      done < "$SUSPECT_FP_FILE"
    fi
    # benign-fingerprint match is the app's own error page — APP-ERR, not a WAF
    if [ -n "$BN_SRV" ] && grep -qaiF "Server: $BN_SRV" "$hf" 2>/dev/null; then echo "APP-ERR"; return; fi
    while IFS= read -r tok; do
      [ -z "$tok" ] && continue
      case "$tok" in
        server:*) continue ;;
        Set-Cookie:*|set-cookie:*) continue ;;
        *)
          if grep -qaiF -- "${tok:0:60}" "$bf" 2>/dev/null; then echo "APP-ERR"; return; fi
          ;;
      esac
    done < "$FP_FILE"
  fi
  if [ "$st" -ge 300 ] && [ "$st" -lt 400 ]; then echo "REDIR"; return; fi
  if [ "$st" -lt 400 ]; then echo "PASS"; return; fi
  echo "APP-ERR"
}

sleep "$RATE"

echo
echo "=== [2/3] mutation matrix ==="
printf '%-3s %-16s %-42s %6s %8s %-7s %s\n' "#" "family" "variant" "http" "size" "verdict" "server"
declare -a RESULTS=()
run() { # family variant url method extra... (one request, budget-checked)
  if [ "$(cat "$COUNTER_FILE")" -gt "$BUDGET" ]; then return; fi
  local fam="$1" var="$2" u="$3" m="$4"
  shift 4
  local label="${fam}-${var}"
  local r n
  r="$(req "$label" "$u" "$m" "$@")"
  IFS='|' read -r st srv sz uu loc <<< "$r"
  n="$(($(cat "$COUNTER_FILE") - 1))"
  local vd
  vd="$(classify "$label" "$st" "$srv")"
  RESULTS+=("$fam|$var|$st|$sz|$vd|$uu|$loc")
  if [ "$vd" = "REDIR" ] && [ -n "$loc" ]; then
    printf '%-3s %-16s %-42s %6s %8s %-7s %s (-> %s)\n' "$n" "$fam" "$var" "$st" "$sz" "$vd" "$srv" "$loc"
  else
    printf '%-3s %-16s %-42s %6s %8s %-7s %s\n' "$n" "$fam" "$var" "$st" "$sz" "$vd" "$srv"
  fi
  sleep "$RATE"
}

run_stdin() { # family variant url body method extra... (chunked TE probe)
  if [ "$(cat "$COUNTER_FILE")" -gt "$BUDGET" ]; then return; fi
  local fam="$1" var="$2" u="$3" body="$4" m="$5"
  shift 5
  local label="${fam}-${var}"
  local r n
  r="$(req_stdin "$label" "$u" "$body" "$m" "$@")"
  IFS='|' read -r st srv sz uu loc <<< "$r"
  n="$(($(cat "$COUNTER_FILE") - 1))"
  local vd
  vd="$(classify "$label" "$st" "$srv")"
  RESULTS+=("$fam|$var|$st|$sz|$vd|$uu|$loc")
  printf '%-3s %-16s %-42s %6s %8s %-7s %s\n' "$n" "$fam" "$var" "$st" "$sz" "$vd" "$srv"
  sleep "$RATE"
}

if [ -n "$PAYLOAD" ]; then
  PV="$PAYLOAD"
else
  PV="$MARKER"
fi

# family A: method differential
for M in GET POST PUT PATCH OPTIONS HEAD; do
  if [ "$M" = "POST" ] || [ "$M" = "PUT" ] || [ "$M" = "PATCH" ]; then
    if [ -n "$BODY" ]; then
      run method "$M" "$(probe_url "$PV")" "$M" --data-urlencode "$BODY"
    else
      run method "$M" "$(probe_url "$PV")" "$M" -d ""
    fi
  else
    run method "$M" "$(probe_url "$PV")" "$M"
  fi
done

# family B: encoding parity on the probe value
run encodings raw "$(probe_url "$PV")" GET
run encodings urlencoded "$(probe_url "$(urlencode "$PV")")" GET
run encodings double-encoded "$(probe_url "$(double_encode "$PV")")" GET
run encodings case-mixed "$(probe_url "$(case_mix "$PV")")" GET
run encodings null-byte-prefixed "$(probe_url "%00$PV")" GET
run encodings tab-injected "$(probe_url "$(printf '%s' "$PV" | sed 's/ /%09/g')")" GET
if [[ "$PV" == *" "* ]]; then
  run encodings comment-spaces "$(probe_url "$(comment_spaces "$PV")")" GET
  run encodings plus-spaces "$(probe_url "$(plus_spaces "$PV")")" GET
fi

# family C: structural ambiguity on the path
run structural semicolon-param "$URL;wafprobe=$MARKER" GET
run structural trailing-dot "$URL/." GET
run structural dot-slash "$URL/./" GET
run structural double-slash "$(printf '%s' "$URL" | sed 's#\(://[^/]*\)/#\1//#')" GET
run structural backslash "$(printf '%s\\' "$URL")" GET

# family D: header normalization
run headers UA-rotate "$(probe_url "$PV")" GET -A "curl/8.0"
run headers Accept-json "$(probe_url "$PV")" GET -H "Accept: application/json"
if [ "$XFF" = "1" ]; then
  run headers XFF-echo "$(probe_url "$PV")" GET -H "X-Forwarded-For: 127.0.0.1"
fi

# family E: body framing / content-type smuggling (needs a param name).
# The URL carries only the clean marker; the PAYLOAD travels in the body so
# the filter's body-handling is isolated from its query-string handling.
if [ -n "$KEY" ]; then
  URL_CLEAN="$(probe_url "$MARKER")"
  UTF16_F="$OUTDIR/utf16body.bin"
  to_utf16le "$KEY=$PV" > "$UTF16_F" 2>/dev/null || printf '%s' "$KEY=$PV" > "$UTF16_F"
  UTF7_S="$(to_utf7 "$KEY=$PV")"
  run body form-urlencoded "$URL_CLEAN" POST --data-urlencode "$KEY=$PV"
  run body json "$URL_CLEAN" POST -H "Content-Type: application/json" --data-binary "{\"$KEY\":\"$(json_escape "$PV")\"}"
  run body json-unicode-escaped "$URL_CLEAN" POST -H "Content-Type: application/json" --data-binary "{\"$KEY\":\"$(printf '%s' "$PV" | sed "s/'/\\\\u0027/g; s/ /\\\\u0020/g")\"}"
  run body multipart "$URL_CLEAN" POST -F "$KEY=$PV"
  run body charset-utf7 "$URL_CLEAN" POST -H "Content-Type: application/x-www-form-urlencoded; charset=UTF-7" --data-binary "$UTF7_S"
  run body charset-utf16le "$URL_CLEAN" POST -H "Content-Type: application/x-www-form-urlencoded; charset=UTF-16LE" --data-binary "@$UTF16_F"
  run body multiline "$URL_CLEAN" POST -H "Content-Type: application/x-www-form-urlencoded" --data-binary "$KEY=$PV%0d%0afoo=bar"
  run_stdin body chunked "$URL_CLEAN" "$KEY=$PV" POST
  # family F: parameter pollution — duplicate param, both orders
  run hpp payload-last "$(printf '%s&%s=%s' "$(probe_url "clean")" "$KEY" "$(raw_quote "$PV")")" GET
  run hpp json-duplicate "$URL_CLEAN" POST -H "Content-Type: application/json" --data-binary "{\"$KEY\":\"clean\",\"$KEY\":\"$(json_escape "$PV")\"}"
  # family G: unicode normalization / homoglyphs
  run unicode homoglyph "$(probe_url "$(urlencode "$(homoglyph "$PV")")")" GET
  run unicode utf7-value "$(probe_url "$(urlencode "$(to_utf7 "$PV")")")" GET
  run unicode utf16le-value "$(probe_url "$(to_utf16le_pct "$PV")")" GET
fi

echo
echo "=== [3/3] summary ==="
APPREACH=0
declare -a CAND=()
for row in "${RESULTS[@]}"; do
  IFS='|' read -r fam var st sz vd uu loc <<< "$row"
  case "$vd" in
    PASS|REDIR|APP-ERR)
      APPREACH=$((APPREACH + 1))
      CAND+=("$fam/$var (HTTP $st, ${sz}B) $uu${loc:+ -> $loc}")
      ;;
    FAIL) log "failed request: $fam/$var (connection/timeout)" ;;
  esac
done
if [ "$BLOCKED_BASE" = "0" ]; then
  log "baseline passed — no block to bypass. ${#RESULTS[@]} probes recorded."
  exit 1
fi
if [ "$APPREACH" -gt 0 ]; then
  log "bypass candidates ($APPREACH):"
  for c in "${CAND[@]}"; do
    log "  $c"
  done
  log "app-level responses with a blocked baseline = filter gaps. Verify each URL reaches the intended route, then feed to the branch."
  exit 0
fi
log "no bypass found: every mutation matched the deny fingerprint. Matrix + artifacts in $OUTDIR."
exit 1
