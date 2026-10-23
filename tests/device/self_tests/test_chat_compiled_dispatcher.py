"""Original 26-step dispatcher/witness with actual closed compiled-source joins.

Native/V8/widgets/network/peer production are explicit seams. No device/app or
Assignment Client runs. All original Python owners, histories and phase joins
run; this does not qualify a peer binary or a complete Pico target journey.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest

from adapters.chat_journey.compiled_samples import CompiledChatSamples,CompiledChatCacheAbsence
from adapters.chat_journey.flow_inputs import ChatFlowInputs
from adapters.chat_journey.samples import ChatCacheAbsence
from adapters.chat_journey.script_source import ChatScriptSource
from adapters.normal_feature_state import PrivateFeatureState
from self_tests import test_chat_dispatcher as dispatcher_seams
from self_tests.test_chat_script_source import CompiledBoundary
from self_tests.test_native_chat_observation import RUN


class CompiledDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.h=dispatcher_seams.DispatcherTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.sources={}
        self.h.h.samples=self.samples
        self.h.roles=tuple(self.samples(role,store) for role,store in zip(('primary','actor'),(self.h.roles[0].store,self.h.roles[1].store)))
        initial=tuple(self.samples(role,sample.store,kind=ChatCacheAbsence) for role,sample in zip(('primary','actor'),self.h.w.initial_roles))
        self.h.flow=ChatFlowInputs(self.h.w.parent_source,self.h.roles,self.h.w.flow_store,self.h.w.witness_store,
            initial_roles=initial,initial_witness_store=self.h.w.initial_witness_store,monotonic=lambda:self.h.h.native.host)
        self.h.owner=self.h.create()

    def code(self,role,store):
        key='witness' if 'witness' in store.path.name else role
        if key not in self.sources:
            native=self.h.h.native;boundary=CompiledBoundary();send=boundary.roots.send;full=boundary.full
            def roots(request):boundary.roots.epoch=native.epoch;send(request);boundary.roots.value['processId']=123
            boundary.roots.send=roots
            def script(value):full(value);value.update(processId=123,capturedEpochMs=native.epoch,requestedEpochMs=native.epoch)
            boundary.script.mutate=script;roots,scripts=boundary.readers()
            for reader in (roots,scripts):reader.pid=123;reader.clock_ms=lambda:native.epoch;reader.monotonic=lambda:native.host;reader.sleep=self.h.sleep
            code_store=PrivateFeatureState(self.h.root/('compiled-'+key+'-code.json'));lock=self.h.roles[0].locks[0]
            with lock.held():self.sources[key]=ChatScriptSource(RUN,role,self.h.h.binding,roots,scripts,code_store,lock,monotonic=lambda:native.host)
        return self.sources[key]

    def samples(self,role,store,*,kind=None,script_source=None):
        original=self.h.h;native=original.native;peer=original.h.peer.reader();peer.pid=456
        selected=CompiledChatCacheAbsence if kind is ChatCacheAbsence else CompiledChatSamples
        result=selected(RUN,role,original.binding,original.peer_binding,original.h.primary.reader(),peer,
            original.h.view.reader(vr=True),original.h.native.reader(),store,original.h.primary_lock,original.h.peer_lock,
            vr=True,script_source=script_source or self.code(role,store),monotonic=lambda:native.host)
        for reader in (result.primary,result.peer,result.view,result.lifecycle):
            reader.clock_ms=lambda:native.epoch;reader.monotonic=lambda:native.host;reader.sleep=self.h.sleep
        return result

    def test_original_compiled_prefix_uses_distinct_code_roles_and_independent_witness_sources(self):
        from adapters.chat_journey.witness import ChatWitness
        actor=self.samples('actor',self.h.w.witness_store);initial=self.samples('actor',self.h.w.initial_witness_store,kind=ChatCacheAbsence)
        publisher=ChatWitness(self.h.w.actor_source,actor,self.h.w.flow_store,self.h.w.publisher_store,initial_samples=initial,
            monotonic=lambda:self.h.h.native.host)
        for index in range(3):self.h.next(index);self.assertEqual(index+1,publisher.publish())
        self.assertEqual({'primary','actor','witness'},set(self.sources))
        self.assertIsNot(self.sources['actor'],self.sources['witness'])
        self.assertTrue(all(role.frames[-1]['compiledChatSourceVersion']==1 for role in self.h.roles))
        self.assertEqual(3,len(publisher.rows));self.assertTrue(all(row['phase']=='published' for row in publisher.rows))

    def test_all_original_25_steps_and_26_independent_compiled_witness_stages(self):
        self.h.test_all_25_real_child_steps_share_original_native_ui_storage_and_peer_histories()
        self.assertEqual({'primary','actor','witness'},set(self.sources))
        self.assertTrue(all(source.frames and not source.failed for source in self.sources.values()))


if __name__=='__main__':unittest.main()
