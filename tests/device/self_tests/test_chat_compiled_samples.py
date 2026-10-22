"""Actual compiled-source/model composition; native/V8/QML seams are synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest

from adapters.chat_journey.compiled_samples import CompiledChatSamples,CompiledChatCacheAbsence
from adapters.chat_journey.flow_inputs import fresh_roles
from adapters.chat_journey.samples import compose
from adapters.chat_journey.script_source import ChatScriptSource
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_journey_samples as model_seams
from self_tests.test_chat_script_source import CompiledBoundary
from self_tests.test_chat_domain_session import session
from self_tests.test_native_chat_observation import RUN


class CompiledChatSamplesTests(unittest.TestCase):
    def setUp(self):
        self.h=model_seams.ChatSamplesTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.binding={key:value for key,value in self.h.samples.binding.items() if key!='scope'}|dict(sourceRevision='1'*40,artifactSha256='2'*64)
        self.peer_binding={key:value for key,value in self.h.peer_binding.items() if key!='scope'}|dict(sourceRevision='1'*40,artifactSha256='2'*64)
        self.code=CompiledBoundary();self.clock=0
        send=self.code.roots.send
        def root_send(request):send(request);self.code.roots.value['processId']=123
        self.code.roots.send=root_send;full=self.code.full
        def script(value):full(value);value['processId']=123
        self.code.script.mutate=script
        self.roots,self.scripts=self.code.readers();self.roots.pid=self.scripts.pid=123
        with self.h.primary_lock.held():
            self.owner=ChatScriptSource(RUN,'primary',self.binding,self.roots,self.scripts,
                PrivateFeatureState(self.h.root/'code.json'),self.h.primary_lock,monotonic=lambda:self.clock)
        self.model=self.sampler()

    def sampler(self,*,absence=False):
        peer=self.h.peer.reader();peer.pid=456
        return (CompiledChatCacheAbsence if absence else CompiledChatSamples)(RUN,'primary',self.binding,self.peer_binding,
            self.h.primary.reader(),peer,self.h.view.reader(vr=True),self.h.native.reader(),
            PrivateFeatureState(self.h.root/('absence.json' if absence else 'compiled.json')),self.h.primary_lock,self.h.peer_lock,
            script_source=self.owner,vr=True,monotonic=lambda:self.clock)

    def test_original_compiled_chat_and_actual_model_share_one_fresh_immutable_frame_and_parent_lock(self):
        result=self.model.read('b'*32,20000);frame=self.model.frames[-1]
        self.assertFalse(result['state']['open']);self.assertEqual(1,frame['compiledChatSourceVersion'])
        self.assertEqual(self.owner.frames[-1],frame['compiledChat']);self.assertIs(self.owner.lock,self.model.locks[0])
        self.assertEqual(result,compose(RUN,frame,123,456,vr=True));self.assertEqual(1,self.model.store.read()['chatCompiledSamplesVersion'])
        self.assertNotIn('chatSamplesVersion',self.model.store.read())
        self.assertEqual(2,len(self.code.roots.commands));self.assertEqual(1,len(self.code.script.commands))
        self.assertEqual(['inspect'],[request['operation'] for request in self.h.primary.commands])

    def test_same_real_phase_can_be_observed_repeatedly_with_new_original_source_transactions(self):
        self.model.read('b'*32,20000);first=deepcopy(self.model.frames[-1]);rebuilt=self.sampler()
        self.assertEqual(1,len(rebuilt.frames));rebuilt.read('b'*32,20000);second=rebuilt.frames[-1]
        self.assertEqual(first['ticket'],second['ticket'])
        self.assertNotEqual(first['compiledChat']['ticket'],second['compiledChat']['ticket'])
        self.assertGreater(second['compiledChat']['before']['sequence'],first['compiledChat']['after']['sequence'])
        self.assertEqual(2,len(self.owner.frames));self.assertEqual(2,len(rebuilt.frames))

    def test_native_lifecycle_birth_and_source_model_order_are_original_join_requirements(self):
        for fault in ('birth','code-after-model','missing-source'):
            if fault!='birth':self.setUp()
            if fault=='birth':self.h.native.mutate=lambda value:value.update(instance='f'*32)
            elif fault=='code-after-model':self.code.roots.epoch=20100
            else:self.code.mutate=lambda value:value['source'].pop('compiledSourceVersion')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.model.read('b'*32,20000)
            self.assertEqual('reading',self.model.store.read()['phase']);self.assertEqual([],self.model.frames)

    def test_legacy_v4_frames_and_foreign_source_originals_cannot_be_adopted_by_compiled_model_reader(self):
        self.h.read();self.model.store=self.h.store
        with self.assertRaises(NativeUIError):self.sampler_with_store(self.h.store)
        self.model=self.sampler();self.model.read('b'*32,20000);original=deepcopy(self.model.frames[-1])
        with self.assertRaises(NativeUIError):self.h.samples._compose(original)
        original['compiledChat']['ticket']='f'*32
        with self.assertRaises(NativeUIError):self.model._compose(original)

    def sampler_with_store(self,store):
        peer=self.h.peer.reader();peer.pid=456
        return CompiledChatSamples(RUN,'primary',self.binding,self.peer_binding,self.h.primary.reader(),peer,
            self.h.view.reader(vr=True),self.h.native.reader(),store,self.h.primary_lock,self.h.peer_lock,
            script_source=self.owner,vr=True,monotonic=lambda:self.clock)

    def test_actual_absence_uses_separate_closed_type_and_can_share_same_original_code_owner(self):
        self.h.primary.present=self.h.peer.present=False;self.h.primary.opened=self.h.peer.opened=0
        self.h.primary.mutate=session;original=self.h.peer.mutate
        def peer(value):original(value);session(value,instance='3'*32)
        self.h.peer.mutate=peer
        absence=self.sampler(absence=True);result=absence.read('b'*32,20000)
        self.assertEqual([],result['resources']);self.assertEqual(1,absence.store.read()['chatCompiledCacheAbsenceVersion'])
        self.assertIs(absence.script_source,self.model.script_source)
        self.h.primary.present=self.h.peer.present=True;self.h.primary.opened=self.h.peer.opened=20000
        self.model.read('c'*32,20000);self.assertEqual(2,len(self.owner.frames))

    def test_slow_final_model_cas_and_original_code_clock_cannot_escape_frozen_other_clocks(self):
        for clock in ('host','code-native'):
            if clock!='host':self.setUp()
            write=self.model.store.write
            def slow(value,previous):
                write(value,previous)
                if value['phase']=='ready':
                    if clock=='host':self.clock+=2
                    else:self.code.roots.epoch+=2000
            self.model.store.write=slow
            with self.subTest(clock=clock),self.assertRaises(NativeUIError):self.model.read('b'*32,20000)
            # Sources/chunks remain original evidence, never green cleanup.
            self.assertIsNotNone(self.model.store.read());self.assertEqual(1,len(self.owner.frames))

    def test_parent_final_guard_rechecks_the_original_code_clock_after_whole_role_join(self):
        self.model.read('b'*32,20000);self.code.roots.epoch+=2000
        with self.assertRaises(NativeUIError):fresh_roles((self.model,),0,lambda:0)


if __name__=='__main__':unittest.main()
