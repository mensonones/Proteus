---
name: hunt-ssrf
description: "Hunting skill for SSRF vulnerabilities in source code. Focuses on URL fetch operations, redirect following, and missing host validations."
version: 1.0.0
author: Proteus
license: GPL-3.0-or-later
metadata:
  proteus:
    tags: [ssrf, codebase, source-review, backend]
    category: redteam
---

# Hunt SSRF (Server-Side Request Forgery)

This skill guides the analysis of a codebase for Server-Side Request Forgery (SSRF) vulnerabilities. In a codebase research context, hunting SSRF involves tracking user-controlled input (like URLs or partial paths) into HTTP client libraries or URL fetching mechanisms, and evaluating the validation logic surrounding them.

## When to Use

Use when the codebase has features that fetch a URL, import data from a remote source, generate previews/screenshots, process webhooks, or render documents (e.g., PDF generation). 

## High-Value Code Patterns

- **Webhook/Callback registration:** Handlers that store and later fetch user-defined URLs.
- **Link preview / URL fetching:** Code that takes a URL, fetches it, and parses the metadata.
- **Headless browsers (Puppeteer, Playwright):** Code that uses headless browsers for screenshots or PDF rendering. These are prime SSRF vectors because they can execute JS and access cloud metadata.
- **XML/DSPL/CSV parsers:** Code that imports files that may reference external schemas or entities.
- **Proxy/API aggregation:** Code that forwards requests to other internal services based on user input.

## Step-by-Step Codebase Hunting Methodology

1. **Grep for HTTP Clients:** Search the codebase for instances where HTTP requests are made.
2. **Trace the URL Parameter:** For each HTTP client call, trace the URL parameter backward. Is any part of it controlled by user input?
3. **Analyze Validation/Allowlisting:** If user input is used, check the validation logic.
   - Is there a blocklist (e.g., blocking `localhost`, `169.254.169.254`)? Blocklists are often bypassable (e.g., via `0177.0.0.1`, DNS rebinding, redirect chains).
   - Is there an allowlist? Are there parser differentials where the allowlist checker parses the URL differently than the HTTP client?
4. **Check Redirect Configuration:** Does the HTTP client follow redirects automatically? (e.g., `follow_redirects=True`). If so, a validated URL might redirect to a blocked internal IP.
5. **Check for Cloud Environments:** Is the application deployed on AWS, GCP, or Azure? If so, the impact of SSRF is critical due to IMDS (Instance Metadata Service) exposure.

## Grep Patterns for Source Code Review

Use these patterns to find potential SSRF sinks:

**JavaScript / Node.js:**
```bash
fetch\(
axios\.get\(
axios\.post\(
http\.get\(
https\.get\(
request\(
node-fetch
XMLHttpRequest
```

**Python:**
```bash
requests\.get\(
requests\.post\(
urllib\.request\.urlopen\(
httpx\.get\(
aiohttp\.ClientSession
```

**Go:**
```bash
http\.Get\(
http\.Post\(
http\.NewRequest\(
```

**Java:**
```bash
new URL\(
HttpURLConnection
HttpClient\.newBuilder
```

**Headless Browsers & Parsers (High Priority):**
```bash
puppeteer\.launch
page\.goto\(
wkhtmltopdf
libxml_disable_entity_loader\(false\)
```

## Common Root Causes in Code

1. **Blind Trust:** Developers trust user-supplied URLs for fetching remote resources without any validation.
2. **Redirect Bypasses:** The code validates the initial URL but configures the HTTP client to follow redirects automatically (`allow_redirects=True`), allowing the attacker's server to redirect to `169.254.169.254`.
3. **Incomplete Blocklists:** Blocking `127.0.0.1` but forgetting IPv6 `[::1]`, decimal IP `2130706433`, or not preventing DNS rebinding (validating an IP once, but the HTTP client resolves it again).
4. **URL Parser Differentials:** The validation logic (e.g., regex or a specific URL parsing library) parses the hostname differently than the actual HTTP client (e.g., `http://evil.com@127.0.0.1/`).
5. **Headless Browser Context:** Executing attacker-controlled HTML/JS in a headless browser (for PDF generation) running in a cloud environment without network sandboxing.

## Gate Validation (Before Promoting to Report)

1. **Root Cause:** Which HTTP client or fetch operation uses user-controlled input?
2. **Attacker Input:** What is the vector (e.g., webhook URL, import parameter)?
3. **Bypass/Validation:** Why is the existing validation (if any) insufficient? (e.g., "The code checks for `127.0.0.1` but does not block `0.0.0.0` or follow redirects").
4. **Impact:** If deployed in AWS/GCP, does it have access to IMDS? Does it leak internal network details?
