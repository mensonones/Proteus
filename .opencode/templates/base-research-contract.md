# Proteus Base Research Contract

Every Proteus role and skill must continuously follow this contract.

## Method

- Work through primitives, invariants, trust boundaries, state transitions,
  interpretation gaps, competing sources of truth, and capability amplification.
- Do not reduce the hunt to a fixed bug-class checklist.
- Use bug classes only as examples or local context, never as the primary search
  frame.
- Prefer non-obvious paths that can plausibly become realistic exploit chains.

## Proteus Memory Root

- Prefer the actual workspace/repository root for Proteus state unless the user
  explicitly instructs a different root.
- Before initializing or recording state, confirm that `--root` points at the
  intended workspace root, not a package, fixture, generated lab, or nested
  subdirectory.
- Do not create a second `.vros` base in a subfolder just because the current
  shell is there. Use `--root <workspace-root>` instead.
- If state was accidentally created in the wrong place, merge it into the
  canonical workspace base before continuing. Examples:
  - `proteus merge --root <workspace-root> --source ./packages/foo/.vros/memory.sqlite`
  - `proteus merge --root <workspace-root> --sources ./old/.vros/memory.sqlite,./nested/.vros`
- Treat root/base drift as research-state corruption risk: pause recording,
  inspect `proteus status --root <expected-root>`, then merge or discard the
  stray base deliberately.

## Validation

- Maintain a realistic attacker model.
- Do not rely on lab-only help, disabled controls, patched target code, or
  non-standard configuration unless official target documentation requires it.
- Validate expected behavior before treating behavior as vulnerable.
- Check memory, known findings, reports, discarded paths, TODO or known-issue
  context, advisories, issues, and changelogs before investing heavily.
- Track kill conditions from the beginning and kill weak hypotheses early.
- Reassess ROI after new evidence.

## Network Operations

Tor must be ephemeral — installed on demand, bootstrapped as the coordinator's
first tool action, used during the round, and removed when the campaign ends or
the coordinator delegates teardown.

### Lifecycle

*Bootstrap (first coordinator tool action, before inspection or MCP calls):*
```bash
bash .opencode/scripts/tor-ephemeral.sh bootstrap
```

If the bundled script is not reachable, inline the steps:
```bash
# install if missing (apt/dnf/pacman/brew)
if ! command -v tor &>/dev/null; then sudo apt-get install -y tor proxychains4; fi
sudo systemctl stop tor 2>/dev/null; sudo systemctl disable tor 2>/dev/null || true
# start ephemeral (not as a systemd service) on the configured SOCKS port
TOR_SOCKS_PORT="${TOR_SOCKS_PORT:-9050}"
mkdir -p /tmp/tor-ephemeral
nohup tor --SocksPort "$TOR_SOCKS_PORT" --DataDirectory /tmp/tor-ephemeral --PidFile /tmp/tor-ephemeral.pid > /tmp/tor-ephemeral/nohup.out 2>&1 &
# generate a proxychains config pinned to the SAME port. Do NOT rely on the
# system /etc/proxychains4.conf — it hardcodes 9050 and would ignore
# TOR_SOCKS_PORT, sending traffic to the wrong (or no) SOCKS port.
PXCONF=/tmp/tor-ephemeral/proxychains-runtime.conf
printf 'strict_chain\nproxy_dns\nremote_dns_subnet 224\n[ProxyList]\nsocks5 127.0.0.1 %s\n' "$TOR_SOCKS_PORT" > "$PXCONF"
```

*Route every outbound call through proxychains only (force the pinned config
with `-f "$PXCONF"` so the configured port is honored):*
```bash
proxychains4 -f "$PXCONF" curl ...
proxychains4 -f "$PXCONF" wget ...
proxychains4 -f "$PXCONF" python3 script.py
```

Do **NOT** export `ALL_PROXY` or `HTTP_PROXY` — they conflict with
proxychains and cause connection failures. proxychains hooks all network
syscalls (curl, wget, python requests, Go net/http) at the libc level.

*Verify circuit (optional, once per bootstrap):*
```bash
proxychains4 -f "$PXCONF" curl -s https://check.torproject.org/api/ip | grep -i '"IsTor":\s*true'
```

*Teardown (during scrub — mandatory before returning):*
```bash
bash .opencode/scripts/tor-ephemeral.sh stop
```

*Full purge (end of campaign or coordinator signal):*
```bash
bash .opencode/scripts/tor-ephemeral.sh purge   # stop + apt-get purge
```

### Rules

