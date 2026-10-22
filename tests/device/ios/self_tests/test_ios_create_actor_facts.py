"""Independent actor originals and UUID adoption using actual typed read owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import unittest
import uuid
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Journal
from ios.adapters.create_actor_facts import CreateActorFacts
from ios.adapters.create_sources import CreateSources
from ios.self_tests import test_ios_create_sources as source_tests
from ios.self_tests.test_ios_create_actions import Product
from ios.self_tests import test_ios_create_actions as action_tests
from ios.self_tests.test_ios_create_files import BINDING
from ios.self_tests.test_ios_create_state import RUN,SESSION
from ios.self_tests.test_ios_create_work import ROOT


class CreateActorFactsTests(unittest.TestCase):
    def setUp(self):
        self.primary_h=source_tests.CreateSourcesTests();self.primary_h.setUp();self.addCleanup(self.primary_h.doCleanups)
        self.peer_h=source_tests.CreateSourcesTests();self.peer_h.setUp();self.addCleanup(self.peer_h.doCleanups)
        self.primary_product=Product();self.primary_product.value['source']['entities']=[]
        self.peer_product=Product();self.peer_product.value['source']['entities']=[]
        self.peer_product.value['source']['localSessionId']='55555555-5555-4555-8555-555555555555'
        self.primary=self.owner(self.primary_h,self.primary_product,'actor-primary',BINDING)
        self.peer_binding=BINDING|dict(processIdentity='43',targetFingerprint='a'*64,sessionId='peer-session')
        self.peer=self.owner(self.peer_h,self.peer_product,'actor',self.peer_binding)
        self.store=PrivateFeatureState(self.peer_h.root/'ios-create-actor-facts.json')
    @contextmanager
    def held(self):
        error=None
        with self.primary_h.lock.held(),self.peer_h.lock.held():
            try:yield
            except Exception as caught:error=caught
        if error is not None:raise error
    def owner(self,h,product,role,binding):
        original=h.sdk.original;pid=int(binding['processIdentity']);state_instance='c'*32 if pid==42 else 'f'*32
        def read(name):
            result=json.loads(original(name));result['processId']=pid
            if name=='create':
                state=product.read(RUN);result['source']=deepcopy(state['source']);result['instance']=state_instance
            elif name=='domain':
                state=product.read(RUN);result['source']['tree']=deepcopy(state['source']['tree'])
                result['source']['scriptOriginal']['processId']=pid
                result['source']['domain']['selfSha256']=hashlib.sha256(uuid.UUID(state['source']['localSessionId']).bytes).hexdigest()
            elif name=='work':
                result['source']['eventSequence']=4+result['sequence']*4
                for index,row in enumerate(result['source']['roles']):
                    row['latest']=deepcopy(row['events'][-1]);row['latest'].update(sequence=5+(result['sequence']-1)*4+index,
                        callerSequence=5+(result['sequence']-1)*4+index,capturedEpochMs=result['clockBefore']['epochMs'],invokedEpochMs=result['clockBefore']['epochMs'])
            return json.dumps(result)
        h.sdk.original=read
        # The real host reader classes consume independently produced native
        # originals. Only the unavailable native/device SDK is simulated.
        with h.lock.held():
            prototype=h.owner();readers=prototype.readers
            for reader in readers.values():reader.pid=pid
            worker_original=readers['worker'].original
            def worker_read():
                value=json.loads(worker_original());value['processId']=pid;return json.dumps(value)
            readers['worker'].original=worker_read
            def stamp(value):value.update(processId=pid,requestedEpochMs=h.sdk.tick(),capturedEpochMs=h.sdk.epoch(),animation={},animationFence={})
            h.native_seam.mutate=stamp
            return CreateSources(PrivateFeatureState(h.root/('ios-create-'+role+'-sources.json')),h.lock,binding,RUN,role,ROOT,lambda:True,
                phase=prototype.phase,readers=readers,epoch_ms=h.sdk.epoch,monotonic=lambda:h.sdk.clock)
    def facts(self):return CreateActorFacts(self.store,self.peer_h.lock,RUN,self.primary,self.peer,lambda:True)
    def phase(self,verb):
        # Both independently credentialed read channels query the same original
        # authority; no expected result enters either SDK/native source.
        for harness,source in ((self.primary_h,self.primary),(self.peer_h,self.peer)):
            harness.sdk.ticket='2'*32
            old=harness.sdk.phase
            def phase(path,_old=old,**kwargs):
                value=_old(path,**kwargs);value['activations'][-1]['stimulus']=dict(verb=verb,inputs={})
                value['activations'][-1]['activatedEpochMs']=1700000000001
                return value
            harness.sdk.phase=phase
            source.phase.client.request=phase
    def replicate(self):
        self.peer_product.value['source']['entities']=deepcopy([row for row in self.primary_product.value['source']['entities'] if row['hostType']=='domain'])
    def authority(self):
        def epoch():return max(self.primary_h.sdk.epoch(),self.peer_h.sdk.epoch())
        journal=Journal(clock=epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.assertEqual(RUN,journal.register('create'))
        journal.activate(RUN,'1'*32);self.posts=[];self.lose_publish=False
        def tick():
            now=max(self.primary_h.sdk.clock,self.peer_h.sdk.clock)+.001
            self.primary_h.sdk.clock=self.peer_h.sdk.clock=now
        def request(path,value=None,method=None,**kwargs):
            tick()
            if path.endswith('/phase'):return journal.phase(RUN,kwargs['phase_nonce'])
            if path.endswith('/samples'):
                self.posts.append(deepcopy(value));journal.publish(RUN,value)
                if self.lose_publish:raise OSError('Lost committed actor receipt')
                return {}
            return journal.snapshot(RUN)
        for source in (self.primary,self.peer):source.phase.client.request=request
        return journal
    def test_shared_publisher_consumes_actual_independent_original_decoder_and_never_replays_lost_post(self):
        with self.held():
            journal=self.authority();facts=self.facts();entry,derived=facts.capture();self.lose_publish=True
            with self.assertRaises(OSError):facts.publisher().publish(facts.original(entry))
            self.assertEqual(1,len(self.posts));self.assertEqual(derived['public']['state'],journal.snapshot(RUN)['entries'][0]['facts'])
            self.lose_publish=False;publisher=self.facts().publisher();self.assertTrue(publisher.resolve());self.assertEqual(1,len(self.posts))
            self.assertEqual(1,publisher.publish(facts.original(entry)));self.assertEqual(1,len(self.posts))
    def test_all_21_shared_actions_have_separately_adopted_and_published_peer_facts(self):
        actions=action_tests.CreateActionsTests();actions.setUp();self.addCleanup(actions.doCleanups)
        # Both observers independently read the same primary SDK product state;
        # only domain replication copies actual domain entities to the peer SDK.
        self.primary_product.value=actions.product.value
        with self.held(),actions.held():
            journal=self.authority();actions.phase=self.primary.phase;owner=actions.owner();owner.prepare()
            facts=self.facts();facts.capture();self.assertEqual(1,facts.publisher().publish(facts.original(facts.state['records'][-1])))
            for index,step in enumerate(action_tests.SCENARIOS['create']['steps']):
                query=actions.query(index);journal.activate(RUN,query['ticket'],query['verb'],query['inputs']);owner.act(query);self.replicate()
                self.peer_product.value['source'].update(canRez=self.primary_product.value['source']['canRez'],canRezTmp=self.primary_product.value['source']['canRezTmp'])
                entry,derived=facts.capture();self.assertEqual(step['state'],derived['public']['state'],step['verb'])
                self.assertEqual(index+2,facts.publisher().publish(facts.original(entry)))
            self.assertEqual(22,len(journal.snapshot(RUN)['entries']));self.assertEqual(5,len(owner.state['owned']))
            self.assertEqual(22,len(facts.state['records']));self.assertNotIn('performed',facts.original(facts.state['records'][-1]))
    def test_native_actor_measurement_owns_its_own_uuid_admission_and_historical_publisher_decoder(self):
        with self.held():
            facts=self.facts();entry,baseline=facts.capture();self.assertEqual([],baseline['public']['state']['objects'])
            self.primary_product.open();self.primary_product.value['source']['tabletShown']=True;self.primary_product.create('model',resource='http://actual/model.gltf')
            actual_id=self.primary_product.selected()['id'];self.primary_product.name_size(actual_id,'e2e-'+RUN+'-model');self.replicate()
            self.phase('open')
            entry,derived=facts.capture();self.assertEqual(['model'],derived['public']['state']['objects']);self.assertTrue(derived['public']['state']['editor'])
            original=facts.original(entry);self.assertEqual(derived,facts.validate_original(original))
            reconstructed=self.facts();self.assertEqual(derived,reconstructed.validate_original(original))
            count=deepcopy(self.primary_h.sdk.counts);reconstructed.validate_original(original);self.assertEqual(count,self.primary_h.sdk.counts)
            forged=deepcopy(original);forged['entry']['sequence']=1
            with self.assertRaises(NativeUIError):facts.validate_original(forged)
    def test_unreplicated_late_actor_never_returns_primary_world_state_and_fresh_read_can_recover(self):
        with self.held():
            facts=self.facts();facts.capture();self.primary_product.open();self.primary_product.value['source']['tabletShown']=True
            self.primary_product.create('model',resource='http://actual/model.gltf');self.primary_product.name_size(self.primary_product.selected()['id'],'e2e-'+RUN+'-model')
            self.phase('open')
            with self.assertRaises(NativeUIError):facts.capture()
            self.assertEqual(1,len(facts.state['records']));self.assertIsNotNone(facts.state['pending']);self.replicate()
            _,derived=facts.capture();self.assertEqual(['model'],derived['public']['state']['objects']);self.assertEqual(1,len(facts.state['interrupted']))
            self.assertEqual(3,len(self.primary.frames));self.assertEqual(3,len(self.peer.frames))
    def test_candidate_alias_and_changed_original_record_cannot_be_reinterpreted_as_actor_evidence(self):
        with self.held():
            facts=self.facts();entry,_=facts.capture();original=facts.original(entry)
            original['primaryBinding']['artifactSha256']='0'*64
            with self.assertRaises(NativeUIError):facts.validate_original(original)
            altered=deepcopy(facts.previous);altered['binding']['targetFingerprint']=BINDING['targetFingerprint']
            with self.assertRaises(NativeUIError):facts.decode(altered)
            reference=facts.state['records'][0]['peer'];reference['sha256']='0'*64
            with self.assertRaises(NativeUIError):facts.validate_original(facts.original(entry))
    def test_serialized_validation_round_rechecks_actual_bytes_and_identity_before_return(self):
        with self.held():
            facts=self.facts();entry,_=facts.capture();original=facts.original(entry)
            store=self.primary.record_store(entry['primary']['index']);before=store.read()
            with self.assertRaises(NativeUIError):
                with facts.validation_round():
                    facts.validate_original(original)
                    changed=deepcopy(before);changed['role']='foreign';store.write(changed,before)
            self.assertIsNone(facts._round)
    def test_version1_actor_history_remains_readable_and_cannot_admit_new_marker_metadata(self):
        with self.held():
            facts=self.facts();facts._version=1;entry,derived=facts.capture();self.assertNotIn('marker',entry)
            reconstructed=self.facts();self.assertEqual(1,reconstructed._version)
            self.assertEqual(derived,reconstructed.validate_original(facts.original(entry)))

    def test_mutated_predecessor_memory_is_never_a_validation_floor_for_an_unchanged_warm_frame(self):
        with self.held():
            facts=self.facts();facts.capture();entry,_=facts.capture();facts.frame(self.primary,entry['primary'])
            self.primary.frames[0]['label']='mutated-in-memory-predecessor'
            with self.assertRaises(NativeUIError):facts.frame(self.primary,entry['primary'])
    def test_typed_actual_primary_marker_lease_is_excluded_without_actor_marker_or_expected_world_values(self):
        from ios.adapters.create_marker_identity import PreparedCreateMarker
        from ios.adapters.create_marker_files import originals
        from ios.self_tests import test_ios_create_marker_measurements as markers
        from ios.self_tests.test_ios_create_peer import domain_pair
        with self.held():
            facts=self.facts();facts.capture();before,after,scripts=markers.frames();domain_before,domain_after=domain_pair(before,after)
            raw=originals(RUN,markers.URL,markers.FILES['ticket'],markers.FILES['nonce'])
            files=dict(contractVersion=1,markerFilesVersion=1,binding=deepcopy(BINDING),ownerToken='f'*64,**markers.FILES,
                hashes={name:hashlib.sha256(value).hexdigest() for name,value in raw.items()})
            lease=PreparedCreateMarker(BINDING,RUN,markers.URL,before=before,after=after,scripts=scripts,files=files,
                directory=markers.DIRECTORY,after_epoch=markers.EPOCH-30,domain_before=domain_before,domain_after=domain_after)
            self.primary_product.value['source']['entities']=[deepcopy(lease.state['admission']['marker'])];self.primary_product.marker=self.primary_product.value['source']['entities'][0]
            native_original=self.primary_h.sdk.original;active=[True]
            def script_original(name):
                value=json.loads(native_original(name))
                if name=='domain':
                    packet=deepcopy(scripts)
                    if not active[0]:packet['source']['engines']=[];packet['source']['membership'].update(revision=2,managers=[])
                    packet.update(requestId=value['requestId'],sequence=value['sequence'],
                        requestedEpochMs=value['clockBefore']['epochMs'],capturedEpochMs=value['clockBefore']['epochMs'])
                    value['source']['scriptOriginal']=packet
                return json.dumps(value)
            self.primary_h.sdk.original=script_original;facts.marker=lease;self.phase('open')
            entry,derived=facts.capture();self.assertEqual([],derived['public']['state']['objects'])
            self.assertIn('entity:create-primary-marker',derived['public']['resources']);self.assertEqual([],self.peer_product.value['source']['entities'])
            rebuilt=CreateActorFacts(self.store,self.peer_h.lock,RUN,self.primary,self.peer,lambda:True,marker=lease)
            original=facts.original(entry);self.assertEqual(derived,rebuilt.validate_original(original))
            self.assertTrue(rebuilt._publication_cache)
            marker_before=deepcopy(lease._admission);binding_before=deepcopy(lease._binding);source_binding=deepcopy(self.primary.binding)
            for fault in ('admission','marker-binding','source-binding','owner-binding','source-role'):
                owner_binding=deepcopy(rebuilt.binding);source_role=self.primary.role
                if fault=='admission':lease._admission['code']['sha256']='0'*64
                elif fault=='marker-binding':lease._binding['artifactSha256']='0'*64
                elif fault=='source-binding':self.primary.binding['artifactSha256']='0'*64
                elif fault=='owner-binding':rebuilt.binding['sessionId']='foreign-session'
                else:self.primary.role='primary'
                with self.subTest(warm_identity=fault),self.assertRaises(NativeUIError):rebuilt.validate_original(original)
                lease._admission=deepcopy(marker_before);lease._binding=deepcopy(binding_before);self.primary.binding=deepcopy(source_binding)
                rebuilt.binding=deepcopy(owner_binding);self.primary.role=source_role
            self.assertEqual(derived,rebuilt.validate_original(original))
            self.primary_product.value['source']['entities']=[]
            with self.assertRaises(NativeUIError):rebuilt.capture(marker_active=False)
            active[0]=False
            _,gone=rebuilt.capture(marker_active=False);self.assertEqual([],gone['public']['resources'])
            self.assertEqual([],gone['public']['state']['objects'])

    def test_returned_original_cannot_poison_cached_native_facts_or_rederived_publication(self):
        with self.held():
            facts=self.facts();entry,derived=facts.capture();original=facts.original(entry)
            returned=facts.frame(self.primary,entry['primary'])
            returned['originals']['createAfter']['source']['canRez']=False
            returned['ticket']='f'*32
            actual=facts.frame(self.primary,entry['primary']);self.assertNotEqual(returned,actual)
            self.assertTrue(actual['originals']['createAfter']['source']['canRez'])
            self.assertEqual(derived,facts.validate_original(original))


if __name__=='__main__':unittest.main()
