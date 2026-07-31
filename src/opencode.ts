import fs from "node:fs";
import path from "node:path";
import { ensureDir, openCodeGlobalConfigDir, toRelative } from "./paths";

type JsonObject = Record<string, unknown>;

export interface OpenCodeInstallOptions {
  force?: boolean;
  /**
   * Install into OpenCode's user-level config directory (flat layout, no
   * `.opencode/` nesting) instead of a project root. This is the only
   * supported way to make Proteus available across every OpenCode workspace;
   * `--root` is ignored when this is set.
   */
  global?: boolean;
}

export interface OpenCodeInstallResult {
  root: string;
  configPath: string;
  created: string[];
  updated: string[];
  skipped: string[];
  advisories: string[];
}

export interface OpenCodeDoctorResult {
  root: string;
  config: {
    path: string;
    exists: boolean;
    validJson: boolean;
    hasProteusMcp: boolean;
    hasProteusInstructions: boolean;
  };
  assets: {
    commands: string[];
    agents: string[];
    skills: string[];
    templates: string[];
  };
  ok: boolean;
  advisories: string[];
}

export const SKILL_ALIASES = [
  {
    source: "continuous-vuln-research",
    target: "proteus",
    description:
      "Coordinate Proteus continuous vulnerability research with memory, campaigns, delegation, validation gates, and report-grade discipline."
  },
  {
    source: "chaining",
    target: "proteus-chaining",
    description:
      "Develop non-obvious Proteus exploit chains from primitives, side effects, state drift, and component coupling."
  },
  {
    source: "checkpoint",
    target: "proteus-checkpoint",
    description:
      "Compress Proteus campaign or round state into a concise checkpoint with facts, killed paths, pivots, and next moves."
  },
  {
    source: "codebase-research",
    target: "proteus-codebase-research",
    description:
      "Map a codebase for Proteus research through architecture, dataflow, trust boundaries, invariants, and high-ROI branch material."
  },
  {
    source: "fuzzing",
    target: "proteus-fuzzing",
    description:
      "Design calibrated Proteus fuzzing and differential probes that learn input behavior instead of spraying generic payloads."
  },
  {
    source: "poc-exploit",
    target: "proteus-poc-exploit",
    description:
      "Build realistic Proteus PoC plans, labs, negative controls, and exploitability evidence for concrete candidates."
  },
  {
    source: "web-intel",
    target: "proteus-web-intel",
    description:
      "Gather Proteus security intelligence for known status, timelines, advisories, changelogs, docs, and duplicate risk."
  },
  {
    source: "web-research",
    target: "proteus-web-research",
    description:
      "Conduct authorized Proteus web research with campaign memory, chaining, fuzzing, intel, and PoC heuristics."
  },
  {
    source: "mobile-reversing",
    target: "proteus-mobile-reversing",
    description:
      "Investigate Android/iOS mobile artifacts (APK/AAB/IPA, React Native/Hermes bundles, native libraries) for Proteus mobile-specific vulnerability research.",
    copyResources: true
  },
  {
    source: "maintainability-review",
    target: "maintainability-review",
    description:
      "Run a strict Proteus structural code quality review focused on maintainability, abstraction quality, and architecture drift."
  },
  {
    source: "logic-and-edge-case-review",
    target: "logic-and-edge-case-review",
    description:
      "Run a strict Proteus review focused on correctness, edge cases, race conditions, and logic bugs."
  },
  {
    source: "defensive-security-review",
    target: "defensive-security-review",
    description:
      "Run a strict Proteus application security review (AppSec) focused on Git diffs."
  },
  {
    source: "performance-scale-review",
    target: "performance-scale-review",
    description:
      "Run a strict Proteus review focused on performance bottlenecks, scalability, and algorithmic efficiency."
  },
  {
    source: "meta/full-review",
    target: "full-review",
    description:
      "Orchestrate a complete 360-degree Proteus review: logic-and-edge-case-review, defensive-security-review, and performance-scale-review sequentially."
  }
];

