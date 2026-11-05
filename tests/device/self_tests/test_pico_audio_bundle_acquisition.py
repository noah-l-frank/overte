"""Actual Actor/archive with declared source packets; no Qt or device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
import uuid
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

    def rename_during_scan(self,temporary,destination):
        original=os.scandir;root=self.actor.store.path.parent
        class Scan:
            def __init__(self,path):self.owner=original(path)
            def __enter__(self):self.owner.__enter__();return self
            def __exit__(self,*args):return self.owner.__exit__(*args)
            def __iter__(self):
                for entry in self.owner:
                    if Path(entry.path)==temporary:os.replace(temporary,destination)
                    yield entry
        return patch.object(os,'scandir',side_effect=lambda path:Scan(path) if Path(path)==root else original(path))

    def test_atomic_writer_rename_preserves_actual_retained_file_charge(self):
        root=self.actor.store.path.parent;destination=root/'retained-bill-counter.json';temporary=root/'feature-input.owned-bill-counter'
        destination.write_bytes(b'owned original');before=self.actor.raw_bill();temporary.write_bytes(b'owned original')
        with self.rename_during_scan(temporary,destination):actual=self.actor.raw_bill()
        self.assertEqual(before,actual);self.assertFalse(temporary.exists())
        self.assertEqual(b'owned original',destination.read_bytes())

    def test_disappearing_regular_file_still_refuses_actual_bill(self):
        root=self.actor.store.path.parent;destination=root/'retained-bill-counter.json';temporary=root/'ordinary-bill-counter.json'
        destination.write_bytes(b'owned original');temporary.write_bytes(b'owned original')
        with self.rename_during_scan(temporary,destination),self.assertRaises(FileNotFoundError):self.actor.raw_bill()

    def test_temporary_prefix_directory_contents_remain_charged(self):
        before=self.actor.raw_bill();directory=self.actor.store.path.parent/'feature-input.owned-directory'
        directory.mkdir();(directory/'retained.bin').write_bytes(b'owned original')
        actual=self.actor.raw_bill()
        self.assertEqual(before['storedBytes']+len(b'owned original'),actual['storedBytes'])
        self.assertEqual(before['decodedBytes']+len(b'owned original'),actual['decodedBytes'])

    def test_temporary_prefix_symlink_still_refuses(self):
        root=self.actor.store.path.parent;destination=root/'retained-bill-counter.json';destination.write_bytes(b'owned original')
        (root/'feature-input.owned-link').symlink_to(destination.name)
        with self.assertRaises(NativeUIError):self.actor.raw_bill()

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


    def test_real_worker_exit_is_followed_by_one_original_completed_source(self):
        ticket = uuid.uuid4().hex
        self.actor.arm(ticket, 3.25)
        before = sum((row['kind'] == 'pc-source' for row in self.actor.frames))
        result = self.actor.wait_saved(ticket)
        self.assertEqual('completed', result['source']['state'])
        self.assertTrue(self.actor.jobs[ticket].done())
        self.assertEqual(before + 1, sum((row['kind'] == 'pc-source' for row in self.actor.frames)))
        self.assertEqual(0, self.fixture.f.native.actions.count('audio.record'))

    def test_lost_completed_receive_return_resolves_only_from_original_source(self):
        self.fixture.pc.lose_reply_once = True
        ticket = uuid.uuid4().hex
        self.actor.arm(ticket, 3.25)
        packet = self.actor.wait_saved(ticket)
        self.assertEqual('completed', packet['source']['state'])
        self.assertIsNotNone(self.actor.jobs[ticket].exception())
        self.assertEqual(1, self.fixture.pc.lost_returns)

    def test_ignored_receive_ack_does_not_become_completion_or_normal_record(self):
        self.fixture.pc.ignore_receive = True
        with self.assertRaises(NativeUIError):
            self.actor.arm(uuid.uuid4().hex, 3.25)
        self.assertEqual(0, self.fixture.f.native.actions.count('audio.record'))

    def test_original_deadline_failure_is_sticky_before_another_source_query(self):
        ticket = uuid.uuid4().hex
        self.actor.arm(ticket, 3.25)
        before = sum((row['kind'] == 'pc-source' for row in self.actor.frames))
        advance = self.fixture.pc.advance
        self.actor.sleep = lambda _seconds: advance(16)
        with self.assertRaises(NativeUIError):
            self.actor.wait_saved(ticket)
        self.assertTrue(self.actor.raws.stopped)
        first = self.actor.completion_failure
        self.assertIsNotNone(first)
        with self.assertRaises(NativeUIError):
            self.actor.wait_saved(ticket)
        self.assertIs(first, self.actor.completion_failure)
        self.assertEqual(before, sum((row['kind'] == 'pc-source' for row in self.actor.frames)))

    def test_post_action_capture_returns_no_record_readiness_authority(self):
        ticket = uuid.uuid4().hex
        self.assertIsNone(self.actor.arm(ticket, 3.25, wait_ready=False))
        self.assertIsNone(self.actor.job(ticket)['ready'])
        packet = self.actor.wait_saved(ticket)
        self.assertEqual('completed', packet['source']['state'])
        self.assertIsNone(self.actor.job(ticket)['ready'])
        self.assertEqual(0, self.fixture.f.native.actions.count('audio.record'))

    def test_completion_only_ignored_ack_still_cannot_become_original_capture(self):
        self.fixture.pc.ignore_receive = True
        ticket = uuid.uuid4().hex
        self.assertIsNone(self.actor.arm(ticket, 3.25, wait_ready=False))
        with self.assertRaises(NativeUIError):
            self.actor.wait_saved(ticket)
        self.assertIsNone(self.actor.job(ticket)['ready'])
        self.assertTrue(self.actor.raws.stopped)
        self.assertEqual(0, self.fixture.f.native.actions.count('audio.record'))

    def test_unfinished_capture_settles_before_old_source_queries_under_actual_capacity(self):
        first, second, third = (uuid.uuid4().hex for _ in range(3))
        self.actor.arm(first, 3.25, wait_ready=False)
        self.actor.wait_saved(first)
        with (self.fixture.f.path / 'owned-overlap-capacity.bin').open('wb') as stream:
            stream.truncate(4 * 1024 * 1024)
        self.actor.arm(second, 3.25, wait_ready=False)
        with patch.object(self.actor, '_source', wraps=self.actor._source) as source:
            self.actor.arm(third, 3.25, wait_ready=False)
            self.assertEqual(second, source.call_args_list[0].args[0])
            self.assertEqual(first, source.call_args_list[1].args[0])
        self.assertEqual('completed', self.actor.wait_saved(third)['source']['state'])
        self.assertFalse(self.actor.raws.stopped)
        self.assertTrue(all((future.done() for future in self.actor.jobs.values())))

if __name__=='__main__':unittest.main()
