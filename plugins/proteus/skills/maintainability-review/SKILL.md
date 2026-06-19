---
name: maintainability-review
description: Run a strict structural code quality review focused on maintainability, abstraction quality, file growth, branching complexity, type boundaries, and architecture drift. Use when the user asks for a maintainability review, structural review, harsh code-quality review, deep code audit, review estrutural, review de manutenibilidade, review mais duro, or asks to look for simplification opportunities beyond correctness bugs.
---

# Maintainability Review

Use this skill for unusually strict reviews of code structure. Prioritize whether the change leaves the codebase easier to understand, extend, and test. Do not use this as a replacement for a normal correctness, security, or regression review; use it as an additional lens when the user wants stronger pressure on design quality.

## Execution Contract

After loading this skill, continue the user's requested review immediately. Do not stop after reading the skill and do not echo the skill text.

Default to reviewing the current git changes unless the user names another target:

1. Inspect `git diff --stat` and `git diff --name-only`.
2. Inspect the changed hunks for the files that matter.
3. Read only the surrounding code needed to judge the structure.
4. Stop exploring once each meaningful changed area has enough context for a high-confidence finding or a clear no-finding decision.
5. Produce the review. If there are no findings, say so instead of continuing to search.

Keep the pass bounded. Do not review the whole repository, chase every reference, or keep reading files looking for a perfect simplification. If more context would materially change the conclusion, state that as residual risk in the final review.

## Review Workflow

1. Inspect the diff and the surrounding code before judging structure.
2. Identify the behavior the change is trying to preserve or introduce.
3. Look for a simpler shape that would preserve behavior while deleting complexity.
4. Separate blocking maintainability regressions from optional improvements.
5. Keep findings actionable: explain the impact and point toward a concrete restructuring path.

## Approval Bar

Treat these as presumptive blockers unless the code gives a strong reason:

- The change preserves incidental complexity when a visible reframing could delete it.
- The change pushes a file from below 1000 lines to above 1000 lines.
- The change adds ad-hoc branching into an already busy flow.
- Feature-specific checks are scattered through shared or canonical code.
- A new abstraction, wrapper, cast, or optional contract makes the design more indirect without buying clarity.
- Logic lands in the wrong layer, package, service, or module when a canonical owner already exists.
- The implementation relies on silent fallback instead of making an invariant explicit.
- Related state updates become easier to leave half-applied.

Do not block on taste alone. If recommending a broad restructuring, show the smallest concrete path that would make the implementation materially simpler.

## What To Look For

- A code-judo move: a reorganization that makes branches, helpers, modes, or layers disappear.
- Repeated conditionals that imply a missing model, helper, dispatcher, or state machine.
- One-off booleans, nullable modes, or flags that complicate existing control flow.
- Thin wrappers or identity helpers that add indirection without improving the reader's model.
- Generic magic that hides simple data-shape assumptions.
- Cast-heavy code, unnecessary `any` or `unknown`, and optional params that obscure the real contract.
- Feature logic leaking into shared paths or implementation details leaking through public APIs.
- Bespoke helpers where the codebase already has a canonical utility.
- Sequential orchestration where independent work could stay clearer in parallel.
- Refactors that move complexity around but do not reduce the number of concepts a reader must hold.

## Preferred Remedies

Prefer remedies that reduce the number of concepts in play:

- Delete an unnecessary layer instead of polishing it.
- Reframe the state model so conditionals disappear.
- Move logic to the layer that already owns the concept.
- Extract a helper, pure function, subcomponent, policy object, dispatcher, or state machine only when it reduces real complexity.
- Split large files into focused modules before they become catch-all surfaces.
- Collapse duplicate branches into one clearer flow.
- Replace casts and optional fallbacks with explicit typed boundaries.
- Reuse canonical helpers instead of adding near-duplicates.
- Separate orchestration from business logic when mixing them makes the flow hard to reason about.
- Make related updates more atomic when partial state would be confusing or dangerous.

## Output Format

Lead with findings, ordered by severity and confidence. Each finding should include:

- Severity: `Blocker`, `Major`, or `Suggestion`.
- Location: file and line when available.
- Impact: why the structure makes future work riskier or harder.
- Concrete path: the smallest credible restructuring direction.

Prefer a small number of high-conviction findings over a long list of minor nits. If there are no structural findings, say that clearly and mention any residual areas that were not validated.

## Tone

Be direct and demanding about maintainability without being rude. Do not soften real structural regressions into vague preferences. Avoid performative harshness; the goal is cleaner code, not theatrics.