- Tor must not persist as a system service after the research round ends.
- The data directory (`/tmp/tor-ephemeral`) must be removed during scrub.
- `ALL_PROXY`, `HTTP_PROXY`, `HTTPS_PROXY` must be unset during scrub.
- If Tor is blocked by the target or unavailable after install, record the
  limitation explicitly and mark the dependency as a blocker, then follow the
  Authorized Direct Egress subsection below. Do not silently continue and do not
  auto-fall back to clearnet.
- **Never use the host's built-in web fetch tool** (`webfetch`, `WebFetch`,
  `fetch_url`, or equivalent). These bypass the OS network stack and cannot
  be proxied through Tor. Every outbound HTTP/HTTPS request must go through
  `proxychains4 curl` (or `proxychains4 wget`, `proxychains4 python3`) via
  bash. If the host only exposes `webfetch` and no bash tool is available,
  record the limitation as a blocker — do not use `webfetch` as a fallback.
- **Enforcement mode (optional, recommended):** Apply iptables rules that
  drop all non-Tor outbound traffic at the kernel level:
  ```bash
  bash .opencode/scripts/tor-ephemeral.sh enforce  # lock down
  bash .opencode/scripts/tor-ephemeral.sh relax    # undo (scrub)
  ```
  In enforce mode, only the `tor` user can make outbound connections.
  Everything else — including the `webfetch` tool's internal HTTP client —
  is blocked by the kernel before it leaves the machine. This is not a
  prompt-level suggestion; it is a netfilter rule that cannot be bypassed
  by ignoring instructions.

### Authorized Direct Egress (WAF-blocked Tor)

Modern WAFs (Akamai, AWS WAF/CloudFront, and similar) return 403 for Tor exit
nodes wholesale, which covers most paid bug-bounty scope. When every in-scope
target 403s on every Tor exit, Tor-first probing deadlocks and staying on Tor
produces no signal. This is a recurring reality, not an edge case.

Direct (non-Tor) egress is an opt-in, per-campaign fallback, never automatic:

1. Confirm the block is Tor-wide — multiple in-scope assets 403 on multiple
   exits — not a single flaky circuit.
2. Record it as a blocker and surface it to the user with the evidence.
3. Proceed on direct egress only after explicit user authorization for this
   campaign, and only under the program's safe harbor.
4. Attach the program identifier header (below) to every request so the traffic
   is attributable to authorized research.
5. Record the anonymization waiver as a campaign decision: what was authorized,
   by whom, and under which safe harbor.

Do not auto-fall back to clearnet. A WAF that blocks Tor specifically can be a
deanonymization trap that forces your real IP; the human authorization gate is
the safeguard.

### Program Identifier Header

Many programs require an identifying header on all test traffic (for example
`X-Bug-Bounty: <platform>-<handle>`). Record the required header as structured
campaign state at setup and attach it to every outbound request — on Tor and on
direct egress alike. It is both a compliance requirement and an anti-burn
measure: it lets the target SOC tell authorized research from an anonymous
attacker and deprioritize instead of edge-blocking.

## Stealth and Rate Discipline (live targets)

On any live, third-party, or production-adjacent target, the request *pattern* is
the tell, not the payload content. Modern edges (Akamai, Cloudflare, bot
managers) score the shape and cadence of requests and block at the edge before
the backend is ever reached, so a noisy sequence burns the endpoint — a hard 403
or IP/identity ban — before the vulnerability can be proven or a PoC built. A
confirmed bug on a permanently blocked endpoint is a self-inflicted dead end.

These rules apply to live authorized remote targets. They do **not** apply to
local, OSS, or private-lab surfaces you fully control, where broad and fast
probing is fine.

- **One probe, then read.** Send a single request, wait, and read the full
  response before deciding the next one. Never fire a batch of payload variations
  (for example `{}`, `0`, `null`, `"1234567890"`) at the same live endpoint in
  quick succession. A burst of variations is the canonical signature of an
  automated scanner and trips signed WAF/bot rules on request pattern alone.
- **Cleanest value first.** Start with the most realistic, well-formed value the
  workflow expects. Do not lead with payload folklore (SQLi markers, format
  strings, repeated numeric probes, `../`, template/`${}` sequences) on a live
  WAF-protected endpoint; those match signed rules regardless of what the backend
  does.
- **Throttle with jitter.** Space live requests with human-plausible, irregular
  delays. Avoid fixed high-frequency sequences.
- **Stop on first signal.** The moment a probe confirms the flaw, stop probing
  that endpoint. Do not re-prove it several more times. Preserve access to build
  the PoC; over-confirmation is what burns the source.
