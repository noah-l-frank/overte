"""Scene metadata selects one consistent fresh tail/final profile.

These are factory/coordination tests over actual private files and locks.
Factories are explicit models, not product observations or retirement proofs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_feature, avatar_held_final
from ios.adapters.avatar_postlogout_tail import IOSAvatarPostLogoutTail
from ios.adapters.avatar_held_tail import IOSAvatarHeldTail
from ios.self_tests import test_ios_avatar_scene_wait_locks as fixture


class AvatarSceneProfileSelectionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.AvatarSceneWaitLocksTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.owner = self.f.owner
        root = self.owner.root
        self.config = dict(root=str(root), paths=dict(tail=str(root/'tail-coordination-model.json')),
            childRunId='b'*32, ticket='f'*32, baseline={}, logoutBefore={}, fixtureUrl=self.owner.client.url)
        self.versions = []
        def inputs(*, version=1):
            self.versions.append(version)
            return {role: deepcopy(self.config) for role in ('primary', 'actor')}
        self.owner.final_inputs = inputs
    def mode(self, version):
        self.f.scene.write(dict(iosAvatarSceneVersion=version), self.f.scene.read())
    def final_model(self, version):
        class FinalModel:
            VERSION = version
            def __init__(self, *_args, **_kwargs):
                self.version = version
        return FinalModel

    def test_each_fresh_scene_uses_matching_account_tail_and_final_profile(self):
        for version in (1, 2):
            with self.subTest(version=version), self.owner.held():
                self.owner.load()
                self.mode(version)
                calls = []
                def tail(*_args, **kwargs):
                    self.owner.lock.assert_held()
                    calls.append(kwargs['held'])
                    return SimpleNamespace(version=4 if kwargs['held'] else 3)
                with patch.object(self.owner.runtime, '_avatar_postlogout_tail', tail), \
                        patch.object(avatar_feature, 'IOSAvatarFinal', self.final_model(1)), \
                        patch.object(avatar_held_final, 'IOSAvatarHeldFinal', self.final_model(2)):
                    self.assertEqual(4 if version==2 else 3, self.owner.account_surface_tail().version)
                    self.assertEqual(version, self.owner.final_owner().version)
                self.assertEqual([version==2], calls)

    def test_historical_tail_uses_its_original_version_without_rewriting(self):
        for version in (1, 2, 3, 4):
            value = dict(iosAvatarPostLogoutTailVersion=version)
            original = deepcopy(value)
            with self.subTest(version=version), self.owner.held():
                self.owner.load()
                with patch.object(IOSAvatarPostLogoutTail, 'archive', return_value='legacy') as old, \
                        patch.object(IOSAvatarHeldTail, 'archive', return_value='held') as held:
                    self.assertEqual('held' if version==4 else 'legacy', self.owner.account_surface_tail(value))
                    self.assertEqual(1 if version==4 else 0, held.call_count)
                    self.assertEqual(0 if version==4 else 1, old.call_count)
            self.assertEqual(original, value)

    def test_foreign_existing_final_or_untyped_scene_cannot_select_a_weaker_profile(self):
        store = PrivateFeatureState(self.owner.store.path.with_name('ios-avatar-primary-final.json'))
        for scene_version, final_version in ((2, 1), (1, 2)):
            with self.subTest(scene=scene_version, final=final_version), self.owner.held():
                self.owner.load()
                self.mode(scene_version)
                value = dict(iosAvatarFinalVersion=final_version)
                store.write(value, store.read())
                with self.assertRaises(NativeUIError):
                    self.owner.final_owner()
                self.assertEqual(value, store.read())
        for invalid in (True, 0, 3):
            with self.subTest(version=invalid), self.owner.held():
                self.owner.load()
                self.mode(invalid)
                with self.assertRaises(NativeUIError):
                    self.owner.account_surface_tail()


if __name__ == '__main__':
    unittest.main()
