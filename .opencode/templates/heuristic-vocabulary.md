# Proteus Heuristic Vocabulary

Canonical slugs for the `heuristicCoverage` field of the contract signature.

**This is not a checklist.** It is a shared vocabulary so the coordinator can
audit *declared* coverage against *skipped* surfaces and catch silent omission.
Nobody has to "cover every slug". The hunt stays primitive-first per the base
contract — bug classes are listed here only as *instances* of a heuristic
family, never as the search frame. A surface that is genuinely out of scope for
a family is fine; an in-scope surface that no role ever probed for a family it
is exposed to is the gap this vocabulary exists to surface.

## How to use it

- **Specialists:** in `heuristicCoverage`, list the family slugs you actually
  reasoned about on your assigned surface. Do not pad. Declaring
  `interpretation-gap` means you looked for it, not that you want credit for it.
- **Coordinator:** after each round, cross the union of declared
  `heuristicCoverage` against the recorded surfaces (selected *and* skipped).
  For every `(surface, family)` pair where the surface exposes the family's
  signals but no role declared it and no "skipped surfaces and why" note
  justifies the gap, either assign it to the owning role or record an explicit
  waiver with a reason. An unexplained gap is a research-state defect, not a
  finding.
- **Slugs are stable.** Add new families by extending this file, not by
  inventing ad-hoc strings in a single agent output. If you need a slug that is
  not here, add it here first so it becomes auditable.

## Families

Each family is a primitive-level lens. `signals` tell you when the family is
in-scope for a surface. `instances` are example bug classes, for local context
only. `owner` is the role that carries the family when a surface strongly
exhibits it (the coordinator still assigns per surface).

### `interpretation-gap`
One input is parsed or interpreted differently by two consumers, so a value that
is inert to one is active to another.
- **signals:** parsers, templating, serializers, query builders, string→structure
  boundaries, encoders/decoders, mixed-format payloads.
- **instances:** SQLi, XSS, SSTI, deserialization, command injection, header/
  request smuggling, XXE.
- **owner:** argus / chaos

### `trust-boundary`
Attacker-influenced data crosses a point where control, origin, or authority
changes hands and is treated as more trusted than it is.
- **signals:** outbound fetchers, file path assembly, redirects, cross-origin
  flows, webhooks, import/include mechanisms, server-initiated requests.
- **instances:** SSRF, path traversal, LFI/RFI, open redirect, CSRF.
- **owner:** argus / loom

### `authorization`
The actor/operation/object matrix has missing, inconsistent, or bypassable
enforcement.
- **signals:** authenticated routes, object references by id, multi-tenant data,
  role/permission checks, admin surfaces, ownership predicates.
- **instances:** IDOR/BOLA, vertical/horizontal privilege escalation, tenant
  isolation gaps, missing/duplicated enforcement checks.
- **owner:** janus

### `invariant-violation`
An assumption the code silently relies on can be made false — business logic,
ordering, bounds, or state-machine constraints.
- **signals:** multi-step flows, balances/quotas/limits, discounts/pricing,
  status transitions, numeric bounds, idempotency assumptions.
- **instances:** business-logic abuse, state-machine drift, integer/bounds
  errors, feature weaponization.
- **owner:** maverick

### `competing-truth`
Two sources of truth disagree, or a value is read at a different time than it is
acted on.
- **signals:** caches and cache keys, replicas, denormalized data, check-then-use
  gaps, distributed state, retries.
- **instances:** cache poisoning / cache-key confusion, TOCTOU, race conditions,
  desync.
- **owner:** chaos / loom

### `capability-amplification`
A small, seemingly low-impact primitive escalates into a materially larger one
through chaining.
- **signals:** arbitrary write/read primitives, partial secret exposure, SSRF to
  metadata, log/error leakage, template or config control.
- **instances:** write-primitive → RCE, SSRF → cloud creds, info leak → auth
  bypass, LFI → RCE.
- **owner:** loom / cicada

### `resource-lifecycle`
Allocation, cleanup, limits, or memory management can be driven into an unsafe
or exhausted state.
- **signals:** native/unmanaged code, unbounded input sizes, recursion, file/
  socket handles, allocation tied to attacker input, amplification.
- **instances:** memory-safety bugs (UAF, overflow), resource exhaustion / DoS,
  decompression bombs.
- **owner:** chaos / mimic

### `crypto-and-token`
Cryptographic, signing, or token-handling assumptions can be broken or sidestepped.
- **signals:** JWT/PASETO, signed cookies/URLs, password/reset flows, nonces,
  randomness sources, signature verification, session issuance.
- **instances:** JWT alg confusion, signature bypass, weak/predictable
  randomness, session fixation, replay.
- **owner:** argus / cicada

### `environment-divergence`
Runtime, deployment, build, or platform behavior differs from what the source
implies, opening gaps that do not exist "on paper".
- **signals:** Docker/WSL/native adapters, build steps, platform-specific paths,
  default configs, dependency/runtime version skew.
- **instances:** deploy-only misconfig, adapter divergence, path/case handling
  differences, build-time injection.
- **owner:** mimic

### `input-anomaly`
Malformed, boundary, or unexpected-shape input reaches a consumer that assumed
well-formed input — the fuzzing/edge lens that seeds the families above.
- **signals:** any parser, decoder, validator, canonicalizer, length/encoding
  handler, or format negotiator.
- **instances:** parser differentials, canonicalization bugs, encoding confusion,
  length/boundary faults.
- **owner:** chaos

## Maintenance

Keep families primitive-level and few. If a proposed slug is really just a bug
class, file it under the family it instantiates instead of adding it. The value
of this list is that it is short enough to audit against every surface in a
round; a sprawling per-CWE list would recreate the checklist this framework
deliberately rejects.
