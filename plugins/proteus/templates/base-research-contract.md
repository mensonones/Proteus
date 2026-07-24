# Proteus Base Research Contract

Every Proteus role and skill must continuously follow this contract.

## Method

- Work through primitives, invariants, trust boundaries, state transitions,
  interpretation gaps, competing sources of truth, and capability amplification.
- Do not reduce the hunt to a fixed bug-class checklist.
- Use bug classes only as examples or local context, never as the primary search
  frame.
- Prefer non-obvious paths that can plausibly become realistic exploit chains.

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

Tor must be ephemeral — installed on demand, used during the round, and
removed when the campaign ends or the coordinator delegates teardown.

### Lifecycle

*Bootstrap (before first outbound request):*
```bash
bash plugins/proteus/scripts/tor-ephemeral.sh bootstrap
```

If the bundled script is not reachable, inline the steps:
```bash
# install if missing (apt/dnf/pacman/brew)
if ! command -v tor &>/dev/null; then sudo apt-get install -y tor proxychains4; fi
sudo systemctl stop tor 2>/dev/null; sudo systemctl disable tor 2>/dev/null || true
# start ephemeral (not as a systemd service)
mkdir -p /tmp/tor-ephemeral
nohup tor --SocksPort 9050 --DataDirectory /tmp/tor-ephemeral --PidFile /tmp/tor-ephemeral.pid > /tmp/tor-ephemeral/nohup.out 2>&1 &
```

*Route every outbound call through proxychains only:*
```bash
proxychains4 curl ...
proxychains4 wget ...
proxychains4 python3 script.py
```

Do **NOT** export `ALL_PROXY` or `HTTP_PROXY` — they conflict with
proxychains and cause connection failures. proxychains hooks all network
syscalls (curl, wget, python requests, Go net/http) at the libc level.

*Verify circuit (optional, once per bootstrap):*
```bash
proxychains4 curl -s https://check.torproject.org/api/ip | grep -i '"IsTor":\s*true'
```

*Teardown (during scrub — mandatory before returning):*
```bash
bash plugins/proteus/scripts/tor-ephemeral.sh stop
```

*Full purge (end of campaign or coordinator signal):*
```bash
bash plugins/proteus/scripts/tor-ephemeral.sh purge   # stop + apt-get purge
```

### Rules

- Tor must not persist as a system service after the research round ends.
- The data directory (`/tmp/tor-ephemeral`) must be removed during scrub.
- `ALL_PROXY`, `HTTP_PROXY`, `HTTPS_PROXY` must be unset during scrub.
- If Tor is blocked by the target or unavailable after install, record the
  limitation explicitly and mark the dependency as a blocker.
- **Never use the host's built-in web fetch tool** (`webfetch`, `WebFetch`,
  `fetch_url`, or equivalent). These bypass the OS network stack and cannot
  be proxied through Tor. Every outbound HTTP/HTTPS request must go through
  `proxychains4 curl` (or `proxychains4 wget`, `proxychains4 python3`) via
  bash. If the host only exposes `webfetch` and no bash tool is available,
  record the limitation as a blocker — do not use `webfetch` as a fallback.
- **Enforcement mode (optional, recommended):** Apply iptables rules that
  drop all non-Tor outbound traffic at the kernel level:
  ```bash
  bash plugins/proteus/scripts/tor-ephemeral.sh enforce  # lock down
  bash plugins/proteus/scripts/tor-ephemeral.sh relax    # undo (scrub)
  ```
  In enforce mode, only the `tor` user can make outbound connections.
  Everything else — including the `webfetch` tool's internal HTTP client —
  is blocked by the kernel before it leaves the machine. This is not a
  prompt-level suggestion; it is a netfilter rule that cannot be bypassed
  by ignoring instructions.

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
    bash plugins/proteus/scripts/tor-ephemeral.sh stop  # every scrub
    bash plugins/proteus/scripts/tor-ephemeral.sh purge # end of campaign
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
