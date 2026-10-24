#!/usr/bin/env python3
"""Device-free proof of the versioned semantic tablet E2E contract."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


DEVICE_ROOT = Path(__file__).resolve().parents[1]
if str(DEVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEVICE_ROOT))

from contracts import (load_capability_registry, load_tablet_product_policy,
                       load_tablet_ui_contract, validate_operation_arguments,
                       validate_tablet_product_policy, validate_tablet_ui_snapshot)  # noqa: E402


class TabletContractValidationTest(unittest.TestCase):
    @staticmethod
    def snapshot() -> dict:
        return {
            "contractVersion": 1,
            "schemaVersion": 1,
            "screenId": "settings.home",
            "ready": True,
            "visibleControlIds": ["nav.home", "settings.general"],
            "selectedControlIds": [],
        }

    def test_snapshot_accepts_only_known_sorted_unique_semantics(self):
        value = self.snapshot()
        self.assertIs(value, validate_tablet_ui_snapshot(value))
        mutations = {
            "malformed": lambda item: item.pop("ready"),
            "duplicate": lambda item: item["visibleControlIds"].append("nav.home"),
            "unsorted": lambda item: item["visibleControlIds"].reverse(),
            "unknown-control": lambda item: item["visibleControlIds"].append(
                "settings.unknown"),
            "unknown-contract": lambda item: item.update(contractVersion=2),
            "unknown-schema": lambda item: item.update(schemaVersion=2),
            "selected-not-visible": lambda item: item["selectedControlIds"].append(
                "nav.close"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                candidate = copy.deepcopy(value)
                mutate(candidate)
                with self.assertRaises(ValueError):
                    validate_tablet_ui_snapshot(candidate)

    def test_activate_request_is_versioned_and_closed(self):
        request = {"contractVersion": 1, "controlId": "app.settings"}
        self.assertIs(request, validate_operation_arguments("tablet.activate", request))
        for candidate in (
                {"contractVersion": 2, "controlId": "app.settings"},
                {"contractVersion": 1, "controlId": "settings.unknown"},
                {"contractVersion": 1, "controlId": "app.settings", "x": 1}):
            with self.assertRaises(ValueError):
                validate_operation_arguments("tablet.activate", candidate)
        with self.assertRaises(ValueError):
            validate_operation_arguments("tablet.snapshot", {"screen": "tablet.home"})

    def test_policy_is_external_versioned_and_fail_closed(self):
        path = DEVICE_ROOT / "policies/mock-flat-touch.json"
        value = load_tablet_product_policy(path)
        self.assertEqual("mock.flat-touch", value["profileId"])
        candidate = copy.deepcopy(value)
        candidate["expectations"]["settings.home"]["forbiddenControlIds"] = [
            "settings.controllers", "settings.controllers"]
        with self.assertRaisesRegex(ValueError, "sorted, unique"):
            validate_tablet_product_policy(candidate)
        candidate = copy.deepcopy(value)
        candidate["expectations"]["settings.general"]["entryControlId"] = "settings.controllers"
        with self.assertRaisesRegex(ValueError, "must be required on settings.home"):
            validate_tablet_product_policy(candidate)

    def test_schema_enums_match_the_taxonomy_and_public_names_are_neutral(self):
        contract = load_tablet_ui_contract()
        snapshot_schema = json.loads((DEVICE_ROOT / "schemas/tablet-ui-snapshot.schema.json")
                                     .read_text(encoding="utf-8"))
        policy_schema = json.loads((DEVICE_ROOT / "schemas/tablet-product-policy.schema.json")
                                   .read_text(encoding="utf-8"))
        for schema in (snapshot_schema, policy_schema):
            self.assertEqual(contract["controlIds"], schema["$defs"]["controlId"]["enum"])
            self.assertEqual(contract["screenIds"], schema["$defs"]["screenId"]["enum"])
        public_names = [*contract["controlIds"], *contract["screenIds"],
                        *load_capability_registry()]
        for value in public_names:
            for product_name in ("android", "iphone", "ipad", "pico", "quest"):
                self.assertNotIn(product_name, value.lower())


class TabletE2EFlowTest(unittest.TestCase):
    def run_composed_control(self, *, mode: str = "valid", screen: str = "settings.home",
                             stable: str = "2"):
        with tempfile.TemporaryDirectory(prefix="overte-tablet-composed-") as temporary:
            root = Path(temporary)
            code = (
                "import json,os,pathlib,sys\n"
                f"sys.path.insert(0,{str(DEVICE_ROOT)!r})\n"
                "import module_support\n"
                "events=[];reads=0;activated=False\n"
                f"mode={mode!r}\n"
                "def observed(_manifest,_target,operation,arguments=None):\n"
                " global reads,activated\n"
                " events.append(operation)\n"
                " if operation=='tablet.activate':\n"
                "  activated=True;return {'performed':True}\n"
                " if operation=='app.process':\n"
                "  return {'running':True,'identity':'foreign-process' if activated and mode=='late-pid' else 'fixture-process'}\n"
                " if operation=='tablet.snapshot':\n"
                "  reads+=1\n"
                "  if mode=='malformed':return {'schemaVersion':99}\n"
                "  screen='tablet.home' if mode=='ignored-input' else 'settings.security' if mode=='wrong-screen' else 'settings.home'\n"
                "  return {'schemaVersion':1,'contractVersion':1,'screenId':screen,'ready':True,'visibleControlIds':['nav.home','settings.audio'],'selectedControlIds':[]}\n"
                " raise AssertionError('Unexpected host-fixture operation')\n"
                "module_support.invoke=observed\n"
                "from overte_session import OverteSession\n"
                "def check():\n"
                f" value=OverteSession().activate_tablet_control_and_wait_for_screen('app.settings',{screen!r},'fixture-process','confirmed.json')\n"
                f" pathlib.Path({str(root / 'result.json')!r}).write_text(json.dumps(value))\n"
                "try:module_support.module_main(check)\n"
                "finally:\n"
                f" pathlib.Path({str(root / 'events.json')!r}).write_text(json.dumps({{'events':events,'reads':reads}}))\n"
            )
            environment = os.environ | {
                "OVERTE_DEVICE_ADAPTER_MANIFEST": str(DEVICE_ROOT / "adapters/mock/adapter.json"),
                "OVERTE_DEVICE_TARGET_SELECTOR": "host-tablet-fixture",
                "OVERTE_DEVICE_ARTIFACT_DIR": str(root),
                "OVERTE_E2E_TABLET_STABLE_SAMPLES": stable,
                "OVERTE_E2E_POLL_SECONDS": "0.05",
                "OVERTE_E2E_TIMEOUT_SECONDS": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            result = subprocess.run([sys.executable, "-B", "-c", code], env=environment,
                                    text=True, capture_output=True, timeout=10, check=False)
            events = json.loads((root / "events.json").read_text())
            observed = (json.loads((root / "result.json").read_text())
                        if (root / "result.json").exists() else None)
            return result, events, observed

    def test_composed_wait_rejects_bad_expectations_before_any_input(self):
        for screen, stable in (("settings.unknown", "2"), ("settings.home", "1"),
                               ("settings.home", "11"), ("settings.home", "invalid")):
            with self.subTest(screen=screen, stable=stable):
                result, events, observed = self.run_composed_control(screen=screen, stable=stable)
                self.assertEqual(75, result.returncode, result.stdout + result.stderr)
                self.assertEqual([], events["events"])
                self.assertIsNone(observed)

    def test_composed_wait_rejects_late_pid_and_invalid_or_ignored_effects(self):
        for mode, expected in (("late-pid", 1), ("ignored-input", 1),
                               ("wrong-screen", 1), ("malformed", 75)):
            with self.subTest(mode=mode):
                result, events, observed = self.run_composed_control(mode=mode)
                self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
                self.assertEqual("tablet.activate", events["events"][0])
                self.assertIsNone(observed)
                if mode == "late-pid":
                    self.assertEqual(["tablet.activate", "app.process"], events["events"])
                    self.assertEqual(0, events["reads"])

    def test_composed_wait_keeps_two_fresh_observations_after_acknowledgement(self):
        result, events, observed = self.run_composed_control()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(["tablet.activate", "app.process", "tablet.snapshot",
                          "app.process", "tablet.snapshot"], events["events"])
        self.assertEqual(2, events["reads"])
        self.assertEqual("settings.home", observed["screenId"])

    def run_tablet(self, profile: str, policy_name: str, *, mutation: str = "",
                   missing_capability: str = "", infrastructure_failure: bool = False):
        temporary = tempfile.TemporaryDirectory(prefix="overte-tablet-e2e-")
        root = Path(temporary.name)
        output = root / "results"
        environment = os.environ.copy()
        environment.update({
            "OVERTE_MOCK_E2E_STATE": str(root / "state.json"),
            "OVERTE_MOCK_TABLET_UI_PROFILE": profile,
            "OVERTE_DEVICE_LAUNCH_SETTLE_SECONDS": "0",
            "OVERTE_DEVICE_LOCK_ROOT": str(root / "locks"),
            "OVERTE_E2E_POLL_SECONDS": "0.05",
            "OVERTE_E2E_TIMEOUT_SECONDS": "1",
            "OVERTE_MOCK_PRIVATE_SECRET": "secret-target-selector-do-not-persist",
            "OVERTE_MOCK_ASSERT_POLICY_ISOLATED": "1",
        })
        if mutation:
            environment["OVERTE_MOCK_TABLET_MUTATION"] = mutation
        if missing_capability:
            environment["OVERTE_MOCK_MISSING_CAPABILITY"] = missing_capability
        if infrastructure_failure:
            environment["OVERTE_MOCK_TABLET_INFRASTRUCTURE_FAILURE"] = "1"
        result = subprocess.run([
            sys.executable, str(DEVICE_ROOT / "run.py"),
            "--adapter-manifest", str(DEVICE_ROOT / "adapters/mock/adapter.json"),
            "--catalog", str(DEVICE_ROOT / "catalog.json"),
            "--suite", "tablet-e2e",
            "--tablet-policy", str(DEVICE_ROOT / f"policies/{policy_name}"),
            "--allow-virtual", "--require-complete",
            "--output-dir", str(output),
        ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
           env=environment, check=False)
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        return temporary, output, result, summary

    @staticmethod
    def tablet_result(summary: dict) -> dict:
        return next(item for item in summary["results"] if item["id"] == "tablet-e2e")

    def assert_flow(self, profile: str, policy: str, expected_status: str,
                    **options) -> tuple[Path, subprocess.CompletedProcess, dict, tempfile.TemporaryDirectory]:
        temporary, output, result, summary = self.run_tablet(
            profile, policy, **options)
        self.assertEqual(expected_status, self.tablet_result(summary)["status"], result.stdout)
        self.assertEqual(0 if expected_status == "passed" else 1, result.returncode, result.stdout)
        return output, result, summary, temporary

    def test_complete_flat_touch_flow_passes(self):
        output, _, _, temporary = self.assert_flow(
            "flat", "mock-flat-touch.json", "passed")
        try:
            evaluation = json.loads((output / "modules/tablet-e2e/tablet-policy-evaluation.json")
                                    .read_text(encoding="utf-8"))
            self.assertEqual("mock.flat-touch", evaluation["profileId"])
            expected = load_tablet_product_policy(DEVICE_ROOT / "policies/mock-flat-touch.json")
            self.assertEqual(set(expected["expectations"]), {
                row["screenId"] for row in evaluation["evaluations"]})
            self.assertTrue(all(row["ready"] and not row["missingRequiredControlIds"]
                                and not row["forbiddenVisibleControlIds"]
                                for row in evaluation["evaluations"]))
            state = json.loads((Path(temporary.name) / "state.json").read_text())
            self.assertFalse(state["tablet"])
            self.assertFalse((output / "modules/tablet-e2e/INVALID").exists())
        finally:
            temporary.cleanup()

    def test_complete_vr_render_resolution_flow_passes(self):
        _, _, _, temporary = self.assert_flow(
            "vr", "mock-vr-render-resolution.json", "passed")
        temporary.cleanup()

    def test_product_assertion_failures_remain_failures(self):
        cases = (
            ("flat", "mock-flat-touch.json", "missing-required", "missing required"),
            ("flat", "mock-flat-touch.json", "show-hmd", "forbidden"),
            ("flat", "mock-flat-touch.json", "show-controllers", "forbidden"),
            ("flat", "mock-flat-touch.json", "show-vr-render-resolution", "forbidden"),
            ("vr", "mock-vr-render-resolution.json", "missing-hmd", "missing required"),
            ("vr", "mock-vr-render-resolution.json", "missing-vr-render-resolution",
             "missing required"),
            ("flat", "mock-flat-touch.json", "not-ready", "ready stable"),
            ("flat", "mock-flat-touch.json", "wrong-screen", "ready stable"),
            ("flat", "mock-flat-touch.json", "action-no-transition", "ready stable"),
            ("flat", "mock-flat-touch.json", "process-restart", "restarted"),
        )
        for profile, policy, mutation, message in cases:
            with self.subTest(mutation=mutation):
                output, _, _, temporary = self.assert_flow(
                    profile, policy, "failed", mutation=mutation)
                try:
                    log = (output / "modules/tablet-e2e/module.log").read_text(
                        encoding="utf-8")
                    self.assertIn("ASSERTION:", log)
                    self.assertIn(message, log)
                finally:
                    temporary.cleanup()

    def test_malformed_adapter_snapshots_are_infrastructure_errors(self):
        for mutation in ("malformed", "duplicate-ids", "unsorted-ids", "unknown-id",
                         "unknown-version", "unknown-schema-version"):
            with self.subTest(mutation=mutation):
                output, _, _, temporary = self.assert_flow(
                    "flat", "mock-flat-touch.json", "error", mutation=mutation)
                try:
                    log = (output / "modules/tablet-e2e/module.log").read_text(
                        encoding="utf-8")
                    self.assertIn("INFRASTRUCTURE:", log)
                finally:
                    temporary.cleanup()

    def test_missing_required_operation_is_completeness_error(self):
        output, _, summary, temporary = self.assert_flow(
            "flat", "mock-flat-touch.json", "error",
            missing_capability="tablet.activate")
        try:
            junit = (output / "junit.xml").read_text(encoding="utf-8")
            error = ET.fromstring(junit).find("./testcase[@name='tablet-e2e']/error")
            self.assertIsNotNone(error)
            self.assertEqual("OVT_TEST_INFRASTRUCTURE_ERROR", error.get("message"))
            self.assertEqual("OVT_REDACTED", error.text)
            self.assertNotIn("Missing capabilities:", junit)
            self.assertEqual(75, self.tablet_result(summary)["returncode"])
            self.assertFalse((output / "modules/tablet-e2e").exists())
        finally:
            temporary.cleanup()

    def test_transport_failure_is_distinct_from_product_assertion(self):
        output, _, _, temporary = self.assert_flow(
            "flat", "mock-flat-touch.json", "error", infrastructure_failure=True)
        try:
            log = (output / "modules/tablet-e2e/module.log").read_text(encoding="utf-8")
            self.assertIn("INFRASTRUCTURE:", log)
            self.assertNotIn("ASSERTION:", log)
        finally:
            temporary.cleanup()

    def test_results_and_artifacts_do_not_persist_private_values(self):
        output, result, _, temporary = self.assert_flow(
            "flat", "mock-flat-touch.json", "passed")
        try:
            persisted = result.stdout
            for path in output.rglob("*"):
                if path.is_file():
                    persisted += path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("mock-e2e-target", persisted)
            self.assertNotIn("secret-target-selector-do-not-persist", persisted)
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
