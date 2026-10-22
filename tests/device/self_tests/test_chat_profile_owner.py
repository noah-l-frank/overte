"""Durable profile source/control boundaries with an explicit native seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_chat_profile import NativeChatProfile,OwnedChatProfile,command
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import unpack
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_native_chat_observation import BINDING,RUN


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.sequence=0;self.requests=[];self.raw=None
        self.attempted=False;self.owned=False;self.ignore=False;self.alive=True;self.mutate=None
        self.hashes=dict(cache={'ArmoredChat-Messages':'c'*64,'ArmoredChat-Config':'d'*64},
            worker={'ArmoredChat-Messages':'c'*64,'ArmoredChat-Config':'d'*64},
            physical={'ArmoredChat-Messages':dict(present=False,empty=True,sha256='e'*64),
                'ArmoredChat-Config':dict(present=True,sha256='f'*64)})
    def send(self,request):
        self.requests.append(deepcopy(request));self.sequence+=1
        if request['operation']=='acquire':self.owned=True
        if request['operation']=='restore':self.attempted=True
        value=dict(chatProfileVersion=1,commandId=request['commandId'],runId=RUN,instance='a'*32,sequence=self.sequence,
            processId=123,capturedEpochMs=self.epoch,owned=self.owned,restoreAttempted=self.attempted,restored=self.attempted,
            original=deepcopy(self.hashes),current=deepcopy(self.hashes),
            settings=dict(instance='b'*32,writerInstance='c'*32,mutationSequence=self.sequence,capturedEpochMs=self.epoch),
            view=dict(instance='d'*32,sequence=self.sequence,capturedEpochMs=self.epoch))
        if self.mutate:self.mutate(value)
        if not self.ignore:self.raw=json.dumps(value)
    def sleep(self,seconds):self.clock+=seconds
    def reader(self):
        return NativeChatProfile(self.send,lambda:self.raw,lambda:self.epoch,lambda:self.alive,123,
            monotonic=lambda:self.clock,sleep=self.sleep)


class ProfileOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700)
        self.store=PrivateFeatureState(self.path/'profile.json');self.lock=ScriptSourceLock(self.path/'script-sources.lock')
        self.native=Boundary();self.owner=self.make()
    def make(self):return OwnedChatProfile(self.native.reader(),self.store,BINDING,RUN,self.lock,component_only=True)
    def test_durable_original_hashes_native_birth_and_private_journal_survive_reconstruction(self):
        acquire=self.owner.perform('acquire');restored=self.make().perform('restore')
        self.assertEqual(acquire['original'],restored['current']);self.assertTrue(restored['restored'])
        self.assertTrue(self.store.path.exists());self.assertEqual(0,self.store.path.stat().st_mode&0o177)
        self.assertEqual(['acquire','restore'],[row['request']['operation'] for row in unpack(self.store.read()['transcript'])])
        before=len(self.native.requests)
        with self.assertRaises(NativeUIError):self.make().perform('restore')
        self.assertEqual(before,len(self.native.requests));self.assertTrue(self.make().perform('inspect')['owned'])
    def test_lost_acquire_receipt_cannot_reacquire_originals_and_recovers_only_by_inspection(self):
        self.native.ignore=True
        with self.assertRaises(NativeUIError):self.owner.perform('acquire')
        self.assertIsNone(unpack(self.store.read()['transcript'])[0]['result'])
        with self.assertRaises(NativeUIError):self.make().perform('acquire')
        self.assertEqual(1,len(self.native.requests));self.native.ignore=False
        self.assertTrue(self.make().perform('inspect')['owned']);self.assertEqual(2,len(self.native.requests))
    def test_lost_restore_receipt_never_repeats_original_write_after_reconstruction(self):
        self.owner.perform('acquire');self.native.ignore=True
        with self.assertRaises(NativeUIError):self.owner.perform('restore')
        with self.assertRaises(NativeUIError):self.make().perform('restore')
        self.assertEqual(['acquire','restore'],[row['operation'] for row in self.native.requests])
        self.native.ignore=False;self.assertTrue(self.make().perform('inspect')['restored'])
        self.assertEqual(['acquire','restore','inspect'],[row['operation'] for row in self.native.requests])

    def test_original_cleanup_phase_change_after_restore_cas_prevents_native_restore_dispatch(self):
        import uuid
        from self_tests import test_chat_cleanup_admission as phase_seams
        from adapters.chat_journey.phase_fence import ChatPhaseFence,bind_phase_fence
        phase=phase_seams.ChatCleanupAdmissionTests();phase.setUp();self.addCleanup(phase.doCleanups)
        store=PrivateFeatureState(phase.h.h.h.root/'cleanup-profile.json')
        owner=OwnedChatProfile(self.native.reader(),store,phase.flow.scope['binding'],RUN,phase.flow.roles[0].locks[0])
        owner.perform('acquire');phase.activate()
        with phase.flow.session():phase.owner.admit()
        fence=ChatPhaseFence(phase.flow,cleanup=phase.owner);bind_phase_fence(owner,fence)
        def send(request):fence.check();self.native.send(request)
        owner.reader.send=send;write=store.write
        def changed(value,previous):
            write(value,previous)
            if unpack(value['transcript'])[-1]['request']['operation']=='restore':phase.h.journal.activate(RUN,uuid.uuid4().hex,'cleanup',{})
        store.write=changed
        with self.assertRaises(NativeUIError),phase.flow.session():owner.perform('restore')
        self.assertEqual(['acquire'],[row['operation'] for row in self.native.requests])
        self.assertIsNone(unpack(store.read()['transcript'])[-1]['result'])
        with self.assertRaises(NativeUIError),phase.flow.session():owner.perform('restore')
        self.assertEqual(['acquire'],[row['operation'] for row in self.native.requests])
    def test_changed_originals_native_sources_false_success_and_private_payload_remain_unresolved(self):
        for fault in ('original','writer','view','process','success','private','stale'):
            with self.subTest(fault=fault):
                self.setUp();self.owner.perform('acquire')
                def mutate(value):
                    if fault=='original':value['original']['cache']['ArmoredChat-Config']='0'*64
                    elif fault=='writer':value['settings']['writerInstance']='0'*32
                    elif fault=='view':value['view']['instance']='0'*32
                    elif fault=='process':value['processId']=124
                    elif fault=='success':value['restored']=True
                    elif fault=='private':value['original']['value']='unowned raw private value'
                    else:value['view']['capturedEpochMs']=19999
                self.native.mutate=mutate
                with self.assertRaises(NativeUIError):self.owner.perform('inspect')
                self.assertIsNone(unpack(self.store.read()['transcript'])[-1]['result'])
    def test_intent_is_on_disk_before_any_transport_and_frozen_clock_cannot_hide_final_guard_delay(self):
        original=self.native.send
        def send(request):
            self.assertEqual(request,unpack(self.store.read()['transcript'])[-1]['request']);original(request)
        self.owner.reader.send=send
        calls=0
        def guard():
            nonlocal calls
            calls+=1
            if calls==5:self.native.clock+=.1
            return True
        self.owner.reader.guard=guard
        epochs=iter([20000,21000,21500]);self.owner.reader.clock_ms=lambda:next(epochs)
        with self.assertRaises(NativeUIError):self.owner.perform('acquire')
        self.assertIsNone(self.owner.reader.last);self.assertEqual(1,len(self.native.requests))
    def test_desired_settings_retire_extra_fields_and_unknown_schema_are_closed(self):
        base=dict(schemaVersion=1,commandId='a'*32,runId=RUN,action='feature-chat-profile',operation='acquire')
        for edit in ({'original':{}},{'operation':'retire'},{'expected':{'restored':True}},{'schemaVersion':True}):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):command(base|edit)


if __name__=='__main__':unittest.main()
