"""Live host transports with synthetic native originals and durable read recovery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters import create_state,create_work
from ios.adapters.create_sources import CreateSources,CreatePhaseChanged
from ios.adapters.emote_world import IOSEmoteWorld
from ios.self_tests.test_ios_create_state import RUN,EPOCH,packet,version2
from ios.self_tests.test_ios_create_files import BINDING,URL
from ios.self_tests.test_ios_create_peer import domain_pair
from ios.self_tests.test_ios_create_work import packet as work_packet,ROOT
from self_tests.test_native_feature_observation import Boundary as ClockBoundary
from self_tests.test_native_script_work import WorkBoundary
from adapters.native_script_work import NativeScriptWork


class OriginalSDK:
    def __init__(self):self.clock=1.;self.queries={};self.counts={};self.phase_sequence=0;self.ticket='1'*32;self.flip=False
    def tick(self):self.clock+=.001;return EPOCH+round(self.clock*1000)
    def epoch(self):return EPOCH+round(self.clock*1000)
    def sleep(self,seconds):self.clock+=seconds
    def send(self,name,query):self.queries[name]=deepcopy(query)
    def original(self,name):
        before=self.tick();self.counts[name]=self.counts.get(name,0)+1;query=self.queries[name]
        if name=='create':value=version2(packet());value['iosCreateStateVersion']=3
        elif name=='domain':
            state=version2(packet());value=domain_pair(state,state)[0]
            delta=before-value['clockAfter']['epochMs']
            def shift(item):
                if type(item) is dict:
                    for key,child in item.items():
                        if (key.endswith('EpochMs') or key=='epochMs') and type(child) is int and child>0:item[key]+=delta
                        else:shift(child)
                elif type(item) is list:
                    for child in item:shift(child)
            shift(value)
        else:value=work_packet()
        value.update(requestId=query['commandId'],sequence=self.counts[name],clockBefore=dict(epochMs=before,monotonicMs=round(self.clock*1000)))
        value['clockAfter']=dict(epochMs=self.tick(),monotonicMs=round(self.clock*1000))
        return json.dumps(value)
    def phase(self,path,**kwargs):
        self.phase_sequence+=1
        if self.flip and self.phase_sequence%2==0:self.ticket='2'*32
        rows=[dict(sequence=1,ticket='1'*32,activatedEpochMs=EPOCH,stimulus=dict(verb='baseline',inputs={}))]
        if self.ticket=='2'*32:rows.append(dict(sequence=2,ticket=self.ticket,activatedEpochMs=self.epoch(),stimulus=dict(verb='cleanup',inputs={})))
        return dict(fixturePhaseVersion=1,instance='a'*32,sequence=self.phase_sequence,requestId=kwargs['phase_nonce'],runId=RUN,area='create',
            capturedEpochMs=self.tick(),active=True,createdEpochMs=EPOCH-1,retiredEpochMs=None,activations=rows)


class CreateSourcesTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.store=PrivateFeatureState(self.root/'ios-create-primary-sources.json');self.sdk=OriginalSDK();b=self.sdk
        self.native_seam=ClockBoundary();self.worker_seam=WorkBoundary()
    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except Exception as caught:error=caught
        if error is not None:raise error
    def owner(self,historical=False):
        b=self.sdk;clock=self.native_seam
        def stamp(value):value.update(processId=42,requestedEpochMs=b.tick(),capturedEpochMs=b.epoch(),animation={},animationFence={})
        clock.mutate=stamp
        native=NativeFeatureObservation(clock.send,clock.original,b.tick,lambda:True,42,ios=True,monotonic=lambda:b.clock,sleep=b.sleep)
        native.native_clock_bound=True
        readers=dict(native=native)
        for name,cls in (('create',create_state.IOSCreateState),('domain',IOSEmoteWorld),('work',create_work.IOSCreateWork)):
            readers[name]=cls(lambda query,key=name:b.send(key,query),lambda key=name:b.original(key),b.tick,lambda:True,42,monotonic=lambda:b.clock,sleep=b.sleep)
        seam=self.worker_seam;role=work_packet()['source']['roles'][0];seam.member=deepcopy(role['manager']);seam.code=deepcopy(role['code'])
        def send(query):seam.epoch=b.tick();seam.send(query);seam.value['processId']=42
        readers['worker']=NativeScriptWork(send,seam.original,b.tick,lambda:True,42,ios=True,monotonic=lambda:b.clock,sleep=b.sleep)
        client=object.__new__(Client);client.url=URL.split('/runs/')[0];client.request=b.phase
        phase=PhaseFixtureReader(client,RUN,'create',epoch_ms=b.epoch,monotonic=lambda:b.clock)
        return CreateSources(self.store,self.lock,BINDING,RUN,'primary',ROOT,lambda:True,phase=phase,readers=readers,historical=historical,
            epoch_ms=b.epoch,monotonic=lambda:b.clock)
    def test_actual_typed_sources_and_worker_bracket_are_preserved_across_historical_reconstruction(self):
        with self.held():
            owner=self.owner();frame=owner.capture('baseline');self.assertEqual('1'*32,frame['ticket'])
            self.assertEqual(42,frame['originals']['worker']['processId']);self.assertEqual(1,len(owner.frames))
            historical=self.owner(True);self.assertEqual(frame,historical.frames[0]);self.assertEqual(self.store.read(),historical.previous)
            self.assertEqual({'create':2,'domain':1,'work':1},self.sdk.counts)
            fresh=self.owner();second=fresh.capture('current');self.assertEqual(2,second['index'])
            self.assertGreater(second['originals']['createBefore']['sequence'],frame['originals']['createAfter']['sequence'])
    def test_interrupted_read_keeps_old_packets_without_retiming_and_new_read_is_independent(self):
        with self.held():
            owner=self.owner();original=owner.readers['domain'].read
            with patch.object(owner.readers['domain'],'read',side_effect=NativeUIError('Lost original read')):
                with self.assertRaises(NativeUIError):owner.capture('interrupted')
            old=deepcopy(owner.state['pending']);self.assertIn('createBefore',old['originals']);self.assertEqual([],owner.frames)
            owner.readers['domain'].read=original;frame=owner.capture('new-read')
            self.assertEqual(old,owner.state['interrupted'][0]);self.assertGreater(frame['originals']['createBefore']['sequence'],old['originals']['createBefore']['sequence'])
            self.assertNotEqual(old['start']['nativeBefore']['requestId'],frame['clockJoin']['nativeBefore']['requestId'])
    def test_changed_phase_is_retained_but_cannot_be_published_as_the_old_ticket(self):
        with self.held():
            self.sdk.flip=True;owner=self.owner()
            with self.assertRaises(CreatePhaseChanged):owner.capture('racing')
            self.assertEqual(1,len(owner.frames));self.assertEqual('1'*32,owner.frames[0]['ticket']);self.assertEqual('2'*32,owner.frames[0]['phaseAfter']['activations'][-1]['ticket'])
    def test_wrong_candidate_record_hash_source_clock_and_native_domain_are_rejected(self):
        with self.held():
            owner=self.owner();frame=owner.capture('baseline')
            for fault in ('pid','domain','tree','order','retime','worker'):
                value=deepcopy(frame)
                if fault=='pid':value['originals']['createAfter']['processId']=43
                elif fault=='domain':value['originals']['domain']['source']['domain']['serverless']=True
                elif fault=='tree':value['originals']['domain']['source']['tree']['revisionBefore']+=1
                elif fault=='order':value['originals']['createAfter']['clockBefore']['epochMs']=EPOCH
                elif fault=='worker':value['originals']['worker']['source']['work']['signalCallbacks']=1
                else:value['clockJoin']['hostBeforeEpochMs']+=2000
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.validate_frame(value)
            altered=deepcopy(owner.previous);altered['binding']['artifactSha256']='0'*64
            with self.assertRaises(NativeUIError):owner.decode(altered)


if __name__=='__main__':unittest.main()
