#!/usr/bin/env python3
"""Verify an unsigned Pico CI APK's actual archive/native outputs, without devices."""
# SPDX-License-Identifier: Apache-2.0
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[4]


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


COMMON = load(ROOT / "android/common/native-ci/apk_native.py", "pico_android_apk_primitives")
elf_dynamic = COMMON.elf_dynamic
unsigned_archive = COMMON.unsigned_archive


def inspect_unsigned_native(apk):
    legacy = load(ROOT / "android/vr/pico/ci/verify-pico-apk.py", "pico_ci_legacy_apk_structure")
    _, _, e2e = legacy.inspect_zip(apk)
    require(not e2e, "Unsigned Release APK contains E2E OpenXR artifacts")
    unsigned_archive(apk)
    libraries = COMMON.inspect_native(apk)
    require((legacy.REQUIRED_LIBRARIES | {"libinterface.so"}) <= libraries.keys(), "Pico/OpenXR native output is missing")
    require({"libssl_3.so", "libcrypto_3.so"} <= libraries.keys(), "Canonical OpenSSL 3 APK providers missing")
    require(not any(name.startswith(("libssl", "libcrypto")) and name not in {"libssl_3.so", "libcrypto_3.so"}
                    for name in libraries), "Legacy/renamed OpenSSL APK provider")
    return libraries


def verify(apk, expected_source, *, aapt, aapt2, apkanalyzer, version_code, version_name, source=ROOT):
    require(re.fullmatch("[0-9a-f]{40}", str(expected_source)), "Missing candidate identity")
    source = source.resolve(strict=True)
    command = ["git", "--no-replace-objects", "-C", str(source)]
    require(subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip() == expected_source,
            "Pico APK candidate HEAD differs")
    require(subprocess.run(command + ["diff", "--quiet", "HEAD", "--"], check=False).returncode == 0,
            "Pico APK tracked candidate inputs changed")
    legacy = load(ROOT / "android/vr/pico/ci/verify-pico-apk.py", "pico_ci_unsigned_apk")
    # Code and network-capability policy stay in the separately pinned controller
    # layout. Only the owning candidate manifest and Git identity come from source.
    legacy.PICO_MANIFEST = source / "android/vr/pico/apps/picoInterface/src/main/AndroidManifest.xml"
    with COMMON.bound_apk(apk) as (snapshot, digest):
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
    parser.add_argument("--source", type=Path, default=ROOT,
                        help="Actual candidate checkout, separate from protected verifier/support code")
    parser.add_argument("--version-code", required=True)
    parser.add_argument("--version-name", required=True)
    parser.add_argument("--aapt", required=True)
    parser.add_argument("--aapt2", required=True)
    parser.add_argument("--apkanalyzer", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.apk, args.expected_source, aapt=args.aapt, aapt2=args.aapt2,
                    apkanalyzer=args.apkanalyzer, version_code=args.version_code, version_name=args.version_name,
                    source=args.source)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
