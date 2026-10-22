#!/usr/bin/env python3
"""Report missing Android native qualification before expensive CI execution.

This read-only classifier does not resolve dependencies or claim build success.
A future qualified producer/consumer must replace the explicit missing state;
passing an arbitrary manifest or setting an environment variable cannot do so.
"""
from pathlib import PurePosixPath

TARGETS = ("main", "apple-main", "apple-ios", "android-main", "android-phone",
           "android-vr", "android-vr-pico")
ANDROID_TARGETS = frozenset(TARGETS[3:])
PRODUCT_ROOTS = ("interface/", "libraries/", "plugins/", "resources/", "cmake/", "security/")
NATIVE_SUFFIXES = frozenset({".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
                           ".in", ".cmake", ".qrc", ".qml", ".vert", ".frag", ".glsl"})
ROOT_BUILD_INPUTS = frozenset({"CMakeLists.txt", "conanfile.py", "conan.lock", ".gitmodules",
                              ".github/dependency-releases.json"})
HOST_TEST_ROOTS = ("android/phone/tests/", "android/vr/pico/tests/", "android/common/tests/",
                   "android/common/web/tests/", "android/common/snapshot/tests/", "android/common/documents/tests/")
# These are exact entrypoints in the trusted platform suite registry. Naming a
# new production file test_*.py does not create a qualification exemption.
HOST_TEST_FILES = frozenset({"android/common/conan/test_package_store.py",
    "android/common/conan/test_package_folder.py", "android/phone/fdroid/profiles/test_doctor.py",
    "android/phone/fdroid/conan/test_stage_host_tools.py", "android/phone/device-tests/parity/test_packet.py"})
BUILD_WORKFLOWS = frozenset({".github/workflows/android-phone-build.yml", ".github/workflows/pico4-build.yml"})
JAVA_ROOTS = ("android/phone/apps/phoneInterface/src/main/", "android/vr/pico/apps/picoInterface/src/main/",
              "android/common/libraries/qt/src/main/")
SHARED_JAVA_ROOTS = ("android/common/web/", "android/common/snapshot/", "android/common/documents/")
PRODUCER = {
    "entrypoint": "android/phone/fdroid/scripts/cold-build.sh",
    "read_only_preflight": ["bash", "android/phone/fdroid/scripts/cold-build.sh", "--preflight"],
    "dependency_executor": "android/phone/fdroid/scripts/build-dependencies.sh",
    "pico_consumer": "android/vr/pico/release/pico-source-inputs.py",
    "documentation": "android/vr/pico/release/SOURCE_INPUTS.md",
    "minimum_free_bytes": 60000000000,
    "toolchain_image_id": "sha256:1b2da099cf7c03f6ea4b751cf8f148784f12db71fdaabb2b6330d60ba1572dda",
    "note": "The existing source-only producer is not a completed or hosted-qualified Android graph.",
}
MISSING = (
    {"id": "qualified-current-android-dependency-graph",
     "detail": "Completed bootstrap/host-tools/target graph with source closure, package revisions and original producer receipts; historical release archives alone are insufficient."},
    {"id": "immutable-hosted-android-build-runtime",
     "detail": "Checksum-bound SDK36/build-tools36.0.0/NDK27.3.13750724/JDK/Gradle and actual matching host tools; the current recipe must not resolve or build missing dependencies during a PR."},
    {"id": "exact-source-android-native-apk-qualification",
     "detail": "Successful actual target application compilation/package verification for the exact candidate; Java/resource compilation and Linux native tests do not supply this result."},
)


def _java_resource_input(path):
    if path.startswith("security/redaction/java/") and path.endswith(".java"):
        return True
    for root in (*JAVA_ROOTS, *SHARED_JAVA_ROOTS):
        if path.startswith(root + "java/") and path.endswith(".java"):
            return True
        if path.startswith(root + "res/") or path == root + "AndroidManifest.xml":
            return True
    return False


def classify(paths, *, target):
    """Return a deterministic prerequisite report from complete changed paths.

    Include deleted paths as well as additions. This reports requirements only;
    it never turns an unavailable Android native build into successful evidence.
    """
    if target not in TARGETS or type(paths) not in (list, tuple) or len(paths) > 100000:
        raise ValueError("unsupported Android prerequisite context")
    for path in paths:
        if (type(path) is not str or not path or any(char in path for char in "\\\0\n\r")
                or path.startswith("/") or any(part in ("", ".", "..") for part in path.split("/"))):
            raise ValueError("canonical changed paths are required")
    relevant = []
    if target in ANDROID_TARGETS:
        for path in sorted(set(paths)):
            relative = PurePosixPath(path)
            if path.endswith((".md", ".markdown")) or path.startswith("tests/"):
                continue
            if path.startswith(HOST_TEST_ROOTS) or path in HOST_TEST_FILES:
                continue
            if _java_resource_input(path):
                continue
            if path in ROOT_BUILD_INPUTS or path in BUILD_WORKFLOWS:
                relevant.append(path)
            elif path.startswith("android/"):
                # Unknown production extensions may influence packaging or a
                # transitive source/dependency graph. Never silently waive them.
                relevant.append(path)
            elif path.startswith(PRODUCT_ROOTS) and (relative.suffix.lower() in NATIVE_SUFFIXES
                    or relative.name == "CMakeLists.txt"):
                relevant.append(path)
    required = bool(relevant)
    return {"schema": 1, "target": target,
            "status": "missing-android-native-prerequisites" if required else "not-required",
            "native_qualification_required": required,
            "paths": relevant, "missing": [dict(item) for item in MISSING] if required else [],
            "producer": dict(PRODUCER) if required else None,
            "execution": False, "build_qualified": False}
