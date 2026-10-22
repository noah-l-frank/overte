#!/usr/bin/env python3
"""Offline tests of central planning with immutable in-memory Git objects."""

from copy import deepcopy
import hashlib
import importlib.util
import json
import subprocess
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pr_ci_plan_under_test",
    ROOT / "tools/repository-checks/pr_ci_plan.py")
PLANNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLANNER)


class Objects:
    def __init__(self):
        self.blobs = {}

    def entry(self, raw, mode="100644"):
        if not isinstance(raw, bytes):
            raw = raw.encode()
        oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        self.blobs[oid] = raw
        return {"mode": mode, "type": "blob", "sha": oid}

    def json_entry(self, value):
        return self.entry(json.dumps(value, separators=(",", ":")))

    def read(self, oid):
        return self.blobs[oid]


class CentralPlannerTests(unittest.TestCase):
    def setUp(self):
        self.objects = Objects()
        self.registry = {"schema": 1, "control_inputs": [
            ".github/test-suites.json", "tests/requirements-host.txt"], "suites": {
            "repository-contract": {"command": ["python", "tests/repository.py"],
                "layer": "quick", "scope": "content", "environment": "host",
                "closure": {"kind": "repository", "inputs": [],
                            "required": ["tests/repository.py"]}},
            "focused": {"command": ["python", "tests/unit/check.py"],
                "layer": "host", "scope": "content", "environment": "host",
                "closure": {"kind": "patterns", "inputs": ["tests/unit/**"],
                            "required": ["tests/unit/check.py"]},
                "python_imports": {"roots": ["tests/unit"], "reviewed": "sha256:" + "0" * 64}},
            "other-component": {"command": ["python", "tests/other.py"],
                "layer": "quick", "scope": "content", "environment": "host",
                "closure": {"kind": "patterns", "inputs": ["libraries/other/**"], "required": []}},
        }}
        self.base = {
            "tests/repository.py": self.objects.entry("pass\n"),
            "tests/unit/check.py": self.objects.entry("pass\n"),
            "tests/requirements-host.txt": self.objects.entry("example==1\n"),
            "libraries/shared/item.cpp": self.objects.entry("int value = 1;\n"),
            "libraries/other/item.cpp": self.objects.entry("int other = 1;\n"),
            "scripts/example.js": self.objects.entry("const x = 1;\n"),
            "ios/App.swift": self.objects.entry("import Foundation\n"),
            "android/App.kt": self.objects.entry("class App\n"),
        }
        for project in ("browser-client", "script-archive/marketplace/S3Server", "tools/jsdoc"):
            self.base[project + "/package.json"] = self.objects.entry('{"name":"fixture"}')
            self.base[project + "/package-lock.json"] = self.objects.entry('{"lockfileVersion":3}')
        # The language selector receives the real protected extractor controls;
        # these entries are not a workflow admission or a fabricated run record.
        for path in PLANNER._CODEQL._REVIEWED_CONTROLS:
            self.base[path] = self.objects.entry((ROOT / path).read_bytes())
        self.base[".github/workflows/repository-checks.yml"] = self.objects.entry(
            (ROOT / ".github/workflows/repository-checks.yml").read_bytes())
        self.install_policy()

    def install_policy(self):
        self.base[PLANNER.REGISTRY] = self.objects.json_entry(self.registry)
        dependencies = {"schema": 1, "suites": {
            name: {"kind": "repository", "setup": ["python", "git"],
                   "definition_digest": PLANNER._INPUTS._suite_definition_digest(suite)}
            for name, suite in self.registry["suites"].items()}}
        self.base[PLANNER.DEPENDENCIES] = self.objects.json_entry(dependencies)
        self.base[".github/attested-runtime.json"] = self.objects.json_entry({"python": "3.12"})
        self.base[".github/ci37-runtime.json"] = self.objects.json_entry({"node": "22"})
        self.trusted = deepcopy(self.base)

    def candidate(self, path, raw, *, mode="100644"):
        result = deepcopy(self.base)
        result[path] = self.objects.entry(raw, mode)
        return result

    def plan(self, candidate, target="main", *, base=None, trusted=None, reader=None):
        return PLANNER.plan(self.base if base is None else base, candidate,
            self.trusted if trusted is None else trusted, read_blob=reader or self.objects.read,
            target=target)

    def active_policy(self):
        for path in (PLANNER.ACTIVE_REGISTRY, PLANNER.ACTIVE_DEPENDENCIES):
            self.base[path] = self.objects.entry((ROOT / path).read_bytes())
        self.trusted = deepcopy(self.base)

    def test_unchanged_complete_tree_has_no_work_on_all_seven_targets(self):
        for target in PLANNER.TARGETS:
            with self.subTest(target=target):
                result = self.plan(self.base, target)
                self.assertEqual([], result["tasks"])
                self.assertEqual([], result["setup"])
                self.assertEqual("skip", result["native"]["mode"])
                self.assertFalse(result["browser_required"])
                self.assertFalse(result["android_required"])
                self.assertFalse(result["ios_required"])

    def test_s3_lock_only_has_its_package_owner_without_cpp_or_browser(self):
        path = "script-archive/marketplace/S3Server/package-lock.json"
        for target in PLANNER.TARGETS:
            with self.subTest(target=target):
                result = self.plan(self.candidate(path, '{"lockfileVersion":3,"changed":true}'), target)
                self.assertEqual(["script-archive/marketplace/S3Server"], result["npm_projects"])
                self.assertEqual([], result["host_suites"])
                self.assertEqual([], result["codeql_languages"])
                self.assertEqual("skip", result["native"]["mode"])
                self.assertFalse(result["browser_required"])
                self.assertFalse(result["android_required"])
                self.assertFalse(result["ios_required"])
                self.assertEqual(["node", "npm"], result["setup"])

    def test_browser_lock_only_keeps_js_build_security_and_package_tests(self):
        result = self.plan(self.candidate("browser-client/package-lock.json", '{"new":true}'))
        self.assertEqual(["browser-client"], result["npm_projects"])
        self.assertEqual([], result["host_suites"])
        self.assertEqual("skip", result["native"]["mode"])
        self.assertFalse(result["browser_required"])
        commands = result["tasks"][0]["command"]
        self.assertIn(["npm", "audit", "--audit-level=low"], commands)
        self.assertIn(["npm", "run", "build"], commands)
        self.assertIn(["npm", "test"], commands)

    def test_browser_source_adds_browser_package_once_and_no_cpp(self):
        result = self.plan(self.candidate("browser-client/src/client.ts", "export const n = 1;"))
        self.assertTrue(result["browser_required"])
        self.assertEqual(["browser-client"], result["npm_projects"])
        self.assertEqual("skip", result["native"]["mode"])
        self.assertEqual(["javascript-typescript"], result["codeql_languages"])

    def test_browser_documentation_does_not_request_browser_execution(self):
        result = self.plan(self.candidate("browser-client/README.md", "documentation"))
        self.assertFalse(result["browser_required"])
        self.assertEqual([], result["npm_projects"])

    def test_browser_product_registry_suites_require_browser_code_but_policy_tests_do_not(self):
        suite = deepcopy(self.registry["suites"]["repository-contract"])
        self.registry["suites"]["browser-journey"] = suite
        self.registry["suites"]["browser-cpu-selection"] = deepcopy(suite)
        self.install_policy()
        normal = self.plan(self.candidate("scripts/example.js", "ordinary script"))
        self.assertNotIn("browser-journey", normal["host_suites"])
        self.assertIn("browser-cpu-selection", normal["host_suites"])
        unknown = self.plan(self.candidate("unknown/opaque", "opaque"))
        self.assertNotIn("browser-journey", unknown["host_suites"])
        browser = self.plan(self.candidate("browser-client/src/client.ts", "export {}"))
        self.assertIn("browser-journey", browser["host_suites"])

    def test_browser_build_definition_is_not_exempted_from_native_validation(self):
        result = self.plan(self.candidate("browser-client/CMakeLists.txt", "add_library(unexpected)"))
        self.assertEqual("full", result["native"]["mode"])

    def test_s3_javascript_selects_s3_without_browser_or_cpp(self):
        result = self.plan(self.candidate("script-archive/marketplace/S3Server/server.js", "const v = 2;"))
        self.assertEqual(["script-archive/marketplace/S3Server"], result["npm_projects"])
        self.assertFalse(result["browser_required"])
        self.assertEqual("skip", result["native"]["mode"])

    def test_mixed_package_and_native_change_keeps_both_owners(self):
        candidate = self.candidate("libraries/shared/item.cpp", "int value = 2;")
        candidate["script-archive/marketplace/S3Server/package-lock.json"] = self.objects.entry('{"new":1}')
        result = self.plan(candidate)
        self.assertEqual("full", result["native"]["mode"])
        self.assertIn("script-archive/marketplace/S3Server", result["npm_projects"])
        self.assertIn("repository-contract", result["host_suites"])

    def test_unknown_path_conservatively_selects_all_host_native_security_without_browser(self):
        result = self.plan(self.candidate("new-system/opaque.input", "opaque"))
        self.assertTrue(result["conservative_fallback"])
        self.assertEqual(list(self.registry["suites"]), result["host_suites"])
        self.assertEqual("full", result["native"]["mode"])
        self.assertEqual(list(PLANNER._CODEQL.LANGUAGES), result["codeql_languages"])
        self.assertFalse(result["browser_required"])

    def test_unknown_extension_inside_a_known_root_still_falls_back(self):
        result = self.plan(self.candidate("tools/new-controller.opaque", "unknown"))
        self.assertTrue(result["conservative_fallback"])
        self.assertEqual(list(self.registry["suites"]), result["host_suites"])
        self.assertEqual("full", result["native"]["mode"])

    def test_deleted_native_input_remains_in_delta_and_security_fallback(self):
        candidate = deepcopy(self.base)
        del candidate["libraries/shared/item.cpp"]
        result = self.plan(candidate)
        self.assertEqual(["libraries/shared/item.cpp"], result["paths"])
        self.assertIsNone(result["changes"][0]["after"])
        self.assertEqual("full", result["native"]["mode"])
        self.assertEqual(list(PLANNER._CODEQL.LANGUAGES), result["codeql_languages"])

    def test_rename_includes_deleted_and_added_languages_without_name_heuristics(self):
        candidate = deepcopy(self.base)
        del candidate["scripts/example.js"]
        candidate["scripts/example.py"] = self.objects.entry("print(1)")
        result = self.plan(candidate)
        self.assertEqual(["scripts/example.js", "scripts/example.py"], result["paths"])
        self.assertEqual(list(PLANNER._CODEQL.LANGUAGES), result["codeql_languages"])
        self.assertEqual("skip", result["native"]["mode"])

    def test_nonregular_mode_is_full_fallback_even_on_a_known_cheap_path(self):
        candidate = self.candidate("docs/link.md", "../../library", mode="120000")
        result = self.plan(candidate)
        self.assertFalse(result["regular"])
        self.assertTrue(result["conservative_fallback"])
        self.assertEqual("full", result["native"]["mode"])
        self.assertEqual(list(self.registry["suites"]), result["host_suites"])

    def test_deleted_manifest_is_not_silently_omitted(self):
        candidate = deepcopy(self.base)
        del candidate["browser-client/package.json"]
        result = self.plan(candidate)
        self.assertEqual(["browser-client"], result["npm_projects"])
        self.assertEqual(["browser-client/package.json"], result["tasks"][0]["missing_inputs"])

    def test_one_task_per_id_for_overlapping_manifests_code_and_controls(self):
        candidate = self.candidate("browser-client/package.json", '{"scripts":{}}')
        candidate["browser-client/package-lock.json"] = self.objects.entry('{"changed":true}')
        candidate["browser-client/src/client.ts"] = self.objects.entry("const x = 1;")
        result = self.plan(candidate)
        ids = [task["id"] for task in result["tasks"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(1, ids.count("npm:browser-client"))
        self.assertEqual(len(result["setup"]), len(set(result["setup"])))

    def test_pattern_suites_compare_whole_closure_and_retain_repository_suites(self):
        result = self.plan(self.candidate("scripts/example.js", "const changed = 2;"))
        self.assertEqual(["repository-contract"], result["host_suites"])
        result = self.plan(self.candidate("tests/unit/new_import.py", "raise RuntimeError('never imported')"))
        self.assertEqual(["repository-contract", "focused"], result["host_suites"])

    def test_existing_alias_prevents_unsafe_pattern_only_closure(self):
        self.base["tests/unit/alias.py"] = self.objects.entry("../../scripts/example.js", "120000")
        result = self.plan(self.candidate("scripts/example.js", "changed target"))
        self.assertIn("focused", result["host_suites"])

    def test_control_changes_select_pattern_suites(self):
        result = self.plan(self.candidate("tests/requirements-host.txt", "example==2\n"))
        self.assertEqual(list(self.registry["suites"]), result["host_suites"])

    def test_candidate_registry_commands_are_data_and_never_imported_or_selected(self):
        candidate_registry = deepcopy(self.registry)
        candidate_registry["suites"]["focused"]["command"] = ["unexpected", "candidate-command"]
        candidate = deepcopy(self.base)
        candidate[PLANNER.REGISTRY] = self.objects.json_entry(candidate_registry)
        result = self.plan(candidate)
        self.assertTrue(result["host_suites"])
        self.assertTrue(all(task["command"][0] != "unexpected" for task in result["tasks"]))
        self.assertFalse(result["execution"])
        self.assertFalse(result["reusable_result"])

    def test_missing_or_mismatched_trusted_policy_fails_closed(self):
        trusted = deepcopy(self.trusted)
        del trusted[PLANNER.REGISTRY]
        with self.assertRaises(PLANNER.PlanError):
            self.plan(self.base, trusted=trusted)
        with self.assertRaisesRegex(PLANNER.PlanError, "blob identity mismatch"):
            self.plan(self.base, reader=lambda oid: b"{}")

    def test_invalid_tree_or_target_cannot_be_treated_as_verified_empty(self):
        candidate = deepcopy(self.base)
        candidate["../escape"] = self.objects.entry("untrusted")
        with self.assertRaises(PLANNER.PlanError):
            self.plan(candidate)
        with self.assertRaises(PLANNER.PlanError):
            self.plan(self.base, "unknown-target")

    def test_workflow_catalog_contents_are_not_generation_admission(self):
        candidate = self.candidate(".github/package-workflow-generations.json", '{"new-policy":true}')
        result = self.plan(candidate)
        self.assertTrue(result["host_suites"])
        self.assertEqual("skip", result["native"]["mode"])

    def test_real_protected_registry_and_dependency_data_support_lock_only_selection(self):
        for path in (PLANNER.REGISTRY, PLANNER.DEPENDENCIES):
            self.base[path] = self.objects.entry((ROOT / path).read_bytes())
        self.trusted = deepcopy(self.base)
        result = self.plan(self.candidate("script-archive/marketplace/S3Server/package-lock.json", '{"v":4}'))
        self.assertEqual([], result["host_suites"])
        self.assertEqual("skip", result["native"]["mode"])
        self.assertEqual(["script-archive/marketplace/S3Server"], result["npm_projects"])

    def test_active_data_preferred_and_retired_control_plane_suites_remain_historical(self):
        self.active_policy()
        result = self.plan(self.candidate("tools/repository-checks/pr_ci_plan.py", "new planner"))
        selected = set(result["host_suites"])
        self.assertTrue({"pr-ci-plan", "pr-ci-context", "pr-ci-run", "pr-ci-observer", "pr-ci-workflow"} <= selected)
        self.assertFalse({"producer-proof", "producer-api", "sync-test-reuse", "test-evidence",
                          "workflow-contracts", "android-orchestration"} & selected)
        product = {"device-control-plane-full", "web-entity-visibility", "lod-preferences",
                   "goto-dialog-script", "recorded-voice-native", "shared-script-behavior"}
        self.assertFalse(product & selected)
        self.assertEqual({"pr-ci-plan", "pr-ci-context", "pr-ci-run", "pr-ci-observer", "pr-ci-workflow", "pr-ci-cli", "pr-ci-transport", "pr-ci-platform", "pr-ci-reuse", "pr-ci-native", "documentation"}, selected)
        self.assertFalse({"host-full", "qt", "compiler", "qt5-qml", "qt6-qml"} & set(result["setup"]))

    def test_platform_ci_metadata_selects_its_own_consumers_without_product_work(self):
        self.active_policy()
        product = {"device-control-plane-full", "web-entity-visibility", "lod-preferences",
                   "goto-dialog-script", "recorded-voice-native", "shared-script-behavior"}
        for path in (".github/pr-ci-platforms.json", "tools/repository-checks/pr_ci_platform.py",
                "tests/pr-ci-platform-test.py", ".github/workflows/pr-ci-ios.yml",
                ".github/workflows/android-tests.yml", ".github/workflows/android-vr-tests.yml",
                ".github/workflows/ios-build-qualification.yml"):
            for target in PLANNER.TARGETS:
                with self.subTest(path=path, target=target):
                    result = self.plan(self.candidate(path, "changed CI input"), target)
                    self.assertFalse(product & set(result["host_suites"]))
                    self.assertEqual("skip", result["native"]["mode"])
                    self.assertFalse(result["android_required"] or result["ios_required"])
                    self.assertFalse(result["browser_required"])

    def test_ios_build_recipes_and_host_tests_have_distinct_owners(self):
        self.active_policy()
        for path in (".github/workflows/ios-integrated.yml", ".github/workflows/ios-qt-source.yml"):
            with self.subTest(path=path):
                result = self.plan(self.candidate(path, "changed build recipe"), "apple-ios")
                self.assertTrue(result["ios_required"] and result["ios_build_required"])
                self.assertFalse(self.plan(self.candidate(path, "changed build recipe"), "main")["ios_required"])
        self.base["ios/tests/existing-host-test.py"] = self.objects.entry("original host test")
        result = self.plan(self.candidate("ios/tests/existing-host-test.py", "changed host test"), "apple-ios")
        self.assertTrue(result["ios_required"])
        self.assertFalse(result["ios_build_required"])

    def test_active_registry_preserves_all_product_suites_and_nonlegacy_direct_tests(self):
        active = json.loads((ROOT / PLANNER.ACTIVE_REGISTRY).read_text())
        old = json.loads((ROOT / PLANNER.REGISTRY).read_text())
        old_deps = json.loads((ROOT / PLANNER.DEPENDENCIES).read_text())
        products = {name for name, row in old_deps["suites"].items()
                    if row["kind"] in {"reviewed-product-inventory", "device-control-plane"}}
        self.assertTrue(products <= set(active["suites"]))
        self.assertTrue({"project-coverage", "native-registration", "documentation", "documentation-contracts",
                         "release-bundle", "branch-policy", "branch-name-guard", "dependency-releases"}
                        <= set(active["suites"]))
        for name in products:
            self.assertEqual(old["suites"][name]["command"], active["suites"][name]["command"])

    def test_partial_active_policy_cannot_silently_fall_back_to_old_registry(self):
        self.trusted[PLANNER.ACTIVE_REGISTRY] = self.objects.entry((ROOT / PLANNER.ACTIVE_REGISTRY).read_bytes())
        with self.assertRaisesRegex(PLANNER.PlanError, "present together"):
            self.plan(self.base)

    def test_product_inventory_compares_actual_reader_and_inputs_without_reader_generation_hash(self):
        self.active_policy()
        candidate = self.candidate("interface/src/LODManager.cpp", "actual changed production body")
        result = self.plan(candidate)
        self.assertIn("lod-preferences", result["host_suites"])
        first = next(task for task in result["tasks"] if task["id"] == "suite:lod-preferences")
        candidate["tests/device/contracts/lifecycle/test_lod_preferences.py"] = self.objects.entry("changed reader")
        changed = self.plan(candidate)
        second = next(task for task in changed["tasks"] if task["id"] == "suite:lod-preferences")
        self.assertNotEqual(first["reuse_key"], second["reuse_key"])

    def test_lock_with_documentation_retains_documentation_owner(self):
        self.active_policy()
        candidate = self.candidate("browser-client/package-lock.json", '{"changed":true}')
        candidate["docs/usage.md"] = self.objects.entry("Changed documented behavior")
        result = self.plan(candidate)
        self.assertIn("documentation", result["host_suites"])
        self.assertEqual(["browser-client"], result["npm_projects"])
        self.assertFalse(result["browser_required"])
        self.assertEqual("skip", result["native"]["mode"])

    def test_mixed_and_source_changes_keep_each_package_owner_and_honest_commands(self):
        candidate = self.candidate("tools/jsdoc/plugins/hifi.js", "changed jsdoc implementation")
        candidate["server-console/src/main.js"] = self.objects.entry("changed console source")
        candidate["libraries/shared/item.cpp"] = self.objects.entry("int changed = 2;")
        result = self.plan(candidate)
        self.assertIn("tools/jsdoc", result["npm_projects"])
        self.assertIn("server-console", result["npm_projects"])
        tasks = {task["id"]: task for task in result["tasks"]}
        jsdoc = tasks["npm:tools/jsdoc"]
        self.assertNotIn(["npm", "test"], jsdoc["command"])
        self.assertIn(["node_modules/.bin/jsdoc", "root.js", "-c", "config.json", "-d", "{temporary_output}"], jsdoc["command"])
        self.assertEqual("outside-checkout-temporary-directory", jsdoc["temporary_output"]["kind"])
        self.assertIn(["node_modules/.bin/electron-packager", "--version"], tasks["npm:server-console"]["command"])

    def test_shared_content_reuse_keys_cross_targets_but_candidate_scoped_keys_do_not(self):
        candidate = self.candidate("scripts/example.js", "shared content")
        main = self.plan(candidate, "main")
        apple = self.plan(candidate, "apple-main")
        key = lambda plan, name: next(task["reuse_key"] for task in plan["tasks"] if task["id"] == name)
        self.assertEqual(key(main, "suite:repository-contract"), key(apple, "suite:repository-contract"))
        self.registry["suites"]["repository-contract"]["scope"] = "candidate"
        self.install_policy()
        self.assertNotEqual(key(self.plan(candidate, "main"), "suite:repository-contract"),
                            key(self.plan(candidate, "apple-main"), "suite:repository-contract"))

    def test_unknown_input_still_selects_all_active_product_suites(self):
        self.active_policy()
        result = self.plan(self.candidate("unknown/new-input.opaque", "unknown"))
        active = json.loads((ROOT / PLANNER.ACTIVE_REGISTRY).read_text())
        self.assertEqual(set(active["suites"]), set(result["host_suites"]))

    def test_unknown_addition_inside_existing_source_tree_is_not_hidden_by_exclusions(self):
        self.active_policy()
        result = self.plan(self.candidate("libraries/new-component/source.cpp", "int unknown = 1;"))
        active = json.loads((ROOT / PLANNER.ACTIVE_REGISTRY).read_text())
        self.assertTrue(result["conservative_fallback"])
        self.assertEqual(set(active["suites"]), set(result["host_suites"]))

    def test_nonordinary_excluded_controller_is_visible_to_product_keys(self):
        self.active_policy()
        path = "tools/repository-checks/pr_ci_plan.py"
        candidate = self.candidate("interface/src/LODManager.cpp", "changed body")
        candidate[path] = self.objects.entry("ordinary independent controller")
        normal = self.plan(candidate)
        candidate[path] = self.objects.entry("../../../interface/src/LODManager.cpp", "120000")
        linked = self.plan(candidate)
        key = lambda plan: next(t["reuse_key"] for t in plan["tasks"] if t["id"] == "suite:lod-preferences")
        self.assertNotEqual(key(normal), key(linked))

    def test_android_compile_selection_tracks_production_inputs_and_deleted_resources(self):
        phone = "android/phone/apps/phoneInterface/src/main/"
        pico = "android/vr/pico/apps/picoInterface/src/main/"
        tree = {phone + "java/Activity.java": self.objects.entry("class Activity {}"),
                pico + "java/Activity.java": self.objects.entry("class Activity {}"),
                "android/common/web/java/Shared.java": self.objects.entry("class Shared {}")}
        select = lambda paths, target="android-phone", after=None: PLANNER._android_compile_products(
            paths, tree, tree if after is None else after, target)
        self.assertEqual(["phone"], select([phone + "java/Activity.java"]))
        self.assertEqual(["pico"], select([pico + "res/xml/policy.xml"], "android-vr-pico"))
        self.assertEqual([], select([pico + "res/xml/policy.xml"], "android-phone"))
        for target, owner in (("android-phone", "phone"), ("android-vr-pico", "pico"),
                ("android-main", "common"), ("android-vr", "common")):
            self.assertEqual([owner], select(["android/common/snapshot/java/Policy.java"], target))
        for path in ("android/phone/tests/Test.java", "android/common/snapshot/tests/java/Test.java",
                "android/phone/README.md", "browser-client/package-lock.json", "android/phone/apps/phoneInterface/build.gradle"):
            self.assertEqual([], select([path]), path)
        self.assertEqual([], select([phone + "java/Activity.java"], "main"))
        self.assertEqual(["phone"], select([phone + "res/xml/policy.xml"], after={}))

    def console_candidate(self):
        self.active_policy()
        registry = json.loads((ROOT / PLANNER.ACTIVE_REGISTRY).read_text())
        for path in registry["suites"]["server-console-behavior"]["closure"]["required"]:
            self.base[path] = self.objects.entry((ROOT / path).read_bytes())
        self.base["server-console/package.json"] = self.objects.entry((ROOT / "server-console/package.json").read_bytes())
        self.trusted = deepcopy(self.base)
        return self.candidate("server-console/src/modules/file-tail.js", "changed console implementation")

    def test_exact_console_npm_script_covers_standalone_task_once(self):
        result = self.plan(self.console_candidate())
        self.assertIn("server-console-behavior", result["host_suites"])
        self.assertEqual("npm:server-console", result["covered_tasks"]["suite:server-console-behavior"])
        tasks = {task["id"]: task for task in result["tasks"]}
        self.assertNotIn("suite:server-console-behavior", tasks)
        self.assertEqual(["suite:server-console-behavior"], tasks["npm:server-console"]["covers"])

    def test_console_overlap_rejects_hooks_altered_script_missing_or_nonordinary_inputs(self):
        candidate = self.console_candidate()
        for mutation in ("pretest", "posttest", "script", "missing", "alias", "extra-alias"):
            with self.subTest(mutation=mutation):
                changed = deepcopy(candidate)
                manifest = json.loads(self.objects.read(changed["server-console/package.json"]["sha"]))
                if mutation in {"pretest", "posttest"}:
                    manifest["scripts"][mutation] = "echo side effect"
                if mutation == "script":
                    manifest["scripts"]["test"] = "echo not a functional test"
                changed["server-console/package.json"] = self.objects.json_entry(manifest)
                if mutation == "missing":
                    del changed["server-console/test/open-url.test.js"]
                if mutation == "alias":
                    changed["server-console/test/open-url.test.js"] = self.objects.entry("../../elsewhere", "120000")
                if mutation == "extra-alias":
                    changed["server-console/test/extra.test.js"] = self.objects.entry("../../elsewhere", "120000")
                result = self.plan(changed)
                self.assertNotIn("suite:server-console-behavior", result["covered_tasks"])
                self.assertIn("suite:server-console-behavior", {task["id"] for task in result["tasks"]})

    def test_schedule_only_codeql_workflow_is_not_a_historical_generation_gate(self):
        self.base[".github/workflows/codeql.yml"] = self.objects.entry(
            "name: CodeQL\non:\n  schedule:\n  - cron: '0 0 * * 1'\n")
        self.trusted = deepcopy(self.base)
        result = self.plan(self.candidate("browser-client/package-lock.json", '{"changed":true}'))
        self.assertEqual([], result["codeql_languages"])

    def test_real_analysis_control_changes_or_unknown_recipe_require_both_languages(self):
        for path in (".github/workflows/repository-checks.yml", ".github/codeql/codeql-config.yml"):
            with self.subTest(path=path):
                result = self.plan(self.candidate(path, "changed analysis control"))
                self.assertEqual(list(PLANNER._CODEQL.LANGUAGES), result["codeql_languages"])
        trusted = deepcopy(self.trusted)
        trusted[".github/workflows/repository-checks.yml"] = self.objects.entry("name: unknown recipe\n")
        self.assertEqual(list(PLANNER._CODEQL.LANGUAGES), self.plan(
            self.candidate("browser-client/package-lock.json", '{"changed":true}'), trusted=trusted)["codeql_languages"])

    def test_actual_extractable_python_json_yaml_and_unknown_java_remain_honest(self):
        for path, expected in (("scripts/source.py", ["python"]),
                               ("scripts/source.js", ["javascript-typescript"]),
                               ("scripts/source.json", ["javascript-typescript"]),
                               (".github/pr-ci-extra.yml", ["javascript-typescript"]),
                               ("android/App.java", list(PLANNER._CODEQL.LANGUAGES))):
            with self.subTest(path=path):
                self.assertEqual(expected, self.plan(self.candidate(path, "changed source"))["codeql_languages"])

    def test_query_packs_and_unresolved_aliases_retain_complete_analysis(self):
        candidate = self.candidate("browser-client/package-lock.json", '{"changed":true}')
        for path, mode in (("queries/qlpack.yml", "100644"), ("scripts/link.py", "120000")):
            with self.subTest(path=path):
                changed = deepcopy(candidate)
                changed[path] = self.objects.entry("unknown query or alias", mode)
                self.assertEqual(list(PLANNER._CODEQL.LANGUAGES), self.plan(changed)["codeql_languages"])

    def vite_candidate(self, project="browser-client"):
        """Small complete object fixture using actual manifests and lock graphs."""
        manifest = json.loads((ROOT / project / "package.json").read_text())
        lock = json.loads((ROOT / project / "package-lock.json").read_text())
        manifest["devDependencies"]["vite"] = "8.3.1"
        lock["packages"][""]["devDependencies"]["vite"] = "8.3.1"
        record = lock["packages"]["node_modules/vite"]
        record.update(version="8.3.1", resolved="https://registry.npmjs.org/vite/-/vite-8.3.1.tgz", integrity="sha512-" + "A" * 86 + "==")
        record["dependencies"]["rolldown"] = "~1.2.9"
        self.base[project + "/package.json"] = self.objects.json_entry(manifest)
        self.base[project + "/package-lock.json"] = self.objects.json_entry(lock)
        consumers = ["vite.config.ts", "tsconfig.json", "tools/build-notices.mjs", "tools/prepare-default-avatar.mjs"]
        if project == "browser-client":
            consumers += ["vite.embedded.config.mjs", "tests/embedded-fbx-worker.test.ts", "tests/fixtures/embedded-worker-entry.ts", "tests/fixtures/node-browser-worker.mjs", "src/model-fbx-worker.ts"]
        for path in consumers:
            self.base[project + "/" + path] = self.objects.entry((ROOT / project / path).read_bytes())
        self.trusted = deepcopy(self.base)
        manifest["devDependencies"]["vite"] = "8.3.3"
        lock["packages"][""]["devDependencies"]["vite"] = "8.3.3"
        record.update(version="8.3.3", resolved="https://registry.npmjs.org/vite/-/vite-8.3.3.tgz", integrity="sha512-" + "B" * 86 + "==")
        record["dependencies"]["rolldown"] = "~1.2.11"
        candidate = deepcopy(self.base)
        candidate[project + "/package.json"] = self.objects.json_entry(manifest)
        candidate[project + "/package-lock.json"] = self.objects.json_entry(lock)
        return candidate

    def test_vite_patch_proves_graph_complement_and_runs_real_built_worker_consumer(self):
        result = self.plan(self.vite_candidate())
        task = next(task for task in result["tasks"] if task["id"] == "npm:browser-client")
        self.assertEqual("vite-compatible-patch", task["profile"]["kind"])
        self.assertIn(["npm", "run", "build"], task["command"])
        self.assertIn(["node_modules/.bin/tsx", "--test", "tests/embedded-fbx-worker.test.ts"], task["command"])
        self.assertNotIn(["npm", "test"], task["command"])
        self.assertFalse(result["browser_required"])
        self.assertEqual("skip", result["native"]["mode"])

    def test_direct_browser_is_an_explicit_package_owner_with_build_and_tests(self):
        result = self.plan(self.vite_candidate("browser-direct-client"))
        self.assertEqual(["browser-direct-client"], result["npm_projects"])
        task = next(task for task in result["tasks"] if task["id"] == "npm:browser-direct-client")
        self.assertEqual("vite-compatible-patch", task["profile"]["kind"])
        self.assertIn(["npm", "run", "build"], task["command"])
        self.assertIn(["npm", "test"], task["command"])
        self.assertFalse(result["browser_required"])
        self.assertEqual("skip", result["native"]["mode"])

    def test_vite_unknown_graph_scripts_configs_consumer_modes_or_source_use_full_profile(self):
        candidate = self.vite_candidate()
        for mutation in ("graph", "runtime-dependency", "vite-new-dependency", "range", "scripts", "config", "worker-mode", "application", "mesh"):
            with self.subTest(mutation=mutation):
                changed = deepcopy(candidate)
                manifest = json.loads(self.objects.read(changed["browser-client/package.json"]["sha"]))
                lock = json.loads(self.objects.read(changed["browser-client/package-lock.json"]["sha"]))
                if mutation == "graph": lock["packages"]["node_modules/rolldown"]["version"] = "1.3.0"
                if mutation == "runtime-dependency": manifest["dependencies"]["three"] = "0.187.0"
                if mutation == "vite-new-dependency": lock["packages"]["node_modules/vite"]["dependencies"]["unknown"] = "1.0.0"
                if mutation == "range": lock["packages"]["node_modules/vite"]["dependencies"]["rolldown"] = "~1.3.0"
                if mutation == "scripts": manifest["scripts"]["build"] = "echo fake build"
                if mutation == "config": changed["browser-client/vite.config.ts"] = self.objects.entry("changed config")
                if mutation == "worker-mode": changed["browser-client/src/model-fbx-worker.ts"]["mode"] = "100755"
                if mutation == "application": changed["browser-client/src/application.ts"] = self.objects.entry("changed application")
                if mutation == "mesh": changed["interface/resources/meshes/new.fbx"] = self.objects.entry("changed build input")
                changed["browser-client/package.json"] = self.objects.json_entry(manifest)
                changed["browser-client/package-lock.json"] = self.objects.json_entry(lock)
                task = next(task for task in self.plan(changed)["tasks"] if task["id"] == "npm:browser-client")
                self.assertEqual("full", task["profile"]["kind"])
                self.assertIn(["npm", "test"], task["command"])

    def pillow_candidate(self):
        self.active_policy()
        raw = (ROOT / "tests/requirements-host.txt").read_text()
        old = __import__("re").sub(r"(?m)^Pillow==[^\n]+$", "Pillow==12.3.0", raw)
        new = old.replace("Pillow==12.3.0", "Pillow==13.0.0")
        self.base["tests/requirements-host.txt"] = self.objects.entry(old)
        self.trusted = deepcopy(self.base)
        return self.candidate("tests/requirements-host.txt", new)

    def test_pillow13_selects_32_image_units_and_one_real_overlay_without_product_build(self):
        result = self.plan(self.pillow_candidate())
        self.assertTrue(result["dependency_profiles"]["pillow13"])
        self.assertEqual({"pillow-image-observation", "pillow-animated-overlay"}, set(result["host_suites"]))
        tasks = {task["id"]: task for task in result["tasks"]}
        self.assertEqual(5, len(tasks["suite:pillow-image-observation"]["command"]) - 3)
        self.assertIn("pillow", tasks["suite:pillow-image-observation"]["setup"])
        self.assertIn("qt6-qml", tasks["suite:pillow-animated-overlay"]["setup"])
        self.assertEqual("skip", result["native"]["mode"])
        self.assertFalse(result["browser_required"])

    def test_unknown_python_requirement_change_retains_conservative_host_tests_not_cpp(self):
        candidate = self.pillow_candidate()
        raw = self.objects.read(candidate["tests/requirements-host.txt"]["sha"]).decode().replace("conan==2.25.2", "conan==2.26.0")
        candidate["tests/requirements-host.txt"] = self.objects.entry(raw)
        result = self.plan(candidate)
        self.assertFalse(result["dependency_profiles"]["pillow13"])
        self.assertIn("device-control-plane-full", result["host_suites"])
        self.assertEqual("skip", result["native"]["mode"])
        sibling = self.plan(self.candidate("tests/requirements-unknown.txt", "new dependency"))
        self.assertEqual("full", sibling["native"]["mode"])

    def test_six_dependency_updates_keep_actual_consumers_without_native_or_device_journeys(self):
        pillow = self.pillow_candidate()["tests/requirements-host.txt"]
        browser = self.vite_candidate()
        browser_entries = {path: browser[path] for path in ("browser-client/package.json", "browser-client/package-lock.json")}
        direct = self.vite_candidate("browser-direct-client")
        candidate = deepcopy(self.base)
        candidate.update(browser_entries)
        for path in ("browser-direct-client/package.json", "browser-direct-client/package-lock.json"):
            candidate[path] = direct[path]
        candidate["tests/requirements-host.txt"] = pillow
        candidate["tools/jsdoc/package-lock.json"] = self.objects.entry('{"markdown-it":"14.3.3"}')
        self.trusted = deepcopy(self.base)
        for target in PLANNER.TARGETS:
            with self.subTest(target=target):
                result = self.plan(candidate, target)
                self.assertEqual({"browser-client", "browser-direct-client", "tools/jsdoc"}, set(result["npm_projects"]))
                self.assertEqual({"pillow-image-observation", "pillow-animated-overlay", "documentation"}, set(result["host_suites"]))
                self.assertEqual("skip", result["native"]["mode"])
                self.assertFalse(result["android_required"])
                self.assertFalse(result["ios_required"])
                self.assertFalse(result["ios_build_required"])
                self.assertFalse(result["browser_required"])
                self.assertEqual({"browser-client", "browser-direct-client"}, set(result["dependency_profiles"]["vite"]))

    def test_target_boundaries_for_native_code_cover_all_seven_contexts(self):
        candidate = self.candidate("libraries/shared/item.cpp", "int value = 2;")
        for target in PLANNER.TARGETS:
            with self.subTest(target=target):
                result = self.plan(candidate, target)
                self.assertEqual(target.startswith("android-"), result["android_required"])
                self.assertEqual(target == "apple-ios", result["ios_required"])
                self.assertEqual(target == "apple-ios", result["ios_build_required"])

    def test_android_and_ios_owned_inputs_do_not_enable_other_platform(self):
        for path, own_target, flag, other_flag in (
                ("android/App.kt", "android-phone", "android_required", "ios_required"),
                ("ios/App.swift", "apple-ios", "ios_required", "android_required")):
            with self.subTest(path=path):
                candidate = self.candidate(path, "changed platform source")
                self.assertTrue(self.plan(candidate, own_target)[flag])
                self.assertFalse(self.plan(candidate, own_target)[other_flag])
                self.assertFalse(self.plan(candidate, "main")[flag])

    def test_reuse_key_binds_candidate_content_modes_commands_and_runtime_not_base_history(self):
        candidate = self.candidate("scripts/example.js", "const changed = 3;")
        first = self.plan(candidate)
        old_base = deepcopy(self.base)
        old_base["scripts/example.js"] = self.objects.entry("const older = 0;")
        second = self.plan(candidate, base=old_base)
        keys = lambda result: {task["id"]: task["reuse_key"] for task in result["tasks"]}
        self.assertEqual(keys(first), keys(second))
        mode_changed = deepcopy(candidate)
        mode_changed["scripts/example.js"]["mode"] = "100755"
        self.assertNotEqual(keys(first), keys(self.plan(mode_changed)))
        runtime_changed = deepcopy(self.trusted)
        runtime_changed[".github/attested-runtime.json"] = self.objects.entry('{"python":"3.13"}')
        self.assertNotEqual(keys(first), keys(self.plan(candidate, trusted=runtime_changed)))
        self.registry["suites"]["repository-contract"]["command"].append("--new-option")
        self.install_policy()
        self.assertNotEqual(keys(first)["suite:repository-contract"],
                            keys(self.plan(candidate))["suite:repository-contract"])

    def test_missing_required_suite_input_is_explicit_not_a_passing_result(self):
        candidate = deepcopy(self.base)
        del candidate["tests/unit/check.py"]
        task = next(task for task in self.plan(candidate)["tasks"] if task["id"] == "suite:focused")
        self.assertEqual(["tests/unit/check.py"], task["missing_inputs"])
        self.assertIn("authenticated-successful-result", task["reuse_requires"])

    def test_planning_does_not_mutate_any_supplied_tree(self):
        candidate = self.candidate("scripts/example.js", "changed")
        before = deepcopy((self.base, candidate, self.trusted))
        self.plan(candidate)
        self.assertEqual(before, (self.base, candidate, self.trusted))


class ActualRegistrySelectionTests(unittest.TestCase):
    """Compose the deployed registry with the complete real tracked inventory."""
    @classmethod
    def setUpClass(cls):
        cls.objects = Objects()
        raw = subprocess.check_output(["git", "ls-tree", "-r", "-z", "HEAD"], cwd=ROOT)
        cls.base = {}
        for record in raw.split(b"\0"):
            if not record:
                continue
            metadata, name = record.split(b"\t", 1)
            mode, kind, oid = metadata.decode().split()
            cls.base[name.decode()] = {"mode": mode, "type": kind, "sha": oid}
        # The tested working registry is intentionally not substituted with the
        # historical HEAD policy; all product inventory still comes from Git.
        for path in (PLANNER.ACTIVE_REGISTRY, PLANNER.ACTIVE_DEPENDENCIES):
            cls.base[path] = cls.objects.entry((ROOT / path).read_bytes())
        cls.cache = {}

    @classmethod
    def read(cls, oid):
        if oid in cls.objects.blobs:
            return cls.objects.read(oid)
        if oid not in cls.cache:
            cls.cache[oid] = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=ROOT)
        return cls.cache[oid]

    def plan_change(self, path, raw, *, base=None, target="main"):
        base = self.base if base is None else base
        candidate = dict(base)
        candidate[path] = self.objects.entry(raw)
        return PLANNER.plan(base, candidate, self.base, read_blob=self.read, target=target)

    def test_real_console_glob_superset_covers_registered_tests(self):
        self.assertIn("server-console/test/dependency-compat.test.js", self.base)
        result = self.plan_change("server-console/package-lock.json", b'{"lockfileVersion":3,"changed":true}')
        self.assertEqual({"suite:server-console-behavior": "npm:server-console"}, result["covered_tasks"])
        self.assertNotIn("suite:server-console-behavior", {t["id"] for t in result["tasks"]})

    def test_existing_phone_java_does_not_select_unrelated_product_suites_or_extractors(self):
        # Main has no Phone application. Compose one ordinary existing leaf
        # into both endpoints, preserving the actual complete shared registry.
        path = "android/phone/apps/phoneInterface/src/main/java/org/overte/phone/PhoneInterfaceActivity.java"
        base = dict(self.base)
        base[path] = self.objects.entry("package org.overte.phone; class PhoneInterfaceActivity {}")
        result = self.plan_change(path, b"package org.overte.phone; class PhoneInterfaceActivity { int n; }", base=base, target="android-phone")
        self.assertEqual(["documentation"], result["host_suites"])
        self.assertEqual([], result["codeql_languages"])
        self.assertTrue(result["android_required"])
        self.assertEqual(["phone"], result["android_compile_products"])
        self.assertIn("--compile-product", next(t for t in result["tasks"] if t["id"] == "platform:android")["command"])

    def test_browser_source_runs_only_its_journey_without_shared_host_contracts(self):
        for project, command in (("browser-client", ["npm", "run", "test:browser"]),
                ("browser-direct-client", ["node", "node_modules/@playwright/test/cli.js", "test", "--config", "playwright.config.ts"])):
            path = next(p for p in self.base if p.startswith(project + "/src/") and p.endswith(".ts"))
            result = self.plan_change(path, self.read(self.base[path]["sha"]) + b"\n// changed source\n")
            self.assertEqual(["documentation"], result["host_suites"])
            task = next(t for t in result["tasks"] if t["id"] == "npm:" + project)
            self.assertIn(command, task["command"])
            self.assertIn("browser", task["setup"])

    def test_membership_and_actual_readers_still_invalidate_narrowed_tasks(self):
        registry, dependencies = PLANNER._policy(self.base, self.read)
        for name, changed in (("project-coverage", "tests/project-coverage.json"),
                ("device-control-plane-full", "tests/device/run_control_plane_tests.py"),
                ("lod-preferences", "interface/src/LODManager.cpp"),
                ("shared-script-behavior", "scripts/system/goto.js")):
            result = self.plan_change(changed, self.read(self.base[changed]["sha"]) + b"\n")
            self.assertIn(name, result["host_suites"])
        candidate = dict(self.base)
        candidate["android/new-source.java"] = self.objects.entry("class NewSource {}")
        for name in ("project-coverage", "device-control-plane-full"):
            self.assertNotEqual(PLANNER._suite_inputs(self.base, registry, registry["suites"][name], dependencies[name]),
                PLANNER._suite_inputs(candidate, registry, registry["suites"][name], dependencies[name]))

    def test_new_java_or_executable_script_retains_conservative_analysis(self):
        for mode, before in (("100644", False), ("100755", True)):
            base = dict(self.base)
            path = "android/phone/Unsafe.java"
            if before:
                base[path] = self.objects.entry("#!/usr/bin/env node\nconsole.log(1)", mode)
            result = self.plan_change(path, b"class Unsafe {}", base=base)
            self.assertEqual(list(PLANNER._CODEQL.LANGUAGES), result["codeql_languages"])

    def test_hidden_eslint_configuration_with_java_suffix_is_still_javascript_input(self):
        path = "android/phone/.eslintrc.java"
        base = dict(self.base)
        base[path] = self.objects.entry('{"root":true}')
        result = self.plan_change(path, b'{"root":false}', base=base)
        self.assertEqual(["javascript-typescript"], result["codeql_languages"])

    def test_versioned_rules_require_only_deployed_central_and_topology_jobs(self):
        expected = {"permanent-branches.json": {"source-policy", "required-ci"},
            "apple-target-branches.json": {"Enforce apple-main sync path"},
            "android-target-branches.json": {"Enforce Android parent sync path"}}
        workflow = (ROOT / ".github/workflows/repository-checks.yml").read_text()
        for filename, contexts in expected.items():
            policy = json.loads((ROOT / ".github/rulesets" / filename).read_text())
            required = next(rule for rule in policy["rules"] if rule["type"] == "required_status_checks")["parameters"]
            self.assertEqual(contexts, {row["context"] for row in required["required_status_checks"]})
            self.assertTrue(all(row["integration_id"] == 15368 for row in required["required_status_checks"]))
            self.assertTrue(required["strict_required_status_checks_policy"])
        for job in expected["permanent-branches.json"]:
            self.assertRegex(workflow, r"(?m)^  " + re.escape(job) + r":$")


if __name__ == "__main__":
    unittest.main()
