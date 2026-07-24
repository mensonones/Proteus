# Proteus Installation

Proteus has four install surfaces:

- CLI/runtime: the `proteus` and `proteus-mcp` commands.
- Codex plugin: installed through a Codex plugin marketplace.
- Claude Code plugin: `/proteus`, plugin subagents, and MCP config.
- Opencode integration: `/proteus` command, skills, subagents, and MCP config.

Install the CLI first. The plugin instructions can load without it, but target
memory, exports, labs, and MCP tools depend on the `proteus` and `proteus-mcp`
runtime commands.

## 1. CLI Install From GitHub

```powershell
npm install -g https://codeload.github.com/rafabd1/Proteus/tar.gz/refs/heads/main
proteus --version
```

Expected shape:

```text
@rafabd1/proteus 1.0.1
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
npm install -g https://codeload.github.com/rafabd1/Proteus/tar.gz/refs/heads/main
```

After npm publishing:

```powershell
npm update -g @rafabd1/proteus
```

Pin a branch, tag, or commit:

```powershell
npm install -g github:rafabd1/Proteus#main
```

## Local Development Install

```powershell
git clone https://github.com/rafabd1/Proteus
cd Proteus
npm install
npm link
proteus --version
```

To install the standalone maintainability review skill globally for Codex,
Claude Code, and Opencode from this clone:

```powershell
npm run install:maintainability-review
```

The installer creates symlinks from the versioned skill at
`plugins/proteus/skills/maintainability-review` into the user-level skill
directories used by those tools.

## 2. Codex Plugin Install

Codex supports marketplace sources in the form `owner/repo[@ref]`, Git URLs,
SSH URLs, or local marketplace root directories.

```powershell
codex plugin marketplace add rafabd1/Proteus
codex plugin add proteus@proteus-marketplace
```

Pin a ref:

```powershell
codex plugin marketplace add rafabd1/Proteus@main
```

The marketplace file is:

```text
.agents/plugins/marketplace.json
```

It exposes the plugin at:

```text
plugins/proteus
```

Start a new Codex CLI session after installation. The installed plugin bundles
its MCP configuration. Register `proteus-mcp` separately only when intentionally
using the standalone runtime without the plugin.

Install the native Proteus custom-agent profiles globally and start a new Codex
session again:

```powershell
proteus-install-codex-agents
```

This installs Atlas, Argus, Loom, Chaos, Libris, Mimic, Artificer, Skeptic, and Cicada
under `~/.codex/agents/`. The coordinator falls back to generic subagents with
inlined role contracts when these profiles are not installed.

In Codex CLI, verify the skill with `/skills`, then invoke:

```text
$proteus initialize continuous vulnerability research for this repository
```

Use `$proteus` as the normal CLI entrypoint so Codex can load the full
coordinator and choose any specialist skill it needs. `@Proteus` is the plugin
mention on supported ChatGPT desktop surfaces, not Codex CLI syntax.

## 3. Claude Code Plugin Install

Install directly inside Claude Code:

```text
/plugin marketplace add rafabd1/Proteus
/plugin install proteus@proteus-marketplace
```

Then use `/proteus` from Claude Code.

Then register the MCP server from the CLI install:

```powershell
claude mcp add -s user proteus -- proteus-mcp
```

## 4. Opencode Integration

The `opencode.json` at the project root configures Proteus for Opencode with
the `/proteus` command, skills from `.opencode/skills/`, subagents from
`.opencode/agents/`, support templates from `.opencode/templates/`, and the MCP
server.

Two options:

### Local (per-project)

Copy into your Opencode workspace:

```powershell
cp /path/to/Proteus/opencode.json opencode.json
cp -r /path/to/Proteus/.opencode .
```

Or if Proteus is already in the workspace (e.g. cloned as a subdirectory),
Opencode picks up the `opencode.json`, skills, agents, and templates
automatically.

### Global (all projects)

Copy skills, agents, and templates to the global Opencode config directory:

```powershell
cp -r /path/to/Proteus/.opencode/skills ~/.config/opencode/skills
cp -r /path/to/Proteus/.opencode/agents ~/.config/opencode/agents
cp -r /path/to/Proteus/.opencode/templates ~/.config/opencode/templates
```

Add the `/proteus` command and MCP server to `~/.config/opencode/opencode.json`:

```json
{
  "skills": { "paths": ["~/.config/opencode/skills"] },
  "command": {
    "proteus": {
      "description": "Inicia pesquisa contínua de vulnerabilidades com memória estruturada.",
      "template": "Atue como coordenador Proteus..."
    }
  },
  "mcp": {
    "proteus": {
      "type": "local",
      "command": ["proteus-mcp"],
      "enabled": true
    }
  }
}
```

Restart Opencode after making config changes.

In Opencode, invoke Proteus with `/proteus`. Opencode loads the coordinator
template from the command definition, the skills from `.opencode/skills/`, the
subagent contracts from `.opencode/agents/`, and support templates from
`.opencode/templates/`.

## Verify Runtime

```powershell
proteus --version
proteus roles
proteus --help
```

## Verify MCP

```powershell
proteus-mcp
```

For Codex, use `codex mcp add proteus -- proteus-mcp`. For Claude Code, use
`claude mcp add -s user proteus -- proteus-mcp`. For Opencode, the MCP server
is declared in `opencode.json`. Plugin hosts that support
plugin-declared MCP servers can also use `plugins/proteus/.mcp.json`. The
wrapper builds the runtime if `dist/` is not present yet.

## Ephemeral Tor (Network Anonymization)

Proteus agents route all outbound research traffic through Tor. The
`plugins/proteus/scripts/tor-ephemeral.sh` script manages the lifecycle:

```bash
bash plugins/proteus/scripts/tor-ephemeral.sh bootstrap   # install + start circuit
bash plugins/proteus/scripts/tor-ephemeral.sh stop        # kill + clean temp dir
bash plugins/proteus/scripts/tor-ephemeral.sh purge       # stop + uninstall packages
```

The bootstrap command auto-detects the package manager (apt/dnf/pacman/brew),
installs `tor` and `proxychains4` if missing, and starts an ephemeral circuit
on `127.0.0.1:9050`. No systemd service is created or left running.

Optional kernel-level enforcement blocks all non-Tor traffic, including the
host's built-in `webfetch` tool:

```bash
sudo bash plugins/proteus/scripts/tor-ephemeral.sh enforce
sudo bash plugins/proteus/scripts/tor-ephemeral.sh relax
```

Requires: a package manager with `sudo` access for installation, and `iptables`
for kernel enforcement. The script handles the absence of both gracefully
(records the limitation as a blocker).

When running Proteus locally (`npm link`), the script is available at
`plugins/proteus/scripts/tor-ephemeral.sh`. When installed globally via npm,
access it from the cloned repository or copy it to your target workspace.

## Uninstall CLI

```powershell
npm uninstall -g @rafabd1/proteus
```

If installed directly from GitHub, npm still records the installed package under
the package name `@rafabd1/proteus`.
