# Fork Differences: Proteus (Custom Local Build)

This repository is a customized fork of the upstream **Proteus (v2.1.4 Chimera Architecture)**. While it benefits from the latest engine updates, it maintains strict local customizations tailored for professional, continuous, and stealthy vulnerability research.

Here is a summary of the unique features present in this fork that differ from the root repository:

## 1. Cross-Wave Delta Analysis
The upstream repository removed the temporal tracking of bugs across multiple rounds. This fork **restored and expanded** the Delta Analysis engine:
- **`deltaStatus` Metadata:** Hypotheses are tracked with states like `new`, `regression`, or `persistent`.
- **Database & CLI Integration:** Upgraded SQLite schema, Zod validation, and CLI commands (`proteus list hypotheses --delta-status`) to natively support delta filtering.
- **Why it matters:** It prevents "report fatigue" in CI/CD continuous scanning, ensuring the team only sees genuine regressions or newly introduced vulnerabilities across consecutive campaign waves.

## 2. Ephemeral Tor & Operational Hygiene (Stealth)
Upstream Proteus agents make direct network calls, exposing the researcher's IP address. This fork enforces strict **Operational Security (OpSec)**:
- **Mandatory Proxychains:** The Coordinator and all subagents are instructed to route all HTTP/HTTPS traffic through `proxychains4` pointing to a local Tor SOCKS5 proxy.
- **`tor-ephemeral.sh` Script:** A custom lifecycle script that bootstraps, enforces (via kernel `iptables` **and** `ip6tables`, dropping all non-Tor outbound TCP **and** UDP over both IPv4 and IPv6 — so direct `webfetch`, `curl`, and plaintext DNS all fail closed instead of leaking), and purges the Tor process. Tor's own traffic is allowed by process owner (`--uid-owner`, auto-detected or via `TOR_UID`) so new circuits keep building under lockdown.
- **8-Step Trace Cleanup:** Every agent contract includes a rigorous hygiene checklist (deleting proxy captures, unsetting credentials, spacing shell commands) executed before every handoff.

## 3. Anti-Slop & Adversarial Refutation
This fork enhances the robustness of the **Skeptic (Devil's Advocate)** agent and the general reporting constraints:
- **Stronger Gating:** Added stringent Anti-Hedging rules that prevent LLMs from generating speculative, "noise" reports. Agents must prove their claims via 11 mandatory Gates (G1-G11) before promoting a candidate.

## 4. Custom Proprietary Skills & Mass Installer
Unlike the root repo, this fork ships with advanced, proprietary local skills tailored for deep code review:
- **Skills:** `maintainability-review`, `logic-and-edge-case-review`, `defensive-security-review`, `performance-scale-review`, and `full-review`.
- **`install:all-skills` Script:** Added to `package.json` to seamlessly deploy these custom skills across all local AI assistant environments (Codex, OpenCode, Claude Code) in a single command, streamlining onboarding for the research team.

## 5. Agentic Exploit Sandbox (Cicada)
This fork modifies the **Cicada** agent and the `poc-exploit` skill to enforce 100% autonomous runtime verification. Instead of just static exploits, the agent now mandates the generation of a `docker-compose.yml` to spin up a fully isolated, ephemeral lab modeling the target. The exploit is executed in this 512MB RAM-limited sandbox, and the runtime output acts as irrevocable proof to disarm the Skeptic gate.

## 6. 0-Day Discovery Agent (Maverick)
To combat "Prompt Schizophrenia" when hunting for novel vulnerabilities, this fork introduces the **`proteus-maverick`** agent. Operating under strict prompt isolation, Maverick ignores all standard OWASP bugs and technical injections. Its sole directive is to apply First Principles and Lateral Thinking to abuse legitimate features and break the business logic state machine. It is triggered optimally in a second wave (Round 2 / Replan) after the application's invariants and intended business logic have been fully mapped by Libris and Argus, feeding 0-day theories directly to the Skeptic for validation.
