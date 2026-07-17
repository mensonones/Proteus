#!/usr/bin/env python3
"""Safely extract and inventory Android/iOS application artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Optional


BUNDLE_HINTS = (".bundle", ".jsbundle", ".hbc", "index.android.bundle", "index.ios.bundle", "index.bundle")
INTERESTING_RESOURCES = {
    "network_security_config.xml",
    "backup_rules.xml",
    "data_extraction_rules.xml",
    "resources.arsc",
}
ARCHIVE_SUFFIXES = {".apk", ".aab", ".xapk", ".apks", ".ipa", ".zip"}
MACHO_MAGICS = {
    bytes.fromhex("feedface"), bytes.fromhex("cefaedfe"),
    bytes.fromhex("feedfacf"), bytes.fromhex("cffaedfe"),
    bytes.fromhex("cafebabe"), bytes.fromhex("bebafeca"),
}
DEFAULT_MAX_FILES = 100_000
DEFAULT_MAX_UNPACKED_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_MAX_FILE_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_COMPRESSION_RATIO = 200.0
COMMAND_OUTPUT_LIMIT = 256 * 1024


class ArtifactError(RuntimeError):
    """Raised when an artifact cannot be processed safely."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_type(path: Path) -> str:
    result = run_command(["file", "-b", str(path)], timeout=15)
    if result["status"] == "ok":
        return result["stdout"].strip()
    try:
        with path.open("rb") as handle:
            sample = handle.read(16)
    except OSError:
        return "unreadable"
    if sample.startswith(b"PK\x03\x04"):
        return "zip archive"
    if sample.startswith(b"\x7fELF"):
        return "ELF binary"
    return "unknown"


def is_macho(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) in MACHO_MAGICS
    except OSError:
        return False


def run_command(command: list[str], timeout: int = 120, cwd: Optional[Path] = None) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if not executable:
        return {"status": "missing", "command": command, "stdout": "", "stderr": ""}
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [executable, *command[1:]],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        stdout = completed.stdout[:COMMAND_OUTPUT_LIMIT].decode("utf-8", errors="replace")
        stderr = completed.stderr[:COMMAND_OUTPUT_LIMIT].decode("utf-8", errors="replace")
        return {
            "status": "ok" if completed.returncode == 0 else "error",
            "command": command,
            "exitCode": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": len(completed.stdout) > COMMAND_OUTPUT_LIMIT or len(completed.stderr) > COMMAND_OUTPUT_LIMIT,
            "durationMs": round((time.monotonic() - started) * 1000),
        }
    except subprocess.TimeoutExpired as error:
        return {
            "status": "timeout",
            "command": command,
            "stdout": (error.stdout or b"")[:COMMAND_OUTPUT_LIMIT].decode("utf-8", errors="replace"),
            "stderr": (error.stderr or b"")[:COMMAND_OUTPUT_LIMIT].decode("utf-8", errors="replace"),
            "durationMs": round((time.monotonic() - started) * 1000),
        }


