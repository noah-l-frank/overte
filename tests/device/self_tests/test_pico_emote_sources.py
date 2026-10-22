"""Real source readers/private ownership with synthetic Qt/Rig/time boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

# Existing fixture modules also support direct execution and import each other
# by their historical module names. Keep that test-only path for Pico's runner.
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]

from adapters.native_animation_inventory import NativeAnimationInventory
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_script_observation import NativeScriptObservation
from adapters.native_script_roots import NativeScriptRoots
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_sources import PicoEmoteSources, EmotePhaseChanged
from adapters.script_journey.history import unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client, Journal
from self_tests.test_emote_rig_measurements import RigPackets
from self_tests.test_native_animation_inventory import InventoryBoundary
from self_tests.test_pico_emote_source import pico_sources
from self_tests.test_token_emote_ui import EmoteBoundary

RUN = 'd' * 32
BINDING = dict(sourceRevision='a'*40, artifactSha256='b'*64, processIdentity='31:original',
    sessionId='11111111-1111-4111-8111-111111111111', generation=0, targetFingerprint='c'*64)


class SourcesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.root.chmod(0o700)
        self.store = PrivateFeatureState(self.root / 'emote-primary.json')
        self.lock = ScriptSourceLock(self.root / 'script-sources.lock')
        self.clock = 0.; self.epoch = 20000; self.okay = True; self.calls = []; self.counts = {}; self.fault = None
        self.journal = Journal(lambda: self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex', return_value=RUN): self.journal.register('emotes')
        self.journal.activate(RUN, 'c'*32)
        client = Client('http://controlled.test/feature-fixture/v1', 'r'*64)
        def request(path, **kwargs):
            self.calls.append('phase'); return self.journal.phase(RUN, kwargs['phase_nonce'])
        client.request = request
        self.phase = PhaseFixtureReader(client, RUN, 'emotes', epoch_ms=lambda: self.epoch, monotonic=lambda: self.clock)
        self.code, self.before, _after, _pin = pico_sources()
        self.code['source'].update(effectSourceVersion=1, effects=dict(complete=True, scanRadiusMeters=64,
            scannedEntities=0, absentIds=[], entities=[]), loadSourceVersion=1,
            loads=dict(complete=True, instance='d'*32, sequence=0, events=[]))
        rig = RigPackets(root=self.before['source']['defaultScriptsUrl'])
        self.native = rig.native(20000, active=True)
        self.native['instance'] = self.before['instance']
        inventory = InventoryBoundary(self.before['source']['defaultScriptsUrl'])
        inventory.send(dict(schemaVersion=1, commandId='e'*32, action='feature-animation-inventory-observe'))
        self.inventory = inventory.value; self.inventory['instance'] = self.before['instance']
        self.widget = EmoteBoundary(); self.widget.instance = BINDING['sessionId']
        self.widget.generation = '22222222-2222-4222-8222-222222222222'

    def guard(self): return self.okay
    def sleep(self, seconds): self.clock += seconds

    def readers(self):
        # Every reader constructor and native request must follow responsibility.
        self.assertEqual('reading', unpack(self.store.read()['payload'])[0]['phase'])
        def make(cls, name, template, field):
            current = {}
            def send(command):
                self.assertEqual('reading', unpack(self.store.read()['payload'])[0]['phase'])
                self.calls.append(name); self.counts[name] = self.counts.get(name, 0) + 1
                value = deepcopy(template); value[field] = command['commandId']; value['sequence'] = self.counts[name]
                value.update(requestedEpochMs=self.epoch, capturedEpochMs=self.epoch)
                if name == 'native':
                    value = deepcopy(self.native); value[field] = command['commandId']; value['sequence'] = self.counts[name]
                    history = value['animation']['history']
                    last = deepcopy(history['frames'][-1]); last['frameSequence'] += 1
                    last['evaluationSequence'] += 1; history['frames'].append(last)
                    history['frameSequence'] = last['frameSequence']
                    value['animation']['evaluationSequence'] = last['evaluationSequence']
                    value['animationFence']['sequence'] = last['evaluationSequence'] - 1
                    self.native = deepcopy(value)
                if self.fault == name: raise NativeUIError('Synthetic lost original reply')
                if self.fault == 'slow' and name == 'native': self.clock += 2
                if self.fault == 'cross-phase' and name == 'native': self.journal.activate(RUN, 'f'*32, 'play', {'name': 'Waving'})
                current.clear(); current.update(value)
            return cls(send, lambda: json.dumps(current), lambda: self.epoch, self.guard, 31,
                monotonic=lambda: self.clock, sleep=self.sleep)
        def capture():
            self.calls.append('widgets'); value = self.widget.capture()
            for row in value['controls']:
                row['token'] = str(uuid.uuid5(uuid.NAMESPACE_URL, row['token']))
                if row['id'].startswith('tablet.'): row.pop('inputReady')
            return dict(schemaVersion=1, bridgeId=value['scope']['instance'], generation=value['scope']['generation'],
                processId=31, elapsedMs=value['scope']['elapsedMs'], updatedEpochMs=self.epoch,
                lastCommandSequence=value['scope']['sequence'], open=True, ready=True, controls=value['controls'],
                emoteControlsVersion=2, emoteSourceSequence=value['scope']['sourceSequence'])
        return (make(NativeScriptRoots, 'roots', self.before, 'commandId'),
            make(NativeScriptObservation, 'script', self.code, 'requestId'),
            make(NativeAnimationInventory, 'inventory', self.inventory, 'commandId'),
            make(NativeFeatureObservation, 'native', self.native, 'requestId'), SimpleNamespace(capture=capture))

    def owner(self, role='primary', binding=None):
        return PicoEmoteSources(self.store, binding or BINDING, self.phase, role, self.lock, self.root,
            self.readers, self.guard, lambda: self.epoch, monotonic=lambda: self.clock)

    def test_original_group_private_manifest_and_fresh_reconstruction(self):
        with self.lock.held():
            owner = self.owner(); first = owner.read(); header = self.store.read()
            self.assertEqual(['phase', 'roots', 'script', 'inventory', 'native', 'roots', 'widgets', 'phase'], self.calls)
            self.assertEqual('retained', __import__('adapters.emote_source_profile', fromlist=['select_from_roots']).select_from_roots(
                first['group']['script'], first['group']['rootsBefore'], first['group']['rootsAfter'], pid=31, epoch=20000)['profile']['chooserAfterPlay'])
            calls = list(self.calls); reconstructed = self.owner()
            self.assertEqual(calls, self.calls); self.assertEqual([first], reconstructed.frames)
            second = reconstructed.read(); self.assertNotEqual(first['group']['script']['requestId'], second['group']['script']['requestId'])
            self.assertEqual(2, len(reconstructed.frames))
            self.assertNotEqual(header, self.store.read())
            for path in self.root.glob('emote-*.json'): self.assertEqual(0o600, path.stat().st_mode & 0o777)

    def test_every_lost_original_read_stays_owned_and_cannot_be_resent_after_reconstruction(self):
        for fault in ('roots', 'script', 'inventory', 'native'):
            with self.subTest(fault=fault):
                self.setUp(); self.fault = fault
                with self.lock.held():
                    with self.assertRaises(NativeUIError): self.owner().read()
                    owner = self.owner(); self.assertEqual('reading', owner.state['phase']); calls = list(self.calls)
                    with self.assertRaises(NativeUIError): owner.read()
                    with self.assertRaises(NativeUIError): owner.recover_complete()
                    self.assertEqual(calls, self.calls)

    def test_original_phase_crossing_is_retained_but_never_delivered(self):
        self.fault = 'cross-phase'
        with self.lock.held():
            owner = self.owner()
            with self.assertRaises(EmotePhaseChanged): owner.read()
            self.assertEqual(1, len(owner.frames)); self.assertEqual('ready', owner.state['phase'])
            self.assertNotEqual(owner.frames[0]['phaseBefore']['activations'], owner.frames[0]['phaseAfter']['activations'])
            self.assertEqual(owner.frames, self.owner().frames)

    def test_frozen_wall_clock_does_not_hide_slow_acquisition(self):
        self.fault = 'slow'
        with self.lock.held():
            with self.assertRaises(NativeUIError): self.owner().read()
            self.assertEqual('reading', self.owner().state['phase'])
            self.assertFalse(list(self.root.glob('emote-frame-*')))

    def test_complete_owned_original_is_recovered_without_fresh_return_or_native_query(self):
        with self.lock.held():
            owner = self.owner(); write = owner.originals.write
            def interrupted(index, frame):
                value = write(index, frame); raise NativeUIError('Synthetic process interruption after saved original')
            owner.originals.write = interrupted
            with self.assertRaises(NativeUIError): owner.read()
            recovered = self.owner(); self.assertEqual('saved', recovered.state['pending']['original']['phase'])
            calls = list(self.calls); self.assertIsNone(recovered.recover_complete()); self.assertEqual(calls, self.calls)
            self.assertEqual('ready', recovered.state['phase']); self.assertEqual(1, len(recovered.frames))
            self.assertIsNotNone(self.store.read())

    def test_foreign_role_candidate_and_replaced_original_cannot_be_adopted(self):
        with self.lock.held():
            owner = self.owner(); owner.read(); calls = list(self.calls)
            for role, binding in (('actor', BINDING), ('primary', BINDING | dict(artifactSha256='f'*64))):
                with self.assertRaises(NativeUIError): self.owner(role, binding)
            original = owner.originals.manifest(owner.state['manifests'][0])[0]
            path = owner.originals.path(owner.originals.expand(original)); raw = path.read_bytes()
            changed = path.with_name('replacement'); changed.write_bytes(raw); changed.chmod(0o600); changed.replace(path)
            with self.assertRaises(NativeUIError): self.owner()
            self.assertEqual(calls, self.calls)

    def test_lock_and_candidate_failure_precede_all_new_queries(self):
        with self.assertRaises(NativeUIError): self.owner()
        with self.lock.held():
            owner = self.owner(); self.okay = False
            with self.assertRaises(NativeUIError): owner.read()
        self.assertEqual([], self.calls)

    def test_changed_cache_birth_unknown_compilation_and_stale_widgets_retain_reading_ownership(self):
        for fault in ('model-birth', 'code', 'widgets'):
            with self.subTest(fault=fault):
                self.setUp()
                with self.lock.held():
                    owner = self.owner(); owner.read()
                    if fault == 'model-birth': self.inventory['source']['resources'][0]['model']['parsedEpochMs'] += 1
                    elif fault == 'code': self.code['source']['engines'][0]['compiled']['compilations'][0]['sha256'] = 'f'*64
                    else: self.widget.source_sequence = 0
                    with self.assertRaises((NativeUIError, RuntimeError)): self.owner().read()
                    reconstructed = self.owner()
                    self.assertEqual('reading', reconstructed.state['phase']); self.assertEqual(1, len(reconstructed.frames))

    def test_late_archival_commit_is_historical_and_never_returned_as_fresh(self):
        with self.lock.held():
            owner = self.owner(); save = owner.save
            def late():
                save()
                if owner.state['revision'] == 1 and owner.state['phase'] == 'ready': self.clock += 2
            owner.save = late
            with self.assertRaises(NativeUIError): owner.read()
            reconstructed = self.owner()
            self.assertEqual('ready', reconstructed.state['phase']); self.assertEqual(1, len(reconstructed.frames))
            self.assertEqual(20000, reconstructed.frames[0]['epochMs'])


if __name__ == '__main__': unittest.main()
