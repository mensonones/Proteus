---
name: waf-bypass
description: Design calibrated WAF evasion and filter bypass probes for Proteus surfaces behind edge WAFs (Akamai, Cloudflare, AWS WAF, F5, ModSecurity). Use when edge-layer 403s, deny pages, bot-manager challenges, or payload-triggered blocks hide an in-scope application from blackbox research. The goal is to learn exactly how the filter discriminates benign from suspect input — one dimension at a time — then pass only what matters, never to spray payloads or evade rate limits.
---

# Proteus WAF Bypass

Use this skill when a web surface is reachable but an edge WAF, bot manager,
or request filter rejects probes before the application can be studied. Treat
the filter as a blackbox component with its own interpretation rules, not as a
wall to smash. A bypass is only interesting when it uncovers or delivers a
finding that the filter was actively hiding; a bypass that leads nowhere is
map data, not a candidate.

Follow the Proteus base research contract. Respect program rules, rate limits,
and scope at all times: bypassing an edge filter to study an in-scope asset is
authorized research; using any bypass to exceed rate limits, brute force,
spray credentials, or attack out-of-scope assets is not.

## Authorization

This skill is for **authorized security testing only**: bug bounty programs
with an active Safe Harbor / scope, your own or client-authorized labs and
environments, and sanctioned red-team engagements. Confirm the target is in
scope and that the engagement permits active probing before running any
probe. If you are not sure the target is authorized, stop and ask. The
methodology here is dual-use: against an owned or in-scope target it is a
legitimate research technique; against anything else it is unauthorized
access. No bypass produced by this skill authorizes exceeding program rate
limits, evading access controls you were not meant to test, or touching
out-of-scope assets.

The companion automation is `scripts/waf-probe.sh`, bundled with this skill:
it executes a bounded block/pass matrix — baseline
fingerprint, method differential, encoding parity, structural ambiguity, and
header normalization — with a request budget, explicit rate limiting, and
raw artifacts for evidence.

## Operating Method

1. **Fingerprint the filter before touching payloads.** Identify the vendor and
   deployment from response signatures: `Server` header values (`AkamaiGHost`,
   `cloudflare`, `BigIP`, `envoy` + Akamai `_abck`/`bm_sz` cookies, AWS WAF
   `x-amzn-RequestId` + `403 Forbidden` HTML), deny-page fingerprints
   (`failover-waf.*`, `Access Denied`, reference IDs), challenge types
   (JavaScript, CAPTCHA, cookie stamping), and `Retry-After`/`429` semantics.
   Record the exact block signature: a 403 with `Server: AkamaiGHost` +
   `failover-waf` reference ID is an edge block; the same path returning 404/500
   with an app `Server` header is an app-level response. Never mix the two in
   evidence.

2. **Classify the block before bypassing.** Three root causes produce 403s, and
   each has a different remedy:
   - **Egress reputation** — the filter denies by source IP/ASN. Diagnostic:
     the identical benign request is denied from multiple exits and egresses.
     Remedy: egress rotation (NEWNYM, exit selection, authorized residential),
     not payload mutation.
   - **Allowlist posture** — the asset is internal-only (403 for every external
     source, residential included). Diagnostic: benign request denied from
     residential IP too. Remedy: kill the surface as external; record evidence.
   - **Payload signature** — the filter inspects content. Diagnostic: benign
     baseline passes on the same egress while a minimal suspect mutation blocks.
     Remedy: the calibrated mutation strategy below.
   One request answers the egress-vs-payload question: replay the exact benign
   baseline and a single minimal suspect payload from the same egress, then
   compare. Change one variable per request, never two.

3. **Build a block/pass matrix.** For each mutation family, run baseline,
   suspect, and mutant probes and record `block | pass | normalized` outcomes.
   A family is useful only when it flips the outcome on a relevant payload.
   Record negative controls: the benign baseline must stay `pass` for the whole
   session, or egress drift invalidates every measurement.

## Mutation Strategy

Mutate one dimension at a time and keep a matrix. Start with the cheapest
discriminators, escalate only families that flip block→pass, and escalate
only when the passed variant still carries the semantic the target needs.

- **Method differential.** Same URL and body, different HTTP method
  (GET/POST/PUT/PATCH/OPTIONS/HEAD). WAFs frequently filter GET query strings
  but not bodies, or filter a specific method. Verify the application still
  honors the method before claiming a bypass.
- **Encoding parity.** URL-encode, double-encode, HTML entities, Unicode
  case-folding and normalization forms, `%00` and other trivially-stripped
  bytes, charset confusion (`Content-Type: application/x-www-form-urlencoded;
  charset=UTF-7`), JSON unicode escapes in bodies, CRLF/tab/vertical-tab
  insertion inside tokens. The filter may normalize differently than the
  application; parity differences are the core primitive.
- **Structural ambiguity.** Parameter pollution (duplicate params), path
  parameter syntax (`/path;param=x`), path normalization (`//`, `/./`, `/%2e/`,
  backslashes), trailing delimiters, semicolons, fragment-style suffixes, and
  oversized or empty values. Filters canonicalize paths differently from
  application routers.
