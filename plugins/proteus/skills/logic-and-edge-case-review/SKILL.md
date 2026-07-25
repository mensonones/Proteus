---
name: logic-and-edge-case-review
description: Run a strict review focused on correctness, edge cases, off-by-one errors, race conditions, async state management, unhandled exceptions, and logic bugs. Use when the user asks to review logic, find bugs, test edge cases, review corretude, or perform a logic review.
---

# Logic and Edge Case Review

Use this skill for rigorously checking if the code *actually works* under all conditions, especially the uncommon ones. Prioritize finding bugs that cause crashes, data corruption, silent failures, or incorrect behavior. Do not focus on style, maintainability (unless it directly obscures logic), or performance (unless it causes a crash/timeout).

## Execution Contract

After loading this skill, continue the user's requested review immediately. Do not stop after reading the skill and do not echo the skill text.

Default to reviewing the current git changes unless the user names another target:

1. Inspect `git diff --stat` and `git diff --name-only`.
2. Inspect the changed hunks for the files that matter.
3. Read surrounding code necessary to trace the data flow and state changes.
4. Stop exploring once you have verified the core logic paths for the changed areas.
5. Produce the review. If no logical flaws are found, clearly state that the logic appears correct.

## Review Workflow

1. **Identify the Happy Path:** What is this code *supposed* to do when everything goes right?
2. **Identify the State Mutations:** What variables, database records, or memory structures are being updated?
3. **Attack the Edge Cases:**
   - What happens if inputs are empty, null, incredibly large, or malformed?
   - What happens if the network fails halfway through?
   - What happens if two users hit this code at the exact same time (race condition)?
4. **Isolate Blocking Bugs from Minor Issues:** Distinguish between a definite crash/data loss and a minor UI state glitch.

## Approval Bar (What to look for)

Treat these as presumptive blockers:

- **Off-by-One Errors:** Loop boundaries (`<` vs `<=`), array indexing, pagination logic.
- **Race Conditions:** Concurrent mutations of shared state without locking, async/await sequencing issues, TOCTOU (Time-of-check to time-of-use) bugs.
- **Unhandled Promises/Exceptions:** Async operations that don't catch errors, risking unhandled rejections that crash the process or leave state dangling.
- **Resource Leaks:** Opening files/connections without `finally` blocks to close them.
- **Null/Undefined Dereferences:** Assuming a deeply nested property exists without checking.
- **State Desync:** Updating the UI before the backend confirms, or partially updating a database record without a transaction.
- **Type Mismatches at Boundaries:** Trusting external API responses to perfectly match an internal interface without validation.

## Output Format

Lead with findings, ordered by severity. Each finding should include:

- **Severity:** `Critical Bug`, `Logic Flaw`, or `Edge Case Suggestion`.
- **Location:** File and line number.
- **The Bug:** Explain exactly *how* it fails, tracing the steps.
- **The Fix:** Provide the specific code correction required to fix the logic.

## Tone

Be analytical, precise, and objective. Show the exact path to failure. Do not guess; if you suspect a race condition but aren't sure, state it as a "Potential Race Condition requiring verification" rather than a definite bug.
