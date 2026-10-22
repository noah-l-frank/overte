#!/usr/bin/env python3
"""Verify an unsigned Pico CI APK's actual archive/native outputs, without devices."""
# SPDX-License-Identifier: Apache-2.0
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[4]
SYSTEM_LIBRARIES = frozenset({
    "libc.so", "libm.so", "libdl.so", "liblog.so", "libandroid.so", "libEGL.so",
    "libGLESv1_CM.so", "libGLESv2.so", "libGLESv3.so", "libOpenSLES.so", "libjnigraphics.so",
    "libz.so", "libvulkan.so", "libmediandk.so", "libnativewindow.so", "libcamera2ndk.so", "libaaudio.so",
})
MAX_LIBRARY = 512 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def elf_dynamic(path):
    common = load(ROOT / "android/common/native-ci/verify.py", "pico_apk_common_elf")
    common.android_elf(path)
    require(path.stat().st_size <= MAX_LIBRARY, "Oversized APK native library")
    with path.open("rb") as stream:
        header = struct.unpack("<16sHHIQQQIHHHHHH", stream.read(64))
        loads, dynamics = [], []
        for number in range(header[10]):
            stream.seek(header[5] + number * header[9])
            row = struct.unpack("<IIQQQQQQ", stream.read(56))
            if row[0] == 1: loads.append(row)
            if row[0] == 2: dynamics.append(row)
        require(len(dynamics) == 1, "Expected one ELF dynamic table")
        dynamic = dynamics[0]
        require(0 < dynamic[5] <= 16 * 1024 * 1024 and dynamic[5] % 16 == 0 and
                dynamic[2] + dynamic[5] <= path.stat().st_size, "Invalid ELF dynamic bounds")
        stream.seek(dynamic[2])
        entries, terminated = {}, False
        for _ in range(dynamic[5] // 16):
            tag, value = struct.unpack("<qQ", stream.read(16))
            if tag == 0:
                terminated = True
                break
            entries.setdefault(tag, []).append(value)
        require(terminated and len(entries.get(5, [])) == 1 and len(entries.get(10, [])) == 1 and
                len(entries.get(14, [])) == 1, "Missing/ambiguous ELF SONAME/string table")
        address, size = entries[5][0], entries[10][0]
        require(0 < size <= 16 * 1024 * 1024, "Invalid ELF string table size")
        mappings = [row for row in loads if row[3] <= address and address + size <= row[3] + row[5]]
        require(len(mappings) == 1, "ELF string table is not in one file-backed LOAD segment")
        row = mappings[0]
        stream.seek(row[2] + address - row[3])
        strings = stream.read(size)
        require(len(strings) == size, "Truncated ELF string table")

    def name(offset):
        require(0 <= offset < len(strings), "ELF dynamic string escaped")
        end = strings.find(b"\0", offset)
        require(end > offset, "Invalid ELF dynamic string")
        value = strings[offset:end].decode("ascii")
        require(re.fullmatch(r"[A-Za-z0-9_.+-]+[.]so(?:[.][0-9]+)*", value), "Unsafe ELF dynamic library name")
        return value

    needed = [name(offset) for offset in entries.get(1, [])]
    require(len(needed) == len(set(needed)), "Duplicate ELF NEEDED entries")
    return {"soname": name(entries[14][0]), "needed": sorted(needed), "sha256": common.digest(path)}


def unsigned_archive(apk):
    """Refuse JAR signatures and the actual APK v2/v3 signing-block location."""
    with zipfile.ZipFile(apk) as archive:
        for name in archive.namelist():
            upper = name.upper()
            require(not (upper.startswith("META-INF/") and upper.endswith((".SF", ".RSA", ".DSA", ".EC"))),
                    "CI APK contains a v1 JAR signature")
        central = archive.start_dir
    with apk.open("rb") as stream:
        if central >= 16:
            stream.seek(central - 16)
            require(stream.read(16) != b"APK Sig Block 42", "CI APK contains an APK v2/v3 signing block")


def inspect_unsigned_native(apk):
    legacy = load(ROOT / "android/vr/pico/ci/verify-pico-apk.py", "pico_ci_legacy_apk_structure")
    _, _, e2e = legacy.inspect_zip(apk)
    require(not e2e, "Unsigned Release APK contains E2E OpenXR artifacts")
    unsigned_archive(apk)
    libraries = {}
    with zipfile.ZipFile(apk) as archive, tempfile.TemporaryDirectory(prefix="pico-ci-native-") as temp:
        for entry in archive.infolist():
            if not entry.filename.startswith("lib/") or entry.is_dir():
                continue
            parts = entry.filename.split("/")
            require(len(parts) == 3 and parts[1] == "arm64-v8a" and parts[2].endswith(".so"),
                    "Unexpected APK native ABI/path")
            require(entry.file_size <= MAX_LIBRARY, "Oversized APK native library")
            path = Path(temp) / parts[2]
            with archive.open(entry) as source, path.open("xb") as output:
                total = 0
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    total += len(chunk)
                    require(total <= MAX_LIBRARY, "Oversized extracted APK library")
                    output.write(chunk)
            info = elf_dynamic(path)
            require(info["soname"] == parts[2], "Packaged filename and ELF SONAME differ")
            libraries[parts[2]] = info
            path.unlink()
    require((legacy.REQUIRED_LIBRARIES | {"libinterface.so"}) <= libraries.keys(), "Pico/OpenXR native output is missing")
    require({"libssl_3.so", "libcrypto_3.so"} <= libraries.keys(), "Canonical OpenSSL 3 APK providers missing")
    require(not any(name.startswith(("libssl", "libcrypto")) and name not in {"libssl_3.so", "libcrypto_3.so"}
                    for name in libraries), "Legacy/renamed OpenSSL APK provider")
    for name, info in libraries.items():
        require(set(info["needed"]) <= libraries.keys() | SYSTEM_LIBRARIES,
                "Packaged ELF has a missing non-platform dependency: " + name)
    return libraries


def verify(apk, expected_source, *, aapt, aapt2, apkanalyzer, version_code, version_name):
    require(re.fullmatch("[0-9a-f]{40}", str(expected_source)), "Missing candidate identity")
    command = ["git", "--no-replace-objects", "-C", str(ROOT)]
    require(subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip() == expected_source,
            "Pico APK candidate HEAD differs")
    require(subprocess.run(command + ["diff", "--quiet", "HEAD", "--"], check=False).returncode == 0,
            "Pico APK tracked candidate inputs changed")
    legacy = load(ROOT / "android/vr/pico/ci/verify-pico-apk.py", "pico_ci_unsigned_apk")
    with legacy.bound_apk(apk) as (snapshot, digest):
        libraries = inspect_unsigned_native(snapshot)
        badging = legacy.run_tool([aapt, "dump", "badging", str(snapshot)])
        metadata = legacy.parse_badging(badging)
        require(metadata["version_code"] == version_code and metadata["version_name"] == version_name,
                "Pico CI APK version identity differs")
        require(not re.search(r"^application-debuggable(?:\s|$)", badging, re.MULTILINE), "Pico Release APK is debuggable")
        args = argparse.Namespace(apk=snapshot, apkanalyzer=apkanalyzer, aapt2=aapt2)
        network = legacy._verify_network_policy(args)
        tree = subprocess.check_output(command + ["rev-parse", "HEAD^{tree}"], text=True).strip()
        require(subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip() == expected_source and
                subprocess.run(command + ["diff", "--quiet", "HEAD", "--"], check=False).returncode == 0,
                "Pico candidate changed during APK verification")
        return {"schema": 1, "status": "PICO_UNSIGNED_CI_APK_OUTPUT_VERIFIED", "candidate_sha": expected_source,
                "candidate_tree": tree, "apk_sha256": digest, "unsigned": True,
                "metadata": metadata, "native_libraries": libraries, "native_page_size": 16384,
                "network_policy": network, "device_tested": False,
                "external_binding_required": "Authenticated actual native build invocation and runtime/package provenance"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--version-code", required=True)
    parser.add_argument("--version-name", required=True)
    parser.add_argument("--aapt", required=True)
    parser.add_argument("--aapt2", required=True)
    parser.add_argument("--apkanalyzer", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.apk, args.expected_source, aapt=args.aapt, aapt2=args.aapt2,
                    apkanalyzer=args.apkanalyzer, version_code=args.version_code, version_name=args.version_name)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
