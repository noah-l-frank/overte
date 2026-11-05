"""Actual fixed factory and SDK endpoint; declared read-only source packets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.pico4.audio_bundle_acquisition import AudioBundleTransport1,DECLARATION
from adapters.pico4.audio_observation_bundle import ACTION,FILE
from self_tests.test_pico_audio_pc_start_binding import AudioPCBindingTests
from self_tests.test_native_feature_observation import Boundary as Native
from self_tests.test_pico_audio_settings_source import Boundary as Settings
from self_tests.test_pico_audio_pages import Boundary as Pages
from self_tests.test_recorded_preview_history import voice


class AudioBundleBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=AudioPCBindingTests();self.addCleanup(self.fixture.doCleanups);self.fixture.setUp()
        self.assertEqual(Path(__file__).resolve().parents[1]/'adapters/pico4/binding.py',
            Path(self.fixture.adapter._audio_pc_start_coordinator.__wrapped__.__code__.co_filename))

    def test_cold_factory_selection_is_exact_and_default_preserves_existing_scope(self):
        f=self.fixture;owner=f.make();self.addCleanup(owner.actor.raws.close_host)
        self.assertIsNone(owner.actor.observation_bundle);self.assertEqual(0,owner.actor.bundle_declaration)
        self.assertNotIn('audioObservationBundleVersion',owner.actor.scope)
        self.assertEqual([],f.sdk.inputs)

    def test_invalid_selection_refuses_before_recipe_or_rpc(self):
        f=self.fixture
        for flag in (0,1,None,'true',{},object()):
            with self.subTest(flag=type(flag).__name__):
                with patch.object(f.adapter,'_audio_recipe',side_effect=AssertionError('No recipe allocation')) as make:
                    with self.assertRaises(ValueError):f.make(bundle_observation=flag)
                    make.assert_not_called()
        self.assertEqual([],f.calls);self.assertEqual([],f.sdk.inputs)

    def test_selected_factory_uses_fixed_original_sdk_command_and_file_before_parser(self):
        f=self.fixture;owner=f.make(bundle_observation=True);actor=owner.actor;self.addCleanup(actor.raws.close_host)
        self.assertIs(type(actor.observation_bundle),AudioBundleTransport1)
        self.assertEqual(DECLARATION,actor.bundle_declaration);self.assertEqual(1,actor.scope['audioObservationBundleVersion'])
        self.assertEqual(1,actor.raw_scope['audioObservationBundleVersion']);self.assertEqual(3,actor.version);events=[];packet=None
        original_write,original_read=f.sdk.write_debug_app_file,f.sdk.read_debug_app_file
        def write(target,package,path,raw):
            nonlocal packet
            command=json.loads(raw)
            if command.get('action')!=ACTION:return original_write(target,package,path,raw)
            events.append(('send',command));self.assertEqual('org.overte.pico',package)
            epoch=f.sdk.epoch_milliseconds(target);pid=actor.native.pid
            native=Native(pid=pid,epoch_ms=lambda:epoch)
            native.mutate=lambda value:value['audio'].update(muted=False,recordedVoice=voice([],cycle=0,started=0))
            native.send(dict(commandId=command['nativeNonce']))
            settings=Settings();settings.epoch=epoch;settings.send(dict(commandId=command['settingsNonce'],runId=command['runId']))
            settings.value['processId']=pid
            pages=Pages();pages.epoch=epoch;page=json.loads(pages.read())
            page.update(bridgeId=actor.pages.bridge,generation=actor.pages.bridge,processId=pid)
            packet=json.dumps(dict(picoAudioObservationBundleVersion=1,commandId=command['commandId'],runId=command['runId'],
                processId=pid,requestedEpochMs=epoch,capturedEpochMs=epoch,status='ready',nativeNonce=command['nativeNonce'],
                settingsNonce=command['settingsNonce'],nativeRaw=native.original(),settingsRaw=settings.read(),
                pagesRaw=json.dumps(page),originalPageKnownClosed=True,nativeAdmissionJoined=False))
        def read(target,package,path,**options):
            if path!='files/overte-e2e/'+FILE:return original_read(target,package,path,**options)
            events.append(('get',path));self.assertEqual('org.overte.pico',package);self.assertEqual({'attempts':1},options)
            return packet
        with patch.object(f.sdk,'write_debug_app_file',side_effect=write),patch.object(f.sdk,'read_debug_app_file',side_effect=read):
            with actor.held():
                actor._begin('native-observation',None);value=actor.observation_bundle.capture(None)
                self.assertEqual(packet,actor.raws.literal(actor.observation_bundle.last_reference))
                self.assertEqual(events[0][1]['nativeNonce'],value['native']['requestId'])
                self.assertEqual(['audio-bundle'],[row['label'] for row in actor.state['pending']['raws']])
        self.assertEqual(['send','get'],[row[0] for row in events]);self.assertEqual([],f.sdk.inputs)
        self.assertEqual('idle',value['actual']['phase'])


if __name__=='__main__':unittest.main()
