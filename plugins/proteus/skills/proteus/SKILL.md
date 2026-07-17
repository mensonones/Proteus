---
name: proteus
description: "Explicit Codex CLI entrypoint for the complete Proteus continuous vulnerability research workflow. Use when the user invokes $proteus or asks to start, resume, plan, or coordinate a Proteus campaign across a target codebase. This entrypoint routes to the full continuous-vuln-research coordinator; it is not a reduced review mode."
---

# Proteus Entrypoint

Treat the user's request following this skill invocation as the objective for a
complete Proteus coordinator run.

Load the sibling `continuous-vuln-research/SKILL.md` skill completely and follow
its research contract, target-context detection, memory recovery, planning,
delegation, validation gates, checkpointing, and final decision discipline. If
the host exposes skills through a selector, activate `continuous-vuln-research`.
If it only exposes filesystem resources, resolve that skill relative to the
installed Proteus plugin root.

Do not stop after explaining this routing step. Continue with the requested
research work. Load tactical skills such as `mobile-reversing`, `chaining`,
`poc-exploit`, or `web-intel` only when the coordinator determines they fit the
target and current branch.
