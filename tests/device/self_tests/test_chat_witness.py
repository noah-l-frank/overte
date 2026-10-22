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
from adapters.chat_journey.samples import ChatCacheAbsence
from self_tests.test_chat_domain_session import session
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
        for name,instance in (('primary','1'*32),('peer','3'*32)):
            boundary=getattr(self.h.h,name);original=boundary.mutate
            def mutate(value,original=original,instance=instance):
                original(value);session(value,instance=instance);value['chatVersion']=3
                value['source'].update(openedCommandId=('8' if instance=='1'*32 else '9')*32 if value['source']['scopePresent'] else '',retiredCommandId='')
            boundary.mutate=mutate;boundary.present=False;boundary.opened=0
        self.journal=Journal(lambda:self.h.native.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('chat')
        self.ticket='b'*32;self.journal.activate(RUN,self.ticket);self.posted=[];self.lose=False
        self.primary=self.client('r'*64);self.actor=self.client('p'*64)
        self.parent_source=self.source(self.primary);self.actor_source=self.source(self.actor)
        self.flow_store=PrivateFeatureState(self.h.h.root/'flow.json');self.witness_store=PrivateFeatureState(self.h.h.root/'witness-source.json')
        self.publisher_store=PrivateFeatureState(self.h.h.root/'witness-publisher.json')
        self.initial_witness_store=PrivateFeatureState(self.h.h.root/'initial-witness.json')
        self.initial_roles=tuple(self.h.samples(role,PrivateFeatureState(self.h.h.root/('initial-'+role+'.json')),kind=ChatCacheAbsence) for role in ('primary','actor'))
        self.initial_samples=self.h.samples('actor',self.initial_witness_store,kind=ChatCacheAbsence)
        self.flow=ChatFlowInputs(self.parent_source,self.h.roles,self.flow_store,self.witness_store,initial_roles=self.initial_roles,initial_witness_store=self.initial_witness_store,monotonic=lambda:self.h.native.host)
        self.samples=self.h.samples('actor',self.witness_store);self.initial_samples=self.h.samples('actor',self.initial_witness_store,kind=ChatCacheAbsence);self.publisher=self.create()
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
    def create(self):return ChatWitness(self.actor_source,self.samples,self.flow_store,self.publisher_store,initial_samples=self.initial_samples,monotonic=lambda:self.h.native.host)
    def baseline(self):
        with self.flow.session():self.flow.begin(self.parent_source.read());return self.flow.finish()
    def test_independent_new_originals_publish_actual_changes_never_parent_or_checkpoint_state(self):
        before=self.baseline();self.assertFalse(before[0]['state']['open']);self.assertEqual([],before[0]['resources'])
        self.assertEqual(1,self.publisher.publish());self.assertEqual(0,len(self.samples.frames));self.assertEqual(1,len(self.initial_samples.frames))
        self.h.sleep(.01);self.ticket='c'*32;self.journal.activate(RUN,self.ticket,'open',{})
        for boundary in (self.h.h.primary,self.h.h.peer):boundary.present=True;boundary.opened=self.h.native.epoch
        with self.flow.session():
            self.flow.begin(self.parent_source.read());self.h.h.open('local');before=self.flow.finish()
        self.h.h.open('domain',context(RUN)['unicode'])
        count=len(self.h.h.primary.commands);self.assertEqual(2,self.publisher.publish())
        self.assertGreater(len(self.h.h.primary.commands),count);actual=self.journal.snapshot(RUN)['entries'][-1]['facts']
        self.assertTrue(actual['open']);self.assertEqual(context(RUN)['unicode'],actual['draft']);self.assertTrue(actual['keyboard'])
        self.assertNotEqual(actual,before[0]['state']);self.assertEqual(self.ticket,self.samples.frames[-1]['ticket'])
        self.assertEqual(1,len(self.samples.frames));self.assertEqual('actor',self.witness_store.read()['role'])
        self.assertNotIn(self.witness_store.path.name,[role.store.path.name for role in self.h.roles])
        count=len(self.h.h.primary.commands);self.assertIsNone(self.publisher.publish());self.assertEqual(count,len(self.h.h.primary.commands));self.assertEqual(2,len(self.posted))
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
        count=len(self.h.h.primary.commands);self.samples=self.h.samples('actor',self.witness_store);self.initial_samples=self.h.samples('actor',self.initial_witness_store,kind=ChatCacheAbsence);self.publisher=self.create()
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(count,len(self.h.h.primary.commands));self.assertEqual(1,len(self.posted));self.assertTrue(self.publisher_store.path.exists())
    def test_changed_original_phase_retains_its_frame_without_relabelling_or_publication(self):
        self.baseline();original=self.initial_samples.lifecycle.read
        def read(*args):
            value=original(*args);self.journal.activate(RUN,'c'*32,'open',{});return value
        self.initial_samples.lifecycle.read=read
        with self.assertRaises(PhasePending):self.publisher.publish()
        self.assertEqual('retired',self.publisher.rows[-1]['phase']);self.assertEqual(self.ticket,self.initial_samples.frames[-1]['ticket']);self.assertEqual([],self.posted)
        self.assertEqual('c'*32,self.publisher.rows[-1]['after']['activations'][-1]['ticket'])
    def test_parent_component_transcript_cannot_be_the_independent_witness(self):
        self.baseline();self.samples=self.h.roles[1];self.publisher=self.create();count=len(self.h.h.primary.commands)
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(count,len(self.h.h.primary.commands));self.assertEqual([],self.posted)
    def test_original_flow_and_witness_reconstruct_without_any_query_or_publication(self):
        self.baseline();self.publisher.publish();count=len(self.h.h.primary.commands)
        self.flow=ChatFlowInputs(self.parent_source,self.h.roles,self.flow_store,self.witness_store,initial_roles=self.initial_roles,initial_witness_store=self.initial_witness_store,monotonic=lambda:self.h.native.host)
        self.samples=self.h.samples('actor',self.witness_store);self.initial_samples=self.h.samples('actor',self.initial_witness_store,kind=ChatCacheAbsence);self.publisher=self.create()
        self.assertEqual(count,len(self.h.h.primary.commands));self.assertEqual(1,len(self.posted));self.assertIsNone(self.publisher.publish())
    def test_all_original_input_tickets_keep_independent_actual_facts_and_reconstruct_full_histories(self):
        from adapters.chat_journey.flow_inputs import recipe
        for index,action in enumerate(recipe(RUN)):
            if index:
                self.h.sleep(.01);self.ticket=('%032x'%(index+100))
                if index==1:
                    for boundary in (self.h.h.primary,self.h.h.peer):boundary.present=True;boundary.opened=self.h.native.epoch
                self.journal.activate(RUN,self.ticket,action['verb'],action['inputs'])
            with self.flow.session():self.flow.begin(self.parent_source.read());self.flow.finish()
            self.assertEqual(index+1,self.publisher.publish())
            # No ordinary product-input seam runs in this metadata test. Every
            # independently acquired product state must therefore stay closed.
            self.assertFalse(self.posted[-1]['facts']['open']);self.assertEqual([],self.posted[-1]['facts']['messages'])
            self.flow=ChatFlowInputs(self.parent_source,self.h.roles,self.flow_store,self.witness_store,initial_roles=self.initial_roles,initial_witness_store=self.initial_witness_store,monotonic=lambda:self.h.native.host)
        self.assertEqual(26,len(self.posted));self.assertEqual(25,len(self.samples.frames));self.assertEqual(1,len(self.initial_samples.frames));self.assertEqual(26,len(validate_flow(self.flow_store.read())))
        before=len(self.h.h.primary.commands);self.samples=self.h.samples('actor',self.witness_store);self.initial_samples=self.h.samples('actor',self.initial_witness_store,kind=ChatCacheAbsence);self.publisher=self.create()
        self.assertEqual(before,len(self.h.h.primary.commands));self.assertEqual(26,len(self.publisher.rows));self.assertIsNone(self.publisher.publish())

    def test_old_parent_source_reference_cannot_complete_a_later_original_input(self):
        self.baseline();self.journal.activate(RUN,'c'*32,'open',{})
        for boundary in (self.h.h.primary,self.h.h.peer):boundary.present=True;boundary.opened=self.h.native.epoch
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
        self.flow=ChatFlowInputs(self.parent_source,self.h.roles,self.flow_store,self.witness_store,initial_roles=self.initial_roles,initial_witness_store=self.initial_witness_store,monotonic=lambda:self.h.native.host)
        with self.flow.session(),self.assertRaises(NativeUIError):self.flow.begin(self.parent_source.read())
        self.assertEqual(before,len(self.h.h.primary.commands));self.assertEqual('issued',self.flow.rows[-1]['phase'])
        with self.assertRaises(PhasePending):self.publisher.publish()
        self.assertEqual([],self.posted)

    def test_live_cache_before_input_or_independent_baseline_is_never_zero_resource_success(self):
        self.h.h.primary.present=True;self.h.h.primary.opened=20000
        with self.flow.session():
            self.flow.begin(self.parent_source.read())
            with self.assertRaises(NativeUIError):self.flow.finish()
        self.assertEqual('issued',self.flow.rows[-1]['phase']);self.assertEqual([],self.posted)
        self.assertTrue(self.h.h.primary.present)

    def test_independent_baseline_rechecks_cache_absence_after_parent_completion(self):
        self.baseline();self.h.h.peer.present=True;self.h.h.peer.opened=20000
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual('reading',self.publisher.rows[-1]['phase']);self.assertEqual([],self.posted)
        self.assertTrue(self.h.h.peer.present)

    def test_v2_unjoined_baseline_journals_remain_without_adoption_or_new_queries(self):
        self.baseline();self.publisher.publish();before=len(self.h.h.primary.commands)
        previous=self.flow_store.read();old={**previous,'chatFlowInputsVersion':2};self.flow_store.write(old,previous)
        with self.assertRaises(NativeUIError):ChatFlowInputs(self.parent_source,self.h.roles,self.flow_store,self.witness_store,
            initial_roles=self.initial_roles,initial_witness_store=self.initial_witness_store,monotonic=lambda:self.h.native.host)
        self.assertEqual(old,self.flow_store.read())
        previous=self.publisher_store.read();old_publisher={**previous,'chatWitnessVersion':2};self.publisher_store.write(old_publisher,previous)
        with self.assertRaises(NativeUIError):self.create()
        self.assertEqual(old_publisher,self.publisher_store.read());self.assertEqual(before,len(self.h.h.primary.commands));self.assertEqual(1,len(self.posted))

    def test_initial_and_active_stages_must_share_the_exact_original_lock_instances(self):
        from adapters.script_journey.lock import ScriptSourceLock
        original=self.initial_roles[0].locks
        self.initial_roles[0].locks=(ScriptSourceLock(original[0].path),original[1])
        with self.assertRaises(NativeUIError):ChatFlowInputs(self.parent_source,self.h.roles,self.flow_store,self.witness_store,
            initial_roles=self.initial_roles,initial_witness_store=self.initial_witness_store)
        self.initial_samples.locks=(ScriptSourceLock(original[0].path),original[1])
        with self.assertRaises(NativeUIError):self.create()
        self.assertEqual([],self.posted)

    def activate_open(self,*,publish_baseline=True):
        self.baseline()
        if publish_baseline:self.publisher.publish()
        self.h.sleep(.01);self.ticket='c'*32;self.journal.activate(RUN,self.ticket,'open',{})
        for boundary in (self.h.h.primary,self.h.h.peer):boundary.present=True;boundary.opened=self.h.native.epoch
        with self.flow.session():self.flow.begin(self.parent_source.read());self.flow.finish()

    def test_stage_join_refuses_original_native_domain_view_keyboard_or_counter_replacement(self):
        from adapters.chat_journey.stage_join import opened
        self.activate_open();before=self.initial_roles[0].frames[0];after=self.h.roles[0].frames[-1];opened(before,after)
        for fault in ('native-instance','peer-pid','native-sequence','view-instance','keyboard-instance','keyboard-sequence',
                'domain-birth','domain-revision','self','mixer','lifecycle-instance','lifecycle-counter','cache-past','cache-id-collision','settings'):
            changed=deepcopy(after)
            if fault=='native-instance':changed['primary']['instance']='f'*32
            elif fault=='peer-pid':changed['peer']['processId']=457
            elif fault=='native-sequence':changed['primary']['sequence']=before['primary']['sequence']
            elif fault=='view-instance':changed['view']['instance']='f'*32
            elif fault=='keyboard-instance':changed['view']['source']['keyboard']['instance']='f'*32
            elif fault=='keyboard-sequence':changed['view']['source']['keyboard']['sequence']=before['view']['source']['keyboard']['sequence']
            elif fault=='domain-birth':changed['primary']['source']['session']['connectionBirth']='f'*32
            elif fault=='domain-revision':changed['primary']['source']['session']['revision']+=2
            elif fault=='self':changed['primary']['source']['selfSha256']='f'*64
            elif fault=='mixer':changed['primary']['source']['mixerSha256']='f'*64
            elif fault=='lifecycle-instance':changed['lifecycle']['instance']='f'*32
            elif fault=='lifecycle-counter':changed['lifecycle']['lifecycle']['activations']=before['lifecycle']['lifecycle']['activations']-1
            elif fault=='cache-past':changed['primary']['source']['openedEpochMs']=before['primary']['capturedEpochMs']-1
            elif fault=='cache-id-collision':changed['peer']['source']['openedCommandId']=changed['primary']['source']['openedCommandId']
            else:changed['view']['source']['storage']['configSha256']='f'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):opened(before,changed)

    def test_observer_cannot_skip_its_original_initial_stage(self):
        self.activate_open(publish_baseline=False);before=len(self.h.h.primary.commands)
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(before,len(self.h.h.primary.commands));self.assertEqual([],self.posted)
        self.assertIsNone(self.publisher_store.read())

    def test_first_active_input_cannot_replace_original_native_source_within_same_pid(self):
        self.baseline();self.publisher.publish();self.h.sleep(.01);self.ticket='c'*32;self.journal.activate(RUN,self.ticket,'open',{})
        for boundary in (self.h.h.primary,self.h.h.peer):boundary.present=True;boundary.opened=self.h.native.epoch
        original=self.h.h.primary.mutate
        def replacement(value):original(value);value['instance']='f'*32
        self.h.h.primary.mutate=replacement
        with self.flow.session():
            self.flow.begin(self.parent_source.read())
            with self.assertRaises(NativeUIError):self.flow.finish()
        self.assertEqual('issued',self.flow.rows[-1]['phase']);self.assertEqual(1,len(self.posted))
        self.assertTrue(self.h.roles[0].store.path.exists())

    def test_independent_first_active_observer_cannot_replace_its_initial_native_source(self):
        self.activate_open();original=self.h.h.primary.mutate
        def replacement(value):original(value);value['instance']='f'*32
        self.h.h.primary.mutate=replacement
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(1,len(self.posted));self.assertEqual('reading',unpack(self.publisher_store.read()['payload'])[-1]['phase'])
        self.assertEqual(1,len(self.samples.frames));self.assertTrue(self.witness_store.path.exists())

    def test_legacy_domain_packet_cannot_supply_new_initial_lifetime_admission(self):
        original=self.h.h.primary.mutate
        def legacy(value):
            original(value);value['chatVersion']=2;value['source'].pop('openedCommandId');value['source'].pop('retiredCommandId')
        self.h.h.primary.mutate=legacy
        with self.flow.session():
            self.flow.begin(self.parent_source.read())
            with self.assertRaises(NativeUIError):self.flow.finish()
        self.assertEqual('issued',self.flow.rows[-1]['phase']);self.assertEqual([],self.posted)

    def test_changed_original_fixture_prefix_or_desired_fact_field_is_not_adopted(self):
        self.baseline();original=self.flow_store.read();rows=unpack(original['payload']);rows[0]['before']['activations'][0]['expected']={}
        bad={**original,'payload':pack(rows)}
        with self.assertRaises(ValueError):validate_flow(bad)
        bad={**original,'expectedState':{}}
        with self.assertRaises(NativeUIError):validate_flow(bad)
        self.assertEqual(original,self.flow_store.read());self.assertEqual([],self.posted)


if __name__=='__main__':unittest.main()
