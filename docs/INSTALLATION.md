# Proteus Installation

Proteus has three install surfaces:

- CLI/runtime: the `proteus` and `proteus-mcp` commands.
- Codex plugin: installed through a Codex plugin marketplace.
- Claude Code plugin: `/proteus:proteus`, plugin subagents, and MCP config.
- OpenCode project support: `/proteus`, project skills, specialist agents,
  templates, and MCP config.

Install the CLI first. The plugin instructions can load without it, but target
memory, exports, labs, and MCP tools depend on the `proteus` and `proteus-mcp`
runtime commands.

## 1. CLI Install From GitHub

```powershell
npm install -g https://codeload.github.com/Vyntra-Research/Proteus/tar.gz/refs/heads/main
proteus --version
```

Expected shape:

```text
@rafabd1/proteus 2.1.4
```

The GitHub tarball install uses the committed `dist/` runtime and has no
install-time build lifecycle, so it does not need to compile TypeScript on the
installing machine.

After publishing to npm, the registry install should be:

```powershell
npm install -g @rafabd1/proteus
proteus --version
```

## CLI Upgrade

```powershell
npm install -g https://codeload.github.com/Vyntra-Research/Proteus/tar.gz/refs/heads/main
```

After npm publishing:

```powershell
npm update -g @rafabd1/proteus
```

Pin a branch, tag, or commit:

```powershell
npm install -g github:Vyntra-Research/Proteus#main
```

## Local Development Install

```powershell
git clone https://github.com/Vyntra-Research/Proteus
cd Proteus
npm install
npm link
proteus --version
```

## 2. Codex Plugin Install

Codex supports marketplace sources in the form `owner/repo[@ref]`, Git URLs,
SSH URLs, or local marketplace root directories.

```powershell
codex plugin marketplace add Vyntra-Research/Proteus
```

Pin a ref:

```powershell
codex plugin marketplace add Vyntra-Research/Proteus@main
```

The marketplace file is:

```text
.agents/plugins/marketplace.json
```

It exposes the plugin at:

```text
plugins/proteus
```

Then register the MCP server from the CLI install:

```powershell
codex mcp add proteus -- proteus-mcp
```

In Codex, invoke the plugin with `@proteus`, for example:

```text
@proteus initialize continuous vulnerability research for this repository
```

Use `@proteus` as the normal entrypoint so Codex can load the plugin and choose
the main coordinator skill plus any specialist skill it needs. Slash-style skill
mentions are for explicitly targeting a single skill and are less ergonomic now
that Proteus ships multiple skills.

## 3. Claude Code Plugin Install

Claude Code support is experimental and has not been exhaustively tested yet.
Because Proteus is heavily focused on offensive security research, Claude
models may also apply safety restrictions that affect exploit-development,
chaining, or other offsec workflows.

Install directly inside Claude Code:

```text
/plugin marketplace add Vyntra-Research/Proteus
/plugin install proteus@proteus-marketplace
```

Then use `/proteus:proteus` from Claude Code.

The plugin starts its bundled Proteus MCP server automatically. If a host does
not load plugin-provided MCP servers, register the CLI runtime as a manual
fallback:

```powershell
claude mcp add -s user proteus -- proteus-mcp
```

## OpenCode Project Support

Install and configure OpenCode from the official project:

- OpenCode repository: <https://github.com/anomalyco/opencode>
- OpenCode docs: <https://opencode.ai/docs/>

Then install Proteus support in each workspace where OpenCode should load it:

```powershell
proteus opencode install --root C:\path\to\target
proteus opencode doctor --root C:\path\to\target
```

This writes project-local OpenCode files:

- `opencode.json` with a local MCP server named `proteus` that runs
  `proteus-mcp`;
- `.opencode/commands/proteus.md` for `/proteus`;
- `.opencode/skills/proteus*/` for coordinator and specialist skills;
- `.opencode/agents/proteus-*.md` for specialist subagents;
- `.opencode/templates/` with the packaged Proteus templates.

It does not initialize Proteus target memory or modify an existing
`.vros/memory.sqlite` base. Use `/proteus` inside OpenCode to start the
coordinator workflow. Use `--force` only when you want to refresh existing
generated OpenCode files.

### OpenCode Global Support