export function installOpenCodeSupport(root: string | undefined, options: OpenCodeInstallOptions = {}): OpenCodeInstallResult {
  const targetRoot = options.global ? openCodeGlobalConfigDir() : path.resolve(root ?? process.cwd());
  const assetsRoot = options.global ? targetRoot : path.join(targetRoot, ".opencode");
  const result: OpenCodeInstallResult = {
    root: targetRoot,
    configPath: path.join(targetRoot, "opencode.json"),
    created: [],
    updated: [],
    skipped: [],
    advisories: []
  };
  ensureDir(targetRoot);
  installOpenCodeConfig(targetRoot, assetsRoot, result, options);
  installOpenCodeInstructions(assetsRoot, result, options);
  installOpenCodeCommand(assetsRoot, result, options);
  installOpenCodeSkills(assetsRoot, result, options);
  installOpenCodeAgents(assetsRoot, result, options);
  installOpenCodeTemplates(assetsRoot, result, options);
  return result;
}

export function doctorOpenCodeSupport(root: string | undefined, options: { global?: boolean } = {}): OpenCodeDoctorResult {
  const targetRoot = options.global ? openCodeGlobalConfigDir() : path.resolve(root ?? process.cwd());
  const assetsRoot = options.global ? targetRoot : path.join(targetRoot, ".opencode");
  const configPath = path.join(targetRoot, "opencode.json");
  const configRead = readJsonConfig(configPath);
  const result: OpenCodeDoctorResult = {
    root: targetRoot,
    config: {
      path: configPath,
      exists: fs.existsSync(configPath),
      validJson: configRead.ok,
      hasProteusMcp: hasProteusMcp(configRead.value),
      hasProteusInstructions: hasProteusInstructions(configRead.value)
    },
    assets: {
      commands: listNames(path.join(assetsRoot, "commands"), ".md"),
      agents: listNames(path.join(assetsRoot, "agents"), ".md"),
      skills: listSkillNames(path.join(assetsRoot, "skills")),
      templates: listNames(path.join(assetsRoot, "templates"))
    },
    ok: false,
    advisories: []
  };
  const installHint = options.global ? "proteus opencode install --global" : "proteus opencode install --root <path>";
  if (!result.config.exists) result.advisories.push(`opencode.json is missing. Run \`${installHint}\`.`);
  if (result.config.exists && !result.config.validJson) result.advisories.push("opencode.json is not valid JSON. Proteus will not modify JSONC/commented configs automatically.");
  if (!result.config.hasProteusMcp) result.advisories.push("opencode.json does not enable the Proteus MCP server.");
  if (!result.config.hasProteusInstructions) result.advisories.push("opencode.json does not reference the Proteus OpenCode instructions.");
  for (const required of SKILL_ALIASES.map((item) => item.target)) {
    if (!result.assets.skills.includes(required)) result.advisories.push(`Missing OpenCode skill: ${required}`);
  }
  if (!result.assets.commands.includes("proteus")) result.advisories.push("Missing OpenCode command: /proteus");
  result.ok = result.config.validJson && result.config.hasProteusMcp && result.config.hasProteusInstructions && result.advisories.length === 0;
  return result;
}

function installOpenCodeConfig(targetRoot: string, assetsRoot: string, result: OpenCodeInstallResult, options: OpenCodeInstallOptions): void {
  const configPath = path.join(targetRoot, "opencode.json");
  const existing = readJsonConfig(configPath);
  if (fs.existsSync(configPath) && !existing.ok) {
    result.skipped.push(configPath);
    result.advisories.push("Existing opencode.json is not valid JSON. Add the Proteus MCP and instructions manually or rerun with --force to replace it.");
    return;
  }
  const config = existing.value ?? {};
  config.$schema = typeof config.$schema === "string" ? config.$schema : "https://opencode.ai/config.json";
  config.mcp = isObject(config.mcp) ? config.mcp : {};
  (config.mcp as JsonObject).proteus = {
    type: "local",
    command: ["proteus-mcp"],
    enabled: true,
    timeout: 15000
  };
  const instructionsPath = toRelative(targetRoot, path.join(assetsRoot, "instructions", "proteus.md"));
  const instructions = Array.isArray(config.instructions) ? config.instructions.filter((item): item is string => typeof item === "string") : [];
  if (!instructions.includes(instructionsPath)) instructions.push(instructionsPath);
  config.instructions = instructions;
  config.permission = isObject(config.permission) ? config.permission : {};
  (config.permission as JsonObject).skill = isObject((config.permission as JsonObject).skill) ? (config.permission as JsonObject).skill : {};
  ((config.permission as JsonObject).skill as JsonObject)["proteus*"] = "allow";
  writeManagedFile(configPath, `${JSON.stringify(config, null, 2)}\n`, result, options);
}

