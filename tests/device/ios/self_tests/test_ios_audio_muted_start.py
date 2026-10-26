"""Normal rejected recording attempts, original host files; audio/SDK modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import NativeFeatureObservation
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.self_tests.test_ios_audio_recorded_owner import AudioRecordedOwnerTests,Model,RUN,BINDING
from self_tests.test_recorded_preview_history import voice,event


class MutedModel(Model):
    def __init__(self):super().__init__();self.muted=True;self.reason='microphone-muted';self.capture_instead=False
    def add_phase(self,verb,ticket,*,enabled=None):
        super().add_phase(verb,ticket)
        if verb=='mute':self.activations[-1]['stimulus']['inputs']=dict(enabled=enabled)
    def io(self):
        result=super().io()
        # Model the actual NativeInput.scroll(direction, token=...) API used
        # by IOSAudioIO, rather than the widget fixture's two-argument method.
        result.original.native=SimpleNamespace(scroll=lambda direction,token:self.scroll('audio.scrollbar',direction,token=token))
        return result
    def scroll(self,identifier,direction,*,token):
        super().scroll(identifier,direction,token=token);self.inputs+=1
    def activate(self,identifier,*,token):
        if identifier=='audio.mute':
            self.original(identifier,token);self.inputs+=1;self.actions.append(identifier)
            if self.ignore:return
            self.tick();self.muted=not self.muted
            if self.muted and self.active:
                self.active=False;self.phase='cancelled';previous=self.recorded
                self.recorded=voice(previous['events']+[event(previous['events'][-1]['eventSequence']+1,'cancelled',
                    previous['events'][-1]['capturedBytes'],epoch=self.native_epoch(),error='microphone-muted')],
                    cycle=self.cycle,started=previous['startedEpochMs'])
            if self.loss:raise NativeUIError('Declared lost return after actual modeled normal mute')
            return
        if not self.muted or self.capture_instead:return super().activate(identifier,token=token)
        self.original(identifier,token);self.inputs+=1;self.actions.append(identifier)
        if self.ignore:return
        # The declared native branch follows AudioClient's real muted Start:
        # begin a new cycle, publish one error, never activate capture.
        assert identifier=='audio.record' and not self.active
        self.tick();self.cycle+=1;self.active=False;self.phase='error'
        sequence=self.recorded['events'][-1]['eventSequence']+1 if self.recorded['events'] else 1
        self.recorded=voice([event(sequence,'error',epoch=self.native_epoch(),error=self.reason)],cycle=self.cycle,started=self.native_epoch())
        if self.loss:raise NativeUIError('Declared lost return after original native muted rejection')


class AudioMutedStartTests(unittest.TestCase):
    def setUp(self):
        self.f=AudioRecordedOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.model=MutedModel()

    def test_original_muted_error_cycle_and_both_quiet_clocks_are_required(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            result=owner.act(m.ticket,'record-start');operation=owner.state['operations'][-1]
            self.assertEqual(2,owner.version);self.assertEqual('error',result['state']['phase'])
            self.assertEqual('microphone-muted',result['state']['error']);self.assertEqual(['error'],result['state']['history'])
            self.assertEqual((0,0,0),tuple(result['state'][key] for key in ('recordedFrames','playedFrames','bufferedFrames')))
            self.assertEqual(2,len(operation['quiet']));self.assertFalse(m.active);self.assertEqual(1,m.actions.count('audio.record'))
            first,last=[owner.original(ref) for ref in operation['quiet']]
            self.assertGreaterEqual(last['clockJoin']['nativeBefore']['capturedEpochMs']-first['clockJoin']['nativeAfter']['capturedEpochMs'],300)
            self.assertGreaterEqual(last['clockJoin']['hostBeforeMonotonic']-first['clockJoin']['hostAfterMonotonic'],.3)

    def test_lost_rejection_return_uses_new_originals_without_second_start(self):
        f=self.f;m=f.model;m.loss=True
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'record-start')
        m.loss=False
        with f.owner() as owner:
            result=owner.act(m.ticket,'record-start')
            self.assertEqual('microphone-muted',result['state']['error']);self.assertIsNone(owner.state['pending'])
        self.assertEqual(1,m.actions.count('audio.record'));self.assertEqual(1,m.cycle)

    def test_successful_input_ack_without_error_cycle_cannot_qualify(self):
        f=self.f;m=f.model;m.ignore=True
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'record-start')
        m.ignore=False
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'record-start')
        self.assertEqual(1,m.actions.count('audio.record'));self.assertEqual(0,m.cycle)

    def test_other_native_error_is_not_relabelled_microphone_muted(self):
        f=self.f;m=f.model;m.reason='input-unavailable'
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'record-start')
        self.assertEqual('input-unavailable',m.recorded['events'][0]['error']);self.assertEqual(1,m.actions.count('audio.record'))

    def test_capture_after_muted_preparation_does_not_satisfy_rejection(self):
        f=self.f;m=f.model;m.capture_instead=True
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'record-start')
        self.assertTrue(m.active);self.assertEqual('capturing',m.recorded['events'][0]['phase'])
        self.assertEqual(1,m.actions.count('audio.record'))

    def test_requested_sleep_without_native_or_host_progress_does_not_supply_quiet(self):
        f=self.f;m=f.model;m.sleep=lambda _seconds:None
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'record-start')
        self.assertEqual(1,m.actions.count('audio.record'))

    def test_completed_error_archive_preserves_original_files_and_uses_no_live_reader(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            result=owner.act(m.ticket,'record-start');expected=deepcopy(owner.state);url=owner.fixture_url
        files={path:(path.stat().st_ino,path.read_bytes()) for path in f.root.iterdir() if path.is_file()}
        with f.lock.held(),patch.object(NativeFeatureObservation,'__init__',side_effect=AssertionError('Archive may not create a live native reader')):
            archive=IOSAudioRecordedOwner.archive(f.store,f.root,BINDING,RUN,f.lock,url)
            self.assertEqual(expected,archive.state);archive.quiet(archive.state['operations'][0],archive.state['records'])
            self.assertEqual(result['state'],archive.effect(archive.state['operations'][0],archive.original(archive.state['operations'][0]['after'])))
        self.assertTrue(all((path.stat().st_ino,path.read_bytes())==value for path,value in files.items()))

    def test_literal_one_normal_cycle_remains_readable_without_rewriting_originals(self):
        f=self.f;m=f.model;m.muted=False
        with f.owner() as owner:
            owner.version=1;owner.act(m.ticket,'record-start');m.add_phase('record-cancel','4'*32)
            owner.act(m.ticket,'record-cancel');self.assertEqual(1,owner.store.read()['iosAudioRecordedOwnerVersion']);url=owner.fixture_url
        files={path:(path.stat().st_ino,path.read_bytes()) for path in f.root.iterdir() if path.is_file()}
        with f.lock.held():
            archive=IOSAudioRecordedOwner.archive(f.store,f.root,BINDING,RUN,f.lock,url)
            self.assertEqual(1,archive.version);self.assertEqual(2,len(archive.state['operations']))
        self.assertTrue(all((path.stat().st_ino,path.read_bytes())==value for path,value in files.items()))

    def test_literal_one_retains_its_muted_input_boundary(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            owner.version=1
            with self.assertRaises(NativeUIError):owner.act(m.ticket,'record-start')
        self.assertEqual([],m.actions)


class AudioMuteFlowTests(unittest.TestCase):
    def setUp(self):
        self.f=AudioRecordedOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.model=MutedModel();self.f.model.muted=False
    def test_normal_mute_rejected_start_unmute_start_and_cancel_join_original_cycles(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            m.add_phase('mute','5'*32,enabled=True);muted=owner.act(m.ticket,'mute',enabled=True)
            self.assertTrue(muted['state']['muted']);self.assertEqual(0,m.cycle)
            m.add_phase('record-start','6'*32);rejected=owner.act(m.ticket,'record-start')
            self.assertEqual('microphone-muted',rejected['state']['error']);self.assertEqual(1,m.cycle)
            original=deepcopy(m.recorded)
            m.add_phase('mute','7'*32,enabled=False);unmuted=owner.act(m.ticket,'mute',enabled=False)
            self.assertFalse(unmuted['state']['muted']);self.assertEqual(original,m.recorded)
            m.add_phase('record-start','8'*32);started=owner.act(m.ticket,'record-start')
            self.assertEqual('capturing',started['state']['phase']);self.assertEqual(2,m.cycle)
            m.add_phase('record-cancel','9'*32);cancel=owner.act(m.ticket,'record-cancel')
            self.assertEqual('cancelled',cancel['state']['phase']);self.assertEqual(5,len(owner.state['operations']))
            self.assertEqual(2,m.actions.count('audio.mute'));self.assertEqual(3,m.actions.count('audio.record'))
    def test_mute_during_capture_preserves_original_capture_prefix_and_reports_real_cancel(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            owner.act(m.ticket,'record-start');first=deepcopy(m.recorded)
            m.add_phase('mute','5'*32,enabled=True);result=owner.act(m.ticket,'mute',enabled=True)
            self.assertEqual('cancelled',result['state']['phase']);self.assertEqual('microphone-muted',result['state']['error'])
            self.assertEqual(['capturing','cancelled'],result['state']['history']);self.assertEqual(0,result['state']['bufferedFrames'])
            self.assertEqual(first['events'],m.recorded['events'][:len(first['events'])]);self.assertEqual(1,m.cycle)
    def test_lost_mute_return_is_resolved_without_second_toggle(self):
        f=self.f;m=f.model;m.add_phase('mute','5'*32,enabled=True);m.loss=True
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'mute',enabled=True)
        self.assertTrue(m.muted);m.loss=False
        with f.owner() as owner:self.assertTrue(owner.act(m.ticket,'mute',enabled=True)['state']['muted'])
        self.assertEqual(1,m.actions.count('audio.mute'))
    def test_ignored_mute_stays_pending_and_does_not_turn_into_a_second_toggle(self):
        f=self.f;m=f.model;m.add_phase('mute','5'*32,enabled=True);m.ignore=True
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'mute',enabled=True)
        m.ignore=False
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'mute',enabled=True)
        self.assertFalse(m.muted);self.assertEqual(1,m.actions.count('audio.mute'))
    def test_wrong_enabled_argument_or_reused_ticket_cannot_relabel_actual_fixture_input(self):
        f=self.f;m=f.model;m.add_phase('mute','5'*32,enabled=True)
        with f.owner() as owner:
            with self.assertRaises(NativeUIError):owner.act(m.ticket,'mute',enabled=False)
            self.assertNotIn('audio.mute',m.actions)
            owner.act(m.ticket,'mute',enabled=True)
            with self.assertRaises(NativeUIError):owner.act(m.ticket,'mute',enabled=False)
            self.assertEqual(1,m.actions.count('audio.mute'))
    def test_already_unmuted_requires_no_toggle_and_preserves_the_original_idle_cycle(self):
        f=self.f;m=f.model;m.add_phase('mute','5'*32,enabled=False);original=deepcopy(m.recorded)
        with f.owner() as owner:
            result=owner.act(m.ticket,'mute',enabled=False)
            self.assertFalse(result['state']['muted']);self.assertEqual(original,m.recorded)
            self.assertEqual([], [row for row in owner.state['operations'][0]['inputs'] if row['verb']=='mute'])
        self.assertNotIn('audio.mute',m.actions)

    def test_normal_mute_archive_replays_both_quiet_originals_and_fixture_value(self):
        f=self.f;m=f.model;m.add_phase('mute','5'*32,enabled=True)
        with f.owner() as owner:
            owner.act(m.ticket,'mute',enabled=True);url=owner.fixture_url;expected=deepcopy(owner.state)
        with f.lock.held(),patch.object(NativeFeatureObservation,'__init__',side_effect=AssertionError('No live source in mute archive')):
            archive=IOSAudioRecordedOwner.archive(f.store,f.root,BINDING,RUN,f.lock,url);self.assertEqual(expected,archive.state)
            operation=archive.state['operations'][0]
            self.assertTrue(archive.effect(operation,archive.original(operation['after']))['muted'])
            bad=deepcopy(expected);bad['operations'][0]['quiet']=[]
            with self.assertRaises(NativeUIError):archive.decode(archive.envelope(bad))

    def test_literal_one_keeps_old_read_grammar_while_two_requires_independent_mute_join(self):
        f=self.f;m=f.model;m.position=0
        def old_ui(value):
            for row in value['controls']:
                if row['id']=='audio.mute':row.update(checked=True,nativeMuted=True)
            return value
        m.transform=old_ui
        with f.owner() as owner:
            owner.version=1;reference=owner.capture(m.ticket,'record-start');original=owner.original(reference)
            self.assertFalse(original['originals']['native']['audio']['muted'])
            self.assertTrue(next(row for row in original['originals']['ui']['controls'] if row['id']=='audio.mute')['nativeMuted'])
            newer=deepcopy(original);newer['iosAudioRecordedObservationVersion']=2;owner.version=2
            with self.assertRaises(NativeUIError):owner.frame(newer)
