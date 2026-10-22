"""Authenticated retirement HTTP/once journals; native cleanup decoder modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_retirement_publisher import PhaseRetirementPublisher,PublicationPending
from adapters.phase_retirement_reader import PhaseRetirementReader
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.retirement_receipts import body
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from self_tests.test_completed_frame_lease import BINDING


class PhaseRetirementTests(unittest.TestCase):
    def setUp(self):
        self.now=100100.;self.server=make_server('r'*64,'a'*64,adapter_token='d'*64);self.server.journal.clock=lambda:self.now
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01),daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.url='http://127.0.0.1:'+str(self.server.server_address[1])+'/feature-fixture/v1'
        self.reader,self.actor,self.adapter=Client(self.url,'r'*64),Client(self.url,'a'*64),Client(self.url,'d'*64)
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.known={};self.validations=0
        self.attach('emotes')
    def stop(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.assertFalse(self.thread.is_alive())
    def attach(self,area):
        self.area=area;self.now=89000.;self.run=self.server.journal.register(area);self.ticket=uuid.uuid4().hex
        self.now=90000.;self.server.journal.activate(self.run,self.ticket,'cleanup');self.now=100100.
        self.phase=PhaseFixtureReader(self.actor,self.run,area,epoch_ms=lambda:self.now,monotonic=lambda:10.1);self.phase.status()
    def validate_original(self,value):
        self.validations+=1;need(digest(value) in self.known);return deepcopy(self.known[digest(value)])
    def original(self,sequence=1):
        value=dict(modeledOriginalVersion=1,runId=self.run,area=self.area,index=sequence,nonce=uuid.uuid4().hex);sha=digest(value)
        public=dict(schemaVersion=1,contractVersion=16,runId=self.run,sequence=sequence,capturedEpochMs=100000.,
            state=deepcopy(SCENARIOS[self.area]['baseline']),artifacts=[],resources=[],lifecycle=dict(backgrounds=0,activations=1,launches=1))
        quiet=dict(hostAfterFirstEpochMs=94000.,hostBeforeLastEpochMs=97000.,hostAfterFirstMonotonic=4.,hostBeforeLastMonotonic=7.,
            nativeAfterFirstEpochMs=20000,nativeBeforeLastEpochMs=23000,nativeAfterFirstMonotonicMs=1000,nativeBeforeLastMonotonicMs=4000,
            nativeInstance='f'*32,processId=42)
        self.known[sha]=dict(ticket=self.ticket,public=public,acquisition=dict(hostBeforeEpochMs=100000.,hostAfterEpochMs=100010.,
            hostBeforeMonotonic=10.,hostAfterMonotonic=10.01),retirement=dict(originalSha256=sha,quiet=quiet,
            provenance=dict(version=1,namespace='modeled-retirement-original',reference=dict(index=sequence,sha256=sha),originalSha256=sha)))
        return value
    def owner(self):return PhaseRetirementPublisher(PrivateFeatureState(self.root/('phase-retirement-'+self.area+'-'+self.run+'-actor.json')),
        BINDING,self.phase,self.lock,lambda:True,self.validate_original,epoch_ms=lambda:self.now,monotonic=lambda:10.1)
    def posts(self,mode):
        real=self.actor.request;calls=[]
        def request(path,value=None,*args,**kwargs):
            if path.endswith('/retirements') and value is not None:
                calls.append(deepcopy(value))
                if mode=='lost-before':raise OSError('Synthetic unknown uncommitted retirement')
                if mode=='ack':return {}
                result=real(path,value,*args,**kwargs)
                if mode=='lost-after':raise OSError('Synthetic lost committed retirement reply')
                return result
            return real(path,value,*args,**kwargs)
        return calls,request
    def test_actual_committed_summary_duplicate_once_and_private_full_original_archive(self):
        with self.lock.held():
            original=self.original();owner=self.owner();calls,request=self.posts('normal')
            with patch.object(self.actor,'request',side_effect=request):
                self.assertEqual(1,owner.publish(original));self.assertEqual(1,self.owner().publish(original))
            self.assertEqual(1,len(calls));entry=self.server.phase_retirements.snapshot(self.run)['entries'][0]
            self.assertEqual(calls[0],{k:entry[k] for k in calls[0]});self.assertNotIn('public',entry);self.assertNotIn('state',entry['cleanup'])
            self.assertIn('state',owner.load(owner.state['records'][0])['intent']['derived']['public'])
            with patch.object(self.actor,'request',side_effect=AssertionError('historical retirement must not use HTTP')):
                value=PhaseRetirementPublisher.archive(owner.store.read(),store=owner.store,binding=BINDING,run=self.run,area=self.area,
                    fixture_url=self.url,phase_instance=self.phase.previous['instance'],validate_original=self.validate_original)
            self.assertEqual(1,len(value['records']))
    def test_adapter_reader_gets_no_actor_animation_pose_state_artifacts_or_opaque_fact_channel(self):
        with self.lock.held():self.owner().publish(self.original())
        observed=self.adapter.request('/runs/'+self.run+'/retirements');entry=observed['entries'][0]
        self.assertEqual({'schemaVersion','contractVersion','runId','sequence','capturedEpochMs','resources','lifecycle'},set(entry['cleanup']))
        self.assertEqual({'index','sha256'},set(entry['provenance']['reference']))
        for word in ('animation','poseProgress','Sit1','facts','artifacts','restoredBeforeNominalEnd'):self.assertNotIn(word,str(observed))
        with self.assertRaises(ValueError):self.reader.request('/runs/'+self.run+'/retirements',{k:entry[k] for k in entry if k not in ('sequence','receivedEpochMs','receiptSha256')})
    def test_unknown_committed_POST_resolves_from_original_read_without_another_POST(self):
        with self.lock.held():
            original=self.original();owner=self.owner();calls,request=self.posts('lost-after')
            with patch.object(self.actor,'request',side_effect=request),self.assertRaises(OSError):owner.publish(original)
            again,request=self.posts('normal')
            with patch.object(self.actor,'request',side_effect=request):self.assertTrue(self.owner().resolve())
            self.assertEqual(1,len(calls));self.assertFalse(again)
    def test_unknown_uncommitted_or_ACK_only_delivery_blocks_same_and_new_source_without_resend(self):
        for mode in ('lost-before','ack'):
            self.attach('emotes')
            with self.subTest(mode=mode),self.lock.held():
                original=self.original();owner=self.owner();calls,request=self.posts(mode)
                with patch.object(self.actor,'request',side_effect=request),self.assertRaises((OSError,PublicationPending)):owner.publish(original)
                again,request=self.posts('normal')
                with patch.object(self.actor,'request',side_effect=request):
                    with self.assertRaises(PublicationPending):self.owner().publish(original)
                    with self.assertRaises(PublicationPending):self.owner().publish(self.original(2))
                self.assertEqual(1,len(calls));self.assertFalse(again)
    def test_phase_advance_retires_only_publication_responsibility_not_native_cleanup(self):
        with self.lock.held():
            original=self.original();owner=self.owner();calls,request=self.posts('lost-before')
            with patch.object(self.actor,'request',side_effect=request),self.assertRaises(OSError):owner.publish(original)
            self.server.journal.activate(self.run,uuid.uuid4().hex,'cleanup');recovered=self.owner();self.assertTrue(recovered.resolve())
            self.assertEqual('phase-retired',recovered.load(recovered.state['records'][0])['mode'])
            self.assertFalse(self.server.phase_retirements.snapshot(self.run)['entries'])
    def test_actual_missing_local_cleanup_verdict_and_nonquiet_or_foreign_original_are_rejected_before_POST(self):
        for fault in ('unknown','resources','quiet','pid','phase','provenance'):
            with self.subTest(fault=fault),self.lock.held():
                original=self.original();derived=self.known[digest(original)]
                if fault=='unknown':self.known.pop(digest(original))
                elif fault=='resources':derived['public']['resources']=['panel:owned-marker']
                elif fault=='quiet':derived['retirement']['quiet']['nativeBeforeLastMonotonicMs']-=1
                elif fault=='pid':derived['retirement']['quiet']['processId']=43
                elif fault=='phase':derived['ticket']='f'*32
                else:derived['retirement']['provenance']['reference']['animation']='Waving'
                with self.assertRaises((ValueError,RuntimeError)):self.owner().publish(original)
        self.assertFalse(self.server.phase_retirements.snapshot(self.run)['entries'])
    def test_closed_summary_rejects_malformed_timestamp_no_launch_and_state_smuggling(self):
        with self.lock.held():
            original=self.original();_derived,valid=self.owner().original(original)
        for fault in (None,True,'100000'):
            value=deepcopy(valid);value['cleanup']['capturedEpochMs']=fault
            with self.subTest(fault=fault),self.assertRaises(ValueError):body(value)
        for edit in (dict(lifecycle=dict(backgrounds=0,activations=1,launches=0)),dict(state=dict(animation='Waving'))):
            value=deepcopy(valid);value['cleanup'].update(edit)
            with self.assertRaises(ValueError):body(value)
    def test_emote_avatar_and_create_share_the_closed_retirement_contract_without_feature_projections(self):
        for area in ('emotes','avatar-people','create'):
            self.attach(area)
            with self.subTest(area=area),self.lock.held():self.assertEqual(1,self.owner().publish(self.original()))
            summary=self.adapter.request('/runs/'+self.run+'/retirements')['entries'][0]['cleanup']
            self.assertNotIn('state',summary);self.assertNotIn('artifacts',summary)
    def primary_reader(self,admission=None,*,client=None):
        primary=dict(BINDING,sessionId='independent-primary-session',targetFingerprint='b'*64,processIdentity='31')
        self.primary_phase=PhaseFixtureReader(client or self.adapter,self.run,self.area,epoch_ms=lambda:self.now,monotonic=lambda:10.1);self.primary_phase.status()
        original=dict(earlierActualAdmissionVersion=1,runId=self.run,phaseInstance=self.phase.previous['instance'],binding=deepcopy(BINDING))
        def admitted(value):
            need(value==original);return {key:value[key] for key in ('runId','phaseInstance','binding')}
        return PhaseRetirementReader(PrivateFeatureState(self.root/('retirement-primary-reader-'+self.run+'.json')),primary,self.primary_phase,
            lambda:True,original if admission is None else admission,admitted,epoch_ms=lambda:self.now,monotonic=lambda:10.1)
    def test_primary_reads_exact_committed_receipt_bound_to_earlier_actual_actor_admission(self):
        with self.lock.held():self.owner().publish(self.original())
        reader=self.primary_reader();record=reader.read()
        self.assertEqual(record['entry'],self.server.phase_retirements.snapshot(self.run)['entries'][0])
        self.assertEqual([],record['entry']['cleanup']['resources']);self.assertEqual(1,len(reader.state['records']))
        self.assertNotIn('sessionId',record['entry']['binding'])
    def test_primary_refuses_caller_supplied_replacement_actor_binding_even_with_same_candidate(self):
        with self.lock.held():self.owner().publish(self.original())
        reader=self.primary_reader();wrong=deepcopy(reader.admitted_original);wrong['binding']['sessionId']='replacement-actor-session'
        with self.assertRaises((ValueError,RuntimeError)):self.primary_reader(wrong)
        reader.actor['targetFingerprint']='e'*64
        with self.assertRaises((ValueError,RuntimeError)):reader.read()
    def test_primary_rejects_stale_committed_cleanup_and_changed_source_phase(self):
        with self.lock.held():self.owner().publish(self.original())
        reader=self.primary_reader();self.now=102000.
        with self.assertRaises((ValueError,RuntimeError)):reader.read()
        self.now=100100.;reader=self.primary_reader();self.server.journal.activate(self.run,uuid.uuid4().hex,'cleanup')
        with self.assertRaises((ValueError,RuntimeError)):reader.read()


if __name__=='__main__':unittest.main()
