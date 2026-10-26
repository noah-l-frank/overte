"""Automatic product-timer model, original host journals; no audio/device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.audio_pcm_lease import IOSAudioPCMLease
from ios.self_tests.test_ios_audio_recorded_owner import AudioRecordedOwnerTests,RUN,BINDING
from ios.self_tests.test_ios_audio_muted_start import MutedModel
from ios.self_tests.test_ios_audio_pcm_lease import PCMModel
from self_tests.test_recorded_preview_history import voice,event


class AutomaticModel(MutedModel):
    def __init__(self):super().__init__();self.muted=False;self.automatic=True;self.fail=False
    def sleep(self,seconds):
        super().sleep(seconds)
        if not self.automatic or not self.active:return
        elapsed=(self.native_epoch()-self.recorded['startedEpochMs'])/1000
        if self.fail and elapsed>=.5:
            self.tick();rows=self.recorded['events'];self.phase='error';self.active=False
            self.recorded=voice(rows+[event(rows[-1]['eventSequence']+1,'error',rows[-1]['capturedBytes'],
                epoch=self.native_epoch(),error='input-unavailable')],cycle=self.cycle,started=self.recorded['startedEpochMs']);return
        timeline=(('playing',.75,96000),('draining',1.,576000),('completed',1.25,576000))
        for phase,deadline,played in timeline:
            existing=[row['phase'] for row in self.recorded['events']]
            if elapsed>=deadline and phase not in existing:
                self.tick();rows=self.recorded['events'];self.phase=phase;self.active=phase!='completed'
                self.recorded=voice(rows+[event(rows[-1]['eventSequence']+1,phase,576000,played,epoch=self.native_epoch())],
                    cycle=self.cycle,started=self.recorded['startedEpochMs'])


class AudioCompletionOwnerTests(unittest.TestCase):
    def setUp(self):
        self.f=AudioRecordedOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.model=AutomaticModel()
    def start(self,owner):
        m=self.f.model;owner.act(m.ticket,'record-start');m.add_phase('await-completion','5'*32)
    def test_normal_owned_cycle_completes_without_an_invented_stop_or_preview_input(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            self.start(owner);actions=deepcopy(m.actions);result=owner.act(m.ticket,'await-completion')
            self.assertEqual(actions,m.actions);self.assertEqual('completed',result['state']['phase'])
            self.assertEqual(['capturing','playing','draining','completed'],result['state']['history'])
            self.assertEqual((144000,144000,0),tuple(result['state'][key] for key in ('recordedFrames','playedFrames','bufferedFrames')))
            operation=owner.state['operations'][-1];self.assertEqual([],operation['inputs']);self.assertEqual([],operation['quiet'])
            self.assertEqual(owner.state['operations'][0]['after'],operation['startedBy'])
            phases=[owner.original(ref)['originals']['native']['audio']['recordedVoice']['event'].get('phase','idle') for ref in owner.state['records']]
            self.assertTrue(all(phase in phases for phase in ('capturing','playing','draining','completed')))
    def test_already_completed_owned_cycle_is_observed_with_original_event_times(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            self.start(owner);m.sleep(1.3);events=deepcopy(m.recorded['events']);count=len(m.actions)
            result=owner.act(m.ticket,'await-completion')
            self.assertEqual('completed',result['state']['phase']);self.assertEqual(events,m.recorded['events']);self.assertEqual(count,len(m.actions))
    def test_foreign_existing_capture_cannot_be_adopted_without_an_owned_start(self):
        f=self.f;m=f.model;m.active=True;m.phase='capturing';m.cycle=1
        m.recorded=voice([event(1,'capturing',96000,epoch=m.native_epoch())],cycle=1,started=m.native_epoch())
        m.add_phase('await-completion','5'*32)
        with f.owner() as owner:
            with self.assertRaises(NativeUIError):owner.act(m.ticket,'await-completion')
        self.assertEqual([],m.actions);self.assertEqual(1,m.cycle)
    def test_missing_automatic_completion_exhausts_existing_budget_without_input_replay(self):
        f=self.f;m=f.model;m.automatic=False
        with f.owner() as owner:
            self.start(owner)
            with self.assertRaises(NativeUIError):owner.act(m.ticket,'await-completion')
            self.assertIsNotNone(owner.state['pending']);self.assertEqual('capturing',m.phase)
        self.assertEqual(1,m.actions.count('audio.record'));self.assertLess(m.clock,26)
    def test_native_error_is_not_relabelled_completed_or_repaired_by_input(self):
        f=self.f;m=f.model;m.fail=True
        with f.owner() as owner:
            self.start(owner)
            with self.assertRaises(NativeUIError):owner.act(m.ticket,'await-completion')
        self.assertEqual('input-unavailable',m.recorded['events'][-1]['error']);self.assertEqual(1,m.actions.count('audio.record'))
    def test_completed_original_storage_recovers_without_restarting_or_retiming_cycle(self):
        f=self.f;m=f.model;write=OriginalFrameStore.write
        def lost(store,index,frame):
            result=write(store,index,frame)
            if store.namespace=='ios-audio-recorded' and frame['verb']=='await-completion' and frame['originals']['native']['audio']['recordedVoice']['event']['phase']=='completed':
                raise OSError('Declared interruption after completed native original saved before parent append')
            return result
        with f.owner() as owner:
            self.start(owner)
            with patch.object(OriginalFrameStore,'write',new=lost):
                with self.assertRaises(OSError):owner.act(m.ticket,'await-completion')
            wire=deepcopy(owner.state['observation']['wire']);path=owner.frames.path(wire);original=(path.stat().st_ino,path.read_bytes())
            events=deepcopy(m.recorded['events'])
        with f.owner() as owner:
            result=owner.act(m.ticket,'await-completion');self.assertEqual('completed',result['state']['phase'])
            self.assertIn(owner.frames.compact(wire),owner.state['records'])
        self.assertEqual(original,(path.stat().st_ino,path.read_bytes()));self.assertEqual(events,m.recorded['events'])
        self.assertEqual(1,m.actions.count('audio.record'))
    def test_pure_completion_archive_keeps_started_by_membership_and_quiet_shape(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            self.start(owner);owner.act(m.ticket,'await-completion');url=owner.fixture_url;state=deepcopy(owner.state)
        with f.lock.held():
            archive=IOSAudioRecordedOwner.archive(f.store,f.root,BINDING,RUN,f.lock,url);self.assertEqual(state,archive.state)
            wrong=deepcopy(state);wrong['operations'][-1]['startedBy']=deepcopy(wrong['operations'][-1]['after'])
            with self.assertRaises(NativeUIError):archive.decode(archive.envelope(wrong))
            wrong=deepcopy(state);wrong['operations'][-1]['quiet']=[deepcopy(wrong['operations'][-1]['after'])]
            with self.assertRaises(NativeUIError):archive.decode(archive.envelope(wrong))

    def test_rejected_start_followed_by_unmute_is_not_an_owned_capture_to_complete(self):
        f=self.f;m=f.model;m.muted=True
        with f.owner() as owner:
            owner.act(m.ticket,'record-start');m.add_phase('mute','4'*32,enabled=False)
            owner.act(m.ticket,'mute',enabled=False);m.add_phase('await-completion','5'*32)
            with self.assertRaises(NativeUIError):owner.act(m.ticket,'await-completion')
            self.assertIsNone(owner.state['pending'])
        self.assertEqual(1,m.actions.count('audio.record'));self.assertEqual(1,m.cycle)

    def test_normal_muted_error_unmute_completion_and_pcm_lease_share_exact_owned_cycle(self):
        f=self.f;m=f.model;store=PrivateFeatureState(f.root/'ios-audio-pcm-lease.json')
        with f.owner() as owner:
            m.add_phase('mute','3'*32,enabled=True);owner.act(m.ticket,'mute',enabled=True)
            m.add_phase('record-start','4'*32);owner.act(m.ticket,'record-start')
            m.add_phase('mute','5'*32,enabled=False);owner.act(m.ticket,'mute',enabled=False)
            m.add_phase('record-start','6'*32);owner.act(m.ticket,'record-start');start=deepcopy(owner.state['operations'][-1])
            m.add_phase('await-completion','7'*32);owner.act(m.ticket,'await-completion')
            events=deepcopy(m.recorded['events']);pcm=PCMModel(m);native,preview=pcm.reader()
            lease=IOSAudioPCMLease(store,owner,native=native,preview=preview);snapshot=lease.capture()
            self.assertEqual(start['ticket'],snapshot['recording']['ticket']);self.assertEqual(start['after'],snapshot['recording']['original'])
            self.assertEqual(2,snapshot['recording']['cycle']);self.assertEqual(576000,len(snapshot['pcm']['input']))
            self.assertEqual(snapshot['pcm']['input'],snapshot['pcm']['sink']);retired=lease.retire()
            self.assertTrue(retired['captured']);self.assertTrue(retired['retired']);self.assertFalse(pcm.files);self.assertFalse(pcm.memory)
            self.assertEqual(events,m.recorded['events']);url=owner.fixture_url
        with f.lock.held():
            archived=IOSAudioRecordedOwner.archive(f.store,f.root,BINDING,RUN,f.lock,url)
            self.assertEqual(retired,IOSAudioPCMLease.archive(store,archived).retired())
        self.assertEqual(2,m.actions.count('audio.record'));self.assertEqual(2,m.actions.count('audio.mute'))
        self.assertEqual(1,pcm.count('feature-recorded-audio-observe'));self.assertEqual(1,pcm.count('feature-recorded-audio-release'))
