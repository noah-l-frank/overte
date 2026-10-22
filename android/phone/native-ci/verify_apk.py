#!/usr/bin/env python3
"""Verify an owning unsigned Phone CI APK using protected acceptance code."""
# SPDX-License-Identifier: Apache-2.0
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = "io.github.noah_be.overte.phone"


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    spec = importlib.util.spec_from_file_location("phone_android_apk_primitives", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate(source, expected):
    require(re.fullmatch("[0-9a-f]{40}", str(expected)), "Missing authenticated Phone candidate SHA")
    command = ["git", "--no-replace-objects", "-C", str(source)]
    require(subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip() == expected,
            "Phone candidate HEAD differs")
    require(subprocess.run(command + ["diff", "--quiet", "HEAD", "--"], check=False).returncode == 0,
            "Phone tracked candidate inputs changed")
    return subprocess.check_output(command + ["rev-parse", "HEAD^{tree}"], text=True).strip()


def tool_identity(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file() and os.access(path, os.X_OK), "Phone SDK tool is not executable")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def legacy_gate(snapshot, head, directory, *, apkanalyzer, apksigner):
    """Execute the unchanged, separately pinned owning Phone package gates."""
    output = directory / "legacy-phone-receipt.json"
    environment = dict(os.environ)
    environment["PHONE_APK_VERIFY_TMPDIR"] = str(directory / "phone-apk-tmp")
    command = [sys.executable, "-I", "-S", "-B", str(ROOT / "android/phone/ci/verify-phone-apk.py"),
               str(snapshot), "--package-gate", str(ROOT / "android/phone/tests/check-phone-apk-16k.sh"),
               "--apkanalyzer", str(apkanalyzer), "--apksigner", str(apksigner),
               "--expect-debuggable", "0", "--expect-unsigned", "--source-revision", head,
               "--output", str(output)]
    with (directory / "legacy-gate.log").open("wb") as log:
        process = subprocess.Popen(command, env=environment, stdout=log, stderr=log, start_new_session=True)
        try:
            code = process.wait(timeout=600)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=10)
            raise
    require(code == 0 and output.is_file() and not output.is_symlink(), "Protected Phone package/signature gate failed")
    require(output.stat().st_size <= 1024 * 1024, "Phone package receipt exceeds bound")
    return json.loads(output.read_text())


def verify(apk, *, source, expected_source, version_code, version_name, apkanalyzer, apksigner, aapt, aapt2):
    source = source.resolve(strict=True)
    tree = candidate(source, expected_source)
    require(re.fullmatch("[1-9][0-9]*", str(version_code)) and int(version_code) <= 2147483647,
            "Invalid expected Phone version code")
    require(re.fullmatch("[A-Za-z0-9][A-Za-z0-9._+-]{0,99}", str(version_name)), "Invalid expected Phone version name")
    tools = {name: tool_identity(path) for name, path in
             (("apkanalyzer", apkanalyzer), ("apksigner", apksigner), ("aapt", aapt), ("aapt2", aapt2))}
    native = load(ROOT / "android/common/native-ci/apk_native.py")
    with native.bound_apk(apk) as (snapshot, checksum):
        native.unsigned_archive(snapshot)
        libraries = native.inspect_native(snapshot)
        require({"libphoneInterface.so", "libinterface.so", "libc++_shared.so", "libssl_3.so", "libcrypto_3.so"}
                <= libraries.keys(), "Phone native output is missing")
        require(not any(name.startswith(("libpico", "libXrApiLayer", "libssl", "libcrypto")) and
                        name not in {"libssl_3.so", "libcrypto_3.so"} for name in libraries),
                "Foreign product, E2E or legacy SSL native output")
        metadata = legacy_gate(snapshot, expected_source, snapshot.parent, apkanalyzer=apkanalyzer, apksigner=apksigner)
        require(metadata.get("sha256") == checksum and metadata.get("size_bytes") == snapshot.stat().st_size,
                "Phone package receipt differs from private snapshot")
        require(metadata.get("package") == PACKAGE and metadata.get("version_code") == int(version_code) and
                metadata.get("version_name") == version_name and metadata.get("min_sdk") == 26 and
                metadata.get("target_sdk") == 36 and metadata.get("debuggable") is False,
                "Phone APK product/version/Release metadata differs")
        require(metadata.get("signing_state") == "unsigned" and metadata.get("signature_verified") is False and
                metadata.get("source_revision") == expected_source and metadata.get("package_gate") == "phone-16k",
                "Phone unsigned package gate provenance differs")
        require(candidate(source, expected_source) == tree, "Phone candidate changed during APK verification")
        for name, path in (("apkanalyzer", apkanalyzer), ("apksigner", apksigner), ("aapt", aapt), ("aapt2", aapt2)):
            require(tool_identity(path) == tools[name], "Phone SDK tool changed during verification")
        result = {"schema": 1, "status": "PHONE_UNSIGNED_CI_APK_OUTPUT_VERIFIED", "candidate_sha": expected_source,
                  "candidate_tree": tree, "apk_sha256": checksum, "unsigned": True, "metadata": metadata,
                  "native_libraries": libraries, "native_page_size": 16384, "sdk_tools_sha256": tools,
                  "device_tested": False,
                  "external_binding_required": "Authenticated actual native build invocation and runtime/package provenance"}
    # The snapshot context closes and rechecks both original and private bytes
    # before this result is allowed to leave the verifier.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--version-code", required=True)
    parser.add_argument("--version-name", required=True)
    for name in ("apkanalyzer", "apksigner", "aapt", "aapt2"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    require(not args.receipt.is_symlink() and (not args.receipt.exists() or args.receipt.is_file()), "Unsafe Phone receipt path")
    args.receipt.unlink(missing_ok=True)
    result = verify(args.apk, source=args.source, expected_source=args.expected_source,
                    version_code=args.version_code, version_name=args.version_name, apkanalyzer=args.apkanalyzer,
                    apksigner=args.apksigner, aapt=args.aapt, aapt2=args.aapt2)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, zipfile.BadZipFile, subprocess.SubprocessError):
        print("PHONE_UNSIGNED_CI_APK_REJECTED", file=sys.stderr)
        raise SystemExit(2)
