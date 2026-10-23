"""Retained navigation ownership must block generic SDK termination fallback."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.adapters.navigation_session_cleanup import retire_existing


class NavigationSessionCleanupTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);test=self
        class InertRuntime(IOSNavigationRuntime):
            def __init__(self):pass
            def state_path(self,_selector):return test.root/'session.json'
            @property
            def adapter(self):test.fail('Unqualified ownership reached candidate/SDK cleanup')
        self.runtime=InertRuntime()

    def test_empty_namespace_has_no_sdk_cleanup_side_effect(self):
        self.assertIsNone(retire_existing(self.runtime,'owned',None));self.assertEqual([],list(self.root.iterdir()))

    def test_actual_orphan_names_and_incomplete_owner_cannot_fall_through_to_stop(self):
        for name in ('ios-navigation-whole-preparation.json','ios-navigation-whole-feature.json',
            'ios-navigation-preparation-abort.json','navigation-baseline-owned.json',
            'phase-publication-world-navigation-'+'a'*32+'-actor.json','ios-navigation-final-archive.json',
            'ios-navigation-feature.json'):
            store=PrivateFeatureState(self.root/name);store.write(dict(incomplete=True),None);before=store.path.read_bytes()
            with self.subTest(name=name),self.assertRaises(NativeUIError):retire_existing(self.runtime,'owned',None)
            self.assertEqual(before,store.path.read_bytes());store.discard(store.read())

    def test_missing_coordinator_does_not_erase_originals_in_separate_configured_root(self):
        artifact=self.root/'artifacts';artifact.mkdir(mode=0o700)
        config=dict(iosFeatureAdapterVersion=5,areas=['world-navigation'],fixtureConfig=str(self.root/'fixture.json'),
            graphics=None,create=None,emotes=None,worldNavigation=dict(artifactRoot=str(artifact)),avatarPeople=None,worldWeb=None,tabletWeb=None)
        store=PrivateFeatureState(artifact/'navigation-initial-restored-original.json');store.write(dict(retained=True),None)
        with self.assertRaises(NativeUIError):retire_existing(self.runtime,'owned',config)
        self.assertEqual(dict(retained=True),store.read())


if __name__=='__main__':unittest.main()
