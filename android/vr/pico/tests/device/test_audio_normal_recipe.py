"""Actual private Pico recipe factories; native/OS/SDK boundaries are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import test_normal_scripts as original
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.audio_recipe import PicoAudioRecipe
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from self_tests.test_pico_audio_recipe import AudioRecipeTests,AudioRecipeFlowTests


class PicoAudioRecipeBindingTests(unittest.TestCase):
    def setUp(self):
        self.h=original.PicoNormalScriptsTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.adapter,self.sdk=self.h.instance,self.h.native
        self.source=PhaseFixtureReader(Client('http://127.0.0.1:9876/feature-fixture/v1','a'*64),'a'*32,'audio')
    def test_factory_reuses_parent_lock_and_binds_both_actual_normal_input_transports(self):
        lock=self.adapter._script_journey()._lock(self.sdk.target)
        session=PicoOpenXrAdapterSession(FakeTransport(),'explicit-audio-recipe',self.h.fixture.state_root);session.begin(self.sdk.identity)
        with patch.object(self.adapter,'pico_input_session',return_value=session):
            owner=self.adapter._audio_recipe(self.sdk.target,'a'*32,self.source,source_lock=lock)
            self.assertIsInstance(owner,PicoAudioRecipe);self.assertIs(owner.lock,lock);self.assertIs(owner.source,self.source)
            with lock.held():page=owner.child('page.prepare')
        self.assertIs(page.lock,lock);self.assertIs(page.preview.lock,lock);self.assertIs(page.session,session)
        for io in (page.route.io,page.preview._ui().io):self.assertIs(io.original.navigation.io._before_send,owner.delivery_callback)
        self.assertIsNone(owner.store.read());self.assertIsNone(page.store.read());self.assertEqual([],self.sdk.inputs)
    def test_cold_unresolved_root_never_reconstructs_native_or_ui_owner(self):
        binding=self.adapter._scripts(self.sdk.target).binding
        store=PrivateFeatureState(self.adapter._audio_page_store(self.sdk.target).path.with_name('audio-recipe-owner.json'))
        store.write(dict(binding=binding,unresolved='original recipe'),None)
        with patch.object(self.adapter,'_scripts',side_effect=AssertionError('Qt reconstruction during cold metadata validation')):
            with self.assertRaises(ValueError):self.adapter._audio_recipe(self.sdk.target,'a'*32,self.source)
        self.assertEqual([],self.sdk.inputs);self.assertEqual(dict(binding=binding,unresolved='original recipe'),store.read())
    def orphan(self,name):
        store=PrivateFeatureState(self.adapter._audio_page_store(self.sdk.target).path.with_name(name));store.write(dict(original=name),None)
        self.adapter._audio_preview_store(self.sdk.target).write(dict(runId='a'*32),None)
        cleanup=self.h.cleanup_instance()
        with patch.object(cleanup,'_audio_preview') as competing:
            with self.assertRaises(ValueError):cleanup.cleanup(self.sdk.target)
            competing.assert_not_called()
        self.assertEqual(dict(original=name),store.read());self.assertTrue(self.adapter._audio_capture_owned(self.sdk.target))
    def test_orphan_manifest_alone_blocks_cleanup_and_competing_release(self):self.orphan('audio-recipe-owner.json')
    def test_orphan_chunk_alone_blocks_cleanup_and_competing_release(self):self.orphan('audio-recipe-owner.json.frame-000.json')


if __name__=='__main__':unittest.main()
