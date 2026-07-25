---
name: proteus
description: "Explicit Codex CLI entrypoint for the complete Proteus continuous vulnerability research workflow. Use when the user invokes $proteus or asks to start, resume, plan, or coordinate a Proteus campaign across a target codebase. This entrypoint routes to the full continuous-vuln-research coordinator; it is not a reduced review mode."
---

# Proteus Entrypoint

Treat the user's request following this skill invocation as the objective for a
complete Proteus coordinator run.

## Mandatory Tor Preflight

After reading this entrypoint, make the Tor bootstrap the first tool action.
Run it before loading the sibling coordinator skill, inspecting the target,
planning, or calling any Proteus MCP tool:

```bash
bash plugins/proteus/scripts/tor-ephemeral.sh bootstrap
```

Resolve the script from the installed Proteus plugin root when the current
workspace is not the Proteus source repository. Do not treat a written plan,
an MCP status call, or a network-free repository inspection as satisfying this
preflight. If the command cannot run because the script, shell, package manager,
or required permission is unavailable, stop and report the bootstrap as the
blocker. Do not continue the campaign without an established Tor circuit.

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
