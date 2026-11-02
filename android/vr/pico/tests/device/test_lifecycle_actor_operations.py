"""Actual Common16 peer readiness and normal PrimaryOperations prefix."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_actor_originals import ActorOriginals
from adapters.normal_ui import NativeUIError
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.chat_journey import source_bundles
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from self_tests.pico_lifecycle_actor_operations_fixture import CanonicalLifecycleOperationGraph
import test_lifecycle_actor_composition as composition_fixture


class LifecycleActorOperationsTests(unittest.TestCase):
    def setUp(self):
        self.stage=composition_fixture.LifecycleActorCompositionTests();self.stage.setUp();self.addCleanup(self.stage.doCleanups)
        self.graph=CanonicalLifecycleOperationGraph(self,self.stage);self.stage.start()

    def baseline(self):
        expected=expand(SCENARIOS['lifecycle-input']['baseline'],context(self.stage.run))
        ticket=self.stage.client.observe()['ticket']
        return self.graph.journey.wait('owned-clean-baseline',ticket,self.stage.native.epoch(),expected,['peer'])

    def fields(self,index):
        row=SCENARIOS['lifecycle-input']['steps'][index];ticket=uuid.uuid4().hex
        fields=dict(verb=row['verb'],inputs=expand(row['inputs'],context(self.stage.run)),ticket=ticket,
            fixtureUrl=self.graph.operations.scope['fixtureUrl'])
        self.stage.client.activate(ticket,row['verb'],fields['inputs']);return fields

    def test_actual_common_readiness_then_two_normal_steps_join_independent_same_scope_sources(self):
        self.baseline();self.assertEqual([],self.stage.editor.os.inputs);self.assertEqual([],self.stage.editor.transport.envelopes)
        self.assertGreaterEqual(len(self.graph.actor_samples),3)
        for index in range(2):
            fields=self.fields(index);barrier=self.stage.native.epoch()
            self.graph.journey.required_lifecycle=self.graph.journey.lifecycle.copy()
            self.graph.journey.continuity('before',fields['verb']);self.graph.journey.call('act',fields)
            self.graph.journey.continuity('after',fields['verb'])
            expected=expand(SCENARIOS['lifecycle-input']['steps'][index]['state'],context(self.stage.run))
            self.graph.journey.wait('canonical-peer-'+str(index+1),fields['ticket'],barrier,expected,['peer'])
        operations=self.graph.operations
        self.assertEqual(2,len(operations.state['steps']));self.assertTrue(all(row['phase']=='returned' for row in operations.state['steps']))
        self.assertTrue(all(sample['witness'] is not None for sample in self.graph.journey.samples))
        self.assertIs(self.stage.editor.owner.phase_fence,operations.fence)
        self.assertIs(self.graph.source.lock,self.stage.editor.owner.lock)
        self.assertEqual(self.graph.source.binding,self.stage.waiting['binding'])
        self.assertEqual('typed',self.stage.editor.owner.state['phase'])
        self.assertLessEqual(len(self.graph.world.state['frames']),128);self.assertLessEqual(len(self.graph.source.disk['records']),128)
        actual=PrivateFeatureState(self.stage.root/'lifecycle-actor-originals.json').read()
        self.assertEqual(len(self.graph.actor_samples),len(actual['records']));self.assertEqual('delivered',actual['publication']['phase'])
        with operations.lock.held():
            operations.archive(dict(commonLifecycleConsumptionVersion=1,phases=deepcopy(self.graph.journey.phases),
                samples=deepcopy(self.graph.journey.samples),primarySequence=self.graph.journey.sequence,
                actorSequence=self.graph.journey.last_actor_sequence,witnessSequence=self.graph.journey.witness_sequence))
        self.stage.command('exit');self.stage.worker.wait(timeout=10);self.assertEqual(0,self.stage.worker.returncode)
        absent=self.stage.process.require_absent();self.stage.process.final_absence(absent)


class LifecycleActorPhaseFenceTests(unittest.TestCase):
    setUp=LifecycleActorOperationsTests.setUp
    baseline=LifecycleActorOperationsTests.baseline
    fields=LifecycleActorOperationsTests.fields

    def test_missing_actual_actor_source_readiness_cannot_deliver_first_normal_input(self):
        self.stage.products.unavailable='subject'
        with self.assertRaises(AssertionError):self.baseline()
        self.stage.worker.wait(timeout=10);self.assertNotEqual(0,self.stage.worker.returncode)
        self.assertEqual([],self.stage.editor.os.inputs);self.assertEqual([],self.stage.editor.transport.envelopes)
        self.assertEqual([],self.graph.operations.state['steps']);self.assertEqual([],self.stage.client.observe()['entries'])
        source=PrivateFeatureState(self.stage.root/'lifecycle-actor-originals.json').read()
        self.assertEqual([],source['records'])
        self.assertEqual('{}',ActorOriginals(PrivateFeatureState(self.stage.root/'lifecycle-actor-originals.json')).last('subject')['subject']['raw'])

    def test_changed_phase_after_actual_normal_intent_is_retained_before_input_refusal(self):
        self.baseline();fields=self.fields(0);save=self.stage.editor.owner.save;changed=[];received=[]
        request=self.stage.client.request
        def original(path,*args,**kwargs):
            value=request(path,*args,**kwargs)
            if changed and path.endswith('/phase'):received.append(deepcopy(value))
            return value
        self.stage.client.request=original
        def changing(value):
            result=save(value)
            if not changed and value['phase']=='opening' and value['inputs'] and value['inputs'][-1]['consumed'] is None:
                changed.append(True);self.fields(1)
            return result
        self.stage.editor.owner.save=changing
        with self.assertRaises(NativeUIError):self.graph.journey.call('act',fields)
        self.assertEqual([True],changed);self.assertEqual(1,len(received))
        self.assertEqual([],self.stage.editor.os.inputs);self.assertEqual(1,len(self.stage.editor.transport.envelopes))
        operations=self.graph.operations;self.assertTrue(operations.failed)
        self.assertEqual('issued',operations.state['steps'][-1]['phase'])
        self.assertIsNone(self.stage.editor.owner.state['inputs'][-1]['consumed'])
        before=deepcopy(self.stage.native_calls())
        with self.assertRaises(NativeUIError):self.graph.journey.call('act',fields)
        self.assertEqual(before,self.stage.native_calls());self.assertEqual([],self.stage.editor.os.inputs)
        saved=operations.store.read();history=ChatSourceChunks(operations.store,operations.scope);history.load(saved['chunks'])
        originals=[source_bundles.original(history,saved['chunks'],saved['bundles'],i)[0] for i in range(len(saved['bundles']))]
        self.assertIn(received[0],originals,'The actual rejected phase original was lost before validation')


if __name__=='__main__':unittest.main()
