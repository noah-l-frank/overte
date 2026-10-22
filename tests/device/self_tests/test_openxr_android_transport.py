#!/usr/bin/env python3
"""Device-free tests for the private Pico OpenXR input transport."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.device.openxr_input.android_transport import (
    AndroidOpenXrTransport, BUILD_MARKER, CONSUMER, TransportError,
    PROFILE_ID, PROFILE_SHA256, profile_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1] / "openxr_input"
sys.path.insert(0,str(ROOT.parent))
PROFILE = json.loads(
    (ROOT / "profiles/pico4-overte-controller.json").read_text(encoding="utf-8"))
NONCE = "d" * 64


class FakeRunner:
    def __init__(self, selector: str) -> None:
        self.selector = selector
        self.calls: list[tuple[list[str], bytes | None]] = []
        self.status = b""

    def __call__(self, command, *, input=None, capture_output, check, timeout):
        if timeout != 20:
            raise AssertionError("controller transport must use a bounded ADB timeout")
        self.calls.append((command, input))
        if command[-1] == "devices":
            output = f"List of devices attached\n{self.selector}\tdevice\n".encode()
        elif command[-1] == "get-state":
            output = b"device\n"
        elif "cat \"$file\"" in command[-1]:
            output = self.status
        else:
            output = b""
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr=b"")


class OpenXrAndroidTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.adb = Path(self.temporary.name) / "adb"
        self.adb.write_text("mock", encoding="utf-8")
        self.selector = "pico-test-target"
        self.runner = FakeRunner(self.selector)
        self.transport = AndroidOpenXrTransport(
            self.adb, self.selector, runner=self.runner)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def envelope(self) -> dict:
        return {
            "schemaVersion": 1,
            "sessionNonce": NONCE,
            "sequence": 4,
            "commands": [{
                "id": "move-forward",
                "operation": "input.move",
                "arguments": {"direction": "forward", "durationSeconds": 0.4},
            }],
        }

    def test_stages_commands_then_exact_short_lived_grant(self) -> None:
        result = self.transport.stage(self.envelope(), PROFILE,
                                      now_ms=2_000_000_000_000, lifetime_ms=60_000)
        writes = [(command, payload) for command, payload in self.runner.calls if payload]
        self.assertEqual(2, len(writes))
        command_payload = json.loads(writes[0][1])
        grant_payload = json.loads(writes[1][1])
        self.assertEqual(self.envelope(), command_payload)
        self.assertEqual(BUILD_MARKER, grant_payload["buildMarker"])
        self.assertEqual(CONSUMER, grant_payload["consumer"])
        self.assertEqual(NONCE, grant_payload["sessionNonce"])
        self.assertEqual(4, grant_payload["sequence"])
        self.assertEqual(2_000_000_060_000, grant_payload["expiresEpochMs"])
        self.assertEqual(profile_fingerprint(PROFILE),
                         grant_payload["bindingProfileSha256"])
        self.assertEqual("[redacted]", result["sessionNonce"])
        self.assertNotIn(NONCE, json.dumps(result))
        self.assertIn("commands.json", writes[0][0][-1])
        self.assertIn("grant.json", writes[1][0][-1])
        self.assertIn(f'expected={len(writes[0][1])};', writes[0][0][-1])
        self.assertIn(f'expected={len(writes[1][1])};', writes[1][0][-1])
        self.assertIn('count="$expected"', writes[0][0][-1])
        self.assertIn('wc -c < "$temporary"', writes[0][0][-1])
        self.assertEqual(["shell", "-T"], writes[0][0][-3:-1])
        self.assertEqual([str(self.adb), "-P", "5038", "-s", self.selector],
                         writes[0][0][:5])

    def test_remote_shell_is_fixed_and_envelope_never_enters_argv(self) -> None:
        envelope = self.envelope()
        envelope["commands"][0]["id"] = "safe-identifier"
        self.transport.stage(envelope, PROFILE, now_ms=2_000_000_000_000)
        for command, payload in self.runner.calls:
            if payload:
                argv = " ".join(command)
                self.assertNotIn("safe-identifier", argv)
                self.assertNotIn(NONCE, argv)
                self.assertIn("run-as org.overte.pico", argv)
                self.assertIn("sh -c '", argv)
                self.assertNotIn("/sdcard", argv)

    def test_stage_requires_the_exact_native_profile_fingerprint(self) -> None:
        changed = deepcopy(PROFILE)
        changed["viewInjection"]["maxYawDegrees"] = 44
        with self.assertRaisesRegex(TransportError, "native Pico layer"):
            self.transport.stage(self.envelope(), changed,
                                 now_ms=2_000_000_000_000)
        self.assertFalse(any(payload for _, payload in self.runner.calls))

    def test_final_callback_is_after_original_sdk_validation_and_cannot_change_wire_bytes(self):
        envelope=self.envelope();original=deepcopy(envelope);seen=[]
        def final(value):
            if not seen:self.assertEqual(['devices','get-state'],[command[-1] for command,_ in self.runner.calls])
            self.assertEqual(len(seen),sum(bool(payload) for _,payload in self.runner.calls));seen.append(deepcopy(value))
            value['commands'][0]['arguments']['durationSeconds']=.9
            envelope['sequence']=999;envelope['commands'][0]['arguments']['durationSeconds']=.8
        self.transport.stage(envelope,PROFILE,now_ms=2_000_000_000_000,before_publish=final)
        self.assertEqual([original,original],seen);writes=[json.loads(payload) for _,payload in self.runner.calls if payload]
        self.assertEqual(original,writes[0]);self.assertEqual(original['sequence'],writes[1]['sequence'])

    def test_final_callback_failure_and_invalid_callback_never_publish_or_retry(self):
        seen=[]
        def refuse(value):seen.append(deepcopy(value));raise RuntimeError('original admission refused')
        with self.assertRaisesRegex(RuntimeError,'original admission refused'):
            self.transport.stage(self.envelope(),PROFILE,before_publish=refuse)
        self.assertEqual(1,len(seen));self.assertFalse(any(payload for _,payload in self.runner.calls))
        before=len(self.runner.calls)
        with self.assertRaises(TransportError):self.transport.stage(self.envelope(),PROFILE,before_publish=False)
        self.assertEqual(before,len(self.runner.calls))
        changed=deepcopy(PROFILE);changed['viewInjection']['maxYawDegrees']=44
        with self.assertRaises(TransportError):self.transport.stage(self.envelope(),changed,before_publish=seen.append)
        self.assertEqual(1,len(seen));self.assertFalse(any(payload for _,payload in self.runner.calls))

    def test_session_final_callback_rejects_slow_sdk_and_command_writer_after_single_durable_intent(self):
        from tests.device.openxr_input.adapter_session import PicoOpenXrAdapterSession,AdapterSessionError
        from adapters.normal_feature_state import PrivateFeatureState
        from adapters.normal_ui import NativeUIError
        root=Path(self.temporary.name);root.chmod(0o700)
        for delayed in ('SDK','commands'):
            with self.subTest(delayed=delayed):
                directory=root/delayed;directory.mkdir(mode=0o700)
                runner=FakeRunner(self.selector);transport=AndroidOpenXrTransport(self.adb,self.selector,runner=runner)
                session=PicoOpenXrAdapterSession(transport,self.selector,directory);session.begin('42:original')
                store=PrivateFeatureState(directory/'owned-original.json');clock=[10.0];writes=[];finals=[]
                anchor=dict(hostStarted=clock[0],nativeEpochMs=10000)
                def intent(value):
                    # The original owner never replaces or resends a consumed intent.
                    self.assertIsNone(store.read());original=dict(envelope=deepcopy(value),anchor=deepcopy(anchor))
                    store.write(original,None);writes.append(original)
                original_guard=transport.require_exclusive_target;original_write=transport._atomic_write
                def guard():
                    original_guard()
                    if delayed=='SDK':clock[0]+=2
                def written(name,payload):
                    original_write(name,payload)
                    if delayed=='commands' and name=='commands.json':clock[0]+=2
                def final(value):
                    finals.append(deepcopy(value));calls=len(runner.calls)
                    # No live IO or session reentry while the actual session lock
                    # is held. Only original private CAS and host-clock reads.
                    with patch.object(transport,'_run',side_effect=AssertionError('callback attempted SDK IO')),\
                            patch.object(session,'_lock',side_effect=AssertionError('callback reentered session')):
                        original=store.read();self.assertEqual(value,original['envelope']);self.assertEqual(anchor,original['anchor'])
                        # Original native epoch stays frozen despite the slow
                        # real SDK guard/command writer. Host age still refuses.
                        effective=max(10000,anchor['nativeEpochMs']+math.ceil((clock[0]-anchor['hostStarted'])*1000))
                        if effective-original['anchor']['nativeEpochMs']>1500:raise NativeUIError('original input anchor aged')
                    self.assertEqual(calls,len(runner.calls))
                with patch.object(transport,'require_exclusive_target',guard),patch.object(transport,'_atomic_write',written),\
                        patch.object(session,'_wait_for_ack',side_effect=AssertionError('unexpected grant/ACK')),self.assertRaises(NativeUIError):
                    session.stage('42:original','input.primary',dict(positionMeters=[0,1,0],orientation=[0,0,0,1]),
                        intent=intent,before_publish=final)
                self.assertEqual(1,len(writes));self.assertEqual(1 if delayed=='SDK' else 2,len(finals));self.assertIsNotNone(store.read())
                payloads=[payload for _,payload in runner.calls if payload]
                self.assertEqual(0 if delayed=='SDK' else 1,len(payloads))
                self.assertFalse(any(payload and 'grant.json' in command[-1] for command,payload in runner.calls))
                self.assertEqual(1,session._load()['nextSequence'])
                before=len(runner.calls)
                with self.assertRaises(AssertionError):
                    session.stage('42:original','input.primary',dict(positionMeters=[0,1,0],orientation=[0,0,0,1]),intent=intent,before_publish=final)
                self.assertEqual(before,len(runner.calls));self.assertEqual(1,len(writes))
                with self.assertRaises(AdapterSessionError):session.stage('42:original','input.primary',{},before_publish=False)

    def test_exclusivity_is_checked_before_any_write(self) -> None:
        class TwoDeviceRunner(FakeRunner):
            def __call__(self, command, **kwargs):
                result = super().__call__(command, **kwargs)
                if command[-1] == "devices":
                    result.stdout += b"other\tdevice\n"
                return result

        runner = TwoDeviceRunner(self.selector)
        transport = AndroidOpenXrTransport(self.adb, self.selector, runner=runner)
        with self.assertRaisesRegex(TransportError, "exactly"):
            transport.stage(self.envelope(), PROFILE, now_ms=2_000_000_000_000)
        self.assertFalse(any(payload for _, payload in runner.calls))

        class OfflineRunner(FakeRunner):
            def __call__(self, command, **kwargs):
                result = super().__call__(command, **kwargs)
                if command[-1] == "devices":
                    result.stdout += b"unrelated\toffline\n"
                return result

        runner = OfflineRunner(self.selector)
        transport = AndroidOpenXrTransport(self.adb, self.selector, runner=runner)
        with self.assertRaisesRegex(TransportError, "exactly"):
            transport.stage(self.envelope(), PROFILE, now_ms=2_000_000_000_000)
        self.assertFalse(any(payload for _, payload in runner.calls))

        class UnauthorizedRunner(FakeRunner):
            def __call__(self, command, **kwargs):
                result = super().__call__(command, **kwargs)
                if command[-1] == "devices":
                    result.stdout += b"unrelated\tunauthorized\n"
                return result

        runner = UnauthorizedRunner(self.selector)
        transport = AndroidOpenXrTransport(self.adb, self.selector, runner=runner)
        with self.assertRaisesRegex(TransportError, "exactly"):
            transport.stage(self.envelope(), PROFILE, now_ms=2_000_000_000_000)
        self.assertFalse(any(payload for _, payload in runner.calls))

    def test_explicitly_detached_usb_record_is_not_an_active_target(self) -> None:
        class DetachedUsbRunner(FakeRunner):
            def __call__(self, command, **kwargs):
                result = super().__call__(command, **kwargs)
                if command[-1] == "devices":
                    result.stdout += b"detached-usb-transport\tdetached\n"
                return result

        runner = DetachedUsbRunner(self.selector)
        transport = AndroidOpenXrTransport(self.adb, self.selector, runner=runner)
        transport.require_exclusive_target()

    def test_status_validates_nonce_and_redacts_it(self) -> None:
        self.runner.status = json.dumps({
            "schemaVersion": 1,
            "buildMarker": BUILD_MARKER,
            "consumer": CONSUMER,
            "profileId": PROFILE_ID,
            "bindingProfileSha256": PROFILE_SHA256,
            "enabled": True,
            "acceptedSequence": 4,
            "viewAppliedSequence": 4,
            "viewAppliedYawDegrees": 25.0,
            "viewAppliedPitchDegrees": 0.0,
            "vectorAppliedSequence": 4,
            "leftThumbstickAppliedX": 0.0,
            "leftThumbstickAppliedY": 0.4,
            "booleanAppliedSequence": 0,
            "leftSecondaryApplied": False,
            "rightSecondaryApplied": False,
            "acceptedNonce": NONCE,
            "activeCommandId": "move-forward",
            "state": "active",
            "detail": "command-window",
            "updatedEpochMs": 2_000_000_000_000,
        }).encode()
        status = self.transport.read_status(expected_nonce=NONCE, expected_sequence=4)
        self.assertEqual("[redacted]", status["acceptedNonce"])
        self.assertEqual(4, status["viewAppliedSequence"])
        self.assertEqual(25.0, status["viewAppliedYawDegrees"])
        self.assertEqual(0.0, status["leftThumbstickAppliedX"])
        self.assertEqual(0.4, status["leftThumbstickAppliedY"])
        with self.assertRaisesRegex(TransportError, "nonce"):
            self.transport.read_status(expected_nonce="e" * 64)

        invalid = json.loads(self.runner.status)
        invalid["enabled"] = 1
        self.runner.status = json.dumps(invalid).encode()
        with self.assertRaisesRegex(TransportError, "values"):
            self.transport.read_status()

        invalid = json.loads(self.runner.status)
        invalid["enabled"] = True
        invalid["viewAppliedSequence"] = 5
        self.runner.status = json.dumps(invalid).encode()
        with self.assertRaisesRegex(TransportError, "values"):
            self.transport.read_status()

    def test_staged_status_poll_reuses_only_a_recent_exclusivity_proof(self) -> None:
        self.transport.stage(
            self.envelope(), PROFILE, now_ms=2_000_000_000_000)
        self.runner.status = json.dumps({
            "schemaVersion": 1,
            "buildMarker": BUILD_MARKER,
            "consumer": CONSUMER,
            "profileId": PROFILE_ID,
            "bindingProfileSha256": PROFILE_SHA256,
            "enabled": True,
            "acceptedSequence": 4,
            "viewAppliedSequence": 0,
            "viewAppliedYawDegrees": 0.0,
            "viewAppliedPitchDegrees": 0.0,
            "vectorAppliedSequence": 4,
            "leftThumbstickAppliedX": 0.0,
            "leftThumbstickAppliedY": 0.4,
            "booleanAppliedSequence": 0,
            "leftSecondaryApplied": False,
            "rightSecondaryApplied": False,
            "acceptedNonce": NONCE,
            "activeCommandId": "move-forward",
            "state": "active",
            "detail": "vector-consumed",
            "updatedEpochMs": 2_000_000_000_000,
        }).encode()
        self.transport.read_status(expected_nonce=NONCE, expected_sequence=4)
        self.assertEqual(
            1, sum(command[-1] == "devices" for command, _ in self.runner.calls))
        self.assertEqual(
            1, sum(command[-1] == "get-state" for command, _ in self.runner.calls))

    def test_cleanup_removes_only_allowlisted_private_transport_files(self) -> None:
        self.transport.cleanup()
        cleanup = self.runner.calls[-1][0]
        self.assertIn("grant.json", cleanup[-1])
        self.assertIn("commands.json", cleanup[-1])
        self.assertNotIn("status.json", cleanup[-1])
        self.assertNotIn("-rf", cleanup[-1])

    def test_timeout_is_reported_without_leaking_target_identity(self) -> None:
        def timeout_runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        transport = AndroidOpenXrTransport(
            self.adb, self.selector, runner=timeout_runner)
        with self.assertRaisesRegex(TransportError, "discovery timed out") as context:
            transport.require_exclusive_target()
        self.assertNotIn(self.selector, str(context.exception))

    def test_broken_write_pipe_is_redacted_and_never_commits_grant(self) -> None:
        class BrokenPipeRunner(FakeRunner):
            def __call__(self, command, **kwargs):
                if command[-3:-1] == ["shell", "-T"]:
                    self.calls.append((command, kwargs.get("input")))
                    raise BrokenPipeError("private-pipe-detail")
                return super().__call__(command, **kwargs)

        runner = BrokenPipeRunner(self.selector)
        transport = AndroidOpenXrTransport(self.adb, self.selector, runner=runner)
        with self.assertRaisesRegex(TransportError, "commands-write failed") as context:
            transport.stage(self.envelope(), PROFILE, now_ms=2_000_000_000_000)
        self.assertNotIn("private-pipe-detail", str(context.exception))
        self.assertEqual(1, sum(payload is not None for _, payload in runner.calls))


if __name__ == "__main__":
    unittest.main()
