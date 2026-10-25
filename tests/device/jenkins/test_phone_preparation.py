"""Exercise real normal Phone input and fresh observation guards without devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
DEVICE = HERE.parent
SOURCE = DEVICE.parents[1]
sys.path[:0] = [str(HERE), str(DEVICE), str(DEVICE / 'adapters/android-phone'), str(SOURCE)]
import phone_preparation as preparation
from phone_worker import validate_tutorial
from appium_adapter import PhoneAppiumAdapter
from adapters.normal_ui import NativeUIError, W3C_ELEMENT
from tests.device.self_tests.test_vertical_locomotion import snapshot


class Clock:
    def __init__(self): self.ms = 2_000_000_000_000
    def time_ns(self): return self.ms * 1_000_000
    def monotonic(self): return self.ms / 1000
    def sleep(self, seconds): self.ms += round(seconds * 1000)


class Client:
    def __init__(self, owner):
        self.owner = owner
        self.open = self.focus = False
        self.text = ''
        self.calls = []
        self.inputs = []
    def call(self, method, path, body=None):
        self.calls.append((method, path, deepcopy(body)))
        if path.endswith('/elements'):
            name = body['value'].split(':id/')[-1]
            visible = (name == 'Go to destination' and not self.open
                       or name in ('PhoneAddressField', 'PhoneAddressCancelButton') and self.open)
            return [{W3C_ELEMENT: name.replace(' ', '-')}] if visible else []
        if path.endswith('/displayed') or path.endswith('/enabled'): return True
        if path.endswith('/click'):
            name = path.split('/element/')[1].split('/')[0]
            self.inputs.append(name)
            if name == 'Go-to-destination': self.open = True
            if name == 'PhoneAddressField' and self.owner.fault != 'focus': self.focus = True
            if self.owner.fault == 'candidate': self.owner.identity['artifactSha256'] = 'c' * 64
            return None
        if path.endswith('/clear'): self.text = ''; self.inputs.append('clear'); return None
        if path.endswith('/value'):
            self.text = body['text']; self.inputs.append('text')
            if self.owner.fault == 'process': self.owner.process['identity'] = '124:456'
            if self.owner.fault == 'session': self.owner.state['generation'] = 2
            return None
        if path.endswith('/text'): return self.text
        if path.endswith('/attribute/focused'): return self.focus
        if path.endswith('/appium/device/press_keycode'):
            self.inputs.append('enter'); assert body == {'keycode': 66}
            if self.owner.fault == 'lost-reply': raise RuntimeError('uncertain reply')
            self.open = False
            return None
        raise AssertionError((method, path))


class PhonePreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.clock = Clock(); self.fault = None; self.sequence = 0; self.probes = []
        self.identity = {'schemaVersion': 1, 'sourceRevision': 'a' * 40,
                         'artifactSha256': 'b' * 64, 'installedCandidateVerified': True}
        self.state = {'sessionId': 'owned', 'generation': 1, 'targetFingerprint': 'fingerprint'}
        self.process = {'running': True, 'identity': '123:456'}
        self.target = {'selector': 'host-only', 'controls': {'normalNavigation': {
            'contractVersion': 1, 'profile': 'phone-native-v1',
            'sceneUrl': 'http://owned.invalid:18080/scene.json'}}}
        self.client = Client(self)
        self.guard_calls = 0
        self.adapter = object.__new__(PhoneAppiumAdapter)
        self.adapter.candidate = object()
        self.adapter.existing_input_session = self.existing_input
        self.adapter.existing_session = lambda _selector: (self.client, 'owned', self.state)
        self.adapter.target = lambda _selector: deepcopy(self.target)
        self.adapter.snapshot_fingerprint = lambda _target: 'fingerprint'
        self.adapter.installed_identity = lambda _selector: deepcopy(self.identity)
        self.adapter.process_state = lambda *_args: deepcopy(self.process)
        self.adapter.read_session = lambda _selector: deepcopy(self.state)
        self.adapter.query_app_state = lambda *_args: 4
        self.adapter.save_session = lambda *_args: None
        self.adapter.existing_probe_snapshot = self.read_probe
        admission = SimpleNamespace(source=SOURCE, client=SOURCE, manifest={
            'client': {'revision': 'a' * 40}, 'candidate': {'sha256': 'b' * 64}})
        self.context = SimpleNamespace(source_guard=self.guard, phone_adapter=self.adapter,
            admission=admission, run_root=Path(temporary.name), target=deepcopy(self.target), nonce='e' * 32)
    def guard(self): self.guard_calls += 1
    @contextmanager
    def existing_input(self, _selector):
        yield
    def read_probe(self, _selector, _values):
        self.clock.ms += 300
        self.sequence += 1
        value = snapshot()
        value.update(sampleEpochMs=self.clock.ms, sampleSequence=self.sequence)
        value['domain'].update(id='retained-old-domain-id', connected=False, serverless=True, protocol='file')
        value['scene'].update(url=preparation.TUTORIAL_URL, ready=False, entityCount=39,
                              fixtureMarkerCount=0, fixtureMarkers=[], domainMarkerCount=0,
                              domainMarkers=[], floorTopY=None, collisionWall=None,
                              avatarAboveFloor=False, spawnLocationObserved=False, spawnValidated=False)
        value['avatar'].update(feetPosition=dict(zip(('x', 'y', 'z'), preparation.SPAWN_FEET)),
                               inAir=False, flying=False, velocity={'x': 0, 'y': .003, 'z': 0})
        if self.fault == 'stale': value['sampleEpochMs'] -= 10_000
        if self.fault == 'replay': value['sampleSequence'] = 1
        if self.fault == 'wrong-world': value['scene']['url'] = 'file:///other.json'
        if self.fault == 'empty': value['scene']['entityCount'] = 0
        if self.fault == 'falling': value['avatar']['feetPosition']['y'] = -47_000
        if self.fault == 'flying': value['avatar'].update(flying=True, inAir=True)
        if self.fault == 'probe-process': value['nativeMotion'] = {'processId': 124, 'sampleEpochMs': self.clock.ms, 'sampleSequence': self.sequence}
        self.probes.append(value)
        return value
    def prepare(self):
        with patch.object(preparation, 'time', self.clock), patch.object(preparation, 'OBSERVATION_SECONDS', 2):
            return preparation.prepare_tutorial(self.context)

    def test_real_click_replace_text_one_enter_and_three_independent_samples(self):
        rows = self.prepare()
        self.assertEqual(self.client.inputs, ['Go-to-destination', 'PhoneAddressField', 'clear', 'text', 'enter'])
        self.assertEqual(len(rows), 3)
        self.assertEqual([r['entityCount'] for r in rows], [39] * 3)
        self.assertTrue(validate_tutorial(rows, self.context.nonce, 2_000_000_000_000, self.clock.ms))
        self.assertGreaterEqual(self.guard_calls, 3)
        self.assertEqual(len(list((self.context.run_root / 'tutorial-preparation').glob('probe-*.private.json'))), 3)
        for path in (self.context.run_root / 'tutorial-preparation').iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
    def test_source_tamper_rejected_before_any_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            client = Path(temporary); tutorial = client / preparation.TUTORIAL_SOURCE
            tutorial.parent.mkdir(parents=True); tutorial.write_text('{}')
            self.context.admission.client = client
            with self.assertRaisesRegex(preparation.PreparationError, 'PHONE_TUTORIAL_CLIENT_SOURCE_CHANGED'): self.prepare()
        self.assertFalse(self.client.inputs)
    def test_missing_existing_session_never_creates_or_repairs_one(self):
        self.adapter.existing_session = lambda _selector: (_ for _ in ()).throw(RuntimeError('missing existing session'))
        with self.assertRaises(RuntimeError): self.prepare()
        self.assertFalse(self.client.inputs)
    def test_focus_failure_blocks_return_without_keyboard_fallback(self):
        self.fault = 'focus'
        with self.assertRaises(NativeUIError): self.prepare()
        self.assertNotIn('enter', self.client.inputs)
        self.assertFalse(any('/hide_keyboard' in path for _method, path, _body in self.client.calls))
    def test_lost_enter_reply_never_replays_and_never_qualifies(self):
        self.fault = 'lost-reply'
        with self.assertRaises(NativeUIError): self.prepare()
        self.assertEqual(self.client.inputs.count('enter'), 1)
        self.assertFalse(self.probes)
    def test_changed_candidate_process_or_session_blocks_remaining_input(self):
        for fault in ('candidate', 'process', 'session'):
            with self.subTest(fault=fault):
                self.setUp(); self.fault = fault
                with self.assertRaises((NativeUIError, preparation.PreparationError)): self.prepare()
                self.assertNotIn('enter', self.client.inputs)
    def test_stale_or_replayed_raw_probe_rejected_and_preserved(self):
        for fault in ('stale', 'replay', 'probe-process'):
            with self.subTest(fault=fault):
                self.setUp(); self.fault = fault
                with self.assertRaises(preparation.PreparationError): self.prepare()
                self.assertTrue(list((self.context.run_root / 'tutorial-preparation').glob('probe-*.private.json')))
                self.assertEqual(self.client.inputs.count('enter'), 1)
    def test_accepted_input_is_not_world_entity_or_ground_proof(self):
        for fault in ('wrong-world', 'empty', 'falling', 'flying'):
            with self.subTest(fault=fault):
                self.setUp(); self.fault = fault
                with self.assertRaisesRegex(preparation.PreparationError, 'PHONE_TUTORIAL_FRESH_GROUNDED_SAMPLES_TIMEOUT'): self.prepare()
                self.assertEqual(self.client.inputs.count('enter'), 1)
    def test_no_unexpected_process_network_or_session_creation(self):
        with (patch.object(subprocess, 'run', side_effect=AssertionError('no process')),
              patch.object(subprocess, 'Popen', side_effect=AssertionError('no process')),
              patch.object(socket, 'socket', side_effect=AssertionError('no network'))):
            self.assertEqual(len(self.prepare()), 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
