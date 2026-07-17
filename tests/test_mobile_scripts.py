from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR_PATH = REPO_ROOT / "plugins/proteus/skills/mobile-reversing/scripts/extract_mobile_artifacts.py"
TOOLCHAIN_PATH = REPO_ROOT / "plugins/proteus/skills/mobile-reversing/scripts/mobile_toolchain.py"


def load_extractor():
    spec = importlib.util.spec_from_file_location("proteus_mobile_extractor", EXTRACTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load mobile extractor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extractor = load_extractor()


class MobileArtifactTests(unittest.TestCase):
    def test_rejects_archive_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive_path = root / "unsafe.apk"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../escaped.txt", "nope")
            with self.assertRaises(extractor.ArtifactError):
                extractor.safe_extract_archive(archive_path, root / "out", self.limits())
            self.assertFalse((root / "escaped.txt").exists())

    def test_rejects_symbolic_links(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive_path = root / "symlink.apk"
            info = zipfile.ZipInfo("link")
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(info, "target")
            with self.assertRaises(extractor.ArtifactError):
                extractor.safe_extract_archive(archive_path, root / "out", self.limits())

    def test_rejects_suspicious_compression_ratio(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive_path = root / "compressed.apk"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("assets/repeated.bin", b"A" * 100_000)
            limits = self.limits()
            limits["max_compression_ratio"] = 2.0
            with self.assertRaises(extractor.ArtifactError):
                extractor.safe_extract_archive(archive_path, root / "out", limits)

    def test_rejects_output_nested_in_source(self):
        with tempfile.TemporaryDirectory() as temp_name:
            source = Path(temp_name) / "source"
            source.mkdir()
            with self.assertRaises(extractor.ArtifactError):
                extractor.ensure_output_is_safe(source, source / "mobile-artifacts")

    def test_xapk_extracts_nested_apk(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            apk_buffer = io.BytesIO()
            with zipfile.ZipFile(apk_buffer, "w") as apk:
                apk.writestr("AndroidManifest.xml", "manifest")
                apk.writestr("classes.dex", b"dex\n035\x00")
            xapk_path = root / "sample.xapk"
            with zipfile.ZipFile(xapk_path, "w") as xapk:
                xapk.writestr("manifest.json", "{}")
                xapk.writestr("base.apk", apk_buffer.getvalue())
            work = root / "work"
            work.mkdir()
            roots, nested = extractor.prepare_roots(xapk_path, work, self.limits())
            self.assertEqual(len(roots), 2)
            self.assertEqual([item.name for item in nested], ["base.apk"])
            self.assertTrue((roots[1] / "classes.dex").exists())

    def test_cli_emits_unified_inventory(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            apk_path = root / "sample.apk"
            output = root / "result"
            with zipfile.ZipFile(apk_path, "w") as archive:
                archive.writestr("AndroidManifest.xml", "manifest")
                archive.writestr("classes.dex", b"dex\n035\x00")
                archive.writestr("assets/index.android.bundle", "var answer = 42; function run() {}")
                archive.writestr("lib/arm64-v8a/libsample.so", b"\x7fELFplaceholder")
                archive.writestr("res/xml/network_security_config.xml", "<network-security-config />")
            completed = subprocess.run(
                [sys.executable, str(EXTRACTOR_PATH), str(apk_path), "-o", str(output), "--no-tools"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(report["schemaVersion"], 1)
            self.assertEqual(report["mobileScope"], "apk")
            self.assertEqual(len(report["inventory"]["dexFiles"]), 1)
            self.assertEqual(report["reactNativeBundle"]["formats"], ["plain-js"])
            self.assertEqual(report["inventory"]["nativeLibraries"][0]["abi"], "arm64-v8a")
            self.assertIn("android-dex", report["mobileAttackSurface"])
            self.assertEqual(report["candidateFindings"], [])

    def test_generic_zip_routes_back_as_not_mobile(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive_path = root / "generic.zip"
            output = root / "result"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("notes.txt", "not a mobile artifact")
            completed = subprocess.run(
                [sys.executable, str(EXTRACTOR_PATH), str(archive_path), "-o", str(output), "--no-tools"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(report["contextDecision"], "not-mobile")
            self.assertEqual(report["mobileScope"], "not-mobile")

    def test_direct_ios_jsbundle_is_mobile_bundle(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            bundle_path = root / "main.jsbundle"
            output = root / "result"
            bundle_path.write_text("var route = 'home'; function start() {}", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(EXTRACTOR_PATH), str(bundle_path), "-o", str(output), "--no-tools"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(report["mobileScope"], "bundle")
            self.assertEqual(report["reactNativeBundle"]["format"], "plain-js")

    def test_cli_rejects_nonempty_output(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive_path = root / "sample.apk"
            output = root / "result"
            output.mkdir()
            (output / "stale.txt").write_text("stale", encoding="utf-8")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("AndroidManifest.xml", "manifest")
            completed = subprocess.run(
                [sys.executable, str(EXTRACTOR_PATH), str(archive_path), "-o", str(output), "--no-tools"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("not empty", completed.stderr)

    def test_toolchain_json_is_machine_readable(self):
        completed = subprocess.run(
            [sys.executable, str(TOOLCHAIN_PATH), "--check", "--profiles", "core,android", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["profiles"], ["core", "android"])
        self.assertIn("present", report)
        self.assertIn("missing", report)

    @staticmethod
    def limits():
        return {
            "max_files": 100,
            "max_unpacked_bytes": 1024 * 1024,
            "max_file_bytes": 512 * 1024,
            "max_compression_ratio": 100.0,
        }


if __name__ == "__main__":
    unittest.main()
