"""Actual private Pico factory; audio/UI/controller sources are explicit seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import test_normal_scripts as original
sys.path.insert(0,str(Path(__file__).resolve().parents[5]))
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.pico4.audio_page_owner import PicoAudioPageOwner
from adapters.normal_feature_state import PrivateFeatureState
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests.test_pico_audio_page_owner import AudioPageOwnerTests
from self_tests.test_pico_openxr_adapter_session import FakeTransport


class PicoAudioPageBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.instance,self.fixture.native
    def test_actual_factory_shares_exact_parent_lock_existing_route_and_current_process(self):
        session=PicoOpenXrAdapterSession(FakeTransport(),'explicit-audio-factory',self.fixture.fixture.state_root)
        session.begin(self.native.identity);lock=self.adapter._script_journey()._lock(self.native.target)
        with patch.object(self.adapter,'pico_input_session',return_value=session):
            owner=self.adapter._audio_page_owner(self.native.target,'a'*32,source_lock=lock)
            self.assertIsInstance(owner,PicoAudioPageOwner);self.assertIs(owner.lock,lock);self.assertIs(owner.session,session)
            self.assertTrue(all(source.source_lock is lock for source in (owner.pages,owner.settings,owner.ui)))
            self.assertIs(owner.preview.lock,lock);self.assertEqual('audio-page-owner.json',owner.store.path.name)
            self.assertIsNone(owner.store.read());self.assertIsNone(owner.preview.store.read())
            self.native.digest='f'*64
            with self.assertRaises((ValueError,RuntimeError)):owner.prepare()
            self.assertEqual([],self.native.inputs);self.assertEqual([],session.transport.envelopes)
    def test_orphan_page_journal_blocks_base_cleanup_without_deleting_it(self):
        store=self.adapter._audio_page_store(self.native.target);store.write({'originalOwnership':'retained'},None)
        with self.assertRaises(ValueError):self.fixture.cleanup_instance().cleanup(self.native.target)
        self.assertEqual({'originalOwnership':'retained'},PrivateFeatureState(store.path).read());self.assertFalse(self.native.running)


if __name__=='__main__':unittest.main()