function installOpenCodeInstructions(assetsRoot: string, result: OpenCodeInstallResult, options: OpenCodeInstallOptions): void {
  const specialistNames = SKILL_ALIASES.map((alias) => alias.target).filter((target) => target !== "proteus");
  const specialistList = specialistNames.map((name) => `\`${name}\``).join(", ").replace(/, ([^,]*)$/, ", and $1");
  const instructions = `# Proteus OpenCode Runtime

Proteus is available in this OpenCode project through:

- the \`proteus\` skill for coordinator-led continuous vulnerability research;
- specialist skills named ${specialistList};
- the local \`proteus\` MCP server, started through \`proteus-mcp\`;
- the \`/proteus\` command for starting the coordinator workflow.

When the user asks for Proteus research, load the \`proteus\` skill first. Use the specialist skills only when the current branch needs that specific method. Prefer MCP tools when available, and fall back to the \`proteus\` CLI when a tool is unavailable.
`;
  writeManagedFile(path.join(assetsRoot, "instructions", "proteus.md"), instructions, result, options);
}

function installOpenCodeCommand(assetsRoot: string, result: OpenCodeInstallResult, options: OpenCodeInstallOptions): void {
  const source = path.join(proteusPluginRoot(), "commands", "proteus.md");
  const command = fs.existsSync(source)
    ? fs.readFileSync(source, "utf8")
    : `---\ndescription: Run Proteus continuous vulnerability research for the current target.\n---\n\nLoad the proteus skill and run the coordinator workflow for: $ARGUMENTS\n`;
  writeManagedFile(path.join(assetsRoot, "commands", "proteus.md"), command, result, options);
}

function installOpenCodeSkills(assetsRoot: string, result: OpenCodeInstallResult, options: OpenCodeInstallOptions): void {
  const skillsRoot = path.join(proteusPluginRoot(), "skills");
  for (const alias of SKILL_ALIASES) {
    const source = path.join(skillsRoot, alias.source, "SKILL.md");
    if (!fs.existsSync(source)) {
      result.advisories.push(`Packaged Proteus skill missing: ${alias.source}`);
      continue;
    }
    const destinationDir = path.join(assetsRoot, "skills", alias.target);
    if (isSymlink(destinationDir)) {
      result.skipped.push(destinationDir);
      result.advisories.push(
        `Skipped symlinked skill directory: ${destinationDir}. It is externally managed (for example by a separate ` +
          "install:*-skill script) and writing through it would overwrite the symlink target instead of this directory. " +
          "Remove the symlink first if you want Proteus to manage this skill directly."
      );
      continue;
    }
    const content = rewriteSkillFrontmatter(fs.readFileSync(source, "utf8"), alias.target, alias.description);
    writeManagedFile(path.join(destinationDir, "SKILL.md"), content, result, options);
    if (alias.copyResources) {
      installSkillResources(path.join(skillsRoot, alias.source), destinationDir, result, options);
    }
  }
}

function isSymlink(targetPath: string): boolean {
  try {
    return fs.lstatSync(targetPath).isSymbolicLink();
  } catch {
    return false;
  }
}

function installSkillResources(sourceDir: string, destinationDir: string, result: OpenCodeInstallResult, options: OpenCodeInstallOptions): void {
  for (const child of ["scripts", "references"]) {
    const sourceChild = path.join(sourceDir, child);
    if (!fs.existsSync(sourceChild)) continue;
    for (const filePath of listFilesRecursive(sourceChild)) {
      const basename = path.basename(filePath);
      if (basename === "__pycache__" || filePath.includes(`${path.sep}__pycache__${path.sep}`) || basename.endsWith(".pyc") || basename.endsWith(".pyo")) continue;
      const relative = path.relative(sourceDir, filePath);
      writeManagedFile(path.join(destinationDir, relative), fs.readFileSync(filePath, "utf8"), result, options);
    }
  }
}

function listFilesRecursive(dir: string): string[] {
  const files: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const entryPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...listFilesRecursive(entryPath));
    } else if (entry.isFile()) {
      files.push(entryPath);
    }
  }
  return files;
}

