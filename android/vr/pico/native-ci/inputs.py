#!/usr/bin/env python3
"""Resolve a separately pinned immutable Pico CI runtime; never build or repair.

Publication of the protected product map requires independent completed producer
and package-origin authentication. This consumer validates its pinned bytes and
candidate declarations; it never manufactures producer or APK qualification.
"""
# SPDX-License-Identifier: Apache-2.0
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
ATTEMPT = Path("/attempt")
PREPARED = Path("/prepared")
PROOF = Path("/qualification")
MAP = PROOF / "product-inputs-pico.json"
PROOF_KINDS = {
    "runtime_inventory": "overte-android-runtime-inventory-v1",
    "producer_completion": "overte-phone-guarded-continuation-v1-complete",
    "package_origins": "overte-android-package-origins-v1",
    "target_graph": "conan-graph-v1",
}
EXTRA_INTENT = (
    "android/common/native-ci/verify.py", "android/common/native-ci/CMakeLists.txt",
    "android/vr/pico/native-ci/target.conanfile.py", "android/vr/pico/native-ci/android-arm64-ci-release",
    "android/vr/pico/native-ci/graph_contract.py", "android/vr/pico/native-ci/inputs.py",
    "android/vr/pico/native-ci/source-inputs.groovy", "android/vr/pico/conan/openxr-16k",
    "android/vr/pico/cmake/pico-source-bootstrap.cmake", "android/vr/pico/cmake/pico-qt-host-tools.cmake",
    "android/vr/pico/apps/picoInterface/build.gradle", "android/vr/pico/settings.gradle",
    "android/vr/pico/build.gradle", "android/common/gradle/wrapper/gradle-wrapper.properties",
    "android/vr/pico/apps/picoInterface/src/main/res/values/qt_dependencies.xml",
)
TOOLS = {"moc", "rcc", "uic", "qmake", "scribe", "glslangValidator", "spirv-cross", "spirv-opt"}
MODULES = {"Qt/labs/settings", "QtQml", "QtQml/Models.2", "QtQml/WorkerScript.2", "QtQuick.2",
           "QtQuick/Controls", "QtQuick/Controls.2", "QtQuick/Dialogs", "QtQuick/PrivateWidgets",
           "QtQuick/Templates.2", "QtQuick/Layouts", "QtQuick/Window.2", "Qt/labs/folderlistmodel", "QtGraphicalEffects"}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hex_sha(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def read_json(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate JSON field")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=pairs)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def intent(repo, expected_head):
    common = module(repo / "android/common/native-ci/verify.py", "pico_ci_common_verify")
    require(common.git(repo, "rev-parse", "HEAD").decode().strip() == expected_head, "Pico candidate HEAD differs")
    inputs = common.dependency_intent(repo, expected_head)["files"]
    for relative in EXTRA_INTENT:
        file = common.regular_inside(repo / relative, repo)
        actual = sha(file)
        require(actual == hashlib.sha256(common.git(repo, "cat-file", "blob", expected_head + ":" + relative)).hexdigest(),
                "Pico declaration differs from candidate Git blob")
        inputs[relative] = actual
    value = {"contract": "overte-owned-pico-ci-dependency-intent-v1", "files": inputs}
    return {**value, "sha256": hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def resolve(expected_map_sha, expected_head, *, repo=ROOT, attempt=ATTEMPT, prepared=PREPARED, proof=PROOF):
    require(hex_sha(expected_map_sha) and re.fullmatch("[0-9a-f]{40}", str(expected_head)), "Missing protected Pico CI identity")
    repo, attempt = repo.resolve(strict=True), attempt.resolve(strict=True)
    prepared, proof = prepared.resolve(strict=True), proof.resolve(strict=True)
    product_map = proof / "product-inputs-pico.json"
    require(product_map.is_file() and not product_map.is_symlink() and sha(product_map) == expected_map_sha,
            "Protected Pico CI product map differs")
    data = read_json(product_map)
    require(data.get("kind") == "overte-pico-ci-product-inputs-v1" and data.get("product") == "android-vr-pico",
            "Wrong Pico CI product contract")
    expected_intent = intent(repo, expected_head)
    require(data.get("dependency_intent") == expected_intent, "Pico CI declarations changed; stale runtime forbidden")

    def confined(value):
        require(isinstance(value, str) and not any(c in value for c in '\0\\";$\n\r'), "Unsafe runtime input path")
        path = Path(value)
        require(path.is_absolute() and ".." not in path.parts and path.is_relative_to(attempt), "Runtime input path escaped")
        result = path.resolve(strict=True)
        require(result.is_relative_to(attempt) and not result.is_relative_to(attempt / "source") and
                not path.is_relative_to(attempt / "source"), "Runtime input points at writable candidate source")
        return result

    def bound_file(item, kind):
        require(isinstance(item, dict) and item.get("kind") == kind and hex_sha(item.get("sha256")),
                "Missing independently pinned proof kind/identity")
        path = Path(item.get("path", ""))
        require(path.is_absolute() and path.is_relative_to(proof) and path.resolve(strict=True).is_relative_to(proof)
                and not path.is_symlink(), "Proof input escaped protected proof root")
        require(path.is_file() and sha(path) == item["sha256"], "Runtime input seal differs")
        return path

    inventory_file = bound_file(data.get("runtime_inventory"), PROOF_KINDS["runtime_inventory"])
    inventory = read_json(inventory_file)
    require(inventory.get("kind") == "overte-android-runtime-inventory-v1" and
            isinstance(inventory.get("entries"), dict) and isinstance(inventory.get("total_bytes"), int),
            "Wrong immutable runtime inventory contract")
    entries, memo = inventory["entries"], {}

    def checked(value):
        path = confined(value)
        relative = path.relative_to(attempt).as_posix()
        entry = entries.get(relative)
        require(isinstance(entry, dict) and entry.get("type") == "file" and path.is_file(), "Runtime input absent from frozen inventory")
        require(path.stat().st_size == entry.get("size") and (path.stat().st_mode & 0o7777) == entry.get("mode"),
                "Runtime input size/mode differs")
        unshadowed = (prepared / relative).resolve(strict=True)
        require(unshadowed.is_relative_to(prepared) and path.samefile(unshadowed),
                "Canonical runtime path differs from the unshadowed immutable payload")
        if path not in memo:
            memo[path] = sha(path)
        require(hex_sha(entry.get("sha256")) and memo[path] == entry["sha256"], "Runtime input bytes differ")
        return path

    # These original proofs were authenticated before protected map publication.
    # Keep their original producer identity; do not relabel Phone completion.
    for name in ("producer_completion", "package_origins", "target_graph"):
        bound_file(data.get(name), PROOF_KINDS[name])
    graph = module(repo / "android/vr/pico/native-ci/graph_contract.py", "pico_ci_graph")
    nodes = read_json(Path(data["target_graph"]["path"]))["graph"]["nodes"]
    graph.validate_pico_target(nodes)
    require(all(key == "0" or node.get("binary") == "Skip" or graph.hexdigest(node.get("prev"), 32)
                for key, node in nodes.items()), "Target graph is incomplete")
    generators = confined(data.get("generators"))
    require(generators == attempt / "pico-target-ci/generators" and generators.is_dir(), "Wrong Pico CI generator root")
    generator_files = list(generators.rglob("*"))
    require(generator_files and all(not p.is_symlink() for p in generator_files), "Unsafe Pico CI generators")
    for path in generator_files:
        if path.is_file(): checked(str(path))
    checked(str(generators / "conandeps_legacy.cmake"))
    qt = confined(data.get("qtPackage"))
    require(qt.is_dir(), "Missing Pico CI Qt package")
    target_qt = [node for node in nodes.values() if (node.get("ref") or "").startswith("qt/") and
                 node.get("settings", {}).get("os") == "Android" and node.get("context") == "host"]
    require(len(target_qt) == 1 and confined(target_qt[0].get("package_folder")) == qt,
            "Qt package is not the selected target graph node")
    qt_data = checked(str(generators / "Qt5-debug-armv8-data.cmake")).read_text()
    qt_locations = re.findall(r'set\(qt_PACKAGE_FOLDER_DEBUG "([^"]+)"\)', qt_data)
    require(len(qt_locations) == 1 and confined(qt_locations[0]) == qt, "Qt generator/package mismatch")
    draco = confined(data.get("dracoInclude"))
    target_draco = [node for node in nodes.values() if (node.get("ref") or "").startswith("draco/") and
                    node.get("settings", {}).get("os") == "Android" and node.get("context") == "host"]
    require(len(target_draco) == 1 and confined(target_draco[0].get("package_folder")) / "include" == draco,
            "Draco package is not the selected target graph node")
    checked(str(draco / "draco/compression/decode.h"))

    def host_elf(value):
        path = checked(value)
        with path.open("rb") as stream: header = stream.read(20)
        require(len(header) == 20 and header[:6] == b"\x7fELF\x02\x01" and
                struct.unpack_from("<H", header, 18)[0] == 62 and os.access(path, os.X_OK), "Wrong Pico CI host executable")
        return str(path)

    tools = data.get("tools")
    require(isinstance(tools, dict) and set(tools) == TOOLS, "Missing bound Pico host tools")
    tools = {key: host_elf(value) for key, value in tools.items()}
    host_qt = [node for node in nodes.values() if (node.get("ref") or "").startswith("qt/") and
               node.get("settings", {}).get("os") == "Linux"]
    require(len(host_qt) == 1 and host_qt[0]["ref"] == target_qt[0]["ref"], "Host/target Qt recipe differs")
    host_qt_root = confined(host_qt[0].get("package_folder"))
    for name in ("moc", "rcc", "qmake"):
        require(confined(tools[name]) == confined(str(host_qt_root / "bin" / name)), "Qt host tool package differs")
    uic_locations = [folder / "bin/uic" for folder in (qt, host_qt_root) if (folder / "bin/uic").exists()]
    require(any(confined(tools["uic"]) == confined(str(path)) for path in uic_locations),
            "Qt uic package differs")
    shader_packages = {"scribe": ("scribe", "tools/scribe"), "glslangValidator": ("glslang", "bin/glslangValidator"),
                       "spirv-cross": ("spirv-cross", "bin/spirv-cross"), "spirv-opt": ("spirv-tools", "bin/spirv-opt")}
    for tool, (package, relative) in shader_packages.items():
        matches = [node for node in nodes.values() if (node.get("ref") or "").split("/")[0] == package and
                   node.get("settings", {}).get("os") == "Linux"]
        require(len(matches) == 1 and confined(str(confined(matches[0].get("package_folder")) / relative)) == Path(tools[tool]),
                "Shader host tool package differs")
    runtime = data.get("runtime")
    staged = data.get("stagedRuntime")
    require(isinstance(runtime, dict) and runtime and isinstance(staged, dict) and staged, "Missing Pico runtime selection")
    require(all(re.fullmatch("[A-Za-z0-9_.+-]+[.]so", name) and Path(path).name == name for name, path in runtime.items()),
            "Unsafe or duplicate Pico runtime basename")
    common = module(repo / "android/common/native-ci/verify.py", "pico_ci_elf_verify")
    runtime = {key: str(checked(value)) for key, value in runtime.items()}
    for value in runtime.values(): common.android_elf(Path(value))
    require(all(key in runtime and runtime[key] == str(confined(value)) for key, value in staged.items()),
            "Pico staged runtime is not a subset of the verified graph")
    for name in ("libssl_3.so", "libcrypto_3.so"):
        require(name in runtime and name in staged, "Canonical OpenSSL 3 provider missing")
    xml = repo / "android/vr/pico/apps/picoInterface/src/main/res/values/qt_dependencies.xml"
    for item in ET.parse(xml).findall("./string-array[@name='bundled_in_lib']/item"):
        require(item.text and item.text.split(":", 1)[0] in staged, "Missing declared Qt runtime extraction input")
    require(not any(name.startswith(("libssl", "libcrypto")) and name not in {"libssl_3.so", "libcrypto_3.so"} for name in runtime),
            "Legacy/renamed OpenSSL provider forbidden")
    openxr = data.get("openxr")
    require(isinstance(openxr, dict) and openxr.get("configuration_sha256") == sha(repo / "android/vr/pico/conan/openxr-16k") and
            openxr.get("package_origin_sha256") == data["package_origins"]["sha256"], "Missing OpenXR configuration/origin binding")
    openxr_path = checked(openxr.get("library"))
    require(hex_sha(openxr.get("sha256")) and sha(openxr_path) == openxr["sha256"], "OpenXR package seal differs")
    checked(str(openxr_path)); common.android_elf(openxr_path)
    require(str(openxr_path) in runtime.values() and "openxr" in openxr_path.name.lower(), "OpenXR runtime graph binding missing")
    require(set(data.get("qmlModules", [])) == MODULES, "Wrong Pico Qt runtime modules")
    for name in MODULES: checked(str(qt / "qml" / name / "qmldir"))
    checked(str(qt / "jar/QtAndroid.jar"))
    require(sha(product_map) == expected_map_sha and intent(repo, expected_head) == expected_intent, "Pico CI inputs changed")
    return {"status": "PICO_CI_INPUT_BYTES_BOUND_NATIVE_VERIFICATION_PENDING", "sourceRevision": expected_head,
            "bindingSha256": expected_map_sha, "generators": str(generators), "qtPackage": str(qt),
            "dracoInclude": str(draco), "tools": tools, "runtime": runtime,
            "stagedRuntime": {key: str(confined(value)) for key, value in staged.items()},
            "qmlModules": sorted(MODULES), "pico_qualified": False,
            "acceptance": "Producer provenance is independently authenticated; actual candidate native/APK verification remains required"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-binding-sha256", default=os.environ.get("PICO_CI_INPUTS_SHA256"))
    parser.add_argument("--expected-source-sha", default=os.environ.get("PICO_EXPECTED_SOURCE_SHA"))
    args = parser.parse_args()
    try:
        print(json.dumps(resolve(args.expected_binding_sha256, args.expected_source_sha), sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, SyntaxError, ET.ParseError, subprocess.SubprocessError):
        print("PICO_CI_INPUTS_REJECTED", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
