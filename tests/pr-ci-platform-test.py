#!/usr/bin/env python3
"""Offline regressions for actual platform ownership and immutable handoffs."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/repository-checks"))
import pr_ci_platform as P
import pr_ci_transport as T
import pr_ci_context as C
import pr_ci_android_native as N


class ProductOwnershipTests(unittest.TestCase):
    def selected(self, target, paths, regular=True):
        profile = P.policy()["android"][target]
        return {suite["name"] for suite in P.android_suites(ROOT, target, profile,
                {"paths": paths, "regular": regular})}

    def test_native_infrastructure_suites_follow_their_actual_inputs(self):
        for target in P.policy()["android"]:
            with self.subTest(target=target):
                for paths in (["browser-client/package-lock.json"], ["docs/README.md"],
                              ["libraries/shared/src/UUID.cpp"],
                              ["android/phone/apps/phoneInterface/src/main/java/Main.java"]):
                    selected = self.selected(target, paths)
                    self.assertNotIn("android-common-native-ci", selected)
                    self.assertFalse(any(name.startswith("pico-native-ci-") for name in selected))
                selected = self.selected(target, ["android/common/native-ci/verify.py"])
                self.assertIn("android-common-native-ci", selected)
                self.assertEqual("pico-native-ci-inputs" in selected, target == "android-vr-pico")
                self.assertEqual("pico-native-ci-unsigned-apk" in selected, target == "android-vr-pico")

    def test_mixed_or_deleted_infrastructure_input_still_selects_owner(self):
        selected = self.selected("android-vr-pico", ["docs/README.md",
            "android/vr/pico/native-ci/graph_contract.py"])
        self.assertIn("pico-native-ci-graph", selected)
        self.assertIn("pico-native-ci-inputs", selected)
        self.assertNotIn("pico-native-ci-unsigned-apk", selected)
        self.assertNotIn("android-common-native-ci", selected)

    def test_unknown_or_nonregular_context_keeps_all_owned_suites(self):
        for target, profile in P.policy()["android"].items():
            expected = {suite["name"] for suite in profile["suites"]}
            for paths, regular in (([], True), (["docs/README.md"], False)):
                with self.subTest(target=target, regular=regular):
                    self.assertEqual(self.selected(target, paths, regular), expected)

    def test_every_declared_infrastructure_input_selects_its_owned_suite(self):
        inputs = json.loads((ROOT / ".github/pr-ci-platform-inputs.json").read_text())
        for closure in inputs["infrastructure"]:
            for target in closure["targets"]:
                for path in closure["inputs"]:
                    with self.subTest(suite=closure["name"], target=target, path=path):
                        self.assertIn(closure["name"], self.selected(target, [path]))

    def test_every_android_target_retains_its_reviewed_inventory(self):
        policy = P.policy()
        for target, profile in policy["android"].items():
            with self.subTest(target=target), patch.object(P.subprocess, "check_output", return_value=json.dumps(profile).encode()):
                commands = P.commands(ROOT, target, "android")
                self.assertEqual(len(commands), len(profile["suites"]))
                self.assertEqual(len(commands), len({tuple(command) for command in commands}))
                self.assertTrue(any("source-boundary" in command[1] for command in commands))

    def test_missing_or_reduced_candidate_inventory_cannot_waive_a_suite(self):
        profile = deepcopy(P.policy()["android"]["android-phone"])
        profile["suites"].pop()
        with patch.object(P.subprocess, "check_output", return_value=json.dumps(profile).encode()):
            with self.assertRaisesRegex(C.ContextError, "mandatory suites"):
                P.commands(ROOT, "android-phone", "android")

    def test_selected_native_owner_is_executed_once_and_cannot_omit_its_runtime(self):
        context = {'target': 'android-phone', 'original_merge': '1' * 40, 'tree': '2' * 40}
        plan = {'android_required': True, 'android_native_products': ['phone']}
        with tempfile.TemporaryDirectory() as scratch:
            runtime = Path(scratch)
            with patch.object(P, 'authenticate', return_value=ROOT), \
                 patch.object(P, 'commands', return_value=[['python', 'owning-host-fixture.py']]), \
                 patch.object(P.R, 'run', return_value=0) as host, \
                 patch.object(N, 'prerequisites'), \
                 patch.object(N, 'execute', return_value={'product': 'phone', 'result': 'success'}) as native:
                result = P.execute(ROOT, context, plan, 'android', [runtime], recompute=lambda *_: plan,
                                   android_native_runtime=runtime)
                native.assert_called_once()
                self.assertEqual(host.call_count, 1)
                self.assertEqual(result['commands'][-1]['scope'], 'production-native-product')
                native.reset_mock(); host.reset_mock()
                with self.assertRaisesRegex(C.ContextError, 'requires its immutable runtime'):
                    P.execute(ROOT, context, plan, 'android', [], recompute=lambda *_: plan)
                native.assert_not_called(); host.assert_not_called()

    def test_unselected_native_owner_does_not_prepare_or_build_it(self):
        context = {'target': 'android-phone', 'original_merge': '1' * 40, 'tree': '2' * 40}
        plan = {'android_required': True, 'android_native_products': []}
        with patch.object(P, 'authenticate', return_value=ROOT), \
             patch.object(P, 'commands', return_value=[['python', 'owning-host-fixture.py']]), \
             patch.object(P.R, 'run', return_value=0), patch.object(N, 'prerequisites') as preflight, \
             patch.object(N, 'execute') as native:
            P.execute(ROOT, context, plan, 'android', [], recompute=lambda *_: plan)
            preflight.assert_not_called(); native.assert_not_called()

    def test_platforms_cannot_execute_on_another_target(self):
        for target, lane in (("main", "android"), ("apple-ios", "android"), ("android-phone", "ios")):
            with self.subTest(target=target), self.assertRaises(C.ContextError):
                P.commands(ROOT, target, lane)

    def test_selected_ios_host_executes_once_inside_the_offline_boundary(self):
        context = {"target": "apple-ios", "original_merge": "1" * 40, "tree": "2" * 40}
        plan = {"ios_required": True}
        with patch.object(P, "authenticate", return_value=ROOT), patch.object(P, "qml_runner", return_value="/usr/lib/qt6/bin/qmltestrunner"), patch.object(P.R, "run", return_value=0) as run:
            result = P.execute(ROOT, context, plan, "ios", [], recompute=lambda *_: plan)
        self.assertEqual(result["result"], "success")
        self.assertEqual(len(result["commands"]), 1)
        self.assertEqual(run.call_args.args[1][-2:], ["bash", "ios/tests/run-tests.sh"])
        self.assertIn("OVERTE_REQUIRE_QML_TESTS=1", run.call_args.args[1])
        self.assertEqual(run.call_args.kwargs["boundary"], "user-namespace")
        self.assertNotIn("network", run.call_args.kwargs)

    def test_failed_or_unselected_product_contract_is_not_success(self):
        context = {"target": "apple-ios", "original_merge": "1" * 40, "tree": "2" * 40}
        for required, status in ((False, 0), (True, 1), (True, 77), (True, 124)):
            with self.subTest(required=required, status=status), patch.object(P, "authenticate", return_value=ROOT):
                with patch.object(P, "qml_runner", return_value="/usr/lib/qt6/bin/qmltestrunner"), patch.object(P.R, "run", return_value=status), self.assertRaises(C.ContextError):
                    P.execute(ROOT, context, {"ios_required": required}, "ios", [], recompute=lambda *_: {})

    def test_host_only_ios_requires_successful_host_and_skipped_build_owners(self):
        context = {"target": "apple-ios", "original_merge": "1" * 40, "tree": "2" * 40}
        plan = {"ios_required": True, "ios_build_required": False}
        needs = {"host": {"result": "success"}, "qt": {"result": "skipped"}, "client": {"result": "skipped"}}
        with patch.object(P, "authenticate", return_value=ROOT), patch.object(C, "bookend"), patch.object(P, "ios_verifier") as verifier:
            result = P.verify_ios(ROOT, context, plan, ROOT, needs, object(), recompute=lambda *_: plan)
            self.assertFalse(result["application_build_required"])
            self.assertIsNone(result["artifact"])
            verifier.assert_not_called()
            for owner, status in (("host", "skipped"), ("qt", "success"), ("client", "failure")):
                bad = deepcopy(needs); bad[owner]["result"] = status
                with self.subTest(owner=owner), self.assertRaises(C.ContextError):
                    P.verify_ios(ROOT, context, plan, ROOT, bad, object(), recompute=lambda *_: plan)

    def test_checkout_head_tree_and_recomputed_selection_are_bound(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
            branch = "test/main/pr-ci-platform-fixture"
            subprocess.run([sys.executable, str(ROOT / "tools/branch-policy/check.py"),
                "check-name", "--branch", branch], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            git("init", "-q", "--initial-branch=" + branch)
            (root / "source").write_text("original\n")
            git("add", "source"); git("-c", "user.name=Offline Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "Fixture")
            context = {"original_merge": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}")}
            plan = {"selected": True}
            self.assertEqual(root, P.authenticate(root, context, plan, lambda *_: plan))
            for key in context:
                wrong = dict(context); wrong[key] = "f" * 40
                with self.subTest(key=key), self.assertRaises(C.ContextError):
                    P.authenticate(root, wrong, plan, lambda *_: plan)
            with self.assertRaises(C.ContextError):
                P.authenticate(root, context, plan, lambda *_: {"selected": False})
            (root / "source").write_text("modified\n")
            with self.assertRaises(C.ContextError):
                P.authenticate(root, context, plan, lambda *_: plan)


class ProtectedBranchWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.trusted = {path: {"mode": "100644", "type": "blob", "sha": "1" * 40} for path in (
            T.WORKFLOW, "tools/repository-checks/pr_ci.py", "tools/repository-checks/pr_ci_context.py",
            "tools/repository-checks/pr_ci_plan.py", "tools/repository-checks/pr_ci_run.py",
            "tools/repository-checks/pr_ci_observer.py", "tools/repository-checks/pr_ci_transport.py",
            ".github/pr-ci-suites.json", ".github/pr-ci-dependencies.json")}
        self.base = deepcopy(self.trusted)
        self.base[".github/workflows/product-build.yml"] = {"mode": "100644", "type": "blob", "sha": "2" * 40}

    def test_unchanged_protected_product_workflow_is_accepted(self):
        self.assertTrue(T.validate_sources(self.base, self.trusted, protected_base=self.base))

    def test_pr_cannot_change_delete_add_or_substitute_a_product_workflow(self):
        for mutation in ("change", "delete", "add", "central", "module"):
            actual = deepcopy(self.base)
            if mutation == "delete": actual.pop(".github/workflows/product-build.yml")
            else:
                key = {"change": ".github/workflows/product-build.yml", "add": ".github/workflows/new.yml",
                       "central": T.WORKFLOW, "module": "tools/repository-checks/pr_ci.py"}[mutation]
                actual[key] = {"mode": "100644", "type": "blob", "sha": "3" * 40}
            with self.subTest(mutation=mutation), self.assertRaises(T.TransportError):
                T.validate_sources(actual, self.trusted, protected_base=self.base)

    def test_main_does_not_gain_child_exceptions(self):
        with self.assertRaises(T.TransportError):
            T.validate_sources(self.base, self.trusted)


class IosNativeJobTests(unittest.TestCase):
    def jobs(self, build):
        rows = []
        def add(name, role, selected=True):
            rows.append({"id": len(rows) + 1, "run_id": 123, "run_attempt": 1,
                "head_sha": "1" * 40, "name": name, "status": "completed",
                "conclusion": "success" if selected else "skipped",
                "steps": [{"name": name, "status": "completed", "conclusion": "success"}
                          for name in T.STEPS[role]] if selected else []})
        add("Select exact candidate tasks", "plan")
        add("Candidate execution receipt", "receipt")
        add("Authenticate candidate policy", "policy")
        add("iOS product owner / iOS host contracts", "ios")
        add("iOS product owner / Verify iOS product qualification", "ios-verify")
        for name, role in (("qt / qt-ios-source", "ios-qt"), ("client / Host contracts", "ios-handoff"),
                ("client / Static JITless V8 checkpoint", "ios-v8"),
                ("client / Toolchain, dependencies, build and package", "ios-build")):
            add("iOS product owner / " + name, role, build)
        return rows

    def validate(self, rows, build):
        owners = {name: name in {"policy", "ios"} for name in T.OWNERS}
        return T.validate_jobs(rows, owners, plan={"npm_projects": [], "codeql_languages": [],
                               "ios_build_required": build})

    def test_real_ios_job_inventory_and_compile_package_upload_steps_are_required(self):
        rows = self.jobs(True)
        self.assertTrue(self.validate(rows, True))
        for mutation in ("missing-build", "skip-build", "missing-step", "wrong-attempt", "failed-artifact-check"):
            bad = deepcopy(rows)
            if mutation == "missing-build": bad.pop()
            elif mutation == "skip-build": bad[-1].update(conclusion="skipped", steps=[])
            elif mutation == "missing-step": bad[-1]["steps"].pop()
            elif mutation == "wrong-attempt": bad[-1]["run_attempt"] = 2
            else: bad[4]["conclusion"] = "failure"
            with self.subTest(mutation=mutation), self.assertRaises(T.TransportError):
                self.validate(bad, True)

    def test_host_only_ios_cannot_execute_an_unselected_build(self):
        rows = self.jobs(False)
        self.assertTrue(self.validate(rows, False))
        rows[-1].update(conclusion="success", steps=[])
        with self.assertRaises(T.TransportError):
            self.validate(rows, False)


if __name__ == "__main__":
    unittest.main()
