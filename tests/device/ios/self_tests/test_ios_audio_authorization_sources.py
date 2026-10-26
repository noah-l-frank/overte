"""Original authorization carriers; Audio/OS/query producers are host models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters.audio_authorization_sources import AudioAuthorizationSources
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.audio_runtime import IOSAudioRuntime
from ios.adapters import audio_session_source
from ios.self_tests import test_ios_audio_recorded_owner as recording
from ios.self_tests.test_ios_audio_session_source import Boundary


class AuthorizationDomain:
    def __init__(self,case,*,started=True):
        self.f=recording.AudioRecordedOwnerTests();self.f.setUp();case.addCleanup(self.f.doCleanups)
        self.parent=case.enterContext(self.f.owner());self.m=self.f.model
        if started:self.parent.act(self.m.ticket,'record-start')
        self.reference=deepcopy(self.parent.state['operations'][-1]['after']) if started else None
        m=self.m
        class Session(Boundary):
            def stamp(self):m.tick();return dict(epochMs=m.native_epoch(),monotonicMs=round(m.clock*1000))
            def send(self,command):super().send(command);m.sleep(self.delay/1000)
        self.session=Session(20000);self.session.instance=m.native_instance
        self.store=PrivateFeatureState(self.f.root/'ios-audio-authorization-owner.json');self.block=False;self.source_reads=0
        adapter=SimpleNamespace(state_path=lambda _:self.f.root/'session.json');self.runtime=object.__new__(IOSAudioRuntime);self.runtime.adapter=adapter
        self.runtime._sources=lambda _:self.source()
        self.owner=self.reopen()

    def source(self):
        m=self.m;native=m.reader();old_send,original=native.send,native.original
        def send(command):
            previous=m.owner;m.owner=SimpleNamespace(query_intent=lambda _:None)
            try:return old_send(command)
            finally:m.owner=previous
        def body():
            if self.block:raise AssertionError('Historical acquisition queried a native original')
            self.source_reads+=1;return original()
        native.send,native.original=send,body
        def session(clock_source):
            def raw():
                if self.block:raise AssertionError('Historical acquisition queried session authorization')
                self.source_reads+=1;return self.session.raw
            return audio_session_source.IOSAudioSession(self.session.send,raw,
                lambda:clock_source.read(clock_source.sequence)['capturedEpochMs'],m.guard,42,monotonic=lambda:m.clock,sleep=m.sleep)
        return dict(binding=recording.BINDING,clock_source=native,check=m.guard,observer=SimpleNamespace(audio_session=session))

    def reopen(self):
        self.owner=self.runtime.authorization_sources('owned',self.parent,epoch_ms=self.m.epoch,monotonic=lambda:self.m.clock)
        return self.owner

    def capture(self):return self.owner.capture(self.m.ticket,'after-start',self.reference)


class AudioAuthorizationSourcesTests(unittest.TestCase):
    def setUp(self):self.d=AuthorizationDomain(self)

    def test_same_recorded_cycle_and_real_raw_bodies_join_original_native_and_host_clocks(self):
        d=self.d;reference=d.capture();value=d.owner.frame(reference)
        self.assertEqual('granted',audio_session_source.definite_permission(value['originals']['session']))
        self.assertEqual(5,len(value['queries']));self.assertEqual(5,len(value['rawRefs']))
        self.assertGreater(value['clockJoin']['hostBeforeEpochMs']-value['clockJoin']['nativeBefore']['capturedEpochMs'],1000000)
        self.assertEqual(d.reference,value['parent']);self.assertEqual(1,d.m.actions.count('audio.record'))

    def test_before_actual_normal_start_then_after_originals_survive_pure_replay(self):
        d=AuthorizationDomain(self,started=False);parent=d.parent;intent=parent.ui.intent;held=[]
        def guarded(verb,value,identifier):
            if verb=='record-start':held.append(d.owner.capture(d.m.ticket,'before-start',parent.state['pending']['before']))
            return intent(verb,value,identifier)
        parent.ui.intent=guarded
        try:result=parent.act(d.m.ticket,'record-start')
        finally:parent.ui.intent=intent
        d.reference=result['original'];after=d.capture();before=d.owner.frame(held[0])
        self.assertFalse(before['clockJoin']['nativeAfter']['audio']['recordedVoice']['active'])
        self.assertGreaterEqual(parent.original(result['original'])['originals']['native']['audio']['recordedVoice']['events'][0]['publishedEpochMs'],
            before['clockJoin']['nativeAfter']['capturedEpochMs'])
        originals={path:(path.stat().st_ino,path.read_bytes()) for path in d.f.root.iterdir() if path.is_file()}
        reads=d.source_reads;d.block=True
        archive_parent=IOSAudioRecordedOwner.archive(d.f.store,d.f.root,recording.BINDING,recording.RUN,d.f.lock,parent.fixture_url)
        archive=AudioAuthorizationSources.archive(d.store,archive_parent)
        self.assertEqual(d.owner.state,archive.state);self.assertEqual(after,archive.state['frames'][-1]);self.assertEqual(reads,d.source_reads)
        self.assertTrue(all((path.stat().st_ino,path.read_bytes())==saved for path,saved in originals.items()))

    def test_denied_os_remains_denied_without_requested_grant_or_new_input(self):
        d=self.d;d.session.gate['osPermission']=2;actions=deepcopy(d.m.actions)
        packet=d.owner.frame(d.capture());self.assertEqual('denied',audio_session_source.definite_permission(packet['originals']['session']))
        self.assertEqual(actions,d.m.actions)

    def test_saved_logical_original_recovers_exact_inode_and_body_without_query(self):
        d=self.d;write=OriginalFrameStore.write;saved={}
        def lost(store,index,value):
            reference=write(store,index,value)
            if store.namespace=='ios-audio-authorization':
                path=store.path(store.expand(reference));saved.update(path=path,inode=path.stat().st_ino,body=path.read_bytes())
                raise OSError('Declared lost return after saved authorization original')
            return reference
        with patch.object(OriginalFrameStore,'write',lost):
            with self.assertRaises(OSError):d.capture()
        reads=d.source_reads;d.block=True;d.reopen().recover_capture()
        self.assertEqual(reads,d.source_reads);self.assertEqual(saved['inode'],saved['path'].stat().st_ino)
        self.assertEqual(saved['body'],saved['path'].read_bytes());self.assertIsNone(d.owner.state['pending'])

    def test_bad_original_is_retained_then_only_new_bracket_can_qualify(self):
        d=self.d;d.session.mutate=lambda value:value['source'].update(osPermission=True)
        with self.assertRaises(NativeUIError):d.capture()
        self.assertIsNone(d.owner.state['pending']['original']);self.assertTrue(d.owner.state['pending']['rawRefs'])
        old={path:(path.stat().st_ino,path.read_bytes()) for path in d.owner.raws.owned_paths()}
        d.owner.interrupt_capture();d.session.mutate=None;d.reopen();reference=d.capture()
        self.assertEqual(2,reference['index']);self.assertEqual(1,len(d.owner.state['interrupted']))
        self.assertTrue(all((path.stat().st_ino,path.read_bytes())==saved for path,saved in old.items()))

    def test_opened_raw_prefix_is_owned_without_reconstruction_or_fresh_read(self):
        d=self.d;intent=d.owner.raws.store.intent
        def interrupted(event,wire):
            intent(event,wire)
            if wire['phase']=='opened':raise OSError('Declared interrupted raw write before its first byte')
            return True
        d.owner.raws.store.intent=interrupted
        with self.assertRaises(NativeUIError):d.capture()
        wire=deepcopy(d.owner.raws.pending['original']);path=d.owner.raws.store.path(wire);saved=(path.stat().st_ino,path.read_bytes())
        self.assertEqual(b'',saved[1]);reads=d.source_reads;d.block=True;d.reopen()
        with self.assertRaises(NativeUIError):d.owner.recover_capture()
        with self.assertRaises(NativeUIError):d.owner.interrupt_capture()
        self.assertEqual(reads,d.source_reads);self.assertEqual(saved,(path.stat().st_ino,path.read_bytes()))

    def test_after_start_cannot_be_relabelled_as_a_before_input_cut(self):
        d=self.d;reads=d.source_reads
        with self.assertRaises(NativeUIError):d.owner.capture(d.m.ticket,'before-start',d.reference)
        self.assertEqual(reads,d.source_reads)

    def test_current_source_loss_refuses_native_io_and_original_owner_write(self):
        d=self.d;d.m.changed=True
        with self.assertRaises(NativeUIError):d.capture()
        self.assertEqual(0,d.source_reads);self.assertIsNone(d.store.read())

    def test_parent_mutation_during_readonly_cut_remains_unqualified(self):
        d=self.d;send=d.session.send
        def changed(command):
            send(command);d.parent.state['pending']=dict(unowned='concurrent parent change')
        d.session.send=changed
        # Reader.send was bound at construction, so install the declared seam
        # on the same retained source object before any query is issued.
        d.owner.session.send=changed
        with self.assertRaises(NativeUIError):d.capture()
        self.assertIsNotNone(d.owner.state['pending']);self.assertEqual([],d.owner.state['frames'])
        self.assertEqual(1,d.m.actions.count('audio.record'))

    def test_pure_archive_does_not_hide_unknown_owned_prefix_files(self):
        d=self.d;d.capture();PrivateFeatureState(d.f.root/'ios-audio-authorization-orphan.json').write(dict(unowned=True),None)
        parent=IOSAudioRecordedOwner.archive(d.f.store,d.f.root,recording.BINDING,recording.RUN,d.f.lock,d.parent.fixture_url)
        with self.assertRaises(NativeUIError):AudioAuthorizationSources.archive(d.store,parent)
