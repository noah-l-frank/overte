#!/usr/bin/env python3
"""Device-free tests for the Pico OpenXR common-adapter session."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.device.openxr_input.adapter_session import (
    AdapterSessionError, PicoOpenXrAdapterSession, isolated_server_port,
    resolve_state_directory,
)


class FakeTransport:
    def __init__(self) -> None:
        self.envelopes: list[dict] = []
        self.cleanup_count = 0

    def stage(self, envelope, profile, *, before_publish=None):
        if before_publish is not None:before_publish(deepcopy(envelope))
        self.envelopes.append(envelope)
        return {"sequence": envelope["sequence"]}

    def read_status(self, *, expected_nonce=None, expected_sequence=None):
        sequence = expected_sequence or len(self.envelopes)
        operation = (self.envelopes[sequence - 1]["commands"][0]["operation"]
                     if sequence else "")
        return {
            "enabled": True,
            "acceptedSequence": sequence,
            "acceptedNonce": "[redacted]",
            "state": "active" if expected_sequence is not None else "neutral",
            "activeCommandId": (f"{operation.replace('.', '-')}-{sequence}"
                                if expected_sequence is not None else ""),
            "viewAppliedSequence": sequence if operation == "input.look" else 0,
            "viewAppliedYawDegrees": 25.0 if operation == "input.look" else 0.0,
            "viewAppliedPitchDegrees": 0.0,
            "vectorAppliedSequence": sequence if operation == "input.move" else 0,
            "leftThumbstickAppliedX": 0.0,
            "leftThumbstickAppliedY": 0.4 if operation == "input.move" else 0.0,
            "booleanAppliedSequence": sequence if (
                operation.startswith("tablet.") or
                operation in {"input.jump", "input.fly"}) else 0,
            "leftSecondaryApplied": operation.startswith("tablet."),
            "rightSecondaryApplied": operation in {"input.jump", "input.fly"},
        }

    def cleanup(self):
        self.cleanup_count += 1


class PicoOpenXrAdapterSessionTests(unittest.TestCase):
    def test_owned_status_preserves_one_active_answer_and_transition_epoch_without_replay(self):
        self.session.begin('42:100')
        self.session.stage('42:100','controller.button',dict(hand='left',control='primary',holdMilliseconds=120))
        owned=self.transport.envelopes[0];original=self.session.state_path.read_bytes()
        status=dict(enabled=True,acceptedSequence=owned['sequence'],acceptedNonce='[redacted]',state='active',activeCommandId='controller-button-1',updatedEpochMs=20000)
        with mock.patch.object(self.transport,'read_status',return_value=status) as read:
            self.assertEqual(status,self.session.observe_owned_status('42:100',owned));read.assert_called_once_with(expected_nonce=owned['sessionNonce'])
            with self.assertRaises(AdapterSessionError):self.session.observe_owned_status('42:101',owned)
            self.assertEqual(1,read.call_count)
        self.assertEqual(original,self.session.state_path.read_bytes());self.assertEqual(1,len(self.transport.envelopes))

    def test_host_binding_absence_is_read_only_and_invalid_or_dangling_state_is_not_absence(self):
        self.assertTrue(self.session.is_unbound())
        self.assertFalse(self.session.state_path.exists())
        self.session.begin('42:100'); self.assertFalse(self.session.is_unbound())
        self.assertEqual([], self.transport.envelopes)
        self.session.state_path.unlink(); self.session.state_path.symlink_to(self.root / 'missing-owned-file')
        with self.assertRaises(AdapterSessionError): self.session.is_unbound()
        self.session.state_path.unlink(); self.session.state_path.write_text('invalid')
        self.session.state_path.chmod(0o600)
        with self.assertRaises(AdapterSessionError): self.session.is_unbound()

    def test_consumed_ack_is_not_lost_to_a_redundant_read_after_watchdog_expiry(self):
        cases = [('input.look', {'horizontal': 0.25, 'vertical': 0.0}),
                 ('input.move', {'direction': 'forward', 'durationSeconds': 1.5}),
                 ('input.fly', {'durationSeconds': 3.0})]
        for operation, arguments in cases:
            with self.subTest(operation=operation):
                directory = self.root/operation
                directory.mkdir(mode=0o700)
                transport = FakeTransport()
                session = PicoOpenXrAdapterSession(transport, 'fixture-target', directory)
                session.begin('42:100')
                original = transport.read_status
                calls = []
                def delayed(**kwargs):
                    status = original(**kwargs)
                    calls.append(status)
                    if len(calls)>1:
                        status.update(state='error', enabled=False, detail='watchdog')
                    return status
                with mock.patch.object(transport, 'read_status', side_effect=delayed):
                    result = session.stage('42:100', operation, arguments)
                self.assertTrue(result['performed'])
                self.assertEqual(len(calls), 1)

    def test_an_accepted_but_unconsumed_ack_cannot_replace_actual_controller_consumption(self):
        self.session.begin('42:100')
        original = self.transport.read_status
        calls = []
        def unconsumed(**kwargs):
            status = original(**kwargs)
            status['vectorAppliedSequence'] = 0
            calls.append(status)
            if len(calls)>1:
                status.update(state='error', enabled=False, detail='watchdog')
            return status
        with mock.patch.object(self.transport, 'read_status', side_effect=unconsumed):
            with self.assertRaises(AdapterSessionError):
                self.session.stage('42:100', 'input.move', {'direction':'forward','durationSeconds':1.5})
        self.assertEqual(len(calls), 2)

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="pico-openxr-session-")
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.transport = FakeTransport()
        self.session = PicoOpenXrAdapterSession(
            self.transport, "private-pico-selector", self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_owned_controller_intent_is_original_and_durable_before_transport(self):
        self.session.begin('42:100');saved=[]
        original=self.transport.stage
        def staged(value,profile):
            self.assertEqual(saved[0],value);return original(value,profile)
        def intent(value):
            saved.append(__import__('copy').deepcopy(value));value['commands'].clear()
        with mock.patch.object(self.transport,'stage',side_effect=staged):
            self.session.stage('42:100','controller.button',{'hand':'left','control':'primary'},intent=intent)
        self.assertEqual(1,len(self.transport.envelopes[0]['commands']))
        self.assertEqual('controller.button',saved[0]['commands'][0]['operation'])

    def test_failed_intent_does_not_stage_or_advance_the_exact_session_cursor(self):
        self.session.begin('42:100')
        def fail(_value):raise RuntimeError('explicit synthetic private-disk failure')
        with self.assertRaises(RuntimeError):
            self.session.stage('42:100','controller.button',{'hand':'left','control':'primary'},intent=fail)
        self.assertEqual([],self.transport.envelopes)
        self.assertEqual(1,self.session._load()['nextSequence'])

    def test_owned_neutral_is_read_only_and_requires_the_original_process_nonce_and_cursor(self):
        self.session.begin('42:100');owned=[]
        self.session.stage('42:100','controller.button',{'hand':'left','control':'primary'},intent=owned.append)
        self.assertEqual('neutral',self.session.require_owned_neutral('42:100',owned[0])['state'])
        self.assertEqual(1,len(self.transport.envelopes));self.assertEqual(0,self.transport.cleanup_count)
        with self.assertRaises(AdapterSessionError):self.session.require_owned_neutral('43:101',owned[0])
        original=owned[0]['sessionNonce'];owned[0]['sessionNonce']='f'*64
        with self.assertRaises(AdapterSessionError):self.session.require_owned_neutral('42:100',owned[0])
        owned[0]['sessionNonce']=original
        self.session.stage('42:100','input.jump',{})
        with self.assertRaises(AdapterSessionError):self.session.require_owned_neutral('42:100',owned[0])
        self.assertEqual(2,len(self.transport.envelopes))

    def test_common_operations_share_nonce_and_advance_sequence(self) -> None:
        self.session.begin("42:100")
        first = self.session.stage(
            "42:100", "input.look", {"horizontal": 0.25, "vertical": 0.0})
        second = self.session.stage(
            "42:100", "input.move",
            {"direction": "forward", "durationSeconds": 1.5})
        self.assertEqual([1, 2], [item["sequence"] for item in self.transport.envelopes])
        self.assertEqual(self.transport.envelopes[0]["sessionNonce"],
                         self.transport.envelopes[1]["sessionNonce"])
        self.assertEqual("head-pose", first["inputDomain"])
        self.assertTrue(first["viewApplied"])
        self.assertEqual(25.0, first["viewYawDegrees"])
        self.assertEqual("controller-action", second["inputDomain"])
        self.assertTrue(second["openXrVectorApplied"])
        self.assertEqual(0.0, second["openXrLeftThumbstickX"])
        self.assertEqual(0.4, second["openXrLeftThumbstickY"])
        serialized = str((first, second))
        self.assertNotIn(self.transport.envelopes[0]["sessionNonce"], serialized)
        self.assertNotIn("private-pico-selector", self.session.state_path.name)
        self.assertEqual(0o600, self.session.state_path.stat().st_mode & 0o777)

    def test_process_restart_fails_closed_without_rotating_nonce(self) -> None:
        self.session.begin("42:100")
        self.session.stage("42:100", "tablet.open", {})
        old_nonce = self.transport.envelopes[-1]["sessionNonce"]
        with self.assertRaisesRegex(AdapterSessionError, "identity changed"):
            self.session.stage("43:200", "tablet.close", {})
        self.assertEqual(0, self.transport.cleanup_count)
        self.assertEqual(1, self.transport.envelopes[-1]["sequence"])
        self.assertEqual(old_nonce, self.transport.envelopes[-1]["sessionNonce"])

    def test_jump_and_fly_use_right_secondary_with_one_shared_session(self) -> None:
        self.session.begin("42:100")
        jumped = self.session.stage("42:100", "input.jump", {})
        flew = self.session.stage(
            "42:100", "input.fly", {"durationSeconds": 3.0})
        self.assertEqual([1, 2], [
            envelope["sequence"] for envelope in self.transport.envelopes])
        self.assertEqual(
            self.transport.envelopes[0]["sessionNonce"],
            self.transport.envelopes[1]["sessionNonce"],
        )
        self.assertTrue(jumped["openXrBooleanApplied"])
        self.assertTrue(jumped["openXrRightSecondaryApplied"])
        self.assertTrue(flew["openXrBooleanApplied"])
        self.assertTrue(flew["openXrRightSecondaryApplied"])
        self.assertFalse(jumped["neutralBeforeCommand"])
        self.assertTrue(flew["neutralBeforeCommand"])

    def test_completed_jump_requires_exact_native_consumption(self) -> None:
        self.session.begin("42:100")
        original = self.transport.read_status
        def completed(**kwargs):
            status = original(**kwargs)
            if kwargs.get("expected_sequence") is not None:
                status.update(state="neutral", enabled=False, detail="watchdog")
            return status
        with mock.patch.object(self.transport, "read_status", side_effect=completed):
            result = self.session.stage("42:100", "input.jump", {})
        self.assertEqual("neutral", result["nativeState"])
        self.assertTrue(result["openXrRightSecondaryApplied"])

    def test_completed_jump_rejects_unconsumed_wrong_expired_and_failed_status(self) -> None:
        base = {"state": "neutral", "enabled": False, "detail": "watchdog",
                "booleanAppliedSequence": 1, "rightSecondaryApplied": True}
        for change in [{"booleanAppliedSequence": 0},
                       {"booleanAppliedSequence": 2},
                       {"rightSecondaryApplied": False},
                       {"detail": "expired-or-clock"}, {"state": "error"}]:
            with self.subTest(change=change):
                status = dict(base, **change)
                self.assertFalse(self.session._completed_jump_applied(status, 1))

    def test_completed_flight_cannot_substitute_for_active_input(self) -> None:
        self.session.begin("42:100")
        original = self.transport.read_status
        def completed(**kwargs):
            status = original(**kwargs)
            if kwargs.get("expected_sequence") is not None:
                status.update(state="neutral", enabled=False, detail="watchdog")
            return status
        with mock.patch.object(self.transport, "read_status", side_effect=completed):
            with self.assertRaisesRegex(AdapterSessionError, "rejected"):
                self.session.stage("42:100", "input.fly", {"durationSeconds": 3.0})

    def test_cleanup_is_neutral_and_idempotent(self) -> None:
        self.session.begin("42:100")
        self.session.stage("42:100", "tablet.open", {})
        self.session.cleanup(process_running=True)
        self.session.cleanup(process_running=False)
        self.assertEqual(2, self.transport.cleanup_count)
        self.assertFalse(self.session.state_path.exists())

    def test_stage_requires_the_single_launcher_session(self) -> None:
        with self.assertRaisesRegex(AdapterSessionError, "not established"):
            self.session.stage("42:100", "input.look", {})
        self.session.begin("42:100")
        self.session.require_process_identity("42:100")
        with self.assertRaisesRegex(AdapterSessionError, "identity changed"):
            self.session.require_process_identity("43:200")
        with self.assertRaisesRegex(AdapterSessionError, "already established"):
            self.session.begin("42:100")

    def test_configuration_requires_nondefault_port_and_private_directory(self) -> None:
        with mock.patch.dict(os.environ, {"ANDROID_ADB_SERVER_PORT": "5037"}, clear=True):
            with self.assertRaisesRegex(AdapterSessionError, "non-default"):
                isolated_server_port()
        insecure = self.root / "insecure"
        insecure.mkdir(mode=0o755)
        insecure.chmod(0o755)  # A restrictive caller umask must not repair this fixture.
        with mock.patch.dict(os.environ, {
                "OVERTE_PICO_OPENXR_STATE_DIR": str(insecure)}, clear=True):
            with self.assertRaisesRegex(AdapterSessionError, "not private"):
                resolve_state_directory()


if __name__ == "__main__":
    unittest.main()
