---
name: performance-scale-review
description: Run a strict review focused on performance bottlenecks, scalability, memory leaks, and algorithmic efficiency. Use when the user asks for a performance review, scalability audit, optimization pass, or to find bottlenecks.
---

# Performance and Scalability Review

Use this skill to evaluate code for how it will behave under heavy load, with large datasets, or over long periods of uptime. Your goal is to find algorithms, patterns, or resource mismanagement that will cause the system to slow down, run out of memory, or crash when scaled.

## Execution Contract

After loading this skill, continue the user's requested review immediately. Do not stop after reading the skill and do not echo the skill text.

Default to reviewing the current git changes unless the user names another target:

1. Inspect `git diff --stat` and `git diff --name-only`.
2. Inspect the changed hunks for the files that matter.
3. Read the surrounding code to understand loops, database queries, and data structures.
4. Extrapolate how the code behaves if collections contain 100,000 items instead of 10.
5. Produce the review. If no performance bottlenecks are found, state that the code appears scalable.

## Review Workflow

1. **Analyze Complexity:** Identify the Big-O time and space complexity of loops and recursive functions.
2. **Track Data Flow (I/O):** Look for network requests, database queries, or disk reads inside loops.
3. **Analyze Memory Footprint:** Look for large datasets loaded entirely into memory instead of being streamed or paginated.
4. **Evaluate Concurrency:** Check if independent tasks are being run sequentially when they could be parallelized (e.g., `Promise.all`).

## Approval Bar (What to look for)

Treat these as presumptive performance blockers:

- **N+1 Query Problems:** Executing a database query inside a loop instead of fetching relations in a single batch query.
- **Hidden O(N^2) Complexity:** Nested loops, or using methods like `.includes()`, `.indexOf()`, or `.find()` inside a `.map()` or `.filter()` over large arrays. (Recommend HashMaps/Sets for O(1) lookups).
- **Unbounded Queries:** Database queries without `LIMIT` or pagination.
- **Memory Leaks:** Unclosed closures, event listeners not removed, or accumulating data in global/module-scoped variables indefinitely.
- **Synchronous Blocking:** Using synchronous I/O operations (like `fs.readFileSync`) in an event-driven server (like Node.js) handling multiple requests.
- **Missing Indexes:** Querying databases on fields that are likely not indexed (extrapolate from context).
- **Over-fetching:** Requesting an entire row or massive JSON object when only one small field is needed.

## Output Format

Lead with findings, ordered by severity. Each finding should include:

- **Severity:** `Critical Bottleneck`, `Performance Flaw`, or `Micro-Optimization`.
- **Location:** File and line number.
- **The Bottleneck:** Explain the current Big-O or architectural flaw and how it fails at scale.
- **The Optimization:** Provide the specific, more efficient code alternative.

## Tone

Be forward-looking and analytical. Assume the data will grow. Differentiate between theoretical micro-optimizations (which can be ignored) and architectural bottlenecks (which will take down production).
