"""Actual private final Audio factory and original normal/native owner tests."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import test_normal_scripts as original
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from self_tests.test_pico_audio_final_close import AudioFinalCloseTests,AudioFinalRetirementTests


class PicoAudioFinalBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.instance,self.fixture.native
    def test_orphan_final_owner_blocks_cleanup_without_competing_preview_release(self):
        store=self.adapter._audio_capture_store(self.native.target,1)
        final=PrivateFeatureState(store.path.with_name('audio-final-close.json'));final.write({'originalFinal':'retained'},None)
        self.adapter._audio_preview_store(self.native.target).write({'runId':'a'*32},None);cleanup=self.fixture.cleanup_instance()
        with patch.object(cleanup,'_audio_preview') as competing:
            with self.assertRaises(ValueError):cleanup.cleanup(self.native.target)
            competing.assert_not_called()
        self.assertEqual({'originalFinal':'retained'},final.read());self.assertTrue(self.adapter._audio_capture_owned(self.native.target))
    def test_final_factory_requires_retained_original_capture_without_input_repair(self):
        with self.assertRaises(ValueError):self.adapter._audio_final_close(self.native.target,'a'*32,1,None)
        self.assertEqual([],self.native.inputs)
        store=self.adapter._audio_capture_store(self.native.target,1)
        self.assertIsNone(PrivateFeatureState(store.path.with_name('audio-final-close.json')).read())


if __name__=='__main__':unittest.main()
