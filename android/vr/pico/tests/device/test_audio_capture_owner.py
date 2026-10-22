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
from self_tests.test_pico_audio_capture_owner import AudioCaptureOwnerTests
from self_tests.test_pico_audio_background import AudioBackgroundTests
from self_tests.test_pico_openxr_adapter_session import FakeTransport


class PicoAudioCaptureBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.instance,self.fixture.native
    def test_capture_factory_uses_existing_parent_lock_and_requires_an_actual_claim(self):
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from feature_journeys.witness import Client
        session=PicoOpenXrAdapterSession(FakeTransport(),'explicit-audio-factory',self.fixture.fixture.state_root)
        session.begin(self.native.identity);lock=self.adapter._script_journey()._lock(self.native.target)
        source=PhaseFixtureReader(Client('http://127.0.0.1:9876/feature-fixture/v1','a'*64),'a'*32,'audio')
        # Construction must fail before a claimed normal page exists. The
        # actual factory resolves the same installed candidate/process/lock;
        # no phase HTTP request or ordinary input is issued to repair it.
        with patch.object(self.adapter,'pico_input_session',return_value=session):
            with self.assertRaises(ValueError):self.adapter._audio_capture_owner(self.native.target,'a'*32,1,source,source_lock=lock)
        self.assertEqual([],session.transport.envelopes);self.assertEqual([],self.native.inputs)
        self.assertIsNone(self.adapter._audio_capture_store(self.native.target,1).read())

    def test_orphan_capture_journal_and_pcm_block_base_cleanup_without_adoption(self):
        store=self.adapter._audio_capture_store(self.native.target,1);store.write({'unresolved':'original capture'},None)
        self.adapter._audio_preview_store(self.native.target).write({'runId':'a'*32},None)
        cleanup=self.fixture.cleanup_instance()
        with patch.object(cleanup,'_audio_preview') as competing:
            with self.assertRaises(ValueError):cleanup.cleanup(self.native.target)
            competing.assert_not_called()
        self.assertEqual({'unresolved':'original capture'},store.read());self.assertTrue(self.adapter._audio_capture_owned(self.native.target))
    def test_background_cold_factory_does_not_reconstruct_native_owners_for_an_unresolved_archive(self):
        binding=self.adapter._scripts(self.native.target).binding;store=self.adapter._audio_background_store(self.native.target,1)
        store.write({'binding':binding,'unresolved':'original owner'},None)
        lock=self.adapter._script_journey()._lock(self.native.target)
        with patch.object(self.adapter,'_scripts') as native:
            with self.assertRaises(ValueError):self.adapter._audio_background_owner(self.native.target,'a'*32,1,None,source_lock=lock)
            native.assert_not_called()
        self.assertEqual([],self.native.inputs)
    def test_orphan_background_alone_blocks_base_cleanup_and_competing_native_release(self):
        store=self.adapter._audio_background_store(self.native.target,1);store.write({'originalBackground':'retained'},None)
        self.adapter._audio_preview_store(self.native.target).write({'runId':'a'*32},None);cleanup=self.fixture.cleanup_instance()
        with patch.object(cleanup,'_audio_preview') as competing:
            with self.assertRaises(ValueError):cleanup.cleanup(self.native.target)
            competing.assert_not_called()
        self.assertEqual({'originalBackground':'retained'},store.read());self.assertTrue(self.adapter._audio_capture_owned(self.native.target))

    def test_orphan_pcm_alone_blocks_base_cleanup(self):
        store=self.adapter._audio_capture_store(self.native.target,1);store._parent()
        original=store.path.with_name('audio-capture-original-retained-input.pcm16le');original.write_bytes(b'original');original.chmod(0o600)
        with self.assertRaises(ValueError):self.fixture.cleanup_instance().cleanup(self.native.target)
        self.assertEqual(b'original',original.read_bytes());self.assertIsNone(store.read())


if __name__=='__main__':unittest.main()
