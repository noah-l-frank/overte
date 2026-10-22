"""Real phase/sample HTTP/private journals; product original decoder is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_witness_publisher import PhaseWitnessPublisher, PublicationPending
from adapters.script_feature.history import pack, unpack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from self_tests.test_completed_frame_lease import BINDING


class PhaseWitnessPublisherTests(unittest.TestCase):
    def setUp(self):
        self.server=make_server('r'*64,'a'*64)
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01),daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.url='http://127.0.0.1:'+str(self.server.server_address[1])+'/feature-fixture/v1'
        self.reader=Client(self.url,'r'*64);self.actor=Client(self.url,'a'*64)
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.known={};self.okay=True;self.validations=0
        self.area='emotes';self.attach(self.area)
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.assertFalse(self.thread.is_alive())
    def attach(self,area):
        self.area=area;self.run=self.server.journal.register(area);self.ticket=uuid.uuid4().hex
        self.server.journal.activate(self.run,self.ticket)
        self.phase=PhaseFixtureReader(self.actor,self.run,area);self.phase.status()
    def validate_original(self,value):
        self.validations+=1;need(digest(value) in self.known);return deepcopy(self.known[digest(value)])
    def original(self,sequence=1):
        started=time.monotonic();epoch=time.time()*1000
        value=dict(modeledOriginalVersion=1,area=self.area,runId=self.run,nonce=uuid.uuid4().hex)
        public=dict(schemaVersion=1,contractVersion=16,runId=self.run,sequence=sequence,capturedEpochMs=epoch,
            state=deepcopy(SCENARIOS[self.area]['baseline']),artifacts=[],resources=[],lifecycle=dict(backgrounds=0,activations=0,launches=1))
        self.known[digest(value)]=dict(ticket=self.ticket,public=public,acquisition=dict(hostBeforeEpochMs=epoch,
            hostAfterEpochMs=time.time()*1000,hostBeforeMonotonic=started,hostAfterMonotonic=time.monotonic()))
        return value
    def owner(self,binding=BINDING):
        return PhaseWitnessPublisher(PrivateFeatureState(self.root/('phase-publication-'+self.area+'-'+self.run+'-actor.json')),
            binding,self.phase,self.lock,lambda:self.okay,self.validate_original)
    def posts(self,mode):
        real=self.actor.request;calls=[]
        def request(path,value=None,*args,**kwargs):
            if path.endswith('/samples'):
                calls.append(deepcopy(value))
                if mode=='lost-before':raise OSError('Synthetic lost uncommitted delivery')
                if mode=='ack':return {}
                result=real(path,value,*args,**kwargs)
                if mode=='lost-after':raise OSError('Synthetic lost committed return')
                return result
            return real(path,value,*args,**kwargs)
        return calls,request
    def pending(self,mode='lost-before'):
        owner=self.owner();original=self.original();calls,request=self.posts(mode)
        with patch.object(self.actor,'request',side_effect=request),self.assertRaises((OSError,PublicationPending)):
            owner.publish(original)
        return owner,original,calls

    def test_real_original_journal_receipt_completes_and_duplicate_does_not_publish_again(self):
        with self.lock.held():
            owner=self.owner();original=self.original();calls,request=self.posts('normal')
            with patch.object(self.actor,'request',side_effect=request):
                self.assertEqual(1,owner.publish(original));self.assertEqual(1,self.owner().publish(original))
            self.assertEqual(1,len(calls));row=owner.load(owner.state['records'][0])
            self.assertEqual('published',row['mode']);self.assertEqual(calls[0],row['intent']['body'])
            self.assertEqual(self.server.journal.snapshot(self.run)['entries'][0],row['entry'])

    def test_lost_committed_post_resolves_without_any_post_redelivery(self):
        with self.lock.held():
            owner,original,calls=self.pending('lost-after');pending=deepcopy(owner.state['pending'])
            recovered=self.owner();again,request=self.posts('normal')
            with patch.object(self.actor,'request',side_effect=request):self.assertTrue(recovered.resolve())
            self.assertEqual([],again);self.assertEqual(1,len(calls))
            self.assertEqual(pending,recovered.load(recovered.state['records'][0])['intent'])

    def test_uncommitted_or_ack_only_post_stays_owned_and_blocks_old_and_new_samples(self):
        for mode in ('lost-before','ack'):
            with self.subTest(mode=mode):
                self.doCleanups();self.setUp()
                with self.lock.held():
                    owner,original,calls=self.pending(mode);recovered=self.owner();again,request=self.posts('normal')
                    with patch.object(self.actor,'request',side_effect=request):
                        with self.assertRaises(PublicationPending):recovered.publish(original)
                        with self.assertRaises(PublicationPending):recovered.publish(self.original(2))
                    self.assertEqual([],again);self.assertEqual(1,len(calls));self.assertIsNotNone(recovered.state['pending'])

    def test_actual_later_phase_retires_responsibility_without_claiming_publication(self):
        with self.lock.held():
            owner,original,calls=self.pending();pending=deepcopy(owner.state['pending'])
            self.server.journal.activate(self.run,uuid.uuid4().hex,'cleanup',{})
            recovered=self.owner();recovered.resolve();row=recovered.load(recovered.state['records'][0])
            self.assertEqual('phase-retired',row['mode']);self.assertIsNone(row['entry']);self.assertEqual(pending,row['intent'])
            self.assertEqual([],self.server.journal.snapshot(self.run)['entries'])

    def test_actual_closed_run_retires_unknown_outcome_without_reading_removed_sample_journal(self):
        for mode in ('lost-before','lost-after'):
            with self.subTest(mode=mode):
                self.doCleanups();self.setUp()
                with self.lock.held():
                    owner,original,calls=self.pending(mode);self.reader.request('/runs/'+self.run,method='DELETE')
                    real=self.actor.request;paths=[]
                    def only_phase(path,*args,**kwargs):
                        paths.append(path);self.assertTrue(path.endswith('/phase'));return real(path,*args,**kwargs)
                    recovered=self.owner()
                    with patch.object(self.actor,'request',side_effect=only_phase):recovered.resolve()
                    row=recovered.load(recovered.state['records'][0]);self.assertEqual('run-retired',row['mode'])
                    self.assertIsNone(row['journal']);self.assertIsNone(row['entry']);self.assertEqual(2,len(paths))
                    self.assertEqual(1,len(calls));self.assertNotIn('cleanup',row)

    def test_lost_stored_receipt_adopts_without_another_http_read_or_post(self):
        with self.lock.held():
            owner=self.owner();original=self.original();write=owner.store_record
            def lost(row):write(row);raise OSError('Synthetic lost retained receipt')
            with patch.object(owner,'store_record',side_effect=lost),self.assertRaises(OSError):owner.publish(original)
            recovered=self.owner()
            with patch.object(self.actor,'request',side_effect=AssertionError('No second HTTP read')):self.assertTrue(recovered.resolve())
            self.assertEqual('published',recovered.load(recovered.state['records'][0])['mode'])

    def test_changed_original_body_candidate_or_phase_instance_cannot_adopt_intent(self):
        with self.lock.held():
            owner,original,calls=self.pending();raw=owner.store.read();state=unpack(raw['payload'])[0]
            state['pending']['body']['facts']['animation']='Waving'
            owner.store.write(dict(raw,payload=pack([state])),raw)
            with self.assertRaises(NativeUIError):self.owner()
            owner.store.write(raw,owner.store.read())
            with self.assertRaises(NativeUIError):self.owner(BINDING|dict(artifactSha256='f'*64))
            self.okay=False
            with self.assertRaises(NativeUIError):self.owner()
            self.okay=True;self.phase.previous['instance']='f'*32
            with self.assertRaises(NativeUIError):self.owner()

    def test_stale_original_cannot_be_retimed_into_a_new_publication(self):
        with self.lock.held():
            owner=self.owner();original=self.original();derived=self.known[digest(original)]
            for key in ('hostBeforeEpochMs','hostAfterEpochMs'):derived['acquisition'][key]-=2000
            for key in ('hostBeforeMonotonic','hostAfterMonotonic'):derived['acquisition'][key]-=2
            derived['public']['capturedEpochMs']-=2000;calls,request=self.posts('normal')
            with patch.object(self.actor,'request',side_effect=request),self.assertRaises(NativeUIError):owner.publish(original)
            self.assertEqual([],calls);self.assertEqual('planned',self.owner().state['pending']['phase'])

    def test_archive_keeps_original_times_after_owner_metadata_removal_without_live_authority(self):
        with self.lock.held():
            owner=self.owner();owner.publish(self.original());raw=deepcopy(owner.previous);state=deepcopy(owner.state)
            owner.store.discard(raw);self.okay=False
            with patch.object(self.actor,'request',side_effect=AssertionError('No historical HTTP')):
                archived=PhaseWitnessPublisher.archive(raw,store=owner.store,binding=BINDING,run=self.run,area=self.area,
                    fixture_url=self.url,phase_instance=owner.instance,validate_original=self.validate_original)
            self.assertEqual(state,archived);self.assertIsNone(owner.store.read())

    def test_all_fourteen_areas_use_the_actual_shared_closed_projection(self):
        for area in SCENARIOS:
            with self.subTest(area=area),self.lock.held():
                self.attach(area);owner=self.owner();self.assertEqual(1,owner.publish(self.original()))
                row=owner.load(owner.state['records'][0]);self.assertEqual(area,row['journal']['area'])
                self.assertEqual(self.server.journal.snapshot(self.run)['entries'][0],row['entry'])

    def test_foreign_stale_or_changed_original_journal_cannot_resolve_an_issued_post(self):
        with self.lock.held():
            owner,original,calls=self.pending('lost-after');real=self.actor.request
            for fault in ('run','time','facts','sequence'):
                recovered=self.owner()
                def changed(path,*args,**kwargs):
                    value=real(path,*args,**kwargs)
                    if path=='/runs/'+self.run:
                        if fault=='run':value['runId']='f'*32
                        elif fault=='time':value['sampleEpochMs']-=10000
                        elif fault=='facts':value['entries'][0]['facts']['animation']='Waving'
                        else:value['entries'][0]['actorSequence']+=1
                    return value
                with self.subTest(fault=fault),patch.object(self.actor,'request',side_effect=changed),self.assertRaises(NativeUIError):
                    recovered.resolve()
                self.assertIsNotNone(recovered.state['pending']);self.assertEqual([],recovered.state['records'])

    def test_phase_crossing_during_receipt_read_does_not_create_a_stable_receipt(self):
        with self.lock.held():
            owner,original,calls=self.pending('lost-after');real=self.actor.request;recovered=self.owner()
            def crossed(path,*args,**kwargs):
                value=real(path,*args,**kwargs)
                if path=='/runs/'+self.run:self.server.journal.activate(self.run,uuid.uuid4().hex,'cleanup',{})
                return value
            with patch.object(self.actor,'request',side_effect=crossed),self.assertRaises(PublicationPending):recovered.resolve()
            self.assertIsNotNone(recovered.state['pending']);self.assertEqual([],recovered.state['records'])

    def test_original_frozen_epoch_cannot_hide_a_slow_monotonic_receipt_acquisition(self):
        with self.lock.held():
            owner,original,calls=self.pending('lost-after');recovered=self.owner();real=self.actor.request
            initial_epoch=time.time()*1000;initial_mono=time.monotonic();clock=[initial_mono]
            recovered.epoch_ms=lambda:initial_epoch;recovered.monotonic=lambda:clock[0];recovered.clock=initial_mono
            def slow(path,*args,**kwargs):
                value=real(path,*args,**kwargs)
                if path=='/runs/'+self.run:clock[0]+=1.6
                return value
            with patch.object(self.actor,'request',side_effect=slow),self.assertRaises(NativeUIError):recovered.resolve()
            self.assertIsNotNone(recovered.state['pending']);self.assertEqual([],recovered.state['records'])

    def test_failed_issue_write_sends_nothing_and_original_planned_intent_can_retire(self):
        with self.lock.held():
            owner=self.owner();original=self.original();save=owner.save;calls,request=self.posts('normal')
            def failed():
                if owner.state['pending'] is not None and owner.state['pending']['phase']=='issued':raise OSError('Synthetic issue write failure')
                return save()
            with patch.object(owner,'save',side_effect=failed),patch.object(self.actor,'request',side_effect=request),self.assertRaises(OSError):
                owner.publish(original)
            self.assertEqual([],calls);recovered=self.owner();self.assertEqual('planned',recovered.state['pending']['phase'])
            self.reader.request('/runs/'+self.run,method='DELETE');recovered.resolve()
            row=recovered.load(recovered.state['records'][0]);self.assertEqual('planned',row['intent']['phase'])
            self.assertEqual('run-retired',row['mode'])

    def test_slow_issued_journal_cannot_publish_expired_original_or_resend_after_reconstruction(self):
        with self.lock.held():
            owner=self.owner();original=self.original();save=owner.save
            epoch,mono=time.time()*1000,time.monotonic();delay=[0.]
            owner.epoch_ms=lambda:epoch+delay[0]*1000;owner.monotonic=lambda:mono+delay[0]
            def slow():
                result=save()
                if owner.state['pending'] is not None and owner.state['pending']['phase']=='issued':delay[0]+=1.6
                return result
            calls,request=self.posts('normal')
            with patch.object(owner,'save',side_effect=slow),patch.object(self.actor,'request',side_effect=request),self.assertRaises(NativeUIError):
                owner.publish(original)
            self.assertEqual([],calls);recovered=self.owner();self.assertEqual('issued',recovered.state['pending']['phase'])
            self.assertEqual(self.known[digest(original)]['public']['capturedEpochMs'],recovered.state['pending']['body']['capturedEpochMs'])
            with self.assertRaises(PublicationPending):recovered.publish(original)
            self.assertEqual([],self.server.journal.snapshot(self.run)['entries'])

    def test_replaced_record_bytes_or_external_owner_write_cannot_be_adopted(self):
        with self.lock.held():
            owner=self.owner();original=self.original();owner.publish(original);ref=owner.state['records'][0]
            record=owner.record_store(ref['ordinal']);raw=record.read();row=unpack(raw['payload'])[0]
            row['entry']['facts']['animation']='Waving';record.write(dict(raw,payload=pack([row])),raw)
            with self.assertRaises(NativeUIError):self.owner()
            record.write(raw,record.read());current=owner.store.read();state=unpack(current['payload'])[0]
            state['records']=[];owner.store.write(dict(current,payload=pack([state])),current)
            with self.assertRaises(NativeUIError):owner.publish(original)
            with self.assertRaises(NativeUIError):self.owner()

    def test_missing_owner_metadata_does_not_mean_an_existing_publication_never_happened(self):
        with self.lock.held():
            owner=self.owner();original=self.original();owner.publish(original);owner.store.discard(owner.previous)
            with patch.object(self.actor,'request',side_effect=AssertionError('No POST or journal query')):
                with self.assertRaises(NativeUIError):self.owner()
