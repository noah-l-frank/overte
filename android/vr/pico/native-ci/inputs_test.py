#!/usr/bin/env python3
"""Actual new Pico input resolver against bounded frozen fixture payloads."""
import copy
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
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INPUTS = load(HERE / "inputs.py", "pico_ci_inputs")
GRAPH_TESTS = load(HERE / "tests.py", "pico_ci_graph_tests")
COMMON = load(ROOT / "android/common/native-ci/verify.py", "pico_ci_common")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(value)


def elf(machine, alignment=16384):
    header = struct.pack("<16sHHIQQQIHHHHHH", b"\x7fELF\x02\x01\x01" + b"\0" * 9,
                         3, machine, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    return header + struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, 120, 120, alignment)


class PicoInputContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.repo, self.payload, self.proof = [base / name for name in ("candidate", "payload", "proof")]
        for path in (self.repo, self.payload, self.proof): path.mkdir()
        for relative in set(COMMON.DEPENDENCY_INPUTS) | set(INPUTS.EXTRA_INTENT):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        for args in (("init", "--quiet"), ("add", "."),
                     ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "Fixture")):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)
        self.head = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.qt = self.payload / "conan/qt/p"
        self.draco = self.payload / "conan/draco/p/include"
        self.host_qt = self.payload / "conan/host-qt/p"
        self.generators = self.payload / "pico-target-ci/generators"
        write(self.generators / "conandeps_legacy.cmake", "# fixture\n")
        write(self.generators / "Qt5-debug-armv8-data.cmake", f'set(qt_PACKAGE_FOLDER_DEBUG "{self.qt}")\n')
        write(self.draco / "draco/compression/decode.h", "// fixture\n")
        write(self.qt / "jar/QtAndroid.jar", b"fixture jar")
        for name in INPUTS.MODULES: write(self.qt / "qml" / name / "qmldir", "module fixture\n")
        tools = {}
        for name in ("moc", "rcc", "qmake"):
            path = self.host_qt / "bin" / name
            write(path, elf(62)); path.chmod(0o755); tools[name] = str(path)
        write(self.qt / "bin/uic", elf(62)); (self.qt / "bin/uic").chmod(0o755)
        tools["uic"] = str(self.qt / "bin/uic")
        shader = {"scribe": ("scribe", "tools/scribe"), "glslangValidator": ("glslang", "bin/glslangValidator"),
                  "spirv-cross": ("spirv-cross", "bin/spirv-cross"), "spirv-opt": ("spirv-tools", "bin/spirv-opt")}
        for tool, (package, relative) in shader.items():
            path = self.payload / "conan" / package / "p" / relative
            write(path, elf(62)); path.chmod(0o755); tools[tool] = str(path)
        graph, _ = GRAPH_TESTS.fixture()
        graph["1"]["package_folder"] = str(self.qt)
        template = copy.deepcopy(graph["4"])
        template.update(id="7", ref="draco/1.3.5#" + "7" * 32, rrev="7" * 32,
                        package_id="7" * 40, prev="7" * 32, package_folder=str(self.draco.parent), dependencies={})
        graph["7"] = template
        for number, (name, path) in enumerate([("qt", self.host_qt)] + [(p, self.payload / "conan" / p / "p") for p, _ in shader.values()], 8):
            node = copy.deepcopy(graph["1"])
            node.update(id=str(number), context="build", package_folder=str(path), dependencies={},
                        settings={"os": "Linux", "arch": "x86_64"})
            if name != "qt": node.update(ref=name + "/1.0#" + f"{number:032x}", rrev=f"{number:032x}")
            graph[str(number)] = node
        self.graph = graph
        host_graph = {"0": copy.deepcopy(graph["0"])}
        host_graph["0"]["dependencies"] = {}
        host_bindings = {}
        for key, node in graph.items():
            if node.get("settings", {}).get("os") != "Linux": continue
            host_bindings[node["ref"] + ":" + node["package_id"] + "#" + node["prev"]] = node["package_folder"]
            original = copy.deepcopy(node)
            original.update(binary="Build", context="host", package_folder="/original/unchanged/raw/package")
            host_graph[key] = original
            node.update(binary="Skip", package_folder=None)
        duplicate = copy.deepcopy(graph["12"])
        duplicate.update(id="13", binary="Cache")
        graph["13"] = duplicate
        self.host_graph = host_graph
        xml = self.repo / "android/vr/pico/apps/picoInterface/src/main/res/values/qt_dependencies.xml"
        names = {item.text.split(":", 1)[0] for item in ET.parse(xml).findall("./string-array[@name='bundled_in_lib']/item")}
        names |= {"libssl_3.so", "libcrypto_3.so", "libopenxr_loader.so"}
        runtime = {}
        for name in names:
            path = self.payload / "native-runtime" / name
            write(path, elf(183)); runtime[name] = str(path)
        self.runtime = runtime
        refs = {}
        for name, kind in INPUTS.PROOF_KINDS.items():
            if name == "runtime_inventory": continue
            file = self.proof / (name + ".json")
            write(file, json.dumps({"graph": {"nodes": graph if name == "target_graph" else host_graph}})
                  if name in {"target_graph", "host_tools_graph"} else json.dumps({"kind": kind, "fixture": True}))
            refs[name] = {"kind": kind, "path": str(file), "sha256": INPUTS.sha(file)}
        self.data = {"kind": "overte-pico-ci-product-inputs-v1", "product": "android-vr-pico",
                     "dependency_intent": INPUTS.intent(self.repo, self.head), **refs,
                     "host_package_bindings": host_bindings,
                     "generators": str(self.generators), "qtPackage": str(self.qt), "dracoInclude": str(self.draco),
                     "tools": tools, "runtime": runtime, "stagedRuntime": runtime.copy(), "qmlModules": sorted(INPUTS.MODULES),
                     "openxr": {"library": runtime["libopenxr_loader.so"], "sha256": INPUTS.sha(Path(runtime["libopenxr_loader.so"])),
                                "configuration_sha256": INPUTS.sha(self.repo / "android/vr/pico/conan/openxr-16k"),
                                "package_origin_sha256": refs["package_origins"]["sha256"]}}
        self.inventory()

    def inventory(self):
        entries, total = {}, 0
        for file in self.payload.rglob("*"):
            name = file.relative_to(self.payload).as_posix()
            if file.is_file():
                entries[name] = {"type": "file", "mode": file.stat().st_mode & 0o7777, "size": file.stat().st_size, "sha256": INPUTS.sha(file)}
                total += file.stat().st_size
            else: entries[name] = {"type": "directory", "mode": file.stat().st_mode & 0o7777}
        file = self.proof / "runtime-inventory.json"
        write(file, json.dumps({"kind": INPUTS.PROOF_KINDS["runtime_inventory"], "entries": entries, "total_bytes": total}))
        self.data["runtime_inventory"] = {"kind": INPUTS.PROOF_KINDS["runtime_inventory"], "path": str(file), "sha256": INPUTS.sha(file)}

    def resolve(self, *, prepared=None):
        file = self.proof / "product-inputs-pico.json"
        write(file, json.dumps(self.data))
        return INPUTS.resolve(INPUTS.sha(file), self.head, repo=self.repo, attempt=self.payload,
                              prepared=prepared or self.payload, proof=self.proof)

    def test_selected_immutable_inputs_bind_without_native_acceptance(self):
        result = self.resolve()
        self.assertEqual(result["status"], "PICO_CI_INPUT_BYTES_BOUND_NATIVE_VERIFICATION_PENDING")
        self.assertFalse(result["pico_qualified"])
        self.assertEqual(result["sourceRevision"], self.head)

    def test_absent_seal_wrong_product_and_changed_declaration_fail(self):
        for key, value in (("product", "android-phone"), ("kind", "old-pico-v3")):
            saved = self.data[key]; self.data[key] = value
            with self.assertRaisesRegex(ValueError, "product contract"): self.resolve()
            self.data[key] = saved
        write(self.repo / "android/vr/pico/native-ci/android-arm64-ci-release", "changed profile\n")
        with self.assertRaises(ValueError): self.resolve()

    def test_producer_proof_missing_or_replaced_cannot_resolve(self):
        saved = self.data.pop("producer_completion")
        with self.assertRaises(ValueError): self.resolve()
        self.data["producer_completion"] = saved
        self.assertEqual(saved["kind"], "overte-phone-guarded-target-complete-v1")
        self.data["producer_completion"] = {**saved, "kind": "overte-phone-guarded-continuation-v1-complete"}
        with self.assertRaisesRegex(ValueError, "proof kind/identity"): self.resolve()
        self.data["producer_completion"] = saved
        write(Path(saved["path"]), "changed receipt")
        with self.assertRaisesRegex(ValueError, "seal differs"): self.resolve()

    def test_graph_incomplete_and_missing_openxr_binding_fail(self):
        saved = self.data.pop("openxr")
        with self.assertRaises(ValueError): self.resolve()
        self.data["openxr"] = saved
        self.graph["5"]["binary"] = "Build"; self.graph["5"]["prev"] = None
        path = Path(self.data["target_graph"]["path"])
        write(path, json.dumps({"graph": {"nodes": self.graph}}))
        self.data["target_graph"]["sha256"] = INPUTS.sha(path)
        with self.assertRaisesRegex(ValueError, "incomplete"): self.resolve()

    def test_null_skip_tools_need_exact_original_build_and_protected_aliases(self):
        host = self.data["host_tools_graph"]
        original = copy.deepcopy(self.host_graph)
        for change in (lambda node: node.update(binary="Cache"),
                       lambda node: node.update(prev="f" * 32),
                       lambda node: node.update(options={"different": True})):
            self.host_graph = copy.deepcopy(original)
            change(self.host_graph["8"])
            write(Path(host["path"]), json.dumps({"graph": {"nodes": self.host_graph}}))
            host["sha256"] = INPUTS.sha(Path(host["path"]))
            with self.assertRaisesRegex(ValueError, "original Build identity"): self.resolve()
        write(Path(host["path"]), json.dumps({"graph": {"nodes": original}}))
        host["sha256"] = INPUTS.sha(Path(host["path"]))
        bindings = self.data["host_package_bindings"]
        identity = next(iter(bindings))
        saved = bindings.pop(identity)
        with self.assertRaises(ValueError): self.resolve()
        bindings[identity] = str(self.qt)
        with self.assertRaises((ValueError, OSError)): self.resolve()
        bindings[identity] = saved
        self.assertFalse(self.resolve()["pico_qualified"])

    def test_duplicate_skip_and_consumed_tool_identity_cannot_hide_changed_metadata(self):
        self.graph["13"]["options"]["changed"] = True
        ref = self.data["target_graph"]
        write(Path(ref["path"]), json.dumps({"graph": {"nodes": self.graph}}))
        ref["sha256"] = INPUTS.sha(Path(ref["path"]))
        with self.assertRaisesRegex(ValueError, "inconsistent metadata"): self.resolve()

    def test_changed_modes_bytes_unmapped_tools_and_unshadowed_copy_fail(self):
        path = Path(self.data["tools"]["moc"])
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "size/mode"): self.resolve()
        path.chmod(0o755); write(path, b"changed host tool")
        with self.assertRaises(ValueError): self.resolve()
        write(path, elf(62))
        duplicate = Path(self.temp.name) / "foreign-prepared"
        shutil.copytree(self.payload, duplicate)
        with self.assertRaisesRegex(ValueError, "unshadowed"): self.resolve(prepared=duplicate)

    def test_writable_source_and_escaped_runtime_input_fail(self):
        write(self.payload / "source/evil", elf(62))
        self.data["tools"]["moc"] = str(self.payload / "source/evil")
        with self.assertRaisesRegex(ValueError, "writable candidate source"): self.resolve()

    def test_selected_graph_package_mismatch_and_legacy_ssl_fail(self):
        self.data["dracoInclude"] = str(self.qt)
        with self.assertRaisesRegex(ValueError, "Draco package"): self.resolve()
        self.data["dracoInclude"] = str(self.draco)
        path = self.payload / "native-runtime/libssl_1_1.so"
        write(path, elf(183)); self.data["runtime"][path.name] = str(path); self.inventory()
        with self.assertRaisesRegex(ValueError, "Legacy/renamed"): self.resolve()

    def test_actual_openxr_alignment_rejected_even_with_fresh_hash_ledger(self):
        path = Path(self.runtime["libopenxr_loader.so"])
        write(path, elf(183, alignment=4096)); self.inventory()
        self.data["openxr"]["sha256"] = INPUTS.sha(path)
        with self.assertRaisesRegex(ValueError, "16 KiB"): self.resolve()

    def test_actual_groovy_loader_and_gradle_parse(self):
        classpath = os.environ.get("PICO_TEST_GROOVY_CLASSPATH")
        if not classpath:
            if os.environ.get("CI", "").lower() in {"true", "1"}:
                self.fail("PICO_CI_GROOVY_PREREQUISITE: CI requires the verified pinned "
                          "PICO_TEST_GROOVY_CLASSPATH before running this suite")
            self.skipTest("Explicit prepared Gradle Groovy classpath required")
        fixture = Path(self.temp.name) / "groovy-pico"
        fixture.mkdir()
        write(fixture / "native-ci/source-inputs.groovy", (HERE / "source-inputs.groovy").read_text())
        write(fixture / "native-ci/inputs.py", '''import json, os
print(json.dumps(dict(status='wrong' if os.environ.get('PICO_FIXTURE_BAD') else
    'PICO_CI_INPUT_BYTES_BOUND_NATIVE_VERIFICATION_PENDING', pico_qualified=False, fixture=True)))
''')
        script = Path(self.temp.name) / "consumer.groovy"
        write(script, '''def root = new File(args[0])
def loader = new GroovyClassLoader()
loader.parseClass('class GradleException extends RuntimeException { GradleException(String text) { super(text) } }')
loader.parseClass(new File(args[1]))
def load = new GroovyShell().evaluate(new File(root, 'native-ci/source-inputs.groovy'))
println groovy.json.JsonOutput.toJson(load(root))
''')
        command = ['java', '-cp', classpath, 'groovy.ui.GroovyMain', str(script), str(fixture),
                   str(ROOT / 'android/vr/pico/apps/picoInterface/build.gradle')]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['fixture'])
        result = subprocess.run(command, env=dict(os.environ, PICO_FIXTURE_BAD='1'), capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PICO_CI_INPUTS_STATUS', result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
