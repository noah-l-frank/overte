#!/usr/bin/env python3
"""Real Phone gate/ZIP/ELF composition; only external SDK tools are fixtures."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[3]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def elf(soname, needed=("libc.so",), machine=183, alignment=16384):
    strings = b"\0"
    offsets = []
    for name in (soname, *needed):
        offsets.append(len(strings)); strings += name.encode() + b"\0"
    dynamic_size = 16 * (4 + len(needed)); dynamic_offset = 176
    string_offset = dynamic_offset + dynamic_size; size = string_offset + len(strings)
    header = struct.pack("<16sHHIQQQIHHHHHH", b"\x7fELF\x02\x01\x01" + b"\0" * 9,
                         3, machine, 1, 0, 64, 0, 0, 64, 56, 2, 0, 0, 0)
    program = struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, size, size, alignment)
    dynamic = struct.pack("<IIQQQQQQ", 2, 4, dynamic_offset, dynamic_offset, dynamic_offset, dynamic_size, dynamic_size, 8)
    tags = [(5, string_offset), (10, len(strings)), (14, offsets[0])]
    tags += [(1, offset) for offset in offsets[1:]] + [(0, 0)]
    return header + program + dynamic + b"".join(struct.pack("<qQ", *row) for row in tags) + strings


class PhoneNativeOutput(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.controller = self.base / "protected-controller"
        files = ["android/phone/native-ci/verify_apk.py", "android/common/native-ci/apk_native.py",
                 "android/common/native-ci/verify.py", "android/phone/ci/verify-phone-apk.py",
                 "android/phone/apps/phoneInterface/src/main/res/values/qt_dependencies.xml"]
        files += ["android/phone/tests/" + name for name in
                  ("check-phone-apk-16k.sh", "check-phone-apk-metadata.sh", "check-phone-apk-contents.py",
                   "check-phone-elf-alignment.sh", "check-phone-apk-padding.py")]
        for name in files:
            target = self.controller / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        self.verifier = load(self.controller / files[0], "relocated_phone_native")
        self.native = load(self.controller / "android/common/native-ci/apk_native.py", "phone_native_fixture")
        contents = load(self.controller / "android/phone/tests/check-phone-apk-contents.py", "phone_contents_fixture")
        self.entries = {name: b"fixture" for name in contents.BASE_REQUIRED_ENTRIES | contents.LINKED_NATIVE_ENTRIES |
                        contents.declared_native_entries() | contents.declared_asset_markers()}
        for name in self.entries:
            if name.startswith("lib/"): self.entries[name] = elf(Path(name).name)
        cache = sorted(contents.REQUIRED_CACHED_ASSETS)
        digest = hashlib.sha256()
        for name in cache:
            self.entries["assets/" + name] = b"fixture"
            digest.update(name.encode() + b"\0" + b"fixture")
        self.entries["assets/cache_assets.txt"] = (digest.hexdigest() + "\n" + "\n".join(cache) + "\n").encode()
        self.apk = self.base / "phone.apk"
        self.source = self.base / "separate-candidate"; self.source.mkdir()
        (self.source / "source.txt").write_text("exact candidate\n")
        for args in (("init", "--quiet"), ("add", "."),
                     ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "Fixture")):
            subprocess.run(["git", "-C", str(self.source), *args], check=True, capture_output=True)
        self.head = subprocess.check_output(["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True).strip()
        self.sdk = self.base / "sdk"; self.tools = self.sdk / "build-tools/36.0.0"; self.tools.mkdir(parents=True)
        self.analyzer = self.tools / "apkanalyzer"
        self.analyzer.write_text('''#!/usr/bin/env python3
import os,sys
if sys.argv[1:3] == ['dex','code']:
 print('.class public L' + sys.argv[4].replace('.','/') + ';');sys.exit()
values={'application-id':'io.github.noah_be.overte.phone','version-code':'1','version-name':os.getenv('PHONE_FIXTURE_VERSION','0.1.0-ci'),'min-sdk':'26','target-sdk':'36','debuggable':'false','permissions':'android.permission.ACCESS_NETWORK_STATE\\nandroid.permission.INTERNET\\nandroid.permission.MODIFY_AUDIO_SETTINGS\\nandroid.permission.RECORD_AUDIO\\nandroid.permission.VIBRATE'}
print(values[sys.argv[2]])
'''); self.analyzer.chmod(0o755)
        for name in ("aapt", "aapt2", "zipalign"):
            path = self.tools / name; path.write_text("#!/bin/sh\nexit 0\n"); path.chmod(0o755)
        self.signer = self.tools / "apksigner"
        self.signer.write_text("#!/bin/sh\necho 'DOES NOT VERIFY' >&2\nexit 1\n"); self.signer.chmod(0o755)
        self.env = mock.patch.dict(os.environ, {"ANDROID_SDK_ROOT": str(self.sdk), "PHONE_FIXTURE_VERSION": "0.1.0-ci"})
        self.env.start(); self.addCleanup(self.env.stop)

    def archive(self):
        with zipfile.ZipFile(self.apk, "w") as archive:
            for name, data in self.entries.items(): archive.writestr(name, data)
        return self.apk

    def verify(self):
        return self.verifier.verify(self.archive(), source=self.source, expected_source=self.head,
                                    version_code="1", version_name="0.1.0-ci", apkanalyzer=self.analyzer,
                                    apksigner=self.signer, aapt=self.tools / "aapt", aapt2=self.tools / "aapt2")

    def test_relocated_cli_runs_actual_phone_gates_and_binds_exact_candidate(self):
        self.archive(); receipt = self.base / "receipt.json"
        command = ["python3", "-I", "-S", "-B", str(self.controller / "android/phone/native-ci/verify_apk.py"),
                   "--source", str(self.source), "--expected-source", self.head, "--apk", str(self.apk),
                   "--version-code", "1", "--version-name", "0.1.0-ci", "--apkanalyzer", str(self.analyzer),
                   "--apksigner", str(self.signer), "--aapt", str(self.tools / "aapt"), "--aapt2", str(self.tools / "aapt2"),
                   "--receipt", str(receipt)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(receipt.read_text())
        self.assertEqual(data["status"], "PHONE_UNSIGNED_CI_APK_OUTPUT_VERIFIED")
        self.assertEqual(data["candidate_sha"], self.head)
        self.assertEqual(data["apk_sha256"], hashlib.sha256(self.apk.read_bytes()).hexdigest())
        self.assertGreater(len(data["native_libraries"]), 80)
        self.assertFalse(data["device_tested"])
        command[command.index("--expected-source") + 1] = "f" * 40
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertFalse(receipt.exists(), "A rejected invocation must not leave stale success")

    def test_host_and_4k_elf_are_rejected(self):
        name = "lib/arm64-v8a/libphoneInterface.so"
        for option in ({"machine": 62}, {"alignment": 4096}):
            self.entries[name] = elf("libphoneInterface.so", **option)
            with self.assertRaises(ValueError): self.verify()

    def test_needed_closure_and_soname_are_required(self):
        name = "lib/arm64-v8a/libphoneInterface.so"
        for data in (elf("libforeign.so"), elf("libphoneInterface.so", needed=("libmissing.so",))):
            self.entries[name] = data
            with self.assertRaises(ValueError): self.verify()

    def test_actual_signing_blocks_and_jar_signatures_are_rejected(self):
        self.entries["META-INF/CERT.RSA"] = b"fixture"
        with self.assertRaisesRegex(ValueError, "v1 JAR"): self.verify()
        del self.entries["META-INF/CERT.RSA"]; self.archive()
        with zipfile.ZipFile(self.apk) as archive: central = archive.start_dir
        data = self.apk.read_bytes(); block = struct.pack("<QQ", 24, 24) + b"APK Sig Block 42"
        data = bytearray(data[:central] + block + data[central:]); eocd = data.rfind(b"PK\x05\x06")
        struct.pack_into("<I", data, eocd + 16, central + len(block)); self.apk.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "v2/v3 signing block"): self.native.unsigned_archive(self.apk)

    def test_unsafe_zip_and_missing_phone_output_fail(self):
        self.entries["../escape"] = b"bad"
        with self.assertRaisesRegex(ValueError, "Unsafe APK ZIP"): self.verify()
        del self.entries["../escape"]; del self.entries["lib/arm64-v8a/libphoneInterface.so"]
        with self.assertRaisesRegex(ValueError, "Phone native output is missing"): self.verify()

    def test_changed_source_and_wrong_version_fail(self):
        (self.source / "source.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "tracked candidate inputs changed"): self.verify()
        (self.source / "source.txt").write_text("exact candidate\n")
        os.environ["PHONE_FIXTURE_VERSION"] = "different"
        with self.assertRaisesRegex(ValueError, "metadata differs"): self.verify()

    def test_snapshot_rejects_changed_original_and_snapshot_bytes(self):
        for which in ("original", "snapshot"):
            self.archive()
            with self.assertRaisesRegex(ValueError, "APK.*changed|snapshot changed"):
                with self.native.bound_apk(self.apk) as (snapshot, checksum):
                    target = self.apk if which == "original" else snapshot
                    target.chmod(0o600); target.write_bytes(b"changed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