`--root` only ever writes into one workspace, so `/proteus` and its coordinator
skill are not available when you open a different project. To make Proteus
available in every OpenCode workspace, install into OpenCode's user-level
config directory instead:

```powershell
proteus opencode install --global
proteus opencode doctor --global
```

`--global` resolves that directory the same way OpenCode itself does:
`$XDG_CONFIG_HOME/opencode` (or `~/.config/opencode` if unset) on Linux/macOS,
`%APPDATA%\opencode` on Windows. Override it with
`PROTEUS_OPENCODE_GLOBAL_DIR` if needed. Unlike `--root`, this writes the
assets flat (`skills/`, `agents/`, `commands/`, `instructions/`,
`opencode.json` directly under that directory, no `.opencode/` wrapper),
because that is the layout OpenCode's global config actually uses.

`--global` is the only supported way to install the full Proteus OpenCode
package (coordinator skill, specialists, agents, `/proteus` command, MCP
wiring) at user level. It is unrelated to the standalone `npm run
install:<skill>` scripts (`install:defensive-security-review`,
`install:full-review`, `install:logic-review`, `install:maintainability-review`,
`install:performance-review`, `install:maverick`), which only symlink
individual generic code-review skills into `~/.claude/skills`,
`~/.codex/skills`, and `~/.config/opencode/skills` and do not touch the
coordinator skill, agents, command, or MCP config. `--root` and `--global`
are mutually exclusive; `--root` is ignored when `--global` is set.

## Verify Runtime

```powershell
proteus --version
proteus roles
proteus --help
```

Use the repository/workspace root as the normal Proteus `--root`. If a memory
base is accidentally created in a nested folder, merge it into the intended
root before continuing:

```powershell
proteus merge --root C:\path\to\workspace --source .\packages\foo\.vros\memory.sqlite --dry-run
proteus merge --root C:\path\to\workspace --source .\packages\foo\.vros\memory.sqlite
```

## Verify MCP

```powershell
proteus-mcp
```

For Codex, use `codex mcp add proteus -- proteus-mcp`. The Claude Code plugin
loads `plugins/proteus/.mcp.json` automatically; use
`claude mcp add -s user proteus -- proteus-mcp` only as a manual fallback. The
wrapper builds the runtime if `dist/` is not present yet.

## Optional Chimera Runtime

Chimera mode uses OpenCode for secondary agents. Normal Proteus usage does not
require OpenCode. Install and configure OpenCode from the official project, then
enable Chimera for a target:

- OpenCode repository: <https://github.com/anomalyco/opencode>
- OpenCode docs: <https://opencode.ai/docs/>

```powershell
proteus chimera config init --opencode-command opencode --model zai/glm-5.2 --variant high
proteus chimera doctor --root C:\path\to\target
```

Chimera config is global for the current user. Workspace commands still use
`--root`. Runs have no default timeout; pass `--timeout N` only for deliberate
smoke tests or short probes.

`--opencode-command` must point at the real `opencode` CLI binary (the one
that supports `opencode serve`), not at an OpenCode Desktop launcher such as
`ai.opencode.desktop`. Chimera spawns `<opencode-command> serve --hostname
127.0.0.1 --port <port>` to get a headless server it talks to over HTTP; a
Desktop GUI launcher does not implement that and will not serve anything.

This is not caught automatically. `proteus chimera doctor`'s `opencode` check
only verifies that `<opencode-command> --version` exits with status 0 — it
does not check the output. A Desktop GUI launcher can exit 0 (for example
because it detects a running instance and exits, or because it just started
without crashing) without ever having run headless, so `chimera doctor` can
report `ok: true` for a command that will still fail when Chimera actually
tries to start a server. If `chimera start`/`chimera doctor` ever reports a
stale or unresponsive `opencodeServerUrl`/`opencodeServerPid`, treat that as a
sign the configured command is not the real CLI, run `proteus chimera
stop-server` to clear the stale state, then re-run `chimera config init` with
`--opencode-command` set to the actual `opencode` CLI path. Desktop and the CLI
can coexist: use Desktop for the interactive `/proteus` chat experience and
the CLI exclusively for Chimera's headless co-agents.

## Uninstall CLI

```powershell
npm uninstall -g @rafabd1/proteus
```

If installed directly from GitHub, npm still records the installed package under
the package name `@rafabd1/proteus`.
