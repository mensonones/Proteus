#!/usr/bin/env python3
"""Inspect mobile reversing tool capabilities and print narrow install hints."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from typing import Any, Optional


PROFILES = {
    "core": ["unzip", "zipinfo", "file", "strings"],
    "android": ["jadx", "apktool", "bundletool", "aapt", "aapt2", "apksigner"],
    "ios": ["plutil", "otool", "lipo", "codesign", "swift-demangle", "class-dump", "ipsw", "macho2json"],
    "rn": ["node", "hermes-dec", "hbctool", "hbc-disassembler", "hermes"],
    "native": ["readelf", "objdump", "nm", "rabin2", "radare2", "checksec", "ghidra-analyzeHeadless"],
    "dynamic": ["adb", "frida", "frida-trace", "objection", "mitmproxy"],
}

VERSION_ARGS = {
    "aapt": ["version"],
    "aapt2": ["version"],
    "apktool": ["--version"],
    "bundletool": ["version"],
    "file": ["--version"],
    "jadx": ["--version"],
    "node": ["--version"],
    "plutil": ["-help"],
    "unzip": ["-v"],
    "zipinfo": ["-h"],
}

# Installation remains explicit and profile-scoped. Profiles without a reliable
# system package recipe return a hint instead of guessing or using curl pipes.
INSTALL_RECIPES = {
    "debian": {
        "core": ["sudo", "apt-get", "install", "-y", "unzip", "file", "binutils"],
        "native": ["sudo", "apt-get", "install", "-y", "binutils", "radare2", "checksec"],
    },
    "darwin": {
        "core": ["brew", "install", "unzip", "file-formula", "binutils"],
        "android": ["brew", "install", "jadx", "apktool", "bundletool"],
        "ios": ["brew", "install", "ipsw", "class-dump"],
        "native": ["brew", "install", "binutils", "radare2", "checksec"],
    },
}


def detect_os() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
    if system == "windows":
        return "windows"
    if system == "linux":
        try:
            with open("/etc/os-release", "r", encoding="utf-8") as handle:
                data = handle.read().lower()
            if "debian" in data or "ubuntu" in data:
                return "debian"
        except OSError:
            pass
    return "generic"


def selected_tools(profiles: list[str]) -> list[str]:
    return list(dict.fromkeys(tool for profile in profiles for tool in PROFILES[profile]))


def tool_version(tool: str, executable: str) -> Optional[str]:
    args = VERSION_ARGS.get(tool, ["--version"])
    try:
        completed = subprocess.run(
            [executable, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
            check=False,
            text=True,
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return lines[0][:300] if lines else None


def inspect(profiles: list[str], versions: bool) -> dict[str, Any]:
    present: list[dict[str, Any]] = []
    missing: list[str] = []
    for tool in selected_tools(profiles):
        executable = shutil.which(tool)
        if not executable:
            missing.append(tool)
            continue
        item: dict[str, Any] = {"name": tool, "path": executable}
        if versions:
            item["version"] = tool_version(tool, executable)
        present.append(item)
    capabilities: dict[str, Any] = {}
    for profile in profiles:
        profile_present = [tool for tool in PROFILES[profile] if shutil.which(tool)]
        profile_missing = [tool for tool in PROFILES[profile] if not shutil.which(tool)]
        capabilities[profile] = {
            "status": "complete" if not profile_missing else "partial" if profile_present else "missing",
            "present": profile_present,
            "missing": profile_missing,
        }
    return {
        "os": detect_os(),
        "profiles": profiles,
        "present": present,
        "missing": missing,
        "capabilities": capabilities,
    }


def install(profile: str, dry_run: bool) -> int:
    os_name = detect_os()
    command = INSTALL_RECIPES.get(os_name, {}).get(profile)
    if not command:
        print(
            f"No reliable automatic install recipe for profile '{profile}' on {os_name}. "
            "Install only the missing tools required by the current artifact.",
            file=sys.stderr,
        )
        return 2
    print("Install command:", " ".join(command))
    if dry_run:
        return 0
    return subprocess.call(command)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Print installed and missing tools")
    parser.add_argument("--install", choices=sorted(PROFILES), help="Install a supported tool profile")
    parser.add_argument("--profiles", default="core,android,ios,rn,native", help="Comma-separated profiles")
    parser.add_argument("--versions", action="store_true", help="Probe tool versions with short timeouts")
    parser.add_argument("--json", action="store_true", help="Print machine-readable capability output")
    parser.add_argument("--dry-run", action="store_true", help="Print an install command without running it")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profiles = [item.strip() for item in args.profiles.split(",") if item.strip()]
    invalid = sorted(set(profiles) - set(PROFILES))
    if invalid:
        print(f"Invalid profiles: {', '.join(invalid)}", file=sys.stderr)
        return 2

    if args.check or not args.install:
        report = inspect(profiles, args.versions)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"Host: {report['os']}")
            print("Present tools:")
            for item in report["present"]:
                version = f" ({item.get('version')})" if item.get("version") else ""
                print(f"  - {item['name']}: {item['path']}{version}")
            print("Missing tools:")
            for tool in report["missing"]:
                print(f"  - {tool}")

    if args.install:
        if os.environ.get("PROTEUS_ALLOW_TOOL_INSTALL") != "1" and not args.dry_run:
            print("Refusing install unless PROTEUS_ALLOW_TOOL_INSTALL=1 is set.", file=sys.stderr)
            return 2
        return install(args.install, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
