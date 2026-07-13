#!/usr/bin/env python3
"""Check and optionally install mobile reversing tools."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys


PROFILES = {
    "core": ["unzip", "zipinfo", "file", "strings", "jadx", "apktool"],
    "ios": ["plutil", "otool", "lipo", "codesign", "swift-demangle", "class-dump"],
    "rn": ["node", "hermes-dec", "hbctool", "hbc-disassembler", "hermes"],
    "native": ["readelf", "objdump", "nm", "rabin2", "radare2", "checksec"],
    "dynamic": ["adb", "frida", "frida-trace", "objection", "mitmproxy"],
}

INSTALL_HINTS = {
    "debian": {
        "core": ["sudo", "apt-get", "install", "-y", "unzip", "zipinfo", "file", "binutils", "jadx", "apktool"],
        "native": ["sudo", "apt-get", "install", "-y", "binutils", "radare2", "checksec"],
        "dynamic": ["python3", "-m", "pip", "install", "--user", "frida-tools", "objection", "mitmproxy"],
    },
    "darwin": {
        "core": ["brew", "install", "jadx", "apktool", "file-formula"],
        "ios": ["brew", "install", "class-dump", "ipsw"],
        "native": ["brew", "install", "binutils", "radare2", "checksec"],
        "dynamic": ["python3", "-m", "pip", "install", "--user", "frida-tools", "objection", "mitmproxy"],
    },
    "generic": {
        "rn": ["python3", "-m", "pip", "install", "--user", "hermes-dec", "hbctool"],
    },
}


def detect_os() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "darwin"
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
    tools: list[str] = []
    for profile in profiles:
        for tool in PROFILES[profile]:
            if tool not in tools:
                tools.append(tool)
    return tools


def check(profiles: list[str]) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for tool in selected_tools(profiles):
        if shutil.which(tool):
            present.append(tool)
        else:
            missing.append(tool)
    return present, missing


def install(profile: str, dry_run: bool) -> int:
    os_name = detect_os()
    command = INSTALL_HINTS.get(os_name, {}).get(profile) or INSTALL_HINTS["generic"].get(profile)
    if not command:
        print(f"No install recipe for profile '{profile}' on {os_name}.", file=sys.stderr)
        return 2
    print("Install command:", " ".join(command))
    if dry_run:
        return 0
    return subprocess.call(command)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Print installed and missing tools.")
    parser.add_argument("--install", choices=sorted(PROFILES), help="Install a tool profile.")
    parser.add_argument("--profiles", default="core,ios,rn,native", help="Comma-separated profiles for --check.")
    parser.add_argument("--dry-run", action="store_true", help="Print install command without running it.")
    args = parser.parse_args()

    profiles = [item.strip() for item in args.profiles.split(",") if item.strip()]
    invalid = sorted(set(profiles) - set(PROFILES))
    if invalid:
        print(f"Invalid profiles: {', '.join(invalid)}", file=sys.stderr)
        return 2

    if args.check or not args.install:
        present, missing = check(profiles)
        print("Present tools:")
        for tool in present:
            print(f"  - {tool}: {shutil.which(tool)}")
        print("Missing tools:")
        for tool in missing:
            print(f"  - {tool}")

    if args.install:
        if os.environ.get("PROTEUS_ALLOW_TOOL_INSTALL") != "1" and not args.dry_run:
            print("Refusing install unless PROTEUS_ALLOW_TOOL_INSTALL=1 is set.", file=sys.stderr)
            return 2
        return install(args.install, args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
