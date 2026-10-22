"""Original phase coordinator, actual strict native joins; transport seams only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.flow_inputs import ChatFlowInputs,validate_flow
from adapters.chat_journey.witness import ChatWitness
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending
from feature_journeys.witness import Client,Journal
from feature_journeys.fixtures import context
from self_tests import test_chat_background as background_seams
from self_tests.test_native_chat_observation import RUN


class WitnessTests(unittest.TestCase):
    def setUp(self):
        self.h=background_seams.BackgroundTests();self.h.setUp();self.addCleanup(self.h.doCleanups);self.h.h.close()
        self.journal=Journal(lambda:self.h.native.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('chat')
        self.ticket='b'*32;self.journal.activate(RUN,self.ticket);self.posted=[];self.lose=False
        self.primary=self.client('r'*64);self.actor=self.client('p'*64)
        self.parent_source=self.source(self.primary);self.actor_source=self.source(self.actor)
        self.flow_store=PrivateFeatureState(self.h.h.root/'flow.json');self.witness_store=PrivateFeatureState(self.h.h.root/'witness-source.json')
        self.publisher_store=PrivateFeatureState(self.h.h.root/'witness-publisher.json')
        self.flow=ChatFlowInputs(self.parent_source,self.h.roles,self.flow_store,self.witness_store,monotonic=lambda:self.h.native.host)
        self.samples=self.h.samples('actor',self.witness_store);self.publisher=self.create()
    def client(self,token):
        client=Client('http://controlled.test/feature-fixture/v1',token)
        def request(path,value=None,method=None,**kwargs):
            if path.endswith('/phase'):return self.journal.phase(RUN,kwargs['phase_nonce'])
            self.assertEqual('p'*64,token);self.assertEqual('/runs/'+RUN+'/samples',path)
            state=unpack(self.publisher_store.read()['payload'])[-1];self.assertEqual('publishing',state['phase'])
            self.posted.append(deepcopy(value));self.journal.publish(RUN,value)
            if self.lose:raise ValueError('Explicit lost publisher transport response')
            return {'accepted':True}
        client.request=request;return client
    def source(self,client):return PhaseFixtureReader(client,RUN,'chat',epoch_ms=lambda:self.h.native.epoch,monotonic=lambda:self.h.native.host)
    def create(self):return ChatWitness(self.actor_source,self.samples,self.flow_store,self.publisher_store,monotonic=lambda:self.h.native.host)
    def baseline(self):
        with self.flow.session():self.flow.begin(self.parent_source.read());return self.flow.finish()
    def test_independent_new_originals_publish_actual_changes_never_parent_or_checkpoint_state(self):
        before=self.baseline();self.assertFalse(before[0]['state']['open'])
        self.h.h.open('domain',context(RUN)['unicode'])
        count=len(self.h.h.primary.commands);self.assertEqual(1,self.publisher.publish())
        self.assertGreater(len(self.h.h.primary.commands),count);actual=self.journal.snapshot(RUN)['entries'][-1]['facts']
        self.assertTrue(actual['open']);self.assertEqual(context(RUN)['unicode'],actual['draft']);self.assertTrue(actual['keyboard'])
        self.assertNotEqual(actual,before[0]['state']);self.assertEqual(self.ticket,self.samples.frames[-1]['ticket'])
        self.assertEqual(1,len(self.samples.frames));self.assertEqual('actor',self.witness_store.read()['role'])
        self.assertNotIn(self.witness_store.path.name,[role.store.path.name for role in self.h.roles])
        count=len(self.h.h.primary.commands);self.assertIsNone(self.publisher.publish());self.assertEqual(count,len(self.h.h.primary.commands));self.assertEqual(1,len(self.posted))
    def test_no_source_queries_or_publication_before_original_input_completion(self):
        before=len(self.h.h.primary.commands)
        with self.assertRaises(PhasePending):self.publisher.publish()
        with self.flow.session():self.flow.begin(self.parent_source.read())
        with self.assertRaises(PhasePending):self.publisher.publish()
        self.assertEqual(before,len(self.h.h.primary.commands));self.assertEqual([],self.posted);self.assertIsNone(self.publisher_store.read())
    def test_input_sequence_skip_duplicate_and_interrupted_admission_never_issue_new_input(self):
        self.baseline();self.journal.activate(RUN,'c'*32,'send',{})
        old=self.flow_store.read()
        with self.flow.session(),self.assertRaises(NativeUIError):self.flow.begin(self.parent_source.read())
        self.assertEqual(old,self.flow_store.read());self.assertEqual([],self.posted)
    def test_lost_publication_is_durable_and_cannot_be_resent_after_reconstruction(self):
        self.baseline();self.lose=True
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(1,len(self.posted));self.assertEqual('publishing',self.publisher.rows[-1]['phase'])
        count=len(self.h.h.primary.commands);self.samples=self.h.samples('actor',self.witness_store);self.publisher=self.create()
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(count,len(self.h.h.primary.commands));self.assertEqual(1,len(self.posted));self.assertTrue(self.publisher_store.path.exists())
    def test_changed_original_phase_retains_its_frame_without_relabelling_or_publication(self):
        self.baseline();original=self.samples.lifecycle.read
        def read(*args):
            value=original(*args);self.journal.activate(RUN,'c'*32,'open',{});return value
        self.samples.lifecycle.read=read
        with self.assertRaises(PhasePending):self.publisher.publish()
        self.assertEqual('retired',self.publisher.rows[-1]['phase']);self.assertEqual(self.ticket,self.samples.frames[-1]['ticket']);self.assertEqual([],self.posted)
        self.assertEqual('c'*32,self.publisher.rows[-1]['after']['activations'][-1]['ticket'])
    def test_parent_component_transcript_cannot_be_the_independent_witness(self):
        self.baseline();self.samples=self.h.roles[1];self.publisher=self.create();count=len(self.h.h.primary.commands)
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(count,len(self.h.h.primary.commands));self.assertEqual([],self.posted)
    def test_original_flow_and_witness_reconstruct_without_any_query_or_publication(self):
        self.baseline();self.publisher.publish();count=len(self.h.h.primary.commands)
        self.flow=ChatFlowInputs(self.parent_source,self.h.roles,self.flow_store,self.witness_store,monotonic=lambda:self.h.native.host)
        self.samples=self.h.samples('actor',self.witness_store);self.publisher=self.create()
        self.assertEqual(count,len(self.h.h.primary.commands));self.assertEqual(1,len(self.posted));self.assertIsNone(self.publisher.publish())
    def test_all_original_input_tickets_keep_independent_actual_facts_and_reconstruct_full_histories(self):
        from adapters.chat_journey.flow_inputs import recipe
        for index,action in enumerate(recipe(RUN)):
            if index:
                self.h.sleep(.01);self.ticket=('%032x'%(index+100))
                self.journal.activate(RUN,self.ticket,action['verb'],action['inputs'])
            with self.flow.session():self.flow.begin(self.parent_source.read());self.flow.finish()
            self.assertEqual(index+1,self.publisher.publish())
            # No ordinary product-input seam runs in this metadata test. Every
            # independently acquired product state must therefore stay closed.
            self.assertFalse(self.posted[-1]['facts']['open']);self.assertEqual([],self.posted[-1]['facts']['messages'])
            self.flow=ChatFlowInputs(self.parent_source,self.h.roles,self.flow_store,self.witness_store,monotonic=lambda:self.h.native.host)
        self.assertEqual(26,len(self.posted));self.assertEqual(26,len(self.samples.frames));self.assertEqual(26,len(validate_flow(self.flow_store.read())))
        before=len(self.h.h.primary.commands);self.samples=self.h.samples('actor',self.witness_store);self.publisher=self.create()
        self.assertEqual(before,len(self.h.h.primary.commands));self.assertEqual(26,len(self.publisher.rows));self.assertIsNone(self.publisher.publish())

    def test_old_parent_source_reference_cannot_complete_a_later_original_input(self):
        self.baseline();self.journal.activate(RUN,'c'*32,'open',{})
        with self.flow.session():self.flow.begin(self.parent_source.read());self.flow.finish()
        original=self.flow_store.read();rows=unpack(original['payload']);rows[-1]['references']=deepcopy(rows[0]['references'])
        with self.assertRaises(NativeUIError):validate_flow({**original,'payload':pack(rows)})
        self.assertEqual(original,self.flow_store.read());self.assertEqual([],self.posted)

    def test_input_completion_copy_is_inside_final_native_clock_freshness(self):
        clock=self.h.native.host;original=deepcopy
        def late(value):
            result=original(value)
            if type(value) is list and len(value)==2 and all(type(row) is dict and 'state' in row for row in value):
                self.h.native.epoch+=2000
            return result
        with self.flow.session():
            self.flow.begin(self.parent_source.read())
            with patch('adapters.chat_journey.flow_inputs.deepcopy',side_effect=late):
                with self.assertRaises(NativeUIError):self.flow.finish()
        self.assertEqual(clock,self.h.native.host);self.assertEqual([],self.posted)
        self.assertTrue(self.flow_store.path.exists())

    def test_frozen_host_and_late_wire_copy_are_checked_against_original_native_clock(self):
        self.baseline();clock=self.h.native.host;original=deepcopy
        def late(value):
            result=original(value)
            if type(value) is dict and set(value)=={'ticket','actor','actorSequence','capturedEpochMs','facts'}:
                self.h.native.epoch+=2000
            return result
        with patch('adapters.chat_journey.witness.deepcopy',side_effect=late):
            with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(clock,self.h.native.host);self.assertEqual([],self.posted)
        self.assertEqual('publishing',self.publisher.rows[-1]['phase']);self.assertTrue(self.publisher_store.path.exists())

    def test_interrupted_input_admission_is_reconstructed_passively_and_never_repeated(self):
        with self.flow.session():self.flow.begin(self.parent_source.read())
        before=len(self.h.h.primary.commands)
        self.flow=ChatFlowInputs(self.parent_source,self.h.roles,self.flow_store,self.witness_store,monotonic=lambda:self.h.native.host)
        with self.flow.session(),self.assertRaises(NativeUIError):self.flow.begin(self.parent_source.read())
        self.assertEqual(before,len(self.h.h.primary.commands));self.assertEqual('issued',self.flow.rows[-1]['phase'])
        with self.assertRaises(PhasePending):self.publisher.publish()
        self.assertEqual([],self.posted)

    def test_changed_original_fixture_prefix_or_desired_fact_field_is_not_adopted(self):
        self.baseline();original=self.flow_store.read();rows=unpack(original['payload']);rows[0]['before']['activations'][0]['expected']={}
        bad={**original,'payload':pack(rows)}
        with self.assertRaises(ValueError):validate_flow(bad)
        bad={**original,'expectedState':{}}
        with self.assertRaises(NativeUIError):validate_flow(bad)
        self.assertEqual(original,self.flow_store.read());self.assertEqual([],self.posted)


if __name__=='__main__':unittest.main()
