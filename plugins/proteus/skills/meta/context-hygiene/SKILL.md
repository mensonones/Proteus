---
name: context-hygiene
description: "Skill to force agents to condense memory and discard large raw logs to prevent context bloat across long-running campaigns."
version: 1.0.0
author: Proteus
license: GPL-3.0-or-later
metadata:
  proteus:
    tags: [meta, hygiene, performance, memory]
    category: meta
---

# Context Hygiene & Memory Condensation

As Proteus agents execute long-running tasks, raw tool outputs (e.g., massive grep results, full HTTP response bodies, lengthy stack traces) can quickly saturate the context window, degrading the model's reasoning capabilities (context bloat) and leading to hallucinations or hedging.

## When to Use

- At the end of any significant round of codebase research.
- Whenever a large volume of raw data has been parsed and an insight has been extracted.
- When preparing data to hand off to the Coordinator or another agent (e.g., Argus passing findings to Loom or Skeptic).

## Methodology: "Condense and Discard"

1. **Extract Only the Invariant:** Instead of remembering a 500-line stack trace or 50 instances of a grep match, extract the core security invariant. 
   - *Bad:* Saving all 50 occurrences of `JSON.parse`.
   - *Good:* "The application relies on `JSON.parse` globally but uniformly wraps it in a Zod validator at the middleware layer, EXCEPT in `src/legacy/importer.ts`."
2. **Record as Evidence:** Use the `record evidence` command in the Proteus CLI to store this condensed insight into the SQLite memory. Give it a descriptive title (e.g., `Condensation: JSON Parse Usage`).
3. **Discard the Raw Log:** Do not copy-paste raw outputs into your final agent output or hypotheses descriptions. Keep the `body` of the hypothesis strictly focused on the logical impact and the specific boundary. 
4. **Use Pointers:** If raw data is absolutely necessary, write it to a temporary file (`scratch/`) and include a file pointer (e.g., "Full HTTP trace saved in `scratch/trace-123.txt`") rather than dumping it into the context.

## Enforcing Anti-Hedging through Hygiene

By stripping away excess conversational padding and raw data, agents are forced to deal only with the logical claims. This directly supports the Anti-Hedging rule: 
- If the condensed evidence does not explicitly support the claim, you MUST state "INSUFFICIENT EVIDENCE" and drop the hypothesis. 
- You cannot hide weak hypotheses behind large walls of raw context.
