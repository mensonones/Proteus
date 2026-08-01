#!/usr/bin/env node

// update-local.mjs — one command to bump the version and refresh every local
// Proteus surface (OpenCode, Codex, Claude Code) from the working tree.
//
// Usage:
//   npm run release:local                 # auto patch bump (X.Y.Z -> X.Y.Z+1)
//   npm run release:local -- minor        # X.Y.0
//   npm run release:local -- major        # X.0.0
//   npm run release:local -- 2.3.0        # explicit version
//
// It does NOT commit. It leaves the working tree modified (bumped manifests +
// a CHANGELOG stub for you to edit) and installs the new build into the three
// local surfaces. Each surface is best-effort: a failure in one is reported but
// does not abort the others.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pluginRoot = path.join(repoRoot, "plugins", "proteus");

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function readText(file) {
  return fs.readFileSync(file, "utf8");
}

function currentVersion() {
  const match = readText(path.join(repoRoot, "package.json")).match(/"version":\s*"(\d+\.\d+\.\d+)"/);
  if (!match) throw new Error("could not read current version from package.json");
  return match[1];
}

function computeNextVersion(current, spec) {
  if (/^\d+\.\d+\.\d+$/.test(spec)) return spec;
  const [major, minor, patch] = current.split(".").map(Number);
  switch (spec) {
    case "major":
      return `${major + 1}.0.0`;
    case "minor":
      return `${major}.${minor + 1}.0`;
    case "patch":
      return `${major}.${minor}.${patch + 1}`;
    default:
      throw new Error(`invalid version spec: "${spec}" (use patch|minor|major or an explicit X.Y.Z)`);
  }
}

// Replace the version value in a file, keeping formatting intact. `pattern`
// captures everything up to the version and everything after it so a suffix
// such as "+codex.<timestamp>" survives untouched.
function replaceVersion(file, pattern, next, { required = true } = {}) {
  const absolute = path.isAbsolute(file) ? file : path.join(repoRoot, file);
  if (!fs.existsSync(absolute)) {
    if (required) throw new Error(`missing manifest: ${absolute}`);
    return false;
  }
  const before = readText(absolute);
  const after = before.replace(pattern, (_m, head, tail = "") => `${head}${next}${tail}`);
  if (after === before) {
    if (required) throw new Error(`version pattern did not match in ${absolute}`);
    return false;
  }
  fs.writeFileSync(absolute, after);
  return true;
}

function bumpManifests(current, next) {
  const esc = escapeRegExp(current);
  // package.json (pretty-printed, single occurrence)
  replaceVersion("package.json", new RegExp(`("version":\\s*")${esc}(")`), next);
  // plugins/proteus/package.json (minified: "version":"X")
  replaceVersion("plugins/proteus/package.json", new RegExp(`("version":\\s*")${esc}(")`), next);
  // Claude plugin manifest
  replaceVersion("plugins/proteus/.claude-plugin/plugin.json", new RegExp(`("version":\\s*")${esc}(")`), next);
  // Codex plugin manifest — preserve the +codex.<timestamp> build suffix
  replaceVersion(
    "plugins/proteus/.codex-plugin/plugin.json",
    new RegExp(`("version":\\s*")${esc}(\\+codex\\.[^"]*")`),
    next
  );
  // marketplace.json carries both the marketplace version and the plugin version
  replaceVersion(
    ".claude-plugin/marketplace.json",
    new RegExp(`("version":\\s*")${esc}(")`, "g"),
    next
  );
}

function updateChangelog(next) {
  const file = path.join(repoRoot, "CHANGELOG.md");
  if (!fs.existsSync(file)) return false;
  const content = readText(file);
  const header = "# Changelog\n\n";
  if (!content.startsWith(header)) throw new Error("unexpected CHANGELOG.md header");
  const date = new Date().toISOString().slice(0, 10);
  const stub = `## ${next} - ${date}\n\n### Changed\n\n- TODO: describe changes in this release.\n\n`;
  fs.writeFileSync(file, header + stub + content.slice(header.length));
  return true;
}

function run(label, command, args, results) {
  process.stdout.write(`\n▶ ${label}\n`);
  try {
    execFileSync(command, args, { cwd: repoRoot, stdio: "inherit" });
    results.push({ label, ok: true });
  } catch (error) {
    results.push({ label, ok: false, error: error.message });
    process.stderr.write(`  ✗ ${label} failed: ${error.message}\n`);
  }
}