function installOpenCodeAgents(assetsRoot: string, result: OpenCodeInstallResult, options: OpenCodeInstallOptions): void {
  const agentsRoot = path.join(proteusPluginRoot(), "agents");
  if (!fs.existsSync(agentsRoot)) return;
  for (const entry of fs.readdirSync(agentsRoot, { withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
    const source = path.join(agentsRoot, entry.name);
    const content = rewriteAgentFrontmatter(fs.readFileSync(source, "utf8"));
    writeManagedFile(path.join(assetsRoot, "agents", entry.name), content, result, options);
  }
}

function installOpenCodeTemplates(assetsRoot: string, result: OpenCodeInstallResult, options: OpenCodeInstallOptions): void {
  const templatesRoot = path.join(proteusPluginRoot(), "templates");
  if (!fs.existsSync(templatesRoot)) return;
  for (const entry of fs.readdirSync(templatesRoot, { withFileTypes: true })) {
    if (!entry.isFile()) continue;
    const source = path.join(templatesRoot, entry.name);
    writeManagedFile(path.join(assetsRoot, "templates", entry.name), fs.readFileSync(source, "utf8"), result, options);
  }
}

function rewriteSkillFrontmatter(content: string, name: string, description: string): string {
  const body = stripFrontmatter(content);
  return `---\nname: ${name}\ndescription: ${description}\ncompatibility: opencode\nmetadata:\n  source: proteus\n---\n${body}`;
}

function rewriteAgentFrontmatter(content: string): string {
  const parsed = parseFrontmatter(content);
  if (!parsed) return content;
  const lines = parsed.frontmatter.split(/\r?\n/).filter((line) => !/^mode\s*:/.test(line) && !/^permission\s*:/.test(line));
  const nameIndex = lines.findIndex((line) => /^name\s*:/.test(line));
  if (nameIndex >= 0) lines.splice(nameIndex, 1);
  const frontmatter = [...lines, "mode: subagent"].join("\n");
  return `---\n${frontmatter}\n---\n${parsed.body}`;
}

function stripFrontmatter(content: string): string {
  const parsed = parseFrontmatter(content);
  return parsed ? parsed.body : content;
}

function parseFrontmatter(content: string): { frontmatter: string; body: string } | null {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) return null;
  return {
    frontmatter: match[1] ?? "",
    body: content.slice(match[0].length)
  };
}

function writeManagedFile(filePath: string, content: string, result: OpenCodeInstallResult, options: OpenCodeInstallOptions): void {
  ensureDir(path.dirname(filePath));
  if (fs.existsSync(filePath) && !options.force) {
    const current = fs.readFileSync(filePath, "utf8");
    if (current === content) {
      result.skipped.push(filePath);
      return;
    }
    result.skipped.push(filePath);
    result.advisories.push(`Skipped existing file: ${filePath}. Rerun with --force to update it.`);
    return;
  }
  const existed = fs.existsSync(filePath);
  fs.writeFileSync(filePath, content);
  (existed ? result.updated : result.created).push(filePath);
}

function readJsonConfig(filePath: string): { ok: true; value: JsonObject | null } | { ok: false; value: null } {
  if (!fs.existsSync(filePath)) return { ok: true, value: null };
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, "utf8")) as unknown;
    if (!isObject(parsed)) return { ok: false, value: null };
    return { ok: true, value: parsed };
  } catch {
    return { ok: false, value: null };
  }
}

function hasProteusMcp(config: JsonObject | null): boolean {
  if (!config || !isObject(config.mcp)) return false;
  const proteus = config.mcp.proteus;
  return isObject(proteus) && proteus.type === "local" && Array.isArray(proteus.command) && proteus.command.includes("proteus-mcp") && proteus.enabled !== false;
}

function hasProteusInstructions(config: JsonObject | null): boolean {
  if (!config || !Array.isArray(config.instructions)) return false;
  return config.instructions.some(
    (item) => typeof item === "string" && item.replace(/\\/g, "/").endsWith("instructions/proteus.md")
  );
}

function listNames(dir: string, suffix?: string): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && (!suffix || entry.name.endsWith(suffix)))
    .map((entry) => suffix ? entry.name.slice(0, -suffix.length) : entry.name)
    .sort();
}

function listSkillNames(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((entry) => isDirectoryEntry(dir, entry) && fs.existsSync(path.join(dir, entry.name, "SKILL.md")))
    .map((entry) => entry.name)
    .sort();
}

function isDirectoryEntry(dir: string, entry: fs.Dirent): boolean {
  if (entry.isDirectory()) return true;
  if (!entry.isSymbolicLink()) return false;
  try {
    return fs.statSync(path.join(dir, entry.name)).isDirectory();
  } catch {
    return false;
  }
}

function proteusPluginRoot(): string {
  return path.resolve(__dirname, "..", "plugins", "proteus");
}

function isObject(value: unknown): value is JsonObject {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
