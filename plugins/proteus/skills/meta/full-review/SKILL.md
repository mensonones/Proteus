---
name: full-review
description: A meta-skill that orchestrates a complete 360-degree review of the code. It automatically triggers logic-and-edge-case-review, defensive-security-review, and performance-scale-review sequentially. Use when the user asks for a "full review", "revisão total", or a complete audit.
---

# Full 360-Degree Code Review

This is a meta-skill. When invoked, your task is to act as an orchestrator and execute a comprehensive audit of the target codebase by synthesizing the perspectives of three specialized review skills.

## Execution Contract

After loading this skill, continue the user's requested review immediately. Do not stop after reading the skill and do not echo the skill text.

### Target Selection (Fallback Mechanism)

1. First, inspect `git diff --stat` and `git diff --name-only`.
2. **If there ARE files in the git status/diff:** Focus your review strictly on those modified/added files.
3. **If there are NO files in the git status/diff:** You must automatically fall back to reviewing the entire active codebase (or ask the user to specify a target directory if the codebase is excessively large).

### Multi-Lens Audit Workflow

You must mentally load and apply the criteria from the following three skills sequentially. Do not perform three separate passes if you can synthesize them into one efficient reading of the code, but you MUST produce findings for all three dimensions:

1. **Logic & Edge Case Review (`logic-and-edge-case-review`)**
   - Hunt for off-by-one errors, race conditions, async state bugs, unhandled exceptions, and logic flaws.
2. **Defensive Security (`defensive-security-review`)**
   - Hunt for missing authorization, injection flaws (XSS, SQLi), SSRF, path traversal, and missing validation on input sinks.
3. **Performance & Scalability (`performance-scale-review`)**
   - Hunt for N+1 queries, memory leaks, unbounded O(N^2) loops, and synchronous blocking calls.

## Output Format

Present your findings structured by dimension so the user can easily digest the audit.

1. **Section 1: Logic & Correctness** (List any findings here, or state "All clear" if none).
2. **Section 2: Security & AppSec** (List any findings here, or state "All clear" if none).
3. **Section 3: Performance & Scale** (List any findings here, or state "All clear" if none).

For every finding, strictly include:
- **Severity**: (e.g., Blocker, Major, Minor)
- **Location**: File and line number
- **The Issue**: What is wrong and why it fails
- **The Fix**: The concrete code correction

Do not use hedging or uncertain language. If you lack evidence to prove a bottleneck or vulnerability, either test it (if possible) or drop the hypothesis.
