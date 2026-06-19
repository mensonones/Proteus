import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = path.join(repoRoot, "plugins", "proteus", "skills", "maintainability-review");
const home = os.homedir();

const destinations = [
  path.join(home, ".codex", "skills", "maintainability-review"),
  path.join(home, ".claude", "skills", "maintainability-review"),
  path.join(home, ".config", "opencode", "skills", "maintainability-review")
];

if (!fs.existsSync(path.join(source, "SKILL.md"))) {
  throw new Error(`missing source skill: ${source}`);
}

for (const destination of destinations) {
  installSymlink(source, destination);
}

console.log("Installed maintainability-review skill links:");
for (const destination of destinations) {
  console.log(`- ${destination} -> ${source}`);
}

function installSymlink(sourcePath, destinationPath) {
  fs.mkdirSync(path.dirname(destinationPath), { recursive: true });

  if (fs.existsSync(destinationPath)) {
    const stat = fs.lstatSync(destinationPath);

    if (stat.isSymbolicLink()) {
      fs.unlinkSync(destinationPath);
    } else if (sameSkillContent(sourcePath, destinationPath)) {
      fs.rmSync(destinationPath, { recursive: true, force: true });
    } else if (sameRealPath(sourcePath, destinationPath)) {
      return;
    } else {
      throw new Error(
        `refusing to replace non-symlink destination: ${destinationPath}\n` +
          "Move it aside or delete it before running this installer."
      );
    }
  }

  fs.symlinkSync(sourcePath, destinationPath, "dir");
}

function sameSkillContent(left, right) {
  const leftSkill = path.join(left, "SKILL.md");
  const rightSkill = path.join(right, "SKILL.md");

  try {
    return fs.readFileSync(leftSkill, "utf8") === fs.readFileSync(rightSkill, "utf8");
  } catch {
    return false;
  }
}

function sameRealPath(left, right) {
  try {
    return fs.realpathSync(left) === fs.realpathSync(right);
  } catch {
    return false;
  }
}
