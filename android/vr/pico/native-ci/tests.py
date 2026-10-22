#!/usr/bin/env python3
"""Offline Pico CI graph/profile regressions; no resolution or builds."""
import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pico_ci_graph", HERE / "graph_contract.py")
GRAPH = importlib.util.module_from_spec(spec)
spec.loader.exec_module(GRAPH)


def fixture():
    nodes = {"0": {"id": "0", "dependencies": {}, "settings": {}, "options": {}}}
    names = ["qt", "libnode", "etc2comp", "openssl", "openxr", "openexr"]
    for number, name in enumerate(names, 1):
        key = str(number)
        rrev = f"{number:032x}"
        ref = name + "/1.0#" + rrev
        if name == "qt":
            ref = GRAPH.QT
            rrev = ref.split("#")[1]
        elif name == "openssl":
            ref = "openssl/3.5.8@overte/stable#" + rrev
        elif name == "openexr":
            ref = "openexr/3.2.12#" + rrev
        settings = {"os": "Android", "arch": "armv8", "os.api_level": "26", "compiler": "clang",
                    "compiler.version": "18", "compiler.libcxx": "c++_shared", "compiler.cppstd": "gnu20",
                    "build_type": GRAPH.OVERRIDES.get(name, "Debug")}
        options = {}
        if name == "qt":
            options = dict(opengl="es2", **{x: "False" for x in ("qtwebengine", "with_mysql", "with_odbc", "with_openal", "with_pq")})
        nodes[key] = dict(id=key, ref=ref, rrev=rrev, package_id=f"{number:040x}", prev=f"{number:032x}",
                          context="host", settings=settings, options=options, package_type="shared-library",
                          binary="Build", dependencies={})
        nodes["0"]["dependencies"][key] = {"direct": True}
    nodes["2"]["dependencies"]["4"] = {"direct": True, "headers": True, "libs": True}
    origin = dict(nodes=nodes, graph_sha256="a" * 64, completion_sha256="b" * 64,
                  producer_revision="c" * 40, completed=True, exit_code=0)
    wanted = copy.deepcopy(nodes)
    for key, node in wanted.items():
        if key != "0":
            node["binary"] = "Cache"
    return wanted, [origin]


class PicoCiGraphContracts(unittest.TestCase):
    def test_exact_phone_builds_are_only_dependency_plan_not_pico_acceptance(self):
        wanted, origins = fixture()
        result = GRAPH.minimum_delta(wanted, origins)
        self.assertEqual(set(result["reused_original_builds"]), set(wanted) - {"0"})
        self.assertFalse(result["pico_qualified"])
        self.assertEqual(result["distinct_nodes_requiring_build"], [])
        self.assertIn("OpenXR", " ".join(result["mandatory_remaining_checks"]))

    def test_actual_new_openxr_revision_is_a_bounded_distinct_node(self):
        wanted, origins = fixture()
        wanted["5"]["binary"] = "Build"
        wanted["5"]["prev"] = None
        result = GRAPH.minimum_delta(wanted, origins)
        self.assertEqual(result["distinct_nodes_requiring_build"], ["5"])
        self.assertEqual(len(result["reused_original_builds"]), 5)

    def test_cached_node_or_changed_dependency_never_becomes_build_origin(self):
        for change in (lambda n: n["4"].update(binary="Cache"),
                       lambda n: n["4"].update(prev="d" * 32),
                       lambda n: n["2"]["dependencies"]["4"].update(libs=False)):
            wanted, origins = fixture()
            change(origins[0]["nodes"])
            with self.assertRaises(ValueError):
                GRAPH.minimum_delta(wanted, origins)

    def test_exact_settings_options_recipe_pid_and_prev_are_required(self):
        for field, value in (("ref", "openssl/3.5.8@overte/stable#" + "e" * 32),
                             ("package_id", "e" * 40), ("prev", "e" * 32),
                             ("options", {"shared": "True"})):
            wanted, origins = fixture()
            origins[0]["nodes"]["4"][field] = value
            if field == "ref":
                origins[0]["nodes"]["4"]["rrev"] = "e" * 32
            with self.assertRaises(ValueError):
                GRAPH.minimum_delta(wanted, origins)

    def test_profile_is_new_explicit_release_consumer_intent(self):
        profile = (HERE / "android-arm64-ci-release").read_text()
        self.assertIn("include(../../../common/native-ci/android-arm64-ci)", profile)
        self.assertIn("openxr/*:tools.android:cmake_legacy_toolchain=False", profile)
        recipe = (HERE / "target.conanfile.py").read_text()
        self.assertIn("android/common/native-ci/target.conanfile.py", recipe)
        self.assertNotIn("android/phone", recipe)

    def test_wrong_target_abi_api_compiler_and_legacy_buildtype_rejected(self):
        for key, field, value in (("1", "os.api_level", "25"), ("1", "arch", "x86_64"),
                                  ("1", "compiler.version", "17"), ("2", "build_type", "Debug"),
                                  ("3", "build_type", "Debug")):
            wanted, origins = fixture()
            wanted[key]["settings"][field] = value
            with self.assertRaises(ValueError):
                GRAPH.minimum_delta(wanted, origins)

    def test_failed_or_unsealed_producer_rejected(self):
        for field, value in (("completed", False), ("exit_code", 1), ("graph_sha256", ""),
                             ("completion_sha256", None), ("producer_revision", "bad")):
            wanted, origins = fixture()
            origins[0][field] = value
            with self.assertRaisesRegex(ValueError, "completed producer seals"):
                GRAPH.minimum_delta(wanted, origins)

    def test_cold_cache_skip_and_transport_do_not_establish_build_origin(self):
        for binary in ("Cache", "Skip"):
            wanted, origins = fixture()
            origins[0]["nodes"]["1"]["binary"] = binary
            with self.assertRaises(ValueError):
                GRAPH.minimum_delta(wanted, origins)

    def test_cycle_and_skipped_dependency_rejected(self):
        wanted, origins = fixture()
        wanted["4"]["dependencies"]["2"] = {"direct": True}
        with self.assertRaisesRegex(ValueError, "cycle"):
            GRAPH.minimum_delta(wanted, origins)
        wanted, origins = fixture()
        wanted["2"]["dependencies"]["4"]["skip"] = True
        with self.assertRaisesRegex(ValueError, "Skipped"):
            GRAPH.minimum_delta(wanted, origins)

    def test_no_second_qt_or_linux_host_graph_build(self):
        wanted, origins = fixture()
        wanted["1"].update(binary="Build", prev=None)
        with self.assertRaisesRegex(ValueError, "second full build is forbidden"):
            GRAPH.minimum_delta(wanted, origins)


if __name__ == "__main__":
    unittest.main(verbosity=2)
