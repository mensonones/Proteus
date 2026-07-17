import { spawnSync } from "node:child_process";

const candidates = process.platform === "win32"
  ? [["py", ["-3"]], ["python", []], ["python3", []]]
  : [["python3", []], ["python", []]];

const selected = candidates.find(([command, prefix]) => {
  const probe = spawnSync(command, [...prefix, "--version"], { encoding: "utf8" });
  return probe.status === 0;
});

if (!selected) {
  console.error("Python 3 is required to run the mobile artifact tests.");
  process.exit(2);
}

const [command, prefix] = selected;
const result = spawnSync(
  command,
  [...prefix, "-m", "unittest", "discover", "-s", "tests", "-p", "test_mobile_*.py"],
  { stdio: "inherit", env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" } }
);

if (result.error) {
  console.error(result.error.message);
  process.exit(2);
}
process.exit(result.status ?? 2);
