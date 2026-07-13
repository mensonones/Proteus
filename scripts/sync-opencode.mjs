import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pluginRoot = path.join(repoRoot, "plugins", "proteus");
const openCodeRoot = path.join(repoRoot, ".opencode");

const skillMap = [
  ["continuous-vuln-research", "proteus"],
  ["chaining", "proteus-chaining"],
  ["checkpoint", "proteus-checkpoint"],
  ["codebase-research", "proteus-codebase-research"],
  ["fuzzing", "proteus-fuzzing"],
  ["maintainability-review", "maintainability-review"],
  ["mobile-reversing", "proteus-mobile-reversing"],
  ["poc-exploit", "proteus-poc-exploit"],
  ["web-intel", "proteus-web-intel"],
  ["web-research", "proteus-web-research"]
];

syncDirectory(path.join(pluginRoot, "agents"), path.join(openCodeRoot, "agents"));
syncDirectory(path.join(pluginRoot, "templates"), path.join(openCodeRoot, "templates"));
syncSkills();

function syncDirectory(source, destination) {
  if (!fs.existsSync(source)) {
    throw new Error(`missing source directory: ${source}`);
  }
  fs.rmSync(destination, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.cpSync(source, destination, { recursive: true });
}

function syncSkills() {
  const destinationRoot = path.join(openCodeRoot, "skills");
  fs.rmSync(destinationRoot, { recursive: true, force: true });
  fs.mkdirSync(destinationRoot, { recursive: true });

  for (const [sourceName, openCodeName] of skillMap) {
    const sourcePath = path.join(pluginRoot, "skills", sourceName, "SKILL.md");
    const destinationDir = path.join(destinationRoot, openCodeName);
    const destinationPath = path.join(destinationDir, "SKILL.md");

    if (!fs.existsSync(sourcePath)) {
      throw new Error(`missing source skill: ${sourcePath}`);
    }

    fs.mkdirSync(destinationDir, { recursive: true });
    fs.writeFileSync(destinationPath, toOpenCodeSkill(fs.readFileSync(sourcePath, "utf8"), sourceName, openCodeName));
    syncSkillResources(sourceName, path.join(pluginRoot, "skills", sourceName), destinationDir);
  }
}

function syncSkillResources(sourceName, sourceDir, destinationDir) {
  if (sourceName !== "mobile-reversing") {
    return;
  }

  for (const child of ["scripts", "references"]) {
    const sourceChild = path.join(sourceDir, child);
    if (fs.existsSync(sourceChild)) {
      fs.cpSync(sourceChild, path.join(destinationDir, child), { recursive: true });
    }
  }
}

function toOpenCodeSkill(content, sourceName, openCodeName) {
  let output = content.replace(new RegExp(`^name: ${escapeRegExp(sourceName)}$`, "m"), `name: ${openCodeName}`);

  output = replaceSkillReferences(output);

  if (sourceName === "codebase-research") {
    output = output.replace("Use when Codex must understand", "Use when OpenCode should understand");
  }

  if (sourceName === "continuous-vuln-research") {
    output = output
      .replace(
        "All Proteus roles and skills must follow\n`plugins/proteus/templates/base-research-contract.md`.",
        "All Proteus roles and skills must follow `base-research-contract.md` from the\ntemplate resolution paths below."
      )
      .replace(
        "Role contracts and templates must be loaded from the Proteus plugin/package, not\nfrom the target workspace.",
        "Role contracts and templates must be loaded from the configured Proteus\nintegration directory, not from arbitrary target source files."
      )
      .replace(
        "2. the host-exposed Proteus plugin root\n3. the installed Codex plugin cache\n4. Claude Code installed plugin package root, when exposed",
        "2. the configured `.opencode/agents` or `.opencode/templates` directory\n3. the installed OpenCode config directory\n4. the host-exposed Proteus plugin root, when available"
      )
      .replace("For Codex subagents", "For OpenCode subagents");
  }

  return output;
}

function replaceSkillReferences(content) {
  let output = content;
  for (const [sourceName, openCodeName] of skillMap) {
    output = output.replaceAll(`\`${sourceName}\``, `\`${openCodeName}\``);
  }
  return output;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
