---
name: proteus-web-research
description: Conduct authorized web application research for Proteus targets using the same campaign, chaining, fuzzing, intel, and PoC heuristics adapted to live or local web surfaces. Use for endpoint behavior mapping, blackbox probes, browser/API workflows, and web pentest-style validation.
---

# Proteus Web Research

Use this skill for authorized web-facing surfaces. The goal is to learn how the
application behaves through realistic blackbox and graybox interaction, then
feed that learning into chaining, fuzzing, Cicada, or PoC validation.

Follow the Proteus base research contract. Respect scope, rate limits, and
program rules. Prefer local or explicitly authorized targets for active probes.

## Network Routing

All outbound probes and web requests must be routed through Tor/Proxychains.
Prefix every network tool invocation with `proxychains4` (for example
`proxychains4 curl ...`). Do **not** export `ALL_PROXY`, `HTTP_PROXY`, or
`HTTPS_PROXY`: they conflict with proxychains and cause connection failures.
Never probe targets directly without the proxy layer unless explicitly
authorized and documented.

If the WAF blocks Tor exits wholesale (403 across in-scope assets on multiple
exits), do not silently go direct and do not fall back to archives/DNS as if the
surface were dead: first invoke the `proteus-waf-bypass` skill (`scripts/waf-probe.sh`)
to fingerprint the filter and classify the block (egress-reputation vs
allowlist-posture vs payload-signature). Only a confirmed egress-reputation block
justifies the Authorized Direct Egress flow in the base research contract (record
blocker, get per-campaign user authorization under safe harbor, then direct
egress); a payload-signature block is solved with the skill's mutation matrix, not
by leaving Tor. When the program requires an identifying header (for example
`X-Bug-Bounty: <platform>-<handle>`), attach it to every request — on Tor and on
direct egress alike.

## Live Probe Discipline

On live third-party targets, the request *pattern* is what gets you blocked, not
the payload content. Edges and bot managers score request shape and cadence and
block before the backend, so a noisy sequence burns the endpoint before you can
prove anything. Follow the Stealth and Rate Discipline section of the base
research contract:

- Send one probe, read the full response, then decide the next. Never fire a
  batch of variations at the same live endpoint in quick succession.
- Lead with the cleanest realistic value; do not open with payload folklore
  (SQLi markers, format strings, repeated numeric probes) on a WAF-protected
  endpoint.
- Throttle with irregular delays. Stop probing an endpoint the moment a probe
  confirms the flaw, and preserve access to build the PoC.
- Treat anonymous access to PII/account/auth-required endpoints as
  high-risk: minimal, deliberate probes only.
- Treat a 403/challenge/ban as a campaign event: record it, do not retry the
  same request shape, and reassess.

During recon and target analysis, stay **read-only**: use safe methods (`GET`,
`HEAD`, `OPTIONS`) against side-effect-free endpoints only. Do not send
state-changing requests (`POST`/`PUT`/`PATCH`/`DELETE`, or side-effecting GETs)
while mapping the target. Mutating probes are a later, deliberately promoted
validation step for one specific branch — not part of enumeration. Mapping
observes behavior; it does not create, update, or delete target state.

Broad, fast probing is only acceptable on local, OSS, or private-lab surfaces
you fully control.

## Operating Method

1. Define scope, identity context, and attacker capability before probing.
2. Map workflows, not just endpoints: authentication, authorization, object
   ownership, state changes, uploads/downloads, callbacks, webhooks, imports,
   exports, background jobs, cacheable responses, and client/server divergence.
3. Use low-noise blackbox probes to learn reactions. Record status codes,
   headers, redirects, body differences, cookies, cache behavior, side effects,
   async events, and server/client disagreement.
4. Turn observations into branches: what state changed, what component consumed
   it, what authority decision could drift, what invariant was assumed?
5. Hand narrow input-reaction questions to `proteus-fuzzing`; hand side-effect chains to
   `proteus-chaining`; hand concrete blockers to Cicada; hand novelty/timeline questions
   to `proteus-web-intel`; hand edge-WAF / bot-manager / Tor-wide 403 blocks that hide an
   in-scope surface to `proteus-waf-bypass` before treating the surface as unreachable.

## Web Heuristics

- Think in workflows and state, not isolated requests.
- Compare roles, tenants, projects, sessions, browsers, runtimes, and replayed
  requests only where scope permits.
- Look for hidden side effects: queued jobs, generated previews, cache entries,
  webhooks, notifications, audit logs, exports, derived files, and delayed
  cleanup.
- Track interpretation drift between browser, API, edge/cache, backend, worker,
  storage, and third-party integrations.
- Prefer manual, readable probes before automation. Automation should preserve
  the story of the attack.

## Anti-Patterns

- Do not spray generic payloads or scanner checks.
- Do not batch multiple payload variations at one live endpoint in quick
  succession; that burst is a scanner signature that blocks you on pattern alone.
- Do not keep re-confirming a flaw on a live endpoint after the first positive
  signal; over-confirmation burns the source and blocks future PoC work.
- Do not treat 500s, noisy errors, or cosmetic client bugs as findings without
  root cause and realistic impact.
- Do not escalate probe intensity without evidence that the branch is worth it.
- Do not retry the same request shape after a 403/challenge/ban; it deepens the
  block and can trigger further defensive hardening.
- Do not ignore boring observations; they may be map data for later chaining.

Required output:

```json
{
  "scopeAndAttackerModel": "...",
  "workflowMap": [],
  "observedBehaviors": [],
  "stateAndSideEffects": [],
  "trustBoundaries": [],
  "candidateBranches": [],
  "probesRun": [],
  "negativeControls": [],
  "handoffs": [],
  "memoryToRecord": [],
  "contractSignature": {}
}
```

Before returning, delete all probe scripts, HTTP response dumps, captured
headers, cookies, body files, and temporary test scaffolding created
during this front.