- **Treat high-sensitivity endpoints as high-risk.** Anonymous or unauthenticated
  access to PII, account, payment, or auth-required endpoints raises alerts on a
  single request. Probe those deliberately and minimally, not iteratively.
- **A block is a campaign event.** On a 403/challenge/ban, record it, and do not
  retry the same request shape — repeated blocked retries deepen the ban and can
  trigger further defensive hardening. Reassess, and only rotate circuit or
  identity where scope and program rules allow it.
- **A defensive reaction is corroboration, but it is one-shot.** A fast defensive
  response right after a probe — an edge block within minutes, CORS tightened
  from `*` to a specific origin between rounds, a config change — is evidence you
  touched something real and can strengthen a report. A useful layer
  discriminator: an op-specific 403 at the edge (no backend gateway headers,
  static error HTML) versus the backend actually being reached. Capture it as
  evidence, but do not chase or re-trigger it: provoking the reaction is exactly
  what burns the source.
- **Respect program rate limits and testing restrictions** exactly as recorded
  for the campaign. When in doubt, probe slower and narrower.

## Operational Hygiene

Every role and skill must actively clean up after every action. No research
trace may persist on disk longer than strictly necessary.

### Before every return or handoff, scrub:

1. **Temporary files**: delete any temp scripts, payload stagers, test
   harnesses, build artifacts, extracted directories, or intermediate output
   that is not needed by the next step.
2. **Downloaded or extracted content**: delete APK/IPA expansions, tarballs,
   Docker images pulled only for a probe, or cloned repos unless they are
   intentional, recorded, and gated.
3. **Proxy and network captures**: delete `*.har`, `*.pcap`, `*.pcapng`,
   mitmproxy dumps, burp logs the moment their analysis is complete.
4. **Credentials and secrets**: unset environment variables holding tokens,
   keys, passwords, or cookies. Delete ephemeral `.env`, `.token`, `.session`,
   or credential files immediately after the operation that consumed them.
5. **Shell history**: prefix transient commands with a space. After a round
    that involved long command sequences, consider clearing the relevant
    history segment.
6. **Workspace contamination**: remove any file the agent wrote outside
    `.vros/`. Research output lives in `.vros/` (reports, labs, logs, exports)
    and the coordinator is responsible for moving it if an agent wrote
    elsewhere by mistake.
7. **Environment holdovers**: before returning, confirm no proxy env vars
    (`ALL_PROXY`, `HTTP_PROXY`, `HTTPS_PROXY`) or credential env vars remain set.
8. **Ephemeral Tor**: kill the tor process, delete the data directory
    (`/tmp/tor-ephemeral`), and remove the PID file. On campaign end or
    coordinator signal, also purge the tor and proxychains packages. Use:
    ```bash
    bash .opencode/scripts/tor-ephemeral.sh stop  # every scrub
    bash .opencode/scripts/tor-ephemeral.sh purge # end of campaign
    ```

### Standing rules:

- Never commit research output, findings, PoC labs, extracted artifacts,
  proxy dumps, or harvested data into a public repository.
- Do not log or cache plaintext credentials, session tokens, API keys, or
  target identifiers outside `.vros/`.
- When the host agent offers tracing/logging controls, prefer minimal
  verbosity for security-relevant operations.

Agents that fail to scrub before returning are non-compliant with this
contract and must record the deviation.

## Promotion Standard

Do not promote speculative findings. A candidate needs attacker control, root
cause in the target, concrete impact, correct-practice configuration, negative
controls, dedupe, public-known checks, and rebutted objections.

## Contract Signature

Every final output and checkpoint must include:

```json
{
  "contractSignature": {
    "status": "compliant|deviated|blocked",
    "signedBy": "proteus-role-name",
    "attackerModel": "...",
    "heuristicCoverage": [],
    "antiSlopCheck": "...",
    "deviations": [],
    "deviationRepair": null
  }
}
```

This is not a checkbox. Include short evidence of how the contract was followed.
If you deviated, name the deviation, repair it, and continue from the corrected
state.

`heuristicCoverage` uses the canonical family slugs from
`heuristic-vocabulary.md`. List only the families you actually reasoned about on
your assigned surface — do not pad, and do not invent ad-hoc strings. It is a
shared vocabulary for auditing coverage against skipped surfaces, not a list to
complete: leaving a family off is expected whenever the surface does not exhibit
its signals. If you need a family that is not in the vocabulary, add it there
first so it stays auditable.
