#!/usr/bin/env python3
"""Extract mobile bundles and native artifacts from APK/AAB/IPA/ZIP or directories."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


BUNDLE_HINTS = (".bundle", ".hbc", "index.android.bundle", "index.bundle")
NATIVE_SUFFIX = ".so"
IOS_BINARY_HINTS = (".app/", ".framework/", ".appex/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_type(path: Path) -> str:
    if shutil.which("file"):
        try:
            output = subprocess.check_output(["file", "-b", str(path)], text=True, stderr=subprocess.DEVNULL)
            return output.strip()
        except subprocess.SubprocessError:
            pass
    with path.open("rb") as handle:
        sample = handle.read(16)
    if sample.startswith(b"PK\x03\x04"):
        return "zip archive"
    return "unknown"


def is_bundle(path: Path) -> bool:
    name = path.name.lower()
    return any(hint in name for hint in BUNDLE_HINTS)


def is_probable_ios_binary(path: Path, root: Path) -> bool:
    relative = str(path.relative_to(root))
    if not any(hint in relative for hint in IOS_BINARY_HINTS):
        return False
    if path.suffix in {".plist", ".strings", ".json", ".png", ".jpg", ".jpeg", ".nib", ".storyboardc"}:
        return False
    kind = file_type(path).lower()
    return "mach-o" in kind


def unpack_input(source: Path, workdir: Path) -> Path:
    if source.is_dir():
        return source
    if zipfile.is_zipfile(source):
        extract_dir = workdir / "unpacked"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source) as archive:
            archive.extractall(extract_dir)
        return extract_dir
    raise SystemExit(f"Unsupported input: {source}")


def copy_artifact(path: Path, root: Path, output_root: Path, category: str) -> dict:
    relative = path.relative_to(root)
    destination = output_root / category / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    return {
        "source": str(path),
        "relative": str(relative),
        "copiedTo": str(destination),
        "size": path.stat().st_size,
        "sha256": sha256(path),
        "fileType": file_type(path),
    }


def extract_strings(path: Path, limit: int = 200) -> list[str]:
    strings_bin = shutil.which("strings")
    if not strings_bin:
        return []
    try:
        output = subprocess.check_output([strings_bin, "-a", "-n", "5", str(path)], text=True, errors="replace")
    except subprocess.SubprocessError:
        return []
    lines: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped and stripped not in lines:
            lines.append(stripped)
        if len(lines) >= limit:
            break
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="APK, AAB, IPA, ZIP, XAPK, or extracted directory.")
    parser.add_argument("-o", "--output", default="mobile-artifacts", help="Output directory.")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="proteus-mobile-") as temp_name:
        root = unpack_input(source, Path(temp_name))
        bundles = []
        native_libs = []
        ios_binaries = []
        manifests = []

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative_name = path.name.lower()
            if relative_name == "androidmanifest.xml":
                manifests.append(copy_artifact(path, root, output, "manifests"))
            elif relative_name in {"info.plist"} or path.suffix.lower() == ".entitlements":
                manifests.append(copy_artifact(path, root, output, "manifests"))
            elif is_bundle(path):
                item = copy_artifact(path, root, output, "bundles")
                item["stringsPreview"] = extract_strings(path, 80)
                bundles.append(item)
            elif path.suffix.lower() == NATIVE_SUFFIX:
                item = copy_artifact(path, root, output, "native-libs")
                item["stringsPreview"] = extract_strings(path, 80)
                native_libs.append(item)
            elif is_probable_ios_binary(path, root):
                item = copy_artifact(path, root, output, "ios-binaries")
                item["stringsPreview"] = extract_strings(path, 80)
                ios_binaries.append(item)

    report = {
        "source": str(source),
        "output": str(output),
        "manifests": manifests,
        "bundles": bundles,
        "nativeLibraries": native_libs,
        "iosBinaries": ios_binaries,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    triage_path = output / "triage.txt"
    triage_path.write_text(
        "\n".join(
            [
                f"Source: {source}",
                f"Bundles: {len(bundles)}",
                f"Native libraries: {len(native_libs)}",
                f"iOS binaries: {len(ios_binaries)}",
                f"Manifests: {len(manifests)}",
                f"Manifest JSON: {manifest_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
