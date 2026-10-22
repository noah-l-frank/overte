#!/usr/bin/env python3
"""Small actual-CMake and negative output-verifier contracts; no Android build."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location("common_native_verify", HERE / "verify.py")
VERIFY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VERIFY)


def run(*command, cwd=None):
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=30)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def elf(path, *, machine=183, alignment=16384, address=0, filesz=120):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack("<16sHHIQQQIHHHHHH", b"\x7fELF\x02\x01\x01" + b"\0" * 9,
                         3, machine, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    segment = struct.pack("<IIQQQQQQ", 1, 5, 0, address, address, filesz, 120, alignment)
    path.write_bytes(header + segment)


class EntryContracts(unittest.TestCase):
    def test_non_android_rejected_before_project(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run("cmake", "-DOVERTE_ANDROID_COMMON_NATIVE=ON", "-P", str(ROOT / "CMakeLists.txt"), cwd=temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires an explicit Android toolchain", result.stderr)

    def test_product_selection_rejected_before_project(self):
        with tempfile.TemporaryDirectory() as temp:
            for product in ("phoneInterface", "picoInterface", "questInterface"):
                result = run("cmake", "-DANDROID=ON", "-DOVERTE_ANDROID_COMMON_NATIVE=ON",
                             "-DHIFI_ANDROID_APP=" + product, "-P", str(ROOT / "CMakeLists.txt"), cwd=temp)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("must not select a product application", result.stderr)

    def test_actual_harness_requires_neutral_identity_and_abi(self):
        with tempfile.TemporaryDirectory() as temp:
            for extra, message in ((["-DHIFI_ANDROID_APP=picoInterface"], "must not select"),
                                   (["-DHIFI_ANDROID_APP=commonNative", "-DANDROID_ABI=x86_64"], "qualified arm64-v8a")):
                result = run("cmake", "-DANDROID=ON", "-DOVERTE_ANDROID_COMMON_NATIVE=ON", *extra,
                             "-P", str(HERE / "CMakeLists.txt"), cwd=temp)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_actual_qt_binding_all_configurations_and_missing_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tools = root / "host-tool"
            tools.write_text("fixture; never executed")
            write(root / "CMakeLists.txt", '''cmake_minimum_required(VERSION 3.24)
project(qt_binding NONE)
foreach(tool moc rcc uic qmake)
add_executable(Qt5::${tool} IMPORTED GLOBAL)
string(TOUPPER "${tool}" upper)
set(OVERTE_ANDROID_CI_${upper} "${BOUND_TOOL}")
endforeach()
include("''' + str(HERE / "qt-host-tools.cmake") + '''")
overte_common_bind_qt_tools()
foreach(tool moc rcc uic qmake)
foreach(config IMPORTED_LOCATION IMPORTED_LOCATION_DEBUG IMPORTED_LOCATION_RELEASE IMPORTED_LOCATION_RELWITHDEBINFO)
get_target_property(actual Qt5::${tool} ${config})
if(NOT actual STREQUAL BOUND_TOOL)
message(FATAL_ERROR "wrong host tool")
endif()
endforeach()
endforeach()
''')
            args = ("cmake", "-S", str(root), "-B", str(root / "out"), "-DBOUND_TOOL=" + str(tools))
            result = run(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            tools.unlink()
            result = run(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing bound Android CI Qt host tool", result.stderr)

    def test_actual_harness_production_targets_get_strict_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            build = Path(temp) / "build"
            write(root / "CMakeLists.txt", '''cmake_minimum_required(VERSION 3.24)
project(common_contract CXX)
set(ANDROID ON)
set(ANDROID_ABI arm64-v8a)
set(OVERTE_ANDROID_COMMON_NATIVE ON)
set(HIFI_ANDROID_APP commonNative)
set(BUILD_SHARED_LIBS ON)
list(PREPEND CMAKE_PREFIX_PATH "${CMAKE_SOURCE_DIR}/qt")
foreach(tool MOC RCC UIC QMAKE)
set(OVERTE_ANDROID_CI_${tool} "${CMAKE_SOURCE_DIR}/host/${tool}")
endforeach()
'''+f'add_subdirectory("{HERE}" "${{CMAKE_BINARY_DIR}}/harness")\n')
            # Fixture dependencies isolate the actual harness wiring. They are
            # not replacement production sources or an Android qualification.
            write(root / "android/common/cmake/overte-android-bootstrap.cmake", '''foreach(module Core Gui AndroidExtras)
add_library(Qt5::${module} INTERFACE IMPORTED GLOBAL)
endforeach()
foreach(dependency draco::draco glad::glad etc2comp::etc2comp nvidia-texture-tools::nvidia-texture-tools)
add_library(${dependency} INTERFACE IMPORTED GLOBAL)
endforeach()
foreach(tool moc rcc uic qmake)
add_executable(Qt5::${tool} IMPORTED GLOBAL)
endforeach()
''')
            write(root / "qt/Qt5Config.cmake", "set(Qt5_FOUND TRUE)\n")
            for tool in ("MOC", "RCC", "UIC", "QMAKE"):
                write(root / "host" / tool, "fixture tool bytes; not executed\n")
            names = sorted((VERIFY.REQUIRED | {"gpu-gl"}) - {"overte-android-common-runtime"})
            write(root / "interface/CMakeLists.txt", ''.join(
                f'add_library({name} SHARED "${{CMAKE_SOURCE_DIR}}/libraries/fixture.cpp")\n' for name in names)
                + 'target_link_libraries(gpu-gl pthread)\nadd_custom_target(resources)\n')
            write(root / "libraries/fixture.cpp", "int common_contract() { return 1; }\n")
            for source in ("QtInputConnectionCompat.cpp", "OffscreenGLCanvas.cpp"):
                write(root / "android/common/src" / source, "int fixture;\n")
            for module, function in (("web", "embedded_web"), ("snapshot", "snapshot"), ("documents", "documents")):
                write(root / f"android/common/{module}/target.cmake",
                      f'function(overte_target_{function} target)\nendfunction()\n')
            VERIFY.query(build)
            result = run("cmake", "-S", str(root), "-B", str(build), "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Debug")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            reply = build / ".cmake/api/v1/reply"
            index = json.loads(next(reply.glob("index-*.json")).read_text())
            model = json.loads((reply / index["reply"]["client-overte-common-native"]["codemodel-v2"]["jsonFile"]).read_text())
            shared = []
            for reference in model["configurations"][0]["targets"]:
                target = json.loads((reply / reference["jsonFile"]).read_text())
                if target["type"] == "SHARED_LIBRARY":
                    self.assertIn("--no-undefined", " ".join(row["fragment"] for row in target["link"]["commandFragments"]))
                    self.assertNotIn("-lpthread", " ".join(row["fragment"] for row in target["link"]["commandFragments"]))
                    shared.append(target["name"])
            self.assertEqual(set(shared), VERIFY.REQUIRED | {"gpu-gl"})


class OutputContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "candidate"
        self.build = Path(self.temp.name) / "build"
        self.source.mkdir(); self.build.mkdir()
        write(self.source / "interface/src/common.cpp", "int interface_source;\n")
        write(self.source / "android/common/src/common.cpp", "int android_common;\n")
        for relative in VERIFY.DEPENDENCY_INPUTS:
            write(self.source / relative, "fixture dependency declaration\n")
        for command in (("init", "--quiet"), ("add", "."),
                        ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "Fixture")):
            result = run("git", *command, cwd=self.source)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.sha = run("git", "rev-parse", "HEAD", cwd=self.source).stdout.strip()
        self.reply = self.build / ".cmake/api/v1/reply"
        self.targets = []
        for name in sorted(VERIFY.REQUIRED):
            source = "android/common/src/common.cpp" if name == "overte-android-common-runtime" else "interface/src/common.cpp"
            artifact = "native/lib" + name + ".so"
            elf(self.build / artifact)
            target = {"name": name, "type": "SHARED_LIBRARY", "sources": [{"path": source, "compileGroupIndex": 0}],
                      "artifacts": [{"path": artifact}], "link": {"commandFragments": [{"fragment": "-shared -Wl,--no-undefined -Wl,-z,max-page-size=16384"}]}}
            self.targets.append(target)
        self.save()

    def save(self):
        refs = []
        for number, target in enumerate(self.targets):
            name = f"target-{number}.json"
            write(self.reply / name, json.dumps(target))
            refs.append({"jsonFile": name})
        write(self.reply / "codemodel.json", json.dumps({"paths": {"source": str(self.source), "build": str(self.build)},
              "configurations": [{"name": "Debug", "targets": refs}]}))
        write(self.reply / "index-one.json", json.dumps({"reply": {"client-overte-common-native": {
              "codemodel-v2": {"kind": "codemodel", "jsonFile": "codemodel.json"}}}}))

    def inspect(self):
        self.save()
        return VERIFY.inspect(self.source, self.build, self.sha)

    def test_complete_shape_and_output_identity(self):
        receipt = self.inspect()
        self.assertEqual({row["target"] for row in receipt["outputs"]}, VERIFY.REQUIRED)
        self.assertFalse(receipt["apk_qualified"])
        self.assertFalse(receipt["device_tested"])
        self.assertEqual(set(receipt["dependency_intent"]["files"]), set(VERIFY.DEPENDENCY_INPUTS))

    def test_changed_owned_dependency_declaration_rejected(self):
        (self.source / "android/common/native-ci/android-arm64-ci").write_text("different profile\n")
        with self.assertRaisesRegex(ValueError, "Tracked candidate inputs changed"):
            self.inspect()

    def test_missing_production_target(self):
        self.targets.pop()
        with self.assertRaisesRegex(ValueError, "Missing required production"):
            self.inspect()

    def test_configure_only_is_not_build_acceptance(self):
        (self.build / self.targets[0]["artifacts"][0]["path"]).unlink()
        with self.assertRaises(FileNotFoundError):
            self.inspect()

    def test_product_child_source_rejected(self):
        write(self.source / "android/phone/app.cpp", "int child;\n")
        self.targets[0]["sources"][0]["path"] = "android/phone/app.cpp"
        with self.assertRaisesRegex(ValueError, "not parent-owned"):
            self.inspect()

    def test_foreign_source_and_output_rejected(self):
        external = Path(self.temp.name) / "foreign.cpp"
        external.write_text("int foreign;\n")
        self.targets[0]["sources"][0]["path"] = str(external)
        with self.assertRaisesRegex(ValueError, "outside the candidate"):
            self.inspect()
        self.targets[0]["sources"][0]["path"] = "interface/src/common.cpp"
        self.targets[0]["artifacts"][0]["path"] = str(external)
        with self.assertRaisesRegex(ValueError, "escapes its declared root"):
            self.inspect()

    def test_missing_link_contract_rejected(self):
        self.targets[0]["link"]["commandFragments"] = [{"fragment": "-shared"}]
        with self.assertRaisesRegex(ValueError, "strict undefined-symbol"):
            self.inspect()

    def test_wrong_head_and_modified_candidate_rejected(self):
        with self.assertRaisesRegex(ValueError, "HEAD differs"):
            VERIFY.inspect(self.source, self.build, "a" * 40)
        (self.source / "interface/src/common.cpp").write_text("int changed;\n")
        with self.assertRaisesRegex(ValueError, "Tracked candidate inputs changed"):
            self.inspect()

    def test_untracked_translation_unit_rejected(self):
        write(self.source / "libraries/untracked.cpp", "int untracked;\n")
        self.targets[0]["sources"][0]["path"] = "libraries/untracked.cpp"
        with self.assertRaises(subprocess.CalledProcessError):
            self.inspect()

    def test_replacement_blob_cannot_hide_modified_candidate(self):
        path = self.source / "interface/src/common.cpp"
        original = run("git", "rev-parse", "HEAD:interface/src/common.cpp", cwd=self.source).stdout.strip()
        path.write_text("int changed_with_replacement;\n")
        replacement = run("git", "hash-object", "-w", str(path), cwd=self.source).stdout.strip()
        result = run("git", "replace", original, replacement, cwd=self.source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(run("git", "diff", "--quiet", "HEAD", cwd=self.source).returncode, 0)
        with self.assertRaisesRegex(ValueError, "Tracked candidate inputs changed"):
            self.inspect()

    def test_host_or_unaligned_or_truncated_elf_rejected(self):
        artifact = self.build / self.targets[0]["artifacts"][0]["path"]
        for values, message in (({"machine": 62}, "AArch64"), ({"alignment": 4096}, "16 KiB"),
                                ({"address": 1}, "alignment differs"), ({"filesz": 4096}, "segment bounds")):
            elf(artifact, **values)
            with self.assertRaisesRegex(ValueError, message):
                self.inspect()

    def test_stale_or_escaped_codemodel_rejected(self):
        write(self.reply / "index-two.json", "{}")
        with self.assertRaisesRegex(ValueError, "one fresh"):
            self.inspect()


if __name__ == "__main__":
    unittest.main(verbosity=2)