// Replicate what a `/plugin` update does for a local (directory) marketplace:
// copy the plugin into the versioned cache and repoint installed_plugins.json.
function updateClaudeCode(next, results) {
  const label = "Claude Code (cache + registry)";
  process.stdout.write(`\n▶ ${label}\n`);
  try {
    const registryPath = path.join(os.homedir(), ".claude", "plugins", "installed_plugins.json");
    if (!fs.existsSync(registryPath)) {
      results.push({ label, ok: false, error: "installed_plugins.json not found (plugin never installed here)" });
      process.stderr.write("  ⚠ skipped: Claude Code plugin registry not found\n");
      return;
    }
    const registry = JSON.parse(readText(registryPath));
    const key = Object.keys(registry.plugins ?? {}).find((k) => k.startsWith("proteus@"));
    if (!key) {
      results.push({ label, ok: false, error: "no proteus@ entry in installed_plugins.json" });
      process.stderr.write("  ⚠ skipped: no proteus plugin entry registered\n");
      return;
    }
    const entry = registry.plugins[key][0];
    // Derive the versioned cache dir from the current installPath (…/<plugin>/<version>).
    const cacheParent = path.dirname(entry.installPath);
    const destDir = path.join(cacheParent, next);
    fs.rmSync(destDir, { recursive: true, force: true });
    fs.mkdirSync(destDir, { recursive: true });
    fs.cpSync(pluginRoot, destDir, { recursive: true });

    let sha = null;
    try {
      sha = execFileSync("git", ["rev-parse", "HEAD"], { cwd: repoRoot }).toString().trim();
    } catch {
      /* not a git repo — leave sha null */
    }
    entry.installPath = destDir;
    entry.version = next;
    entry.lastUpdated = new Date().toISOString().replace(/\.(\d{3})\d*Z$/, ".$1Z");
    if (sha) entry.gitCommitSha = sha;
    fs.writeFileSync(registryPath, `${JSON.stringify(registry, null, 4)}\n`);

    process.stdout.write(`  ✓ cached ${destDir}\n  ✓ registry -> ${next}\n`);
    results.push({ label, ok: true, note: "restart Claude Code to load the new version" });
  } catch (error) {
    results.push({ label, ok: false, error: error.message });
    process.stderr.write(`  ✗ ${label} failed: ${error.message}\n`);
  }
}

function main() {
  const spec = process.argv[2] ?? "patch";
  const current = currentVersion();
  const next = computeNextVersion(current, spec);
  if (next === current) throw new Error(`next version equals current (${current})`);

  process.stdout.write(`Proteus local update: ${current} -> ${next}\n`);

  // 1. Bump manifests + CHANGELOG stub (working tree only; no commit).
  bumpManifests(current, next);
  const changelog = updateChangelog(next);
  process.stdout.write(`✓ bumped 6 manifests${changelog ? " + CHANGELOG stub" : ""}\n`);

  const results = [];

  // 2. Build (tsc + sync-plugin-dist + sync-opencode + sync-codex-agents).
  run("build", "npm", ["run", "build"], results);

  // 3. OpenCode global install.
  run("OpenCode (global install)", "node", ["dist/cli.js", "opencode", "install", "--global", "--force"], results);

  // 4. Codex agents (symlink .codex/agents/*.toml -> ~/.codex/agents).
  run("Codex (install agents)", "node", ["scripts/install-codex-agents.mjs"], results);

  // 5. Claude Code cache + registry repoint.
  updateClaudeCode(next, results);

  // Summary
  process.stdout.write(`\n── Summary (${current} -> ${next}) ──\n`);
  for (const r of results) {
    process.stdout.write(`  ${r.ok ? "✓" : "✗"} ${r.label}${r.note ? ` — ${r.note}` : ""}${r.error ? ` — ${r.error}` : ""}\n`);
  }
  const failed = results.filter((r) => !r.ok);
  process.stdout.write(
    `\nWorking tree is modified (not committed). Edit the CHANGELOG stub, review, then commit \`chore(release): ${next}\`.\n`
  );
  if (failed.length) {
    process.stderr.write(`\n${failed.length} surface(s) failed — see above.\n`);
    process.exitCode = 1;
  }
}

main();
