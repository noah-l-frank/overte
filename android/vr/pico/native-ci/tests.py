#!/usr/bin/env python3
"""Offline Pico CI graph/profile regressions; no resolution or builds."""
import copy
import ast
import configparser
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


def portable_build_tool():
    # Actual Meson 1.6 identity from completed Pico graph (node 56, skipped):
    # fc971a14be7dfd1b794ec6330f8a2dd898caa4f2089c3f4c95952ab68b7575bb.
    # Use it as a consumed tool here so the independent Build-lineage gate is
    # also exercised; do not change or relabel the original producer graph.
    return dict(id="7", ref="meson/1.6.0#df190c5b0592572e6f5a1b05999e7e6d",
                rrev="df190c5b0592572e6f5a1b05999e7e6d", package_id="da39a3ee5e6b4b0d3255bfef95601890afd80709",
                prev="6e4dcc10bd6989a72a3bec7c1c328cfe", context="build", settings={}, options={},
                package_type="application", binary="Build", dependencies={})


def fixture_with_portable_tool():
    wanted, origins = fixture()
    original = origins[0]["nodes"]
    original["7"] = portable_build_tool()
    wanted["7"] = dict(copy.deepcopy(original["7"]), binary="Cache")
    for nodes in (wanted, original):
        nodes["0"]["dependencies"]["7"] = {"direct": True, "build": True, "run": True}
    return wanted, origins


class PicoCiGraphContracts(unittest.TestCase):
    def test_actual_portable_meson_identity_retains_complete_build_lineage(self):
        wanted, origins = fixture_with_portable_tool()
        result = GRAPH.minimum_delta(wanted, origins)
        self.assertEqual(result["reused_original_builds"]["7"]["node_id"], "7")
        self.assertEqual(result["distinct_nodes_requiring_build"], [])
        self.assertFalse(result["pico_qualified"])

    def test_portable_application_does_not_bypass_role_options_pid_or_target_abi(self):
        for field, value in (("context", "host"), ("package_type", "shared-library"),
                             ("package_type", "header-library"), ("options", {"shared": "True"}),
                             ("package_id", "e" * 40), ("settings", {"arch": "armv8"}),
                             ("settings", {"os": "Linux", "arch": "armv8"}),
                             ("settings", {"os": "Android", "arch": "armv8", "os.api_level": "26"})):
            with self.subTest(field=field, value=value):
                wanted, origins = fixture_with_portable_tool()
                wanted["7"][field] = value
                with self.assertRaises(ValueError):
                    GRAPH.minimum_delta(wanted, origins)

    def test_portable_cache_skip_or_changed_prev_cannot_establish_original_build(self):
        for change in (dict(binary="Cache"), dict(binary="Skip"), dict(prev="e" * 32)):
            with self.subTest(change=change):
                wanted, origins = fixture_with_portable_tool()
                origins[0]["nodes"]["7"].update(change)
                with self.assertRaises(ValueError):
                    GRAPH.minimum_delta(wanted, origins)

    def test_portable_build_tool_does_not_trigger_second_host_graph_build(self):
        wanted, origins = fixture_with_portable_tool()
        wanted["7"].update(binary="Build", prev=None)
        with self.assertRaisesRegex(ValueError, "second full build is forbidden"):
            GRAPH.minimum_delta(wanted, origins)

    def test_portable_tool_does_not_satisfy_missing_target_dependency(self):
        wanted, _ = fixture_with_portable_tool()
        del wanted["1"]
        del wanted["0"]["dependencies"]["1"]
        with self.assertRaisesRegex(ValueError, "Required Pico dependency missing"):
            GRAPH.validate_pico_target(wanted)

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
        # The hermetic SDK contains this reviewed build-tools cohort only;
        # compileSdk alone does not override AGP's older default tool version.
        gradle = (HERE.parent / "apps/picoInterface/build.gradle").read_text()
        self.assertRegex(gradle, r"(?m)^    buildToolsVersion '36[.]0[.]0'$")
        properties = dict(line.split("=", 1) for line in
                          (HERE.parent / "gradle.properties").read_text().splitlines()
                          if line and not line.startswith("#"))
        # Packaging has its own JVM inside the bounded 8 GiB native consumer.
        # Avoid Gradle's 512 MiB default without granting an unbounded heap.
        self.assertEqual(properties["org.gradle.jvmargs"].split(), ["-Xms256m", "-Xmx4g"])

    def test_declared_dependency_cohort_matches_graph_admission(self):
        common = HERE.parents[2] / "common/native-ci"
        declaration = ast.parse((common / "target.conanfile.py").read_text())
        target = next(node for node in declaration.body if isinstance(node, ast.ClassDef) and node.name == "AndroidCiTarget")
        values = {node.targets[0].id: ast.literal_eval(node.value) for node in target.body
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                  and isinstance(node.value, ast.Constant)}
        self.assertEqual(values["qt_ref"], GRAPH.QT)
        self.assertEqual(values["openexr_ref"], "openexr/3.2.12")
        profile = configparser.ConfigParser(interpolation=None, delimiters=("=",), strict=True, allow_no_value=True)
        profile.optionxform = str
        profile.read_string("\n".join(line for line in (common / "android-arm64-ci").read_text().splitlines()
                                      if not line.startswith("{%")))
        expected = {"os": "Android", "os.api_level": "26", "arch": "armv8", "compiler": "clang",
                    "compiler.version": "18", "compiler.libcxx": "c++_shared", "compiler.cppstd": "gnu20", "build_type": "Debug"}
        expected.update({name + "/*:build_type": value for name, value in GRAPH.OVERRIDES.items() if value is not None})
        self.assertEqual(dict(profile["settings"]), expected)
        for option in ("qtwebengine", "with_mysql", "with_odbc", "with_openal", "with_pq"):
            self.assertEqual(profile["options"]["qt/*:" + option], "False")
        self.assertEqual(profile["options"]["qt/*:opengl"], "es2")
        self.assertEqual(dict(profile["tool_requires"]),
                         {"opus/*:cmake/3.31.12": None, "abseil/*:cmake/3.31.12": None})

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