def safe_member_path(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    member = PurePosixPath(normalized)
    if member.is_absolute() or not member.parts or any(part in {"", ".", ".."} for part in member.parts):
        raise ArtifactError(f"Unsafe archive member path: {name!r}")
    if member.parts[0].endswith(":"):
        raise ArtifactError(f"Unsafe archive drive path: {name!r}")
    return member


def validate_archive(
    archive: zipfile.ZipFile,
    max_files: int,
    max_unpacked_bytes: int,
    max_file_bytes: int,
    max_compression_ratio: float,
) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
    total_size = 0
    file_count = 0
    for info in archive.infolist():
        member = safe_member_path(info.filename)
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ArtifactError(f"Archive contains a symbolic link: {info.filename!r}")
        if info.is_dir():
            members.append((info, member))
            continue
        file_count += 1
        total_size += info.file_size
        if file_count > max_files:
            raise ArtifactError(f"Archive contains more than {max_files} files")
        if info.file_size > max_file_bytes:
            raise ArtifactError(f"Archive member exceeds size limit: {info.filename!r}")
        if total_size > max_unpacked_bytes:
            raise ArtifactError("Archive exceeds the total uncompressed size limit")
        ratio = info.file_size / max(info.compress_size, 1)
        if ratio > max_compression_ratio:
            raise ArtifactError(f"Suspicious compression ratio for {info.filename!r}: {ratio:.1f}")
        members.append((info, member))
    return members


def safe_extract_archive(
    source: Path, destination: Path, limits: dict[str, Any], budget: Optional[dict[str, int]] = None
) -> None:
    with zipfile.ZipFile(source) as archive:
        members = validate_archive(archive, **limits)
        archive_files = sum(1 for info, _ in members if not info.is_dir())
        archive_bytes = sum(info.file_size for info, _ in members if not info.is_dir())
        if budget is not None:
            if budget["files"] + archive_files > limits["max_files"]:
                raise ArtifactError("Nested archives exceed the aggregate file-count limit")
            if budget["bytes"] + archive_bytes > limits["max_unpacked_bytes"]:
                raise ArtifactError("Nested archives exceed the aggregate expanded-size limit")
            budget["files"] += archive_files
            budget["bytes"] += archive_bytes
        destination_resolved = destination.resolve()
        for info, member in members:
            target = destination.joinpath(*member.parts)
            target_resolved = target.resolve()
            if target_resolved != destination_resolved and destination_resolved not in target_resolved.parents:
                raise ArtifactError(f"Archive member escapes extraction root: {info.filename!r}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with archive.open(info) as source_handle, target.open("wb") as destination_handle:
                    shutil.copyfileobj(source_handle, destination_handle, length=1024 * 1024)
            except (RuntimeError, NotImplementedError) as error:
                raise ArtifactError(f"Could not extract {info.filename!r}: {error}") from error


def detect_scope(source: Path) -> str:
    suffix = source.suffix.lower()
    suffix_scope = {
        ".apk": "apk",
        ".aab": "aab",
        ".xapk": "xapk",
        ".apks": "xapk",
        ".ipa": "ipa",
        ".app": "app",
        ".so": "native-so",
    }
    if suffix in suffix_scope:
        return suffix_scope[suffix]
    if source.is_file() and (suffix in {".bundle", ".jsbundle", ".hbc"} or any(hint in source.name.lower() for hint in BUNDLE_HINTS)):
        return "bundle"
    if source.is_file() and is_macho(source):
        return "macho"
    if source.is_dir():
        android = any(source.rglob("AndroidManifest.xml")) or (source / "app" / "src" / "main").exists()
        ios = any(source.rglob("Info.plist")) or any(source.glob("*.xcodeproj"))
        if android and ios:
            return "mixed"
        if android:
            return "android-project"
        if ios:
            return "ios-project"
    return "mixed"


def prepare_roots(source: Path, workdir: Path, limits: dict[str, Any]) -> tuple[list[Path], list[Path]]:
    if source.is_dir():
        return [source], []
    if not source.is_file():
        raise ArtifactError(f"Source does not exist or is not a regular file: {source}")
    if source.suffix.lower() not in ARCHIVE_SUFFIXES and not zipfile.is_zipfile(source):
        single_root = workdir / "single"
        single_root.mkdir(parents=True)
        shutil.copy2(source, single_root / source.name)
        return [single_root], []
    if not zipfile.is_zipfile(source):
        raise ArtifactError(f"Artifact has an archive extension but is not a valid ZIP: {source}")

    primary = workdir / "primary"
    primary.mkdir(parents=True)
    extraction_budget = {"files": 0, "bytes": 0}
    safe_extract_archive(source, primary, limits, extraction_budget)
    roots = [primary]
    nested_archives: list[Path] = []
    if source.suffix.lower() in {".xapk", ".apks"}:
        for index, nested in enumerate(sorted(primary.rglob("*.apk"))):
            nested_root = workdir / "nested" / f"{index:03d}-{nested.stem}"
            nested_root.mkdir(parents=True)
            safe_extract_archive(nested, nested_root, limits, extraction_budget)
            roots.append(nested_root)
            nested_archives.append(nested)
    return roots, nested_archives


def ensure_output_is_safe(source: Path, output: Path) -> None:
    if source.is_dir() and (output == source or source in output.parents):
        raise ArtifactError("Output directory must not be inside the source directory")
    if output.exists() and any(output.iterdir()):
        raise ArtifactError(f"Output directory is not empty: {output}. Choose a fresh directory.")


def artifact_record(path: Path, root: Path, copied_to: Optional[Path] = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "source": str(path),
        "relative": str(path.relative_to(root)),
        "size": path.stat().st_size,
        "sha256": sha256(path),
        "fileType": file_type(path),
    }
    if copied_to:
        record["copiedTo"] = str(copied_to)
    return record


def copy_artifact(path: Path, root: Path, output: Path, category: str) -> dict[str, Any]:
    relative = path.relative_to(root)
    destination = output / "artifacts" / category / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    return artifact_record(path, root, destination)


def bundle_format(path: Path) -> str:
    with path.open("rb") as handle:
        sample = handle.read(4096)
    if sample.startswith(bytes.fromhex("c61fbc03c103191f")) or path.suffix.lower() == ".hbc":
        return "hermes"
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"
    if any(marker in text for marker in ("__d(", "require(", "function", "const ", "var ")):
        return "plain-js"
    return "unknown"


def strings_preview(path: Path, limit: int = 80) -> list[str]:
    result = run_command(["strings", "-a", "-n", "5", str(path)], timeout=30)
    if result["status"] != "ok":
        return []
    unique: list[str] = []
    for line in result["stdout"].splitlines():
        value = line.strip()
        if value and value not in unique:
            unique.append(value)
        if len(unique) >= limit:
            break
    return unique


def native_analysis(path: Path) -> dict[str, Any]:
    commands = {
        "elfHeader": ["readelf", "-h", str(path)],
        "dynamicSection": ["readelf", "-d", str(path)],
        "dynamicSymbols": ["nm", "-D", str(path)],
        "hardening": ["checksec", "--file", str(path)],
    }
    return {name: run_command(command, timeout=45) for name, command in commands.items()}


def decode_primary_artifact(
    source: Path, scope: str, output: Path, nested_archives: list[Path]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if scope in {"apk", "xapk"}:
        apks = [source] if scope == "apk" else nested_archives
        for index, apk in enumerate(apks):
            label = f"{index:03d}-{apk.stem}"
            if shutil.which("jadx"):
                results.append(run_command(["jadx", "-d", str(output / "decompiled" / label / "jadx"), str(apk)], timeout=900))
            if shutil.which("apktool"):
                results.append(run_command(["apktool", "d", "-f", "-o", str(output / "decompiled" / label / "apktool"), str(apk)], timeout=900))
            elif shutil.which("aapt2") or shutil.which("aapt"):
                tool = "aapt2" if shutil.which("aapt2") else "aapt"
                results.append(run_command([tool, "dump", "xmltree", str(apk), "AndroidManifest.xml"], timeout=120))
    elif scope == "aab" and shutil.which("bundletool"):
        results.append(run_command(["bundletool", "dump", "manifest", f"--bundle={source}"], timeout=180))
    return results


def collect_inventory(
    roots: list[Path], output: Path, analyze_tools: bool, max_native_analysis: int, limits: dict[str, Any]
) -> dict[str, Any]:
    categories: dict[str, list[dict[str, Any]]] = {
        "manifests": [],
        "dexFiles": [],
        "bundles": [],
        "nativeLibraries": [],
        "iosBinaries": [],
        "resources": [],
    }
    extensions: Counter[str] = Counter()
    total_files = 0
    total_bytes = 0
    native_analyzed = 0

    for root_index, root in enumerate(roots):
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ArtifactError(f"Directory input contains a symbolic link: {path}")
            if not path.is_file():
                continue
            total_files += 1
            total_bytes += path.stat().st_size
            if total_files > limits["max_files"]:
                raise ArtifactError("Artifact inventory exceeds the file-count limit")
            if path.stat().st_size > limits["max_file_bytes"]:
                raise ArtifactError(f"Artifact file exceeds the per-file size limit: {path}")
            if total_bytes > limits["max_unpacked_bytes"]:
                raise ArtifactError("Artifact inventory exceeds the total-size limit")
            extensions[path.suffix.lower() or "<none>"] += 1
            name = path.name.lower()
            record: Optional[dict[str, Any]] = None
            if name == "androidmanifest.xml" or name == "info.plist" or path.suffix.lower() == ".entitlements":
                record = copy_artifact(path, root, output, f"root-{root_index}/manifests")
                if analyze_tools and (name == "info.plist" or path.suffix.lower() == ".entitlements"):
                    record["analysis"] = run_command(["plutil", "-p", str(record["copiedTo"])], timeout=30)
                categories["manifests"].append(record)
            elif path.suffix.lower() == ".dex":
                record = copy_artifact(path, root, output, f"root-{root_index}/dex")
                categories["dexFiles"].append(record)
            elif any(hint in name for hint in BUNDLE_HINTS):
                record = copy_artifact(path, root, output, f"root-{root_index}/bundles")
                record["format"] = bundle_format(path)
                record["stringsPreview"] = strings_preview(path)
                categories["bundles"].append(record)
            elif path.suffix.lower() == ".so":
                record = copy_artifact(path, root, output, f"root-{root_index}/native-libs")
                record["abi"] = next((part for part in path.parts if part in {"arm64-v8a", "armeabi-v7a", "x86", "x86_64"}), "unknown")
                record["stringsPreview"] = strings_preview(path)
                if analyze_tools and native_analyzed < max_native_analysis:
                    record["analysis"] = native_analysis(Path(record["copiedTo"]))
                    native_analyzed += 1
                categories["nativeLibraries"].append(record)
            elif is_macho(path):
                record = copy_artifact(path, root, output, f"root-{root_index}/ios-binaries")
                record["stringsPreview"] = strings_preview(path)
                categories["iosBinaries"].append(record)
            elif name in INTERESTING_RESOURCES:
                categories["resources"].append(copy_artifact(path, root, output, f"root-{root_index}/resources"))

    return {
        **categories,
        "summary": {
            "files": total_files,
            "bytes": total_bytes,
            "extensions": dict(extensions.most_common()),
            "nativeLibrariesAnalyzed": native_analyzed,
        },
    }


def tool_status() -> tuple[list[dict[str, str]], list[str]]:
    tools = [
        "file", "strings", "jadx", "apktool", "aapt", "aapt2", "bundletool", "apksigner",
        "plutil", "otool", "lipo", "codesign", "readelf", "objdump", "nm", "checksec",
        "hbctool", "hbc-disassembler", "hermes", "frida", "adb",
    ]
    present = [{"name": tool, "path": str(shutil.which(tool))} for tool in tools if shutil.which(tool)]
    missing = [tool for tool in tools if not shutil.which(tool)]
    return present, missing


def build_attack_surface(inventory: dict[str, Any]) -> list[str]:
    surface: list[str] = []
    if inventory["manifests"]:
        surface.append("manifest-plist-entitlements")
    if inventory["dexFiles"]:
        surface.append("android-dex")
    if inventory["bundles"]:
        surface.append("react-native-or-script-bundle")
    if inventory["nativeLibraries"]:
        surface.append("native-library-bridge")
    if inventory["iosBinaries"]:
        surface.append("ios-macho-framework")
    return surface


def used_tools(inventory: dict[str, Any], tool_runs: list[dict[str, Any]], no_tools: bool) -> list[str]:
    used: set[str] = set()
    if shutil.which("file"):
        used.add("file")
    if shutil.which("strings") and any(inventory[key] for key in ("bundles", "nativeLibraries", "iosBinaries")):
        used.add("strings")
    for result in tool_runs:
        command = result.get("command", [])
        if command:
            used.add(str(command[0]))
    if not no_tools and inventory["summary"]["nativeLibrariesAnalyzed"]:
        used.update(tool for tool in ("readelf", "nm", "checksec") if shutil.which(tool))
    if not no_tools and any(item.get("analysis") for item in inventory["manifests"]):
        used.add("plutil")
    return sorted(used)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="APK, AAB, IPA, XAPK, APKS, ZIP, app, bundle, or extracted directory")
    parser.add_argument("-o", "--output", default="mobile-artifacts", help="Fresh output directory")
    parser.add_argument("--no-tools", action="store_true", help="Do not run decompilers or native analysis tools")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-unpacked-bytes", type=int, default=DEFAULT_MAX_UNPACKED_BYTES)
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-compression-ratio", type=float, default=DEFAULT_MAX_COMPRESSION_RATIO)
    parser.add_argument("--max-native-analysis", type=int, default=50)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    limits = {
        "max_files": args.max_files,
        "max_unpacked_bytes": args.max_unpacked_bytes,
        "max_file_bytes": args.max_file_bytes,
        "max_compression_ratio": args.max_compression_ratio,
    }

    try:
        ensure_output_is_safe(source, output)
        output.mkdir(parents=True, exist_ok=True)
        scope = detect_scope(source)
        with tempfile.TemporaryDirectory(prefix="proteus-mobile-") as temp_name:
            roots, nested_archives = prepare_roots(source, Path(temp_name), limits)
            nested_archive_names = [item.name for item in nested_archives]
            inventory = collect_inventory(roots, output, not args.no_tools, args.max_native_analysis, limits)
            tool_runs = [] if args.no_tools else decode_primary_artifact(source, scope, output, nested_archives)

        present_tools, missing_tools = tool_status()
        attack_surface = build_attack_surface(inventory)
        context_decision = "mobile"
        if scope == "mixed":
            context_decision = "mixed-mobile-entry" if attack_surface else "not-mobile"
        limitations: list[str] = []
        if scope in {"apk", "xapk", "aab"} and not (shutil.which("jadx") or shutil.which("apktool")):
            limitations.append("Android code/resources were not decompiled because jadx and apktool are unavailable")
        if any(item.get("format") == "hermes" for item in inventory["bundles"]) and not (shutil.which("hbctool") or shutil.which("hbc-disassembler")):
            limitations.append("Hermes bytecode was identified but no Hermes disassembler is available")
        report = {
            "schemaVersion": 1,
            "contextDecision": context_decision,
            "mobileScope": scope if context_decision != "not-mobile" else "not-mobile",
            "source": {"path": str(source), "size": source.stat().st_size if source.is_file() else None},
            "output": str(output),
            "artifactsReviewed": [str(source)],
            "nestedArchives": nested_archive_names,
            "toolsUsed": used_tools(inventory, tool_runs, args.no_tools),
            "toolsAvailable": present_tools,
            "toolsMissing": missing_tools,
            "toolRuns": tool_runs,
            "reactNativeBundle": {
                "present": bool(inventory["bundles"]),
                "format": inventory["bundles"][0]["format"] if len(inventory["bundles"]) == 1 else "unknown",
                "formats": sorted({item["format"] for item in inventory["bundles"]}),
                "evidence": [item["relative"] for item in inventory["bundles"]],
            },
            "nativeLibraries": inventory["nativeLibraries"],
            "iosArtifacts": inventory["iosBinaries"],
            "mobileAttackSurface": attack_surface,
            "knownBaseline": [],
            "exploratoryHypotheses": [],
            "validationExperiments": [],
            "candidateFindings": [],
            "limitations": limitations,
            "inventory": inventory,
            "extractionLimits": limits,
            "nextProteusRoute": "continue-mobile" if context_decision != "not-mobile" else "blocked",
            "contractSignature": {
                "status": "compliant",
                "signedBy": "mobile-artifact-extractor",
                "attackerModel": "Artifact contents are treated as untrusted input; exploitability is evaluated in the follow-up research pass",
                "heuristicCoverage": ["safe-extraction", "artifact-inventory"],
                "antiSlopCheck": "No vulnerability claims are produced by this extraction stage",
                "deviations": [],
                "deviationRepair": None,
            },
        }
        manifest_path = output / "manifest.json"
        manifest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        (output / "triage.txt").write_text(
            "\n".join(
                [
                    f"Source: {source}",
                    f"Scope: {scope}",
                    f"Files inventoried: {inventory['summary']['files']}",
                    f"DEX files: {len(inventory['dexFiles'])}",
                    f"Bundles: {len(inventory['bundles'])}",
                    f"Native libraries: {len(inventory['nativeLibraries'])}",
                    f"iOS binaries: {len(inventory['iosBinaries'])}",
                    f"Manifest JSON: {manifest_path}",
                ]
            ) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, indent=2))
        return 0
    except (ArtifactError, OSError, zipfile.BadZipFile) as error:
        print(json.dumps({"error": str(error), "source": str(source), "output": str(output)}), file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
