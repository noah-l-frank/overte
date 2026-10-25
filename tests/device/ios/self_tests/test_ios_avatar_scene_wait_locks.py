"""Real source locks around stage admission, released for the passive wait.

The journal/receipt boundary is an explicit coordination model. No product
fact, retirement result or complete feature is qualified by these tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from feature_journeys.retirement_receipts import AVATAR_SCOPED_STAGE as SCENE_STAGE
from ios.adapters import avatar_feature
from ios.self_tests import test_ios_avatar_feature as fixture
from ios.self_tests.test_ios_avatar_input_owner import BINDING


class AvatarSceneWaitLocksTests(unittest.TestCase):
    def setUp(self):
        f = fixture.AvatarFeatureLocksTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.owner = owner = f.owner('primary')
        self.ticket = 'f'*32
        self.scene = PrivateFeatureState(f.root/'primary'/'scene-version-coordination-model.json')
        self.scene.write(dict(iosAvatarSceneVersion=1), None)
        state = dict(bindings=dict(primary=deepcopy(BINDING)), peerAdmission=dict(model='admitted-peer'),
            phaseInstance='a'*32, cleanup=[dict(kind='start', ticket=self.ticket),
                dict(kind='scene', owner=dict(index=1, sha256=digest(self.scene.read())))])
        owner.store.write(owner.envelope(state), None)
        def load():
            owner.lock.assert_held()
            owner.previous = owner.store.read()
            owner.state = unpack(owner.previous['payload'])[0]
        def save():
            owner.lock.assert_held()
            value = owner.envelope(owner.state)
            owner.store.write(value, owner.previous)
            owner.previous = value
        def kept(reference):
            owner.lock.assert_held()
            return self.scene.read()
        self.snapshots = []
        def keep(value):
            owner.lock.assert_held()
            self.snapshots.append(deepcopy(value))
            return dict(index=len(self.snapshots), sha256=digest(value))
        owner.load, owner.save, owner.kept, owner.keep = load, save, kept, keep
        owner.cleanup_deadline = lambda: None
        self.waits = []
        def released():
            try:
                owner.lock.assert_held()
            except NativeUIError:
                self.waits.append('released')
            else:
                raise AssertionError('Passive receipt I/O must not hold the source lock')
        self.released = released
        owner.phase.read = released

    def reader(self, mutate=False):
        test = self
        class ReceiptBoundary:
            def __init__(self, *_args, **kwargs):
                test.released()
                test.assertEqual(SCENE_STAGE, kwargs['stage'])
                self.state = dict(records=[dict(entry=dict(ticket=test.ticket))])
                self.previous = dict(coordinationModel='reader-return')
            def read(self):
                test.released()
                if mutate:
                    with test.owner.held():
                        test.owner.load()
                        test.owner.state['bindings']['primary']['generation'] += 1
                        test.owner.save()
        return ReceiptBoundary

    def test_stage_reads_are_locked_but_actual_receipt_wait_is_unlocked(self):
        with patch.object(avatar_feature, 'PhaseRetirementReader', self.reader()):
            self.owner.wait_actor_scene()
        current = unpack(self.owner.store.read()['payload'])[0]
        self.assertEqual(3, len(self.waits))
        self.assertEqual('actor-scene', current['cleanup'][-1]['kind'])
        self.assertEqual(1, len(self.snapshots))

    def test_changed_current_binding_after_unlocked_wait_cannot_adopt_a_receipt(self):
        with patch.object(avatar_feature, 'PhaseRetirementReader', self.reader(mutate=True)), self.assertRaises(NativeUIError):
            self.owner.wait_actor_scene()
        current = unpack(self.owner.store.read()['payload'])[0]
        self.assertFalse(any(row['kind']=='actor-scene' for row in current['cleanup']))
        self.assertEqual([], self.snapshots)


if __name__ == '__main__':
    unittest.main()
