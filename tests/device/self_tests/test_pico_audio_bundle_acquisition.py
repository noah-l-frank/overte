"""Actual Actor/archive with declared source packets; no Qt or device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_bundle_acquisition import AudioBundleTransport1,DECLARATION
from adapters.pico4.audio_observation_bundle import FILE
from adapters.pico4.audio_pc_actor import PicoAudioPCActor
from adapters.pico4.audio_pc_originals import AudioPCActorOriginals
from self_tests import test_pico_audio_pc_start as base


class BundleModel:
    def __init__(self,native,settings,pages,run):
        self.native,self.settings,self.pages,self.run=native,settings,pages,run
        self.native_send,self.native_read=native.send,native.original
        self.settings_send,self.settings_read=settings.send,settings.original
        self.pages_read=pages.read
        self.commands=[];self.reads=0;self.raw=None;self.noise=False;self.pending=False
    def send(self,command):
        self.commands.append(deepcopy(command));requested=self.native.clock_ms()
        self.native_send(dict(schemaVersion=1,action='feature-native-observe',commandId=command['nativeNonce']))
        self.settings_send(dict(schemaVersion=1,action='feature-audio-settings-observe',commandId=command['settingsNonce'],runId=self.run))
        native_raw,settings_raw,pages_raw=self.native_read(),self.settings_read(),self.pages_read()
        self.raw=json.dumps(dict(picoAudioObservationBundleVersion=1,commandId=command['commandId'],runId=self.run,
            processId=self.native.pid,requestedEpochMs=requested,capturedEpochMs=self.native.clock_ms(),status='ready',
            nativeNonce=command['nativeNonce'],settingsNonce=command['settingsNonce'],nativeRaw=native_raw,
            settingsRaw=settings_raw,pagesRaw=pages_raw,originalPageKnownClosed=True,nativeAdmissionJoined=False))
    def read(self):
        self.reads+=1
        if self.noise:return 'original invalid packet'
        if self.pending:
            self.pending=False
            return json.dumps(dict(picoAudioObservationBundleVersion=1,commandId=self.commands[-1]['commandId'],status='pending'))
        return self.raw


class AudioBundleAcquisitionTests(unittest.TestCase):
    def setUp(self):
        case=self
        def selected_actor(*args,**kwargs):
            case.model=BundleModel(args[3],args[4],args[5],args[0].run)
            case.transport=AudioBundleTransport1(case.model.send,case.model.read)
            return PicoAudioPCActor(*args,**kwargs,observation_bundle=case.transport)
        self.fixture=base.AudioPCStartTests();self.addCleanup(self.fixture.doCleanups)
        with patch.object(base,'PicoAudioPCActor',side_effect=selected_actor):self.fixture.setUp()
        self.actor=self.fixture.actor;self.fixture.owner.prepare()
        self.before_commands=len(self.model.commands);self.before_reads=self.model.reads

    def test_selected_actor_uses_one_original_bundle_and_passive_reader_reconstructs_sources(self):
        before=self.actor.raws.state['reads'];frame=self.actor.observe()
        self.assertEqual(DECLARATION,self.actor.bundle_declaration)
        self.assertEqual(before+1,self.actor.raws.state['reads']);self.assertEqual(self.before_commands+1,len(self.model.commands))
        self.assertEqual(['audio-bundle'],[row['label'] for row in frame['raws']])
        self.assertEqual(self.model.raw,self.actor.raws.literal(frame['raws'][0]['rawReference']))
        index=self.actor.state['lastObservation'];reader=AudioPCActorOriginals(self.actor.store.path)
        try:
            original=reader.original(index)
            for field in ('native','settings','pages','bundle'):self.assertEqual(frame[field],original[field])
        finally:self.assertTrue(reader.close())
        second=self.actor.observe();self.assertGreater(second['native']['sequence'],frame['native']['sequence'])
        self.assertEqual(self.before_commands+2,len(self.model.commands));self.assertFalse(self.transport.failed)

    def test_readonly_pending_keeps_original_command_and_every_actual_wire(self):
        self.model.pending=True;before=self.actor.raws.state['reads'];frame=self.actor.observe()
        self.assertEqual(self.before_commands+1,len(self.model.commands));self.assertEqual(self.before_reads+2,self.model.reads)
        self.assertEqual(before+2,self.actor.raws.state['reads']);self.assertEqual(2,len(frame['raws']))
        pending=json.loads(self.actor.raws.literal(frame['raws'][0]['rawReference']))
        self.assertEqual('pending',pending['status']);self.assertEqual(self.model.commands[-1]['commandId'],pending['commandId'])

    def test_invalid_original_is_durable_and_first_failure_prevents_another_command(self):
        self.model.noise=True
        with self.assertRaises((NativeUIError,ValueError)):self.actor.observe()
        self.assertTrue(self.transport.failed);self.assertTrue(self.actor.raws.stopped)
        self.assertIsNotNone(self.transport.failure);first=self.transport.failure
        self.assertEqual('original invalid packet',self.actor.raws.literal(self.transport.last_reference))
        with self.assertRaises((NativeUIError,ValueError)):self.actor.observe()
        self.assertEqual(self.before_commands+1,len(self.model.commands));self.assertIs(first,self.transport.failure)

    def test_global_capacity_refuses_before_bundle_send_or_getter(self):
        with (self.fixture.f.path/'owned-capacity.bin').open('wb') as stream:stream.truncate(16*1024*1024)
        with self.assertRaises(NativeUIError):self.actor.observe()
        self.assertEqual(self.before_commands,len(self.model.commands));self.assertEqual(self.before_reads,self.model.reads)
        self.assertIsNotNone(self.actor.state['pending'])


if __name__=='__main__':unittest.main()
