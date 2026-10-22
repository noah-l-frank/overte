#!/usr/bin/env python3
"""Consume a separately authenticated immutable Android runtime offline.

The host controller owns provenance and authorization. This PID-1 worker checks
its sealed inputs, executes fixed owning build vectors, stops candidate children,
and joins protected output verification to the actual successful invocation.
No Conan command, dependency producer or network operation is exposed here.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time

KIND = "overte-android-offline-consumer-v1"
SHA = re.compile(r"[0-9a-f]{64}")
GIT_SHA = re.compile(r"[0-9a-f]{40}")
TOOLS = frozenset({"moc", "rcc", "uic", "qmake", "scribe", "glslangValidator", "spirv-cross", "spirv-opt"})
COMMON_INTENT = frozenset({
    "conanfile.py", "android/common/conan/conanfile-pico.py",
    "android/common/conan/patches/qt-pico-android-runtime.patch",
    "android/common/cmake/overte-android-bootstrap.cmake", "android/common/cmake/overte-android-toolchain.cmake",
    "android/common/native-ci/target.conanfile.py", "android/common/native-ci/android-arm64-ci",
    "android/common/native-ci/qt-host-tools.cmake",
})
PICO_INTENT = COMMON_INTENT | frozenset({
    "android/common/native-ci/verify.py", "android/common/native-ci/CMakeLists.txt",
    "android/vr/pico/native-ci/target.conanfile.py", "android/vr/pico/native-ci/android-arm64-ci-release",
    "android/vr/pico/native-ci/graph_contract.py", "android/vr/pico/native-ci/inputs.py",
    "android/vr/pico/native-ci/source-inputs.groovy", "android/vr/pico/conan/openxr-16k",
    "android/vr/pico/cmake/pico-source-bootstrap.cmake", "android/vr/pico/cmake/pico-qt-host-tools.cmake",
    "android/vr/pico/apps/picoInterface/build.gradle", "android/vr/pico/settings.gradle",
    "android/vr/pico/build.gradle", "android/common/gradle/wrapper/gradle-wrapper.properties",
    "android/vr/pico/apps/picoInterface/src/main/res/values/qt_dependencies.xml",
})
PHONE_INTENT = frozenset({
    "conanfile.py", "android/phone/settings.gradle", "android/phone/build.gradle",
    "android/phone/gradle.properties", "android/phone/apps/phoneInterface/build.gradle",
    "android/phone/apps/phoneInterface/src/main/res/values/qt_dependencies.xml",
    "android/common/gradle/wrapper/gradle-wrapper.properties",
    "android/phone/tests/verify-phone-16k-dependencies.sh",
    "android/phone/tests/check-phone-elf-alignment.sh",
})
REQUIRED_CODE = {
    "common": {"android/common/native-ci/verify.py"},
    "pico": {"android/vr/pico/native-ci/verify_apk.py", "android/vr/pico/ci/verify-pico-apk.py",
             "android/common/native-ci/verify.py", "android/common/web/network_policy.py",
             "android/common/web/network-capability.json",
             "android/common/web/res/xml/overte_embedded_web_network_security_config.xml"},
    "phone": {"android/phone/native-ci/verify_apk.py", "android/common/native-ci/apk_native.py",
              "android/common/native-ci/verify.py", "android/phone/ci/verify-phone-apk.py",
              "android/phone/tests/check-phone-apk-16k.sh", "android/phone/tests/check-phone-apk-metadata.sh",
              "android/phone/tests/check-phone-apk-contents.py", "android/phone/tests/check-phone-elf-alignment.sh",
              "android/phone/tests/check-phone-apk-padding.py",
              "android/phone/apps/phoneInterface/src/main/res/values/qt_dependencies.xml"},
}
PATH = ("/usr/lib/jvm/java-17-openjdk-amd64/bin:/opt/android-sdk/build-tools/36.0.0:"
        "/opt/android-sdk/ndk/27.3.13750724/toolchains/llvm/prebuilt/linux-x86_64/bin:"
        "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")


class PrerequisiteError(ValueError):
    """Known unqualified prerequisite; never a successful merge gate."""


class Roots:
    def __init__(self, *, source="/attempt/source", attempt="/attempt", prepared="/prepared",
                 sdk="/opt/android-sdk", controller="/ci-controller", proof="/qualification", scratch="/scratch"):
        self.source, self.attempt, self.prepared, self.sdk, self.controller, self.proof, self.scratch = (
            Path(p) for p in (source, attempt, prepared, sdk, controller, proof, scratch))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate consumer JSON field")
            result[key] = value
        return result
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 150_000_000,
            "missing, linked or oversized consumer JSON")
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def relative(value):
    require(type(value) is str and value and not value.startswith("/") and "\\" not in value
            and all(part not in {"", ".", ".."} for part in value.split("/"))
            and not any(ord(c) < 32 for c in value), "unsafe consumer relative path")
    return value


def ordinary(path, root):
    path, root = Path(path), Path(root)
    require(path.is_absolute() and path.is_relative_to(root) and ".." not in path.parts,
            "consumer input escaped its root")
    require(not path.is_symlink() and path.is_file() and path.resolve(strict=True).is_relative_to(root),
            "consumer input is not a confined ordinary file")
    require(all(not parent.is_symlink() for parent in path.parents if parent != root.parent),
            "consumer input has a linked ancestor")
    return path


def bound_ref(item, roots):
    require(type(item) is dict and set(item) == {"path", "sha256"}
            and type(item["path"]) is str and type(item["sha256"]) is str and SHA.fullmatch(item["sha256"]),
            "invalid protected consumer reference")
    path = ordinary(item["path"], roots.proof)
    require(sha(path) == item["sha256"], "protected consumer reference changed")
    return path


def git(roots, *args):
    return subprocess.check_output(["/usr/bin/git", "--no-replace-objects", "-C", str(roots.source), *args],
                                   env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1",
                                        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0"}, stderr=subprocess.PIPE)


def source_identity(roots, head, tree):
    require(git(roots, "rev-parse", "HEAD").decode().strip() == head
            and git(roots, "rev-parse", "HEAD^{tree}").decode().strip() == tree,
            "consumer candidate HEAD/tree changed")
    require(not git(roots, "diff", "--no-ext-diff", "--no-textconv", "HEAD", "--"),
            "consumer tracked candidate source changed")


def controller_identity(roots, files, product):
    require(type(files) is dict and files and len(files) <= 256, "invalid protected controller files")
    required = REQUIRED_CODE[product] | {"tools/repository-checks/pr_ci_android_worker.py",
                                         "tools/repository-checks/pr_ci_android_runtime.py"}
    require(required <= files.keys(), "protected controller bundle is incomplete")
    actual = set()
    for path in roots.controller.rglob("*"):
        require(not path.is_symlink(), "linked controller entry")
        if path.is_dir():
            continue
        require(stat.S_ISREG(path.stat().st_mode), "special controller entry")
        actual.add(path.relative_to(roots.controller).as_posix())
    require(actual == files.keys(), "protected controller membership changed")
    for name, digest in files.items():
        relative(name)
        require(type(digest) is str and SHA.fullmatch(digest)
                and sha(ordinary(roots.controller / name, roots.controller)) == digest,
                "protected controller bytes changed")


def dependency_identity(roots, files, product, head):
    require(type(files) is dict and 0 < len(files) <= 1024, "invalid frozen dependency declaration closure")
    require({"common": COMMON_INTENT, "phone": PHONE_INTENT, "pico": PICO_INTENT}[product] <= files.keys(),
            "incomplete frozen dependency declaration closure")
    for name, digest in files.items():
        relative(name)
        require(type(digest) is str and SHA.fullmatch(digest), "invalid dependency declaration digest")
        file = ordinary(roots.source / name, roots.source)
        mode = git(roots, "ls-tree", head, "--", name).decode().split(" ", 1)[0]
        require(mode in {"100644", "100755"} and sha(file) == digest
                and hashlib.sha256(git(roots, "cat-file", "blob", head + ":" + name)).hexdigest() == digest,
                "frozen dependency declaration changed; prepare a new runtime")


def load_runtime(roots):
    spec = importlib.util.spec_from_file_location("android_sealed_payload", roots.controller / "tools/repository-checks/pr_ci_android_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(product, head, config_path, config_sha256, *, roots=None):
    """Read-only admission; no candidate program or scratch creation occurs."""
    roots = roots or Roots()
    require(product in REQUIRED_CODE and type(head) is str and GIT_SHA.fullmatch(head), "invalid Android consumer identity")
    require(type(config_sha256) is str and SHA.fullmatch(config_sha256), "protected consumer config digest required")
    config_path = ordinary(config_path, roots.proof)
    require(sha(config_path) == config_sha256, "protected consumer configuration changed")
    config = read(config_path)
    require(type(config) is dict and set(config) == {"kind", "product", "candidate_tree", "dependency_intent",
            "runtime_inventory", "sdk_inventory", "controller_files", "tools", "gradle_seed", "product_map", "apkanalyzer"}
            and config["kind"] == KIND and config["product"] == product
            and type(config["candidate_tree"]) is str and GIT_SHA.fullmatch(config["candidate_tree"]),
            "invalid protected consumer configuration")
    controller_identity(roots, config["controller_files"], product)
    source_identity(roots, head, config["candidate_tree"])
    dependency_identity(roots, config["dependency_intent"], product, head)
    require(not git(roots, "ls-files", "--others", "--directory"),
            "consumer candidate contains pre-existing untracked build inputs")
    runtime = load_runtime(roots)
    runtime.verify(roots.prepared, bound_ref(config["runtime_inventory"], roots), config["runtime_inventory"]["sha256"])
    runtime.verify(roots.sdk, bound_ref(config["sdk_inventory"], roots), config["sdk_inventory"]["sha256"])
    # Both mounts must expose the same actual immutable payload, not a second
    # verified-but-unused copy while /attempt resolves candidate-controlled bytes.
    require(roots.attempt.samefile(roots.prepared), "consumer payload mount is not the verified unshadowed payload")
    require(type(config["tools"]) is dict and config["tools"].keys() == TOOLS, "incomplete protected host tools")
    for path in config["tools"].values():
        require(type(path) is str, "invalid protected host tool path")
        file = Path(path)
        require(file.is_absolute() and file.is_relative_to(roots.attempt)
                and not file.is_relative_to(roots.source) and file.resolve(strict=True).is_relative_to(roots.attempt)
                and not file.resolve().is_relative_to(roots.source) and file.is_file() and os.access(file, os.X_OK),
                "host tool escaped the sealed payload")
    require(roots.scratch.is_dir() and not roots.scratch.is_symlink() and not any(roots.scratch.iterdir()),
            "consumer scratch must be fresh and empty")
    if product == "common":
        require(config["gradle_seed"] is None and config["product_map"] is None and config["apkanalyzer"] is None,
                "common consumer does not accept product APK inputs")
    else:
        require(config["gradle_seed"] == str(roots.attempt / "gradle-home")
                and (roots.attempt / "gradle-home").is_dir() and not (roots.attempt / "gradle-home").is_symlink(),
                "missing exact prepared Gradle seed")
        require(config["apkanalyzer"] == str(roots.sdk / "cmdline-tools/22.0/bin/apkanalyzer"),
                "unreviewed APK analyzer location")
        ordinary(config["apkanalyzer"], roots.sdk)
        if product == "pico":
            require(config["product_map"] is not None, "missing protected Pico product map")
            require(bound_ref(config["product_map"], roots) == roots.proof / "product-inputs-pico.json",
                    "unreviewed Pico product map location")
        else:
            require(config["product_map"] is None, "Phone cannot consume a Pico product map")
    return roots, config, runtime


def environment(product, config, roots):
    env = {"PATH": PATH, "HOME": str(roots.scratch / "home"), "TMPDIR": str(roots.scratch / "tmp"),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC", "CI": "true",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0",
           "JAVA_HOME": "/usr/lib/jvm/java-17-openjdk-amd64", "ANDROID_SDK_ROOT": str(roots.sdk),
           "ANDROID_HOME": str(roots.sdk), "ANDROID_NDK_HOME": str(roots.sdk / "ndk/27.3.13750724"),
           "GRADLE_USER_HOME": str(roots.scratch / "gradle-home"), "CONAN_HOME": str(roots.attempt / "conan"),
           "OVERTE_QT_COMPOSED_SOURCE": str(roots.attempt / "qt-composed"),
           "CMAKE_BUILD_PARALLEL_LEVEL": "2", "MAKEFLAGS": "-j2", "PICO_BUILD_JOBS": "2",
           "OMP_NUM_THREADS": "2", "OMP_THREAD_LIMIT": "2"}
    if product in {"common", "phone"}:
        env["OVERTE_FDROID_CONAN_DIR"] = str(roots.attempt / "target-continuation")
    if product == "phone":
        env["PHONE_VERIFY_TMPDIR"] = str(roots.scratch / "phone-verify-tmp")
        env["PHONE_APK_VERIFY_TMPDIR"] = str(roots.scratch / "phone-apk-tmp")
    if product == "pico":
        env.update(PICO_CI_INPUTS_SHA256=config["product_map"]["sha256"], PICO_EXPECTED_SOURCE_SHA=config["expected_head"])
    return env


def vectors(product, head, config, roots):
    source, scratch, sdk, controller = map(str, (roots.source, roots.scratch, roots.sdk, roots.controller))
    verify = controller + "/android/common/native-ci/verify.py"
    if product == "common":
        build = scratch + "/common-native-build"
        configure = ["cmake", "-S", source, "-B", build, "-G", "Ninja", "-DANDROID=ON",
            "-DOVERTE_ANDROID_COMMON_NATIVE=ON", "-DANDROID_ABI=arm64-v8a", "-DANDROID_PLATFORM=android-26",
            "-DANDROID_STL=c++_shared", "-DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON",
            "-DCMAKE_TOOLCHAIN_FILE=" + sdk + "/ndk/27.3.13750724/build/cmake/android.toolchain.cmake",
            "-DCMAKE_BUILD_TYPE=RelWithDebInfo", "-DCMAKE_MAKE_PROGRAM=/usr/bin/ninja",
            "-DCMAKE_C_FLAGS=-O2 -falign-functions=32 -fPIC -D__BIONIC_NO_PAGE_SIZE_MACRO",
            "-DCMAKE_CXX_FLAGS=-O2 -falign-functions=32 -fPIC -D__BIONIC_NO_PAGE_SIZE_MACRO",
            "-DCMAKE_CXX_SCAN_FOR_MODULES=OFF",
            "-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384",
            "-DCMAKE_EXE_LINKER_FLAGS=-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384",
            "-DHIFI_ANDROID_CONAN_GENERATORS=" + str(roots.attempt / "target-continuation/generators"),
            "-DCMAKE_PREFIX_PATH=" + str(roots.attempt / "target-continuation/generators"),
            "-DCMAKE_MODULE_PATH=" + source + "/android/common/cmake/android-modules;" + str(roots.attempt / "target-continuation/generators"),
            "-DCMAKE_FIND_PACKAGE_PREFER_CONFIG=ON", "-DUSE_BREAKPAD=OFF", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]
        configure += ["-DOVERTE_ANDROID_CI_" + name.upper() + "=" + config["tools"][name] for name in ("moc", "rcc", "uic", "qmake")]
        return {"query": [sys.executable, "-I", "-S", "-B", verify, "--query", "--build", build],
                "candidate": [configure, ["cmake", "--build", build, "--target", "overte-android-common-native", "--parallel", "2"]],
                "verify": [sys.executable, "-I", "-S", "-B", verify, "--source", source, "--build", build,
                           "--expected-head", head, "--receipt", scratch + "/common-native-receipt.json"],
                "receipt": scratch + "/common-native-receipt.json"}
    owner = "android/phone" if product == "phone" else "android/vr/pico"
    app = "phoneInterface" if product == "phone" else "picoInterface"
    version = "0.1.0-ci"
    command = [source + "/android/common/gradlew", "--offline", "--no-daemon", "--settings-file", source + "/" + owner + "/settings.gradle",
               "-p", source + "/" + owner, "-PVERSION_CODE=1", "-PRELEASE_NUMBER=" + version,
               "-Pandroid.aapt2FromMavenOverride=" + sdk + "/build-tools/36.0.0/aapt2", ":" + app + ":assembleRelease", "--max-workers=2"]
    if product == "pico":
        command.insert(-2, "-PPICO_UNSIGNED=1")
    apk = source + "/" + owner + "/apps/" + app + "/build/outputs/apk/release/" + app + "-release-unsigned.apk"
    verifier = "/android/phone/native-ci/verify_apk.py" if product == "phone" else "/android/vr/pico/native-ci/verify_apk.py"
    receipt = scratch + ("/phone-native-apk-receipt.json" if product == "phone" else "/pico-unsigned-receipt.json")
    verify = [sys.executable, "-I", "-S", "-B", controller + verifier,
              "--source", source, "--apk", apk, "--expected-source", head, "--version-code", "1", "--version-name", version,
              "--aapt", sdk + "/build-tools/36.0.0/aapt", "--aapt2", sdk + "/build-tools/36.0.0/aapt2",
              "--apkanalyzer", config["apkanalyzer"], "--receipt", receipt]
    if product == "phone":
        verify += ["--apksigner", sdk + "/build-tools/36.0.0/apksigner"]
    return {"query": None, "candidate": [command], "apk": apk, "receipt": receipt, "verify": verify}


def stop_candidate_processes():
    """PID-1-only cleanup also catches children that escaped their process group."""
    require(os.getpid() == 1, "consumer worker must be PID 1 in its private PID namespace")
    deadline = time.monotonic() + 10
    while True:
        others = []
        for path in Path("/proc").iterdir():
            if not path.name.isdigit() or int(path.name) == 1:
                continue
            try:
                if path.stat().st_uid == os.getuid():
                    others.append(int(path.name))
            except FileNotFoundError:
                pass
        for pid in others:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        while True:
            try:
                if os.waitpid(-1, os.WNOHANG)[0] == 0:
                    break
            except ChildProcessError:
                break
        # A process may fork between enumeration and SIGKILL. Rescan rather
        # than only checking the old PID set before granting a quiet namespace.
        remaining = []
        for path in Path("/proc").iterdir():
            if path.name.isdigit() and int(path.name) != 1:
                try:
                    if path.stat().st_uid == os.getuid():
                        remaining.append(path.name)
                except FileNotFoundError:
                    pass
        if not remaining:
            return
        require(time.monotonic() < deadline, "candidate child processes did not stop")
        time.sleep(.01)


def invoke(command, roots, env):
    try:
        result = subprocess.run(command, cwd=roots.source, env=env, start_new_session=True, check=False)
    finally:
        stop_candidate_processes()
    require(result.returncode == 0, "Android consumer invocation failed: " + command[0])


def copy_gradle_seed(seed, destination):
    seed = Path(seed)
    for path in seed.rglob("*"):
        if path.is_symlink():
            require(path.resolve(strict=True).is_relative_to(seed), "Gradle seed symlink escapes its own seed")
    shutil.copytree(seed, destination, symlinks=False)


def execute(product, head, config_path, config_sha256):
    require(os.getpid() == 1 and os.getuid() > 0, "Android consumer requires nonroot PID 1 inside its private boundary")
    roots, config, runtime = prepare(product, head, config_path, config_sha256)
    config["expected_head"] = head
    commands = vectors(product, head, config, roots)
    for name in ("home", "tmp"):
        (roots.scratch / name).mkdir()
    if config["gradle_seed"] is not None:
        copy_gradle_seed(config["gradle_seed"], roots.scratch / "gradle-home")
    env = environment(product, config, roots)
    log = []
    if commands["query"]:
        invoke(commands["query"], roots, env)
    for command in commands["candidate"]:
        invoke(command, roots, env)
        log.append(command)
    source_identity(roots, head, config["candidate_tree"])
    controller_identity(roots, config["controller_files"], product)
    # Candidate code has stopped. Its writable outputs cannot self-assert the
    # protected acceptance receipt; remove any pre-created receipt first.
    receipt_path = Path(commands["receipt"])
    require(not receipt_path.is_symlink() and not receipt_path.is_dir(), "candidate substituted protected receipt path")
    receipt_path.unlink(missing_ok=True)
    verifier_home = roots.scratch / "verifier-home"
    require(not verifier_home.exists() and not verifier_home.is_symlink(), "candidate substituted verifier home")
    verifier_home.mkdir(mode=0o700)
    env = dict(env, HOME=str(verifier_home))
    if product != "common":
        apk_tmp = roots.scratch / "apk-verification"
        require(not apk_tmp.exists() and not apk_tmp.is_symlink(), "candidate substituted APK verification scratch")
        apk_tmp.mkdir()
        env = dict(env, TMPDIR=str(apk_tmp))
    invoke(commands["verify"], roots, env)
    output = read(receipt_path)
    require(output.get("candidate_sha") == head and output.get("candidate_tree") == config["candidate_tree"],
            "protected output receipt candidate identity differs")
    require(output.get("device_tested") is False, "unexpected device acceptance claim")
    if product == "common":
        require(output.get("scope") == "parent-owned-android-common-native-elf" and output.get("apk_qualified") is False
                and output.get("abi") == "arm64-v8a" and output.get("page_size") == 16384 and output.get("outputs"),
                "incomplete protected common native output receipt")
    else:
        require(output.get("status") == ("PHONE_UNSIGNED_CI_APK_OUTPUT_VERIFIED" if product == "phone" else "PICO_UNSIGNED_CI_APK_OUTPUT_VERIFIED") and output.get("unsigned") is True
                and output.get("native_page_size") == 16384 and output.get("native_libraries"),
                "incomplete protected owning APK output receipt")
    source_identity(roots, head, config["candidate_tree"])
    result = {"kind": "overte-android-offline-consumer-result-v1", "result": "success", "product": product, "candidate_sha": head,
              "candidate_tree": config["candidate_tree"], "config_sha256": config_sha256,
              "runtime_inventory_sha256": config["runtime_inventory"]["sha256"], "sdk_inventory_sha256": config["sdk_inventory"]["sha256"],
              "executed_build_commands": log, "output_receipt_sha256": sha(receipt_path), "output_receipt": output,
              "actual_build_exit_code": 0, "device_tested": False, "apk_qualified": product in {"phone", "pico"}}
    destination = roots.scratch / "android-native-execution.json"
    with destination.open("x") as stream:
        stream.write(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", choices=sorted(REQUIRED_CODE), required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--config-sha256", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args.product, args.expected_head, args.config, args.config_sha256), sort_keys=True))
    except PrerequisiteError as error:
        print("ANDROID_CONSUMER_PREREQUISITE: " + str(error), file=sys.stderr)
        return 78
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print("ANDROID_CONSUMER_STOPPED: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
