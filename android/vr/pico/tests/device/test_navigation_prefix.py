"""Navigation opening prefix and actual private Pico factory; no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]))
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_navigation_prefix import NavigationPrefixTests
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from self_tests.test_navigation_directory import INPUTS,PROFILE,RUN
from adapters.pico4.navigation import NativeNavigationIO
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from openxr_input.adapter_session import PicoOpenXrAdapterSession
import test_normal_scripts as original


class NavigationPrefixFactoryTests(unittest.TestCase):
    def setUp(self):
        self.h=original.PicoNormalScriptsTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
    def test_actual_factory_shares_exact_normal_io_source_lock_and_original_session_without_input(self):
        h=self.h;root=h.instance._script_journey().state_path(h.native.target).parent
        lock=ScriptSourceLock(root/'script-sources.lock');session=PicoOpenXrAdapterSession(FakeTransport(),h.native.target,root)
        session.begin(h.native.identity)
        phase=PhaseFixtureReader(Client('https://fixture.invalid/feature-fixture/v1','f'*64),RUN,'world-navigation')
        def unavailable():self.fail('Passive constructor queried an input provider')
        with patch.object(h.instance,'pico_input_session',return_value=session),lock.held():
            owner=h.instance._navigation_prefix(h.native.target,RUN,phase,unavailable,'e'*32,INPUTS,'https://fixture.invalid',PROFILE,source_lock=lock)
        self.assertIs(owner.lock,lock);self.assertIs(owner.session,session);self.assertIsInstance(owner.transport,NativeNavigationIO)
        self.assertIs(owner.directory.ui.io.original,owner.source.normal.io.original)
        self.assertIs(owner.bookmarks.ui.io.original,owner.source.normal.io.original)
        self.assertIs(owner.origin.io.original,owner.source.normal.io.original)
        self.assertEqual([],h.native.inputs);self.assertEqual([],h.native.controllers)
        self.assertIsNone(owner.store.read());self.assertNotIn('feature.world-navigation.act',h.instance.capabilities(h.native.target))
    def test_original_parent_child_chunk_and_environment_archive_orphans_block_cleanup_admission(self):
        h=self.h;root=h.instance._script_journey().state_path(h.native.target).parent
        self.assertFalse(h.instance._navigation_prefix_owned(h.native.target))
        for name in ('navigation-prefix-owner.json','navigation-prefix-primary-sources.json.frame-000.json',
                     'navigation-'+RUN+'-environment-'+('a'*64)+'.json'):
            path=root/name;PrivateFeatureState(path).write({},None)
            self.assertTrue(h.instance._navigation_prefix_owned(h.native.target));self.assertEqual('{}\n',path.read_text())
            path.unlink()
        self.assertFalse(h.instance._navigation_prefix_owned(h.native.target))


if __name__=='__main__':unittest.main()