- **Header normalization.** Case variation, duplicate headers, header-value
  folding, `X-Forwarded-For`/`X-Real-IP` trust edges only where the
  application is documented or demonstrably IP-trusting (never to disguise
  abusive volume; that violates program rules). Rotate `User-Agent` between
  known-good browser fingerprints when reputation scoring is suspect.
- **Signature-aware token mutation.** Only after context is understood:
  comment insertion in SQL (`/**/`, `--+`, line comments), case mixing in
  interpreters, whitespace/delimiter alternatives (`|`, `||`, `and`/`&&`),
  HTML/JS context escapes for XSS. This family is last: it needs a real
  injection hypothesis, not folklore.
- **Body framing.** Multipart boundary confusion, `Content-Type` switching
  (form vs JSON vs multipart), charset metadata, chunked transfer framing.
  Mostly relevant to payload-in-body WAFs.

## Validated Lab Evidence

A validation lab (Flask SQLi app behind `owasp/modsecurity-crs:nginx`
at PL1, `PARANOIA=1`) validated the families against CRS 4.28. Reproduced
results (run with `scripts/waf-probe.sh -u http://127.0.0.1:8082/search -p "x' OR 1=1 --" -k q`):

- Baseline raw SQLi and all encodings/hpp/unicode/JSON/multipart variants:
  `403` (CRS 942100 libinjection fingerprint, 548B deny page).
- Method differential: all methods blocked (CRS 911100 adds PUT/PATCH/OPTIONS).
- Structural path tricks (`/search;q=...`, trailing-dot, `/%2e/`, backslash)
  normalize to the same route and never reach the app (`404` app response).
- **Bypass: body multiline framing.** `q=x' OR 1=1 --%0d%0afoo=bar` as
  form-urlencoded body with the payload NOT in the URL passes the WAF (`200`)
  and reaches the SQL parser (app returns `SQL_ERROR near "foo"`; a lone
  `q=x'` also returns `SQL_ERROR`, proving the value reaches SQLite).
  Root cause visible in the ModSecurity audit log: libinjection (942100) does
  not fingerprint `... OR 1=1 --\r\n...` when a line comment is followed by
  CRLF + trailing tokens, while the same SQL without CRLF (`q=x' OR 1=1 -- foo`)
  is blocked (`403`). Control pair: identical SQL, only the `%0d%0a` differs.
- Notable non-bypasses (recorded kills): `charset=UTF-7` and `charset=UTF-16LE`
  bodies are blocked at PL1 (charset not honored for decoding by the app;
  CRS 920250 rejects non-UTF8), chunked transfer is reassembled and inspected
  (`403`), and `OR '1'='1` keeps its libinjection fingerprint even with CRLF.
- Lesson: fingerprint classifiers with comment stripping (libinjection) can be
  defeated by line-comment + CRLF framing that survives app-side decoding.
  Always verify the passed variant against the app response — a `200` alone
  means nothing unless the app interpreted the value.

## Feedback Loop

- Each passing mutant must be re-verified against the block signature AND
  against the application's interpretation: did the app see the value you
  intended? A mutant that passes the WAF but is also stripped by the app is a
  dead end.
- After one family succeeds, re-test the baseline from the same egress to
  confirm the filter did not change state (e.g., temporary IP trust).
- When multiple families pass, prefer the smallest, most reliable mutation for
  the report; enumerate the matrix as evidence, not a payload zoo.
- Record every killed family with the discriminator that killed it (e.g.,
  "double-encoding normalized by filter AND app — no parity gap").

## Compliance and Guardrails

- Respect program rate limits (typically ≤3 req/s): add explicit sleeps, and
  batch matrix probes so a family costs a handful of requests, not dozens.
- Never use a confirmed bypass to exceed rate limits, brute force, credential
  spray, or enumerate out-of-scope assets.
- Do not attack the WAF vendor's infrastructure; study only the filter behavior
  visible from the in-scope origin.
- Prefer Tor/proxychains routing per the base contract; when the program
  requires an identifying header, attach it to every request, on any egress.
- A method/egress differential that bypasses the WAF but delivers no finding is
  only reportable if the program explicitly covers WAF-posture issues (check
  the program policy; many treat "WAF bypass" alone as out of scope).

## Reporting Evidence

- Exact request/response pairs for baseline, blocked suspect, and passing
  mutant (headers + body, truncated only for length).
- The filter fingerprint (vendor, deny-page signature, reference IDs) proving
  the block was edge-layer, plus the app-level fingerprint proving the passed
  request reached the application.
- The block/pass matrix with one-mutation-per-row, and negative controls.
- What the bypass enables: the specific vulnerability or data access that was
  previously unreachable, and why the filter was the only barrier.

## Handoff

Feed passing mutants to `proteus-chaining` or `proteus-cicada` when a
vulnerability branch becomes reachable, and to `proteus-chaos` when the filter
itself (canonicalization, cache-key, header parsing) becomes the hypothesis.
Record the matrix, fingerprints, and kill criteria as evidence records so
future rounds do not re-walk denied families on the same target.
