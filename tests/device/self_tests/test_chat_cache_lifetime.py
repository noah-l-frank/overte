"""Once-only native cache ownership on explicit synthetic native/clock seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
from adapters.native_chat_observation import ChatCaptureOwner,OwnedChatCapture,NativeChatObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_chat_domain_session import session
from self_tests.test_native_chat_observation import Boundary,RUN,BINDING


class NativeBoundary(Boundary):
    def __init__(self):
        super().__init__();self.open_id='';self.retire_id='';self.epoch=20000;self.lose=None;self.apply=True
    def send(self,request):
        if self.apply:
            if request['operation']=='observe' and not self.present and not self.retired:self.open_id=request['commandId']
            if request['operation']=='retire' and not self.retired:self.retire_id=request['commandId']
            super().send(request);session(self.value);self.value['chatVersion']=3
            self.value['capturedEpochMs']=self.epoch
            self.value['source'].update(openedCommandId=self.open_id,retiredCommandId=self.retire_id)
        else:self.commands.append(deepcopy(request))
        if request['operation']==self.lose:raise OSError('Explicit lost native response')
    def reader(self):
        return NativeChatObservation(self.send,self.read,lambda:self.epoch,self.guard,123,
            monotonic=lambda:self.clock,sleep=self.sleep)


class CacheLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='chat-cache-lifetime-');self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.native=NativeBoundary();self.lock=ScriptSourceLock(root/'script-sources.lock')
        self.owner=ChatCaptureOwner(PrivateFeatureState(root/'capture.json'),BINDING,self.native.guard,component_only=True)
        self.native.store=self.owner.store;self.owner.begin(RUN)
        initial=self.native.reader().perform(RUN,'inspect');self.owner.admit(initial)
        self.store=PrivateFeatureState(root/'lifetime.json');self.flow=self.create()
    def create(self):
        return ChatCacheLifetime(OwnedChatCapture(self.native.reader(),self.owner,RUN),self.store,self.lock,monotonic=lambda:self.native.clock)
    def mutations(self):return [row for row in self.native.commands if row['operation']!='inspect']

    def test_actual_original_mutations_and_two_passive_release_queries_survive_cold_reconstruction(self):
        self.flow.activate();self.native.event();flow=self.create();value=flow.activate()
        self.assertEqual(1,len(value['source']['events']));self.assertEqual(['observe'],[row['operation'] for row in self.mutations()])
        retired=flow.retire();self.assertTrue(retired['source']['retired']);self.assertFalse(retired['source']['scopePresent'])
        self.assertEqual(self.mutations()[0]['commandId'],retired['source']['openedCommandId'])
        self.assertEqual(self.mutations()[1]['commandId'],retired['source']['retiredCommandId'])
        self.assertEqual(['inspect','inspect'],[row['operation'] for row in self.native.commands[-2:]])
        self.assertEqual('retired',self.store.read()['phase']);self.assertIsNotNone(self.owner.store.read())
        self.create().retire();self.assertEqual(['observe','retire'],[row['operation'] for row in self.mutations()])

    def test_lost_observe_result_uses_only_matching_original_native_open_id(self):
        self.native.lose='observe'
        with self.assertRaises(NativeUIError):self.flow.activate()
        self.assertTrue(self.native.present);self.assertEqual('activation-issued',self.store.read()['phase'])
        self.native.lose=None;value=self.create().activate()
        self.assertTrue(value['source']['scopePresent']);self.assertEqual(['observe'],[row['operation'] for row in self.mutations()])

    def test_uncertain_unapplied_observe_is_never_resent_or_adopted(self):
        original=self.native.send
        def ignored(request):
            if request['operation']=='observe':self.native.commands.append(deepcopy(request));raise OSError('Not applied')
            return original(request)
        self.native.send=ignored;self.flow=self.create()
        with self.assertRaises(NativeUIError):self.flow.activate()
        with self.assertRaises(NativeUIError):self.create().activate()
        self.assertEqual(['observe'],[row['operation'] for row in self.mutations()]);self.assertFalse(self.native.present)
        self.assertEqual('activation-issued',self.store.read()['phase'])

    def test_foreign_first_open_id_after_lost_result_never_becomes_our_effect(self):
        self.native.lose='observe'
        with self.assertRaises(NativeUIError):self.flow.activate()
        self.native.lose=None;self.native.open_id='f'*32
        with self.assertRaises(NativeUIError):self.create().activate()
        self.assertEqual(['observe'],[row['operation'] for row in self.mutations()]);self.assertFalse(self.owner.owned()['active'])

    def test_lost_retire_result_requires_actual_matching_original_fence_and_never_retires_twice(self):
        self.flow.activate();self.native.lose='retire'
        with self.assertRaises(NativeUIError):self.flow.retire()
        self.assertTrue(self.native.retired);self.assertEqual('retirement-issued',self.store.read()['phase'])
        self.native.lose=None;retired=self.create().retire();self.assertTrue(retired['source']['retired'])
        self.assertEqual(['observe','retire'],[row['operation'] for row in self.mutations()])
        self.assertEqual('retired',self.store.read()['phase']);self.assertIsNotNone(self.owner.store.read())

    def test_unapplied_retire_and_lost_intent_write_never_issue_a_second_mutation(self):
        self.flow.activate();original=self.native.send
        def ignored(request):
            if request['operation']=='retire':self.native.commands.append(deepcopy(request));raise OSError('Explicit unapplied retire')
            return original(request)
        self.native.send=ignored;flow=self.create()
        with self.assertRaises(NativeUIError):flow.retire()
        with self.assertRaises(NativeUIError):self.create().retire()
        self.assertTrue(self.native.present);self.assertFalse(self.native.retired)
        self.assertEqual(['observe','retire'],[row['operation'] for row in self.mutations()])

    def test_original_request_is_durable_before_native_mutation_dispatch(self):
        original=self.native.send;seen=[]
        def admitted(request):
            if request['operation']!='inspect':
                disk=self.store.read();key='activation' if request['operation']=='observe' else 'retirement'
                self.assertEqual(request,disk[key]['request']);seen.append(request['operation'])
            return original(request)
        self.native.send=admitted;flow=self.create();flow.activate();flow.retire()
        self.assertEqual(['observe','retire'],seen)

    def test_final_before_source_copy_cannot_age_cache_absence_before_observe(self):
        original=self.store.write
        def late(value,previous):
            original(value,previous)
            if value['phase']=='ready':self.native.epoch+=2000
        self.store.write=late
        with self.assertRaises(NativeUIError):self.flow.activate()
        self.assertEqual([],self.mutations());self.assertFalse(self.native.present)
        self.assertEqual('ready',self.store.read()['phase'])

    def test_slow_durable_mutation_intent_cannot_dispatch_under_frozen_host_clock(self):
        original=self.store.write
        def late(value,previous):
            original(value,previous)
            if value['phase']=='activation-issued':self.native.epoch+=2000
        self.store.write=late
        with self.assertRaises(NativeUIError):self.flow.activate()
        self.assertEqual([],self.mutations());self.assertFalse(self.native.present)
        self.assertEqual('activation-issued',self.store.read()['phase'])

    def test_foreign_retire_fence_is_not_our_release(self):
        self.flow.activate();self.native.lose='retire'
        with self.assertRaises(NativeUIError):self.flow.retire()
        self.native.lose=None;self.native.retire_id='f'*32
        with self.assertRaises(NativeUIError):self.create().retire()
        self.assertEqual('retirement-issued',self.store.read()['phase'])
        self.assertEqual(['observe','retire'],[row['operation'] for row in self.mutations()])

    def test_lost_durable_activation_intent_ack_cannot_dispatch_or_warm_overwrite(self):
        original=self.store.write
        def lost(value,previous):
            original(value,previous)
            if value['phase']=='activation-issued':raise OSError('Durable write landed, receipt lost')
        self.store.write=lost
        with self.assertRaises(NativeUIError):self.flow.activate()
        original_disk=self.store.read();self.assertEqual([],self.mutations());self.assertEqual('activation-issued',original_disk['phase'])
        with self.assertRaises(NativeUIError):self.flow.activate()
        self.assertEqual(original_disk,self.store.read());self.store.write=original
        with self.assertRaises(NativeUIError):self.create().activate()
        self.assertEqual([],self.mutations());self.assertFalse(self.native.present)

    def test_lost_capture_owner_active_write_ack_recovers_without_second_observe(self):
        original=self.owner.store.write
        def lost(value,previous):
            original(value,previous)
            if value['active']:raise OSError('Original active owner receipt lost')
        self.owner.store.write=lost
        with self.assertRaises(NativeUIError):self.flow.activate()
        self.assertTrue(self.owner.store.read()['active']);self.assertEqual('activation-issued',self.store.read()['phase'])
        self.owner.store.write=original;self.create().activate()
        self.assertEqual(['observe'],[row['operation'] for row in self.mutations()])

    def test_final_original_native_clock_cannot_age_under_frozen_host_copy(self):
        import adapters.chat_journey.cache_lifetime as module
        original=module.deepcopy;armed=[False]
        def late(value):
            result=original(value)
            if armed[0] and isinstance(value,dict) and value.get('chatVersion')==3:self.native.epoch+=2000;armed[0]=False
            return result
        # Fault specifically at final returned packet copying after active save.
        finish=self.flow.finished
        def final(value):
            armed[0]=True
            with patch.object(module,'deepcopy',side_effect=late):return finish(value)
        self.flow.finished=final
        with self.assertRaises(NativeUIError):self.flow.activate()
        self.assertEqual(['observe'],[row['operation'] for row in self.mutations()]);self.assertIsNotNone(self.store.read())

    def test_same_run_foreign_process_source_and_old_native_schema_cannot_adopt(self):
        for fault in ('instance','old-schema'):
            # No mutation may be issued before native v3 original admission.
            original=self.native.send
            def wrong(request):
                original(request)
                if fault=='instance':self.native.value['instance']='f'*32
                else:
                    self.native.value['chatVersion']=2;self.native.value['source'].pop('openedCommandId');self.native.value['source'].pop('retiredCommandId')
            self.native.send=wrong
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.create().activate()
            self.assertEqual([],self.mutations());self.native.send=original


if __name__=='__main__':unittest.main()
