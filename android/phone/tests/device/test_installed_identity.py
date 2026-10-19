# SPDX-License-Identifier: Apache-2.0
"""Real Phone adapter/SH-009 validator; all ADB observations are synthetic."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
ENTRY = ROOT / "tests/device/adapters/android-phone/adapter.py"
spec = importlib.util.spec_from_file_location("phone_installed_adapter", ENTRY)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
appium_spec = importlib.util.spec_from_file_location("phone_appium_identity", ENTRY.with_name("appium_adapter.py"))
appium = importlib.util.module_from_spec(appium_spec)
appium_spec.loader.exec_module(appium)
snapshot_spec = importlib.util.spec_from_file_location('_overte_phone_snapshot_native_boundary',
    Path(__file__).with_name('snapshot_native_boundary.py'))
snapshot_boundary = importlib.util.module_from_spec(snapshot_spec)
snapshot_spec.loader.exec_module(snapshot_boundary)
from artifact_identity import INPUT_KEYS, normalized_inputs
from execution_identity import ExecutionIdentity
from adapter_client import load_command
import test_android_build_evidence as shared_evidence_tests


class ObservedAdb:
    """Test-only Android boundary; never invokes a command."""
    def __init__(self, digest):
        self.digest = digest
        self.path = "/data/app/~~test-only/io.github.noah_be.overte.phone-test/base.apk"
        self.paths = None
        self.events = []
        self.change_after_hash = False

    def prop(self, target, name):
        return "35" if name.endswith("sdk") else "15"

    def shell(self, target, *arguments, **kwargs):
        self.events.append(arguments)
        if arguments == ("pm", "path", "io.github.noah_be.overte.phone"):
            return self.paths if self.paths is not None else "package:" + self.path + "\n"
        if arguments == ("sha256sum", self.path):
            result = self.digest + "  " + self.path + "\n"
            if self.change_after_hash:
                self.path = "/data/app/changed/base.apk"
            return result
        raise AssertionError("unexpected synthetic ADB command")


class InstalledIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="phone-install-identity-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        artifact = self.root / "synthetic-not-an-apk.bin"
        artifact.write_bytes(b"synthetic byte fixture, never installed")
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        self.sha = sha(artifact)
        inputs = {key: hashlib.sha256(key.encode()).hexdigest() for key in INPUT_KEYS}
        inputs_path = self.root / "independently-expected-test-inputs.json"
        inputs_path.write_text(json.dumps(inputs))
        evidence = {key: self.root / (key + ".json") for key in adapter.EVIDENCE_KEYS}
        for key, path in evidence.items():
            path.write_text(json.dumps({"syntheticOnly": key}))
        self.record = dict(contract="overte-sh009-identity-v1", sourceRevision="a" * 40,
                           product="android-phone", versionCode=3, channel="internal-candidate",
                           artifactSha256=self.sha, inputs=inputs,
                           normalizedInputsSha256=normalized_inputs(inputs),
                           evidence={key: sha(path) for key, path in evidence.items()},
                           signature=dict(state="pending", receiptSha256=None),
                           upgrade=dict(state="pending", receiptSha256=None))
        record_path = self.root / "candidate.json"
        record_path.write_text(json.dumps(self.record))
        self.args = argparse.Namespace(record=record_path, artifact=artifact,
            expected_source_sha="a" * 40, expected_inputs=inputs_path,
            expected_version_code=3, minimum_version_code=2, channel="internal-candidate", **evidence)
        self.adb = ObservedAdb(self.sha)
        with patch("adapters.android.adapter.AdbTransport", return_value=self.adb):
            self.phone = adapter.PhoneAdapter(adapter.VerifiedCandidate(self.args))

    def describe(self):
        # Original profile/authorized-target checks have their own tests. Only
        # that OS-dependent guard is replaced; actual describe/binding code runs.
        with patch.object(self.phone, "require"):
            return self.phone.describe("test-only-target")

    def arguments(self):
        result = ["describe", "--target", "test-only-target"]
        for key in ("record", "artifact", "expected_source_sha", "expected_inputs",
                    "expected_version_code", "minimum_version_code", "channel", *adapter.EVIDENCE_KEYS):
            result += ["--" + key.replace("_", "-"), str(getattr(self.args, key))]
        return result

    def tier_fixture(self):
        fixture = shared_evidence_tests.AndroidEvidence().fixture(self.root / "test-only-tiers")
        evidence, record, artifact, inputs, source, artifact_sha, _ = fixture["args"]
        self.args.record, self.args.artifact, self.args.expected_inputs = record, artifact, inputs
        self.args.expected_source_sha = source
        self.args.expected_version_code, self.args.minimum_version_code = 2, 1
        for key, path in fixture["files"].items(): setattr(self.args, key, path)
        self.args.build_evidence = evidence
        self.args.expected_artifact_sha256 = artifact_sha
        self.sha = self.adb.digest = artifact_sha
        return fixture

    def tier_arguments(self):
        return self.arguments() + ["--build-evidence", str(self.args.build_evidence),
                                    "--expected-artifact-sha256", self.args.expected_artifact_sha256]

    def test_both_phone_dispatchers_consume_original_mandatory_tiers(self):
        self.tier_fixture()
        appium_instance, _ = self.appium_instance()
        for dispatch, instance, target in ((adapter.main, self.phone, "test-only-target"),
                                           (appium.main, appium_instance, "test-only-appium")):
            arguments = self.tier_arguments()
            arguments[2] = target
            output = io.StringIO()
            def factory(candidate):
                instance.candidate = candidate
                return instance
            with patch.object(self.phone, "require"), contextlib.redirect_stdout(output):
                self.assertEqual(dispatch(arguments, adapter_class=factory), 0)
            result = json.loads(output.getvalue())
            ExecutionIdentity(self.args.artifact, "a" * 40, self.sha).verify_description(result)
            self.assertEqual(set(result["executionIdentity"]),
                             {"schemaVersion", "sourceRevision", "artifactSha256", "installedCandidateVerified"})
            # No new common execution receipt or producer-trust field is emitted.

    def test_failed_or_partial_tier_inputs_reject_before_any_native_constructor(self):
        fixture = self.tier_fixture()
        fixture["receipts"]["fdroid-source-scanner"]["status"] = "ERROR"
        shared_evidence_tests.AndroidEvidence().update(fixture)
        variants = [self.tier_arguments(),
                    self.arguments() + ["--build-evidence", str(self.args.build_evidence)],
                    ["discover", "--build-evidence", str(self.args.build_evidence),
                     "--expected-artifact-sha256", self.sha]]
        for dispatch in (adapter.main, appium.main):
            for arguments in variants:
                error = io.StringIO()
                with patch.object(adapter, "PhoneAdapter") as factory, contextlib.redirect_stderr(error):
                    self.assertEqual(dispatch(arguments, adapter_class=factory), 2)
                    factory.assert_not_called()
                self.assertEqual(error.getvalue(), "PHONE_ADAPTER_REJECTED\n")
        self.assertEqual(self.adb.events, [])

    def test_invalidated_tier_evidence_still_allows_both_cleanup_paths(self):
        self.tier_fixture()
        self.args.build_evidence.write_text("invalidated test-only receipt")
        appium_instance, _ = self.appium_instance()
        for dispatch, instance, target in ((adapter.main, self.phone, "test-only-target"),
                                           (appium.main, appium_instance, "test-only-appium")):
            arguments = self.tier_arguments()
            arguments[0], arguments[2] = "cleanup", target
            output = io.StringIO()
            with patch.object(instance, "cleanup", return_value={"cleaned": True}) as cleanup, \
                 contextlib.redirect_stdout(output):
                self.assertEqual(dispatch(arguments, adapter_class=lambda _: instance), 0)
            cleanup.assert_called_once_with(target)
            self.assertNotIn("executionIdentity", json.loads(output.getvalue()))

    def test_actual_description_satisfies_original_execution_contract(self):
        result = self.describe()
        ExecutionIdentity(self.args.artifact, "a" * 40, self.sha).verify_description(result)
        self.assertEqual(self.adb.events, [("pm", "path", "io.github.noah_be.overte.phone"),
            ("sha256sum", self.adb.path), ("pm", "path", "io.github.noah_be.overte.phone")])
        exported = json.dumps(result)
        self.assertNotIn("test-only-target", exported)
        self.assertNotIn("/data/app", exported)
        self.assertEqual(set(result["executionIdentity"]),
                         {"schemaVersion", "sourceRevision", "artifactSha256", "installedCandidateVerified"})

    def test_foreign_or_malformed_installed_hash_never_becomes_identity(self):
        for value in ("b" * 64, "not-a-hash", self.sha.upper(), ""):
            with self.subTest(value=value):
                self.adb.digest = value
                with self.assertRaises(ValueError):
                    self.describe()

    def test_missing_split_and_unsafe_package_paths_reject_before_hash(self):
        for value in ("", "package:" + self.adb.path + "\npackage:/data/app/x/split.apk\n",
                      "package:/data/app/a/../b/base.apk\n", "package:/data/app/a;secret/base.apk\n",
                      "package:/data/local/tmp/base.apk\n", "package:/data/app/a//base.apk\n"):
            self.adb.paths = value
            self.adb.events.clear()
            with self.assertRaises(ValueError):
                self.describe()
            self.assertEqual(self.adb.events, [("pm", "path", "io.github.noah_be.overte.phone")])

    def test_changed_installed_path_is_rejected(self):
        self.adb.change_after_hash = True
        with self.assertRaises(ValueError):
            self.describe()

    def test_foreign_source_inputs_or_changed_candidate_fail_before_native_hash(self):
        self.record["sourceRevision"] = "c" * 40
        self.args.record.write_text(json.dumps(self.record))
        with self.assertRaises(ValueError):
            self.describe()
        self.assertEqual(self.adb.events, [])
        self.record["sourceRevision"] = "a" * 40
        self.args.record.write_text(json.dumps(self.record))
        self.args.artifact.write_bytes(b"changed candidate")
        with self.assertRaises(ValueError):
            self.describe()
        self.assertEqual(self.adb.events, [])

    def test_diagnostic_mode_does_not_claim_installation(self):
        self.phone.candidate = None
        self.assertNotIn("executionIdentity", self.describe())
        self.assertEqual(self.adb.events, [])

    def test_bound_install_checks_bytes_and_rechecks_actual_installation(self):
        foreign = self.root / "foreign.bin"
        foreign.write_bytes(b"foreign")
        with patch.object(adapter.AndroidAdapter, "invoke", return_value={"installed": True}) as native:
            with self.assertRaises(ValueError):
                self.phone.invoke("test-only-target", "app.install", {"path": str(foreign)})
            with self.assertRaises(ValueError):
                self.phone.invoke("test-only-target", "app.upgrade", {})
            native.assert_not_called()
            self.assertEqual(self.phone.invoke("test-only-target", "app.install",
                {"path": str(self.args.artifact)}), {"installed": True})
            native.assert_called_once()
            self.assertEqual(len(self.adb.events), 3)

    def test_real_cli_dispatch_and_closed_failures(self):
        output, error = io.StringIO(), io.StringIO()
        with patch.object(adapter, "PhoneAdapter", return_value=self.phone), \
             patch.object(self.phone, "require"), contextlib.redirect_stdout(output), \
             contextlib.redirect_stderr(error):
            self.assertEqual(adapter.main(self.arguments()), 0)
        ExecutionIdentity(self.args.artifact, "a" * 40, self.sha).verify_description(json.loads(output.getvalue()))
        with patch.object(adapter, "PhoneAdapter") as factory, \
             contextlib.redirect_stderr(error):
            self.assertEqual(adapter.main(["discover", "--record", "private.invalid"]), 2)
            factory.assert_not_called()
        self.assertEqual(error.getvalue(), "PHONE_ADAPTER_REJECTED\n")

    def test_duplicate_cli_option_never_reaches_device(self):
        error = io.StringIO()
        with patch.object(adapter, "PhoneAdapter") as factory, \
             contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as stop:
            adapter.main(["discover", "--record", "private.invalid", "--record", "second.invalid"])
        self.assertEqual(stop.exception.code, 2)
        self.assertEqual(error.getvalue(), "PHONE_ADAPTER_ARGUMENTS_REJECTED\n")
        factory.assert_not_called()

    def test_changed_candidate_cannot_prevent_cleanup(self):
        self.args.artifact.write_bytes(b"invalidated after execution")
        arguments = self.arguments()
        arguments[0] = "cleanup"
        output = io.StringIO()
        with patch.object(adapter, "PhoneAdapter", return_value=self.phone), \
             patch.object(self.phone, "cleanup", return_value={"cleaned": True}) as cleanup, \
             contextlib.redirect_stdout(output):
            self.assertEqual(adapter.main(arguments), 0)
        cleanup.assert_called_once_with("test-only-target")
        self.assertEqual(json.loads(output.getvalue()), {"cleaned": True})

    def appium_instance(self):
        target = dict(appId="io.github.noah_be.overte.phone", physical=True, platform="android", enabled=True,
                      serverUrl="http://127.0.0.1:4723", process={"kind": "adb"},
                      capabilities={"appium:udid": "test-only-native-target", "appium:appPackage": "io.github.noah_be.overte.phone"})
        with patch.object(appium.AppiumAdapter, "load_targets", return_value={"test-only-appium": target}):
            instance = appium.PhoneAppiumAdapter(adapter.VerifiedCandidate(self.args))
        for boundary in (patch.object(instance, "attest_android_phone_profile"),
                         patch("adapters.android.adapter.AdbTransport", return_value=self.adb)):
            boundary.start()
            self.addCleanup(boundary.stop)
        return instance, target

    def test_appium_description_uses_same_real_installed_binding(self):
        instance, _ = self.appium_instance()
        result = instance.describe("test-only-appium")
        self.assertEqual(result["adapter"], "appium-android")
        ExecutionIdentity(self.args.artifact, "a" * 40, self.sha).verify_description(result)
        self.assertNotIn("test-only", json.dumps(result))
        self.assertEqual(len(self.adb.events), 3)

    def test_appium_virtual_remote_foreign_and_mismatched_device_are_rejected(self):
        instance, target = self.appium_instance()
        changes = [("physical", "false"), ("appId", "org.overte.pico"),
                   ("serverUrl", "https://remote.invalid"),
                   ("process", {"kind": "adb", "selector": "different-test-only-target"}),
                   ("capabilities", {"appium:udid": "auto"})]
        for key, value in changes:
            original = target[key]
            target[key] = value
            with self.assertRaises(ValueError):
                instance.describe("test-only-appium")
            target[key] = original
        self.assertEqual(self.adb.events, [])

    def test_appium_rechecks_after_session_creation_before_operation(self):
        instance, _ = self.appium_instance()
        def session(selector):
            self.adb.digest = "b" * 64  # Synthetic Appium auto-install changed the selected app.
            return (object(), "test-only-session", {})
        with patch.object(appium.AppiumAdapter, "ensure_session", side_effect=session) as native:
            with self.assertRaises(ValueError):
                instance.ensure_session("test-only-appium")
        native.assert_called_once()
        self.assertEqual(sum(event[0] == "sha256sum" for event in self.adb.events), 2)

    def test_appium_bound_guard_runs_before_session_side_effects(self):
        instance, target = self.appium_instance()
        target["serverUrl"] = "https://remote.invalid"
        with patch.object(appium.AppiumAdapter, "ensure_session") as native:
            with self.assertRaises(ValueError):
                instance.ensure_session("test-only-appium")
            native.assert_not_called()
        with patch.object(appium.AppiumAdapter, "invoke") as native:
            with self.assertRaises(ValueError):
                instance.invoke("test-only-appium", "app.upgrade", {})
            native.assert_not_called()

    def test_appium_cli_dispatch_and_invalid_candidate_cleanup(self):
        instance, _ = self.appium_instance()
        arguments = self.arguments()
        arguments[2] = "test-only-appium"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(appium.main(arguments, adapter_class=lambda _: instance), 0)
        self.assertIn("executionIdentity", json.loads(output.getvalue()))
        self.args.artifact.write_bytes(b"invalidated")
        arguments[0] = "cleanup"
        output = io.StringIO()
        with patch.object(instance, "cleanup", return_value={"cleaned": True}) as cleanup, \
             contextlib.redirect_stdout(output):
            self.assertEqual(appium.main(arguments, adapter_class=lambda _: instance), 0)
        cleanup.assert_called_once_with("test-only-appium")
        self.assertNotIn("executionIdentity", json.loads(output.getvalue()))

    def test_appium_capability_install_requires_verified_candidate_bytes(self):
        instance, target = self.appium_instance()
        target["capabilities"]["appium:app"] = str(self.args.artifact)
        self.assertIn("executionIdentity", instance.describe("test-only-appium"))
        target["capabilities"]["appium:app"] = "https://private.invalid/foreign.apk"
        self.adb.events.clear()
        with self.assertRaises(ValueError):
            instance.describe("test-only-appium")
        self.assertEqual(self.adb.events, [])

    def test_appium_emulator_binds_only_actual_x86_64_virtual_observations(self):
        instance, target = self.appium_instance()
        target["physical"] = False
        properties = {"ro.kernel.qemu": "1", "ro.product.cpu.abi": "x86_64",
                      "ro.build.version.sdk": "35", "ro.opengles.version": "196610"}
        with patch.object(self.adb, "require_connected", create=True), \
             patch.object(self.adb, "prop", side_effect=lambda _target, name: properties[name]):
            description = instance.describe("test-only-appium")
            self.assertEqual(description["role"], "phone-emulator-e2e")
            ExecutionIdentity(self.args.artifact, "a" * 40, self.sha).verify_description(description)
            for key, value in [("ro.kernel.qemu", "0"), ("ro.kernel.qemu", ""),
                               ("ro.product.cpu.abi", "arm64-v8a"), ("ro.product.cpu.abi", "x86"),
                               ("ro.build.version.sdk", "25"), ("ro.opengles.version", "0")]:
                original = properties[key]
                properties[key] = value
                self.adb.events.clear()
                with self.assertRaises(ValueError):
                    instance.describe("test-only-appium")
                self.assertEqual(self.adb.events, [])
                properties[key] = original

    def test_original_manifest_prefix_order_reaches_both_real_phone_entrypoints(self):
        appium_instance, _ = self.appium_instance()
        variants = [(ENTRY, "android-phone-adb", adapter.main, self.phone, "test-only-target"),
                    (ENTRY.with_name("appium_adapter.py"), "appium-android", appium.main,
                     appium_instance, "test-only-appium")]
        for entry, identifier, dispatch, instance, target in variants:
            with self.subTest(adapter=identifier):
                manifest = self.root / (identifier + ".json")
                manifest.write_text(json.dumps(dict(schemaVersion=1, id=identifier,
                    command=[str(entry), *self.arguments()[3:]])))
                command = load_command(manifest)
                self.assertEqual(command[:2], [sys.executable, str(entry)])
                output = io.StringIO()
                with patch.object(self.phone, "require"), contextlib.redirect_stdout(output):
                    self.assertEqual(dispatch([*command[2:], "describe", "--target", target],
                        adapter_class=lambda _candidate: instance), 0)
                ExecutionIdentity(self.args.artifact, "a" * 40, self.sha).verify_description(
                    json.loads(output.getvalue()))

    def navigation_instance(self):
        # The UI boundary is shared in-tree. Do not substitute a reference
        # header/module or stub the real Phone SH009 verifier/installed binding.
        sys.path.insert(0, str(ROOT / 'tests/device/self_tests'))
        from test_phone_navigation import NativePhone
        native = NativePhone()
        instance, target = self.appium_instance()
        target.update(scene={'kind': 'android-debug-e2e'},
            probe={'kind': 'android-run-as', 'relativePath': instance.ANDROID_DEBUG_PROBE},
            clientControl={'kind': 'android-run-as-command', 'relativePath': instance.ANDROID_CLIENT_COMMAND},
            controls={'normalNavigation': native.profile})
        path = self.root / 'normal-navigation-session.json'
        instance.state_path = lambda _selector: path

        def session(_selector):
            state = instance.read_session('test-only-appium') if path.exists() else {
                'sessionId': 'owned-session', 'generation': 1}
            return native, 'owned-session', state

        for boundary in (
                patch.object(appium.AppiumAdapter, 'ensure_session', side_effect=session),
                patch.object(instance, 'query_app_state', return_value=4),
                patch.object(instance, 'process_state', side_effect=lambda *_arguments:
                             {'running': True, 'identity': native.process})):
            boundary.start()
            self.addCleanup(boundary.stop)
        native.invoke = lambda operation, values: instance.invoke('test-only-appium', operation, values)
        return instance, target, native, path

    def test_real_candidate_bound_normal_navigation_reaches_actual_journey_and_native_input(self):
        instance, target, native, path = self.navigation_instance()
        required = {'places.open', 'places.close', 'places.goto', 'places.back', 'places.forward'}
        self.assertTrue(required <= set(instance.advertised_capabilities(target)))
        result = native.run()
        self.assertEqual(8, len(result['phases']))
        self.assertTrue(native.reports[0]['sequenceCompleted'])
        self.assertFalse(native.reports[0]['deviceAcceptance'])
        self.assertEqual(2, native.inputs.count('goBack'))
        self.assertEqual(2, native.inputs.count('goForward'))
        self.assertIn('PhoneAddressGoButton', native.inputs)
        self.assertNotIn('normalNavigation', instance.read_session('test-only-appium'))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertGreater(sum(event[0] == 'sha256sum' for event in self.adb.events), 20)

    def test_normal_navigation_is_unadvertised_and_cannot_create_sessions_without_candidate_or_opt_in(self):
        instance, target, native, _path = self.navigation_instance()
        original = instance.candidate
        for change in ('unbound', 'not-configured'):
            with self.subTest(change=change):
                instance.candidate = None if change == 'unbound' else original
                if change == 'not-configured': target['controls'] = {}
                self.assertFalse(any(operation.startswith('places.')
                    for operation in instance.advertised_capabilities(target)))
                with patch.object(appium.AppiumAdapter, 'ensure_session') as create_session:
                    with self.assertRaises(ValueError):
                        native.invoke('places.open', {})
                    create_session.assert_not_called()
        self.assertEqual([], native.inputs)
        self.assertEqual([], self.adb.events)

    def test_changed_installed_apk_rejects_normal_navigation_before_native_session_or_input(self):
        _instance, _target, native, _path = self.navigation_instance()
        self.adb.digest = 'b' * 64
        with patch.object(appium.AppiumAdapter, 'ensure_session') as create_session:
            with self.assertRaises(ValueError): native.invoke('places.open', {})
            create_session.assert_not_called()
        self.assertEqual([], native.inputs)

    def test_normal_navigation_rechecks_installed_bytes_after_the_real_ui_operation(self):
        _instance, _target, native, _path = self.navigation_instance()
        original_call = native.call
        def replacing_native_install(method, path, body=None):
            value = original_call(method, path, body)
            if path.endswith('/click'):
                self.adb.digest = 'b' * 64
            return value
        native.call = replacing_native_install
        with self.assertRaises(ValueError): native.invoke('places.open', {})
        self.assertEqual(['Go to destination'], native.inputs)
        self.assertGreaterEqual(sum(event[0] == 'sha256sum' for event in self.adb.events), 4)

    def test_process_replacement_after_native_lookup_prevents_normal_ui_input(self):
        instance, _target, native, _path = self.navigation_instance()
        def process(*_arguments):
            return {'running': True, 'identity': 'replaced' if native.calls else native.process}
        with patch.object(instance, 'process_state', side_effect=process):
            with self.assertRaisesRegex(RuntimeError, 'bound application state'):
                native.invoke('places.open', {})
        self.assertEqual([], native.inputs)

    def test_snapshot_requires_candidate_physical_debug_opt_in_before_creating_sessions(self):
        instance, target, native, _ = snapshot_boundary.attach(self, appium)
        original = instance.candidate
        for change in ('candidate', 'opt-in', 'physical', 'controlled'):
            with self.subTest(change=change), contextlib.ExitStack() as stack:
                if change == 'candidate': stack.enter_context(patch.object(instance, 'candidate', None))
                if change == 'opt-in': stack.enter_context(patch.dict(os.environ, {'OVERTE_PHONE_NORMAL_SNAPSHOT': '0'}))
                if change == 'physical': stack.enter_context(patch.dict(target, {'physical': False}))
                if change == 'controlled': stack.enter_context(patch.dict(target, {'clientControl': {}}))
                self.assertNotIn('snapshot.open', instance.advertised_capabilities(target))
                create = stack.enter_context(patch.object(appium.AppiumAdapter, 'ensure_session'))
                with self.assertRaises(ValueError): native.invoke('snapshot.open')
                create.assert_not_called()
        self.assertIs(instance.candidate, original)
        self.assertEqual([], native.inputs)
        self.assertEqual([], self.adb.events)

    def test_snapshot_changed_installed_bytes_fail_before_session_and_input(self):
        _instance, _target, native, _ = snapshot_boundary.attach(self, appium)
        self.adb.digest = 'b' * 64
        with patch.object(appium.AppiumAdapter, 'ensure_session') as create:
            with self.assertRaises(ValueError): native.invoke('snapshot.open')
            create.assert_not_called()
        self.assertEqual([], native.inputs)

    def test_snapshot_rechecks_actual_installed_bytes_after_native_input(self):
        instance, _target, native, _ = snapshot_boundary.attach(self, appium)
        call = native.call
        def replace(method, path, body=None):
            result = call(method, path, body)
            if path.endswith('/click'): self.adb.digest = 'b' * 64
            return result
        native.call = replace
        with self.assertRaisesRegex(ValueError, 'INSTALLED_BYTES_MISMATCH'):
            native.invoke('snapshot.open')
        self.assertIn('SNAP', native.inputs)
        self.assertIsNotNone(instance.snapshot_store(snapshot_boundary.SELECTOR).read())

    def test_snapshot_private_session_change_stops_before_input(self):
        instance, _target, native, path = snapshot_boundary.attach(self, appium)
        original = native.call
        def replace(method, endpoint, body=None):
            result = original(method, endpoint, body)
            state = instance.read_session(snapshot_boundary.SELECTOR)
            state['generation'] += 1
            instance.save_session(snapshot_boundary.SELECTOR, state)
            return result
        native.call = replace
        with self.assertRaisesRegex(RuntimeError, 'bound application state'):
            native.invoke('snapshot.open')
        self.assertEqual([], native.inputs)
        self.assertTrue(path.exists())

    def test_snapshot_process_replacement_after_lookup_prevents_input(self):
        instance, _target, native, _ = snapshot_boundary.attach(self, appium)
        def process(*_arguments):
            return {'running': True, 'identity': 'other-process' if native.calls else native.process}
        with patch.object(instance, 'process_state', side_effect=process):
            with self.assertRaisesRegex(RuntimeError, 'bound application state'):
                native.invoke('snapshot.open')
        self.assertEqual([], native.inputs)

    def test_snapshot_cannot_bind_an_unknown_process_start_or_pid(self):
        _instance, _target, native, _ = snapshot_boundary.attach(self, appium)
        for identity_value in ('31415:unknown', '0:123', '31415', '31415:'):
            native.process = identity_value
            with self.subTest(identity=identity_value), self.assertRaisesRegex(ValueError, 'START_TICKS_REQUIRED'):
                native.invoke('snapshot.open')
        self.assertEqual([], native.inputs)

    def test_snapshot_partial_entry_cleanup_closes_only_its_owned_panel(self):
        instance, _target, native, _ = snapshot_boundary.attach(self, appium, mutation='partial-entry-error')
        with self.assertRaisesRegex(RuntimeError, 'transport failed'): native.invoke('snapshot.open')
        self.assertEqual(native.screen, 'snapshot')
        self.assertTrue(instance.snapshot_store(snapshot_boundary.SELECTOR).read()['snapshotOwned'])
        self.assertEqual(native.invoke('snapshot.close'), {'performed': True})
        self.assertIsNone(native.screen)
        self.assertEqual((native.mode, native.format), ('animated', 'webp'))
        self.assertIsNone(instance.snapshot_store(snapshot_boundary.SELECTOR).read())
        self.assertEqual(1, native.releases)

    def test_snapshot_preexisting_tablet_is_never_taken_over_or_closed(self):
        instance, _target, native, _ = snapshot_boundary.attach(self, appium)
        native.screen = 'settings'
        with self.assertRaisesRegex(RuntimeError, 'pre-existing tablet'): native.invoke('snapshot.open')
        native.invoke('snapshot.close')
        self.assertEqual(native.screen, 'settings')
        self.assertEqual([], native.inputs)
        self.assertIsNone(instance.snapshot_store(snapshot_boundary.SELECTOR).read())

    @unittest.skipIf(os.name == 'nt', 'POSIX host fixture for actual Android private file scripts')
    def test_snapshot_bound_capture_transports_original_bytes_and_restores_preferences(self):
        instance, target, native, _ = snapshot_boundary.attach(self, appium)
        self.assertTrue({'snapshot.open', 'snapshot.capture', 'snapshot.files', 'snapshot.close'}
                        <= set(instance.advertised_capabilities(target)))
        native.invoke('snapshot.open')
        prefix = snapshot_boundary.PREFIX
        self.assertEqual(native.invoke('snapshot.files', {'prefix': prefix}), {'files': []})
        native.invoke('snapshot.capture', {'name': prefix, 'mode': 'still', 'format': 'png'})
        observed = native.invoke('snapshot.files', {'prefix': prefix})['files']
        self.assertEqual(1, len(observed))
        self.assertEqual((native.artifacts / observed[0]['artifact']).read_bytes(), b'original synthetic file bytes')
        self.assertFalse(native.screen)
        self.assertNotIn('passed', observed[0])
        native.invoke('snapshot.close')
        self.assertEqual((native.mode, native.format), ('animated', 'webp'))
        self.assertIsNone(native.screen)
        self.assertIsNone(instance.snapshot_store(snapshot_boundary.SELECTOR).read())
        self.assertEqual(1, native.captures)
        self.assertGreater(sum(event[0] == 'sha256sum' for event in self.adb.events), 15)

    @unittest.skipIf(os.name == 'nt', 'POSIX host fixture for actual Android private file scripts')
    def test_snapshot_cancel_uses_actual_owned_cancel_before_restoring_preferences(self):
        instance, _target, native, _ = snapshot_boundary.attach(self, appium, mutation='capture-pending')
        native.invoke('snapshot.open')
        native.invoke('snapshot.files', {'prefix': snapshot_boundary.PREFIX})
        native.invoke('snapshot.capture', {'name': snapshot_boundary.PREFIX, 'mode': 'still', 'format': 'png'})
        self.assertTrue(native.capturing)
        native.invoke('snapshot.close')
        self.assertIn('snapshotCancelCapture', native.inputs)
        self.assertFalse(native.capturing)
        self.assertEqual((native.mode, native.format), ('animated', 'webp'))
        self.assertIsNone(instance.snapshot_store(snapshot_boundary.SELECTOR).read())

    @unittest.skipIf(os.name == 'nt', 'POSIX host fixture for actual Android private file scripts')
    def test_snapshot_prefix_must_be_empty_and_owned_before_any_capture(self):
        instance, _target, native, _ = snapshot_boundary.attach(self, appium)
        native.invoke('snapshot.open')
        with self.assertRaisesRegex(RuntimeError, 'empty owned'):
            native.invoke('snapshot.capture', {'name': snapshot_boundary.PREFIX, 'mode': 'still', 'format': 'png'})
        prefix = snapshot_boundary.PREFIX
        native.invoke('snapshot.files', {'prefix': prefix})
        foreign = 'parity-abcdef0123456789-still-png'
        with patch.object(appium.AndroidSnapshotFiles, 'files') as read:
            with self.assertRaisesRegex(RuntimeError, 'another run'):
                native.invoke('snapshot.files', {'prefix': foreign})
            read.assert_not_called()
        (native.files / (prefix + '-preexisting.png')).write_bytes(b'old')
        with self.assertRaisesRegex(RuntimeError, 'no longer empty'):
            native.invoke('snapshot.capture', {'name': prefix, 'mode': 'still', 'format': 'png'})
        self.assertEqual(0, native.captures)
        native.invoke('snapshot.close')

    def test_snapshot_changed_ownership_context_and_nonprivate_state_reject(self):
        instance, _target, native, _ = snapshot_boundary.attach(self, appium)
        native.invoke('snapshot.open')
        store = instance.snapshot_store(snapshot_boundary.SELECTOR)
        owned = store.read(); owned['processIdentity'] = 'other-process'
        store.write(owned)
        native.inputs.clear()
        with self.assertRaisesRegex(RuntimeError, 'different bound session'):
            native.invoke('snapshot.open')
        self.assertEqual([], native.inputs)
        if os.name != 'nt':
            store.path.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, 'private file'): native.invoke('snapshot.open')
            self.assertEqual([], native.inputs)

    @unittest.skipIf(os.name == 'nt', 'POSIX ownership aliases')
    def test_snapshot_private_state_aliases_are_never_read_or_overwritten(self):
        instance, _target, native, _ = snapshot_boundary.attach(self, appium)
        native.invoke('snapshot.open')
        store = instance.snapshot_store(snapshot_boundary.SELECTOR)
        original = store.path.read_bytes()
        foreign = self.root / 'foreign-state.json'
        store.path.rename(foreign)
        for alias in ('symlink', 'hardlink'):
            if alias == 'symlink': store.path.symlink_to(foreign)
            else: os.link(foreign, store.path)
            with self.subTest(alias=alias), self.assertRaisesRegex(RuntimeError, 'private file'):
                native.invoke('snapshot.open')
            self.assertEqual(original, foreign.read_bytes())
            store.path.unlink()

    def test_snapshot_cleanup_confirms_stop_even_when_candidate_and_terminate_are_invalid(self):
        instance, _target, native, path = snapshot_boundary.attach(self, appium)
        native.invoke('snapshot.open')
        self.args.artifact.write_bytes(b'invalidated candidate after local fixture input')
        self.assertTrue(path.exists())
        with snapshot_boundary.cleanup_boundary(self, native):
            self.assertEqual(instance.cleanup(snapshot_boundary.SELECTOR), {'cleaned': True})
        self.assertFalse(path.exists())
        self.assertIsNone(instance.snapshot_store(snapshot_boundary.SELECTOR).read())
        self.assertIn(('am', 'force-stop', snapshot_boundary.PACKAGE), self.adb.events)
        self.assertEqual(4, self.adb.events.count(('pidof', '-s', snapshot_boundary.PACKAGE)))

    def test_snapshot_cleanup_retains_retry_state_if_process_stop_is_not_confirmed(self):
        instance, _target, native, path = snapshot_boundary.attach(self, appium)
        native.invoke('snapshot.open')
        before = instance.snapshot_store(snapshot_boundary.SELECTOR).read()
        with snapshot_boundary.cleanup_boundary(self, native, stopped=False):
            with self.assertRaisesRegex(RuntimeError, 'did not stop'):
                instance.cleanup(snapshot_boundary.SELECTOR)
        self.assertTrue(path.exists())
        self.assertEqual(before, instance.snapshot_store(snapshot_boundary.SELECTOR).read())
        self.assertFalse(any(method == 'DELETE' and endpoint == '/session/owned-session'
                             for method, endpoint, _ in native.calls))

    def test_snapshot_cleanup_preserves_both_states_on_session_delete_failure(self):
        instance, _target, native, path = snapshot_boundary.attach(self, appium, mutation='session-delete-error')
        native.invoke('snapshot.open')
        before = instance.snapshot_store(snapshot_boundary.SELECTOR).read()
        with snapshot_boundary.cleanup_boundary(self, native):
            with self.assertRaisesRegex(RuntimeError, 'retry state was retained'):
                instance.cleanup(snapshot_boundary.SELECTOR)
        self.assertTrue(path.exists())
        self.assertEqual(before, instance.snapshot_store(snapshot_boundary.SELECTOR).read())

    def test_snapshot_cleanup_refuses_changed_target_before_any_os_action(self):
        instance, target, native, path = snapshot_boundary.attach(self, appium)
        native.invoke('snapshot.open')
        self.adb.events.clear()
        target['capabilities']['appium:udid'] = 'different-test-only-device'
        with self.assertRaisesRegex(ValueError, 'CLEANUP_TARGET_CHANGED'):
            instance.cleanup(snapshot_boundary.SELECTOR)
        self.assertTrue(path.exists())
        self.assertEqual([], self.adb.events)


if __name__ == "__main__":
    unittest.main()
