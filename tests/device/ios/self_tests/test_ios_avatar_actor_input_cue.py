"""Completed input only schedules independent Actor acquisition.

Real private controller files/locks exercise the handoff. The archive and
observer boundaries below are coordination models, never product evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from feature_journeys.contract import VERSION
from ios.adapters.avatar_feature import IOSAvatarFeature, AvatarFeaturePending
from ios.self_tests import test_ios_avatar_feature as fixture
from ios.self_tests.test_ios_avatar_input_owner import BINDING


class AvatarActorInputCueTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.AvatarFeatureLocksTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.actor, self.primary = self.f.owner('actor'), self.f.owner('primary')
        self.current = dict(ticket='f'*32, verb='peer-accept', inputs={},
            status=dict(active=True, instance='b'*32))
        actor_binding = dict(BINDING, sessionId='independent-actor')
        self.bindings = dict(primary=deepcopy(BINDING), actor=actor_binding)
        self.actor.state = dict(phase='ready', bindings=deepcopy(self.bindings), phaseInstance='b'*32,
            initialBarrier=dict(subject='primary', owner=dict(index=1, sha256='c'*64)))
        self.call = dict(contractVersion=VERSION, runId=self.actor.run, ticket=self.current['ticket'],
            fixtureUrl=self.actor.phase.fixture_url, verb=self.current['verb'], inputs={})
        self.primary_state = dict(phase='ready', bindings=deepcopy(self.bindings), phaseInstance='b'*32,
            lastCall=dict(call=deepcopy(self.call), phase='complete'))
        self.admitted = self.primary.envelope(deepcopy(self.primary_state))
        self.primary.store.write(deepcopy(self.admitted), None)
        def kept(_reference):
            self.actor.lock.assert_held()
            return deepcopy(self.admitted)
        self.actor.kept = kept
        self.actor.load = lambda: None
        self.actor.phase.read = lambda: deepcopy(self.current)
        def archive(_runtime, value, _client, locks):
            for lock in locks.values():
                lock.assert_held()
            return SimpleNamespace(role=value['role'], run=value['runId'], selectors=value['selectors'],
                state=unpack(value['payload'])[0])
        self.archive = patch.object(IOSAvatarFeature, 'archive', side_effect=archive)
        self.archive.start()
        self.addCleanup(self.archive.stop)
    def save_primary(self):
        self.primary.store.write(self.primary.envelope(deepcopy(self.primary_state)), self.primary.store.read())
    def ready(self):
        with self.actor.held(paired=True):
            return self.actor.actor_input_returned(self.current)

    def test_baseline_is_allowed_but_cleanup_and_foreign_phase_cannot_use_active_capture(self):
        self.current['verb'] = 'baseline'
        self.assertTrue(self.ready())
        self.current['verb'] = 'cleanup'
        self.assertFalse(self.ready())
        self.current['status']['instance'] = 'd'*32
        with self.assertRaises(NativeUIError):
            self.ready()

    def test_missing_issued_or_old_ticket_never_enables_acquisition(self):
        self.primary.store.path.unlink()
        self.assertFalse(self.ready())
        self.primary_state['lastCall']['phase'] = 'issued'
        self.save_primary()
        self.assertFalse(self.ready())
        self.primary_state['lastCall']['phase'] = 'complete'
        self.primary_state['lastCall']['call']['ticket'] = 'e'*32
        self.save_primary()
        self.assertFalse(self.ready())

    def test_complete_matching_call_is_only_a_cue_and_wrong_context_is_refused(self):
        self.assertTrue(self.ready())
        self.primary_state['lastCall']['call']['verb'] = 'peer-reject'
        self.save_primary()
        with self.assertRaises(NativeUIError):
            self.ready()
        self.primary_state['lastCall']['call'] = deepcopy(self.call)
        self.primary_state['bindings']['primary']['generation'] += 1
        self.save_primary()
        with self.assertRaises(NativeUIError):
            self.ready()

    def test_changed_primary_outer_original_cannot_select_the_cue(self):
        value = self.primary.store.read()
        value['artifactRoot'] = str(self.f.root/'actor')
        self.primary.store.write(value, self.primary.store.read())
        with self.assertRaises(NativeUIError):
            self.ready()

    def test_consent_runs_before_the_gate_but_no_early_source_or_publication_occurs(self):
        events = []
        self.primary_state['lastCall']['phase'] = 'issued'
        self.save_primary()
        self.actor.prepare = lambda: events.append('prepare')
        def consent(_current):
            try:
                self.actor.locks['primary'].assert_held()
            except NativeUIError:
                events.append('consent')
            else:
                raise AssertionError('Consent cannot wait under the Primary input lock')
        self.actor.consent = consent
        def source():
            raise AssertionError('Incomplete input cannot acquire or publish Actor facts')
        self.actor.source_parts = source
        with self.assertRaises(AvatarFeaturePending):
            self.actor.observe(dict(contractVersion=VERSION, runId=self.actor.run, afterSequence=0))
        self.assertEqual(['prepare', 'consent'], events)

    def test_stale_consent_phase_cannot_even_open_its_source(self):
        current = deepcopy(self.current)
        self.current['ticket'] = 'e'*32
        self.actor.own_source = lambda: self.fail('A stale phase cannot admit a consent input')
        with self.assertRaises(AvatarFeaturePending):
            self.actor.consent(current)


if __name__ == '__main__':
    unittest.main()
