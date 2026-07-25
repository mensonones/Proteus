---
name: defensive-security-review
description: Run a strict application security review (AppSec) focused on Git diffs. Use when the user asks for a security review of a PR, threat modeling on new changes, AppSec review, or wants to ensure no new vulnerabilities are introduced.
---

# Defensive Security Review

Use this skill to act as a strict Application Security (AppSec) reviewer. Unlike offensive red-team skills that hunt across the whole codebase, this skill focuses *defensively* on the specific lines of code being added or modified to prevent vulnerabilities from reaching production.

## Execution Contract

After loading this skill, continue the user's requested review immediately. Do not stop after reading the skill and do not echo the skill text.

Default to reviewing the current git changes unless the user names another target:

1. Inspect `git diff --stat` and `git diff --name-only`.
2. Inspect the changed hunks for the files that matter.
3. Read the surrounding code to trace where input comes from (source) and where it goes (sink).
4. Verify authentication and authorization boundaries for new endpoints.
5. Produce the review. If no security issues are found, state that the changes pass the defensive security check.

## Review Workflow

1. **Identify Inputs:** What data is controlled by the user in this diff (headers, params, JSON bodies, uploaded files)?
2. **Trace to Sinks:** Does that input flow into dangerous sinks without sanitization or parameterization? (e.g., SQL queries, DOM rendering, OS commands, filesystem paths).
3. **Check Auth/Authz:** If a new route/function is added, is it protected by the correct authentication middleware? Does it check authorization (e.g., IDOR checks - does user A own resource B)?
4. **Assume Hostility:** Assume every piece of data coming from outside the function is malicious.

## Approval Bar (What to look for)

Treat these as presumptive security blockers:

- **Missing Authorization (IDOR):** Fetching or modifying a record by ID without verifying the current user owns it.
- **Injection Flaws (SQLi, Command Injection):** String concatenation in SQL queries or passing user input to `exec`/`spawn`.
- **Cross-Site Scripting (XSS):** Bypassing framework protections (e.g., `dangerouslySetInnerHTML`) or failing to escape user input before rendering.
- **Server-Side Request Forgery (SSRF):** Making outbound HTTP requests to URLs partially or fully controlled by the user without strict allowlisting.
- **Mass Assignment:** Passing a full JSON payload directly into a database update without filtering out protected fields (like `is_admin` or `password`).
- **Path Traversal:** Concatenating user input into filesystem paths.
- **Hardcoded Secrets:** Committing API keys, passwords, or tokens in the code.

## Output Format

Lead with findings, ordered by severity. Each finding should include:

- **Severity:** `Critical Vulnerability`, `High Risk`, `Medium Risk`, or `Security Best Practice`.
- **Location:** File and line number.
- **The Threat:** What an attacker could do with this flaw.
- **The Remediation:** Concrete code fix (e.g., "Use a parameterized query instead of string concatenation").

## Tone

Be strictly defensive and paranoid. Treat missing validation as a bug, not a suggestion. Demand proof of safety rather than assuming it.
