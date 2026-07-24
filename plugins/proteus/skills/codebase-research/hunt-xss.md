---
name: hunt-xss
description: "Hunting skill for XSS vulnerabilities in source code. Focuses on dangerous sinks, sanitizer bypasses, and framework-specific escaping flaws."
version: 1.0.0
author: Proteus
license: GPL-3.0-or-later
metadata:
  proteus:
    tags: [xss, codebase, source-review, frontend]
    category: redteam
---

# Hunt XSS (Cross-Site Scripting)

This skill guides the analysis of a codebase for Cross-Site Scripting (XSS) vulnerabilities. Unlike dynamic blackbox testing, codebase research for XSS requires tracing data flow from user-controlled sources (API responses, URL parameters, file uploads) to dangerous rendering sinks in the frontend code.

## When to Use

Use this skill when analyzing frontend code (React, Vue, Angular, Svelte, vanilla JS) or backend templating engines (ERB, Jinja, Twig, Blade) where user-controlled data is rendered into HTML.

### ⚠️ CRITICAL: Presence ≠ Exploitation

**Reflection of HTML tags does NOT mean XSS is exploitable.** Modern frameworks escape text by default. Before flagging a finding as XSS, you MUST verify the sink in the code:

| Framework | Default Behavior | XSS Possible Only With |
|-----------|-----------------|----------------------|
| React/JSX | Escapes all text | `dangerouslySetInnerHTML`, `innerHTML` on refs |
| Vue | Escapes `{{ }}` | `v-html` directive |
| Angular | Escapes `{{ }}` | `[innerHTML]` binding |
| Svelte | Escapes `{ }` | `{@html}` tag |
| Next.js RSC | Escapes JSX text | `dangerouslySetInnerHTML` in components |
| Plain HTML/JS | Does NOT escape | `innerHTML`, `document.write()`, `eval()`, `insertAdjacentHTML` |
| Rails/ERB | Escapes by default| `html_safe`, `raw`, `sanitize` (with dangerous allowlists) |

**Codebase Verification Checklist:**
1. ✅ **Source:** Is the data user-controlled (e.g., from DB, URL, API)?
2. ✅ **Sink:** Is the data passed to a dangerous sink WITHOUT escaping?
3. ✅ **Validation/Sanitization:** Are there sanitizers in place (e.g., DOMPurify)? Are they configured securely or can they be bypassed?

## High-Value Code Patterns

Look for these patterns during source code review:

- **Admin/Internal Panels:** Often have less strict sanitization or trust input from the database implicitly.
- **Markdown/Wiki Renderers:** Custom parsers or insecure configurations of marked.js, Kramdown, etc.
- **File Uploads (SVG):** SVGs are XML and can execute JavaScript. Check if the backend allows SVG uploads and if they are served inline or without CSP.
- **PostMessage/DOM:** Event listeners (`window.addEventListener('message')`) that process data insecurely.

## Step-by-Step Codebase Hunting Methodology

1. **Grep for Dangerous Sinks:** Start by searching the codebase for known dangerous sinks.
2. **Trace the Data Flow (Taint Analysis):** Once a sink is found, trace the variable backward. Where does the data come from? If it's hardcoded, it's safe. If it comes from an API, URL, or database (Stored XSS), it's potentially vulnerable.
3. **Analyze Sanitization Logic:** If a sanitizer is used (e.g., DOMPurify, sanitize-html), check its configuration. Are dangerous tags (`<style>`, `<math>`, `<svg>`) or attributes allowlisted?
4. **Identify Client-Side Routing/URL processing:** Look for code that parses `window.location.hash` or `window.location.search` and uses it to render content or evaluate logic.
5. **Check Template Helpers:** In backend templating (e.g., Rails), search for instances where developers explicitly disable escaping (`.html_safe`, `raw()`).

## Grep Patterns for Source Code Review

Use these patterns with your search tools to find potential XSS sinks:

**JavaScript / TypeScript / Frameworks:**
```bash
dangerouslySetInnerHTML
v-html
\[innerHTML\]
\{@html\}
innerHTML\s*=
outerHTML\s*=
insertAdjacentHTML
document\.write\(
eval\(
setTimeout\([^,]*\s*,
setInterval\([^,]*\s*,
location\.hash
location\.search
```

**Backend Templating (e.g., Ruby on Rails):**
```bash
\.html_safe
raw\(
sanitize\(
```

## Common Root Causes in Code

1. **Trusting `html_safe` / `raw`:** Developers mark strings as safe after partial/incorrect sanitization.
2. **Insecure Sanitizer Allowlists:** Allowing `style` alongside `math` or `svg` creates mXSS (mutation XSS) opportunities.
3. **Markdown-to-HTML Pipelines:** Missing a final sanitization step after rendering markdown to HTML.
4. **SVG treated as images:** Backend allows `.svg` uploads, and frontend renders them without `Content-Disposition: attachment` or CSP constraints.
5. **postMessage missing origin checks:** `window.addEventListener('message', (e) => { eval(e.data) })` without checking `e.origin`.

## Gate Validation (Before Promoting to Report)

1. **Root Cause:** Exactly which file and line number contains the dangerous sink?
2. **Attacker Input:** How does the attacker inject the payload (e.g., modifying their bio, sending a specific URL parameter)?
3. **Bypass/Sink Confirmation:** Why is the framework's default escaping not protecting this? (e.g., "Developer explicitly used `dangerouslySetInnerHTML` on line 42").
