"""Whole cleanup replay over real private files; native producers are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_controls import project
from ios.adapters.emote_retirement import IOSEmoteRetirement
from ios.adapters.emote_sources import IOSEmoteSources
from ios.self_tests import test_ios_emote_marker_scope as marker_fixture
from ios.self_tests.test_ios_emote_marker_owner import Domain
from ios.self_tests.marker_entities_fixture import EntityDomain
from ios.self_tests.emote_pointer_fixture import PointerDomain
from ios.adapters.emote_retirement_scope import refresh
from ios.self_tests.test_ios_emote_sources import BINDING,RUN,phase
from self_tests.test_emote_rig_measurements import RigPackets


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.fixture=marker_fixture.MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.root,self.lock=self.fixture.root,self.fixture.lock;self.scope=self.fixture.owner();self.domain=Domain(self.scope)
        self.qt=PointerDomain(self,self.scope,self.domain);self.pointers=self.qt.owner();self.pointers.capture()
        self.entity_fixture=EntityDomain(self,self.scope,self.domain);self.entities=self.entity_fixture.owner();self.entities.capture()
        self.scope.cleanup();refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep,pointers=self.pointers)
        self.entities.capture();self.sources=IOSEmoteSources(PrivateFeatureState(self.root/'ios-emote-primary-sources.json'),
            self.root,BINDING,RUN,'primary',self.lock,lambda:True,None,historical=True)
        self.sources.historical=False;self.sources.save();self.model=RigPackets()
        self.original=self.make_original()
        self.store=PrivateFeatureState(self.root/'retirement.json')
    def make_original(self):
        d=self.domain;before=self.scope.native.read(self.scope.native.sequence)
        group=self.model.group(self.scope.native.read(before['sequence']));widgets=d.widgets();world=d.world(RUN)
        after=self.scope.native.read(group['native']['sequence']);host=self.scope.epoch_ms();mono=d.time
        original_sources=dict(group,widgets=widgets,world=world)
        join=dict(clockJoinVersion=1,hostBeforeEpochMs=host-100,hostAfterEpochMs=host,hostBeforeMonotonic=mono-.1,hostAfterMonotonic=mono,
            nativeBefore=before,nativeAfter=after,originalsSha256=digest(original_sources),sourceTimes=[
                dict(source=name,field=field,epochMs=p[field]) for name,p in original_sources.items()
                for field in ('capturedEpochMs','sampleEpochMs') if field in p])
        status=phase(1,host-100);status['activations'][-1]['stimulus']=dict(verb='cleanup',inputs={})
        final=phase(2,host);final['activations']=deepcopy(status['activations'])
        frame=dict(group=group,widgets=widgets,ui=project(widgets),world=world,clockJoin=join,phaseBefore=deepcopy(status),phaseAfter=final)
        self.sources.validate_frame(frame)
        self.sources.state.update(phase='reading',pending=dict(original=None,manifest=None,partial={}));self.sources.save()
        item=self.sources.originals.write(1,frame);self.sources.state['manifests']=self.sources.originals.append([],item)
        self.sources.frames.append(frame);self.sources.state.update(phase='ready',revision=1,pending=None);self.sources.save()
        ref=dict(index=1,sha256=digest(frame))
        observation=dict(iosEmoteObservationOriginalVersion=1,runId=RUN,role='primary',binding=BINDING,primaryBinding=BINDING,
            sequence=1,ticket='4'*32,source=ref,sourceRecovery=None,peerRecovery=None,
            proof=dict(kind='idle',baseline=ref,before=None,played=None,inputBarrier=None),peerBefore=None,peerAfter=None,
            marker=None,imageBefore=None,image=None,acquisition={key:join[key] for key in
                ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')})
        self.pointers.capture()
        return dict(observation=observation,sources=self.sources.store.read(),peers=None,scope=self.scope.store.read(),
            fileReceipts=None,entities=self.entities.store.read(),pointers=self.pointers.store.read(),sampleOwners=None,inputOwners=dict(cleanup=None,actions=None,background=None))
    def owner(self):
        return IOSEmoteRetirement(self.store,self.root,BINDING,BINDING,RUN,'primary',self.scope.fixture_url,'3'*32,
            self.lock,self.lock,dict(source='world-render-target'),dict(sources=self.sources.store.path,peers=None,files=self.root/'files.json',entities=self.entities.store.path,pointers=self.pointers.store.path),lambda:True)
    def test_original_cleanup_replays_after_live_metadata_removed_without_native_reads(self):
        owner=self.owner();ref=owner.retain(self.original);calls=len(self.domain.history)
        self.sources.store.discard(self.sources.store.read());self.scope.store.discard(self.scope.store.read())
        replay=self.owner().derive(ref);self.assertEqual([],replay['public']['resources']);self.assertEqual([],replay['public']['artifacts'])
        self.assertGreaterEqual(replay['retirement']['quiet']['hostBeforeLastMonotonic']-replay['retirement']['quiet']['hostAfterFirstMonotonic'],3)
        self.assertEqual(calls,len(self.domain.history))
    def test_lost_original_file_return_adopts_exact_candidate_without_any_new_read(self):
        owner=self.owner();original_write=PrivateFeatureState.write;lost=[]
        def write(store,value,previous):
            original_write(store,value,previous)
            if store.path==owner.record_store(1).path and not lost:lost.append(True);raise OSError('Lost original-file return')
        with patch.object(PrivateFeatureState,'write',write),self.assertRaises(OSError):owner.retain(self.original)
        calls=len(self.domain.history);rebuilt=self.owner();ref=rebuilt.resolve()
        self.assertEqual(1,ref['index']);self.assertEqual(calls,len(self.domain.history));self.assertIsNone(rebuilt.state['pending'])
    def test_invalid_native_closure_is_preserved_then_fresh_distinct_original_can_complete(self):
        corrupt=deepcopy(self.original);corrupt['inputOwners']['actions']={}
        owner=self.owner()
        with self.assertRaises(NativeUIError):owner.retain(corrupt)
        rebuilt=self.owner();self.assertTrue(rebuilt.abandon());self.assertEqual(1,len(rebuilt.state['abandoned']))
        ref=rebuilt.retain(self.original);self.assertEqual(2,ref['index']);self.assertEqual(corrupt,rebuilt.original(rebuilt.state['abandoned'][0]))
        self.assertEqual([ref],self.owner().state['records'])
    def test_lost_metadata_commit_return_rebuilds_without_duplicate_original(self):
        owner=self.owner();write=PrivateFeatureState.write;seen=[]
        def lost(store,value,previous):
            write(store,value,previous)
            if store.path==self.store.path and len(seen)==1:
                seen.append(True);raise OSError('Lost completed metadata return')
            if store.path==self.store.path:seen.append(True)
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(OSError):owner.retain(self.original)
        rebuilt=self.owner();self.assertIsNone(rebuilt.resolve());self.assertEqual(1,len(rebuilt.state['records']))
        self.assertEqual(1,len(list(self.root.glob('emote-retirement-*'))))
    def test_fresh_retirement_quiet_extends_native_histories_without_normal_inputs(self):
        from ios.adapters.emote_retirement_scope import refresh
        before=len(self.domain.history);operations=deepcopy(self.scope.state['operations'])
        old=list(self.scope.state['quiet']);refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep)
        self.assertGreater(len(self.domain.history),before);self.assertGreater(self.scope.state['quiet'][0],old[-1])
        self.assertEqual(operations,self.scope.state['operations']);self.assertEqual('released',self.scope.state['phase'])
        self.assertTrue(self.scope.quiet_interval(self.scope.frames[self.scope.state['quiet'][0]-1],self.scope.frames[-1]))
    def test_interrupted_first_or_middle_refresh_reconstructs_the_released_original_scope(self):
        from ios.adapters.emote_retirement_scope import refresh
        for fail_at in (1,3):
            old=list(self.scope.state['quiet']);read=self.domain.web;count=[0]
            def interrupted(run,url):
                count[0]+=1
                if count[0]==fail_at:raise OSError('Lost passive refresh Web return')
                return read(run,url)
            self.scope.web.read=interrupted
            with self.subTest(fail_at=fail_at),self.assertRaises(OSError):refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep)
            rebuilt=self.fixture.owner();self.assertEqual('released',rebuilt.state['phase']);self.assertEqual(old,rebuilt.state['quiet'])
            self.assertIsNotNone(rebuilt.state['pending'])
            self.scope.web.read=read
            refresh(self.scope,clock=lambda:self.domain.time,sleep=self.domain.sleep)
            self.assertIsNone(self.scope.state['pending']);self.assertEqual('released',self.fixture.owner().state['phase'])

    def test_a_later_unadmitted_scope_frame_cannot_borrow_earlier_quiet(self):
        self.scope.capture('later-unadmitted-original');original=deepcopy(self.original);original['scope']=self.scope.store.read()
        with self.assertRaises(NativeUIError):self.owner().retain(original)

    def test_rewritten_or_short_quiet_does_not_become_a_native_retirement_fact(self):
        original=deepcopy(self.original);value=self.scope.store.read();from adapters.script_feature.history import pack,unpack
        state=unpack(value['payload'])[0];state['quiet']=state['quiet'][-2:];value['payload']=pack([state]);original['scope']=value
        with self.assertRaises(NativeUIError):self.owner().retain(original)

    def test_later_actual_contact_or_new_input_cannot_borrow_completed_resource_quiet(self):
        for ended in (False,True):
            self.qt.boundary.touch('touch-begin')
            if ended:self.qt.boundary.touch('touch-end')
            self.pointers.capture();original=deepcopy(self.original);original['pointers']=self.pointers.store.read()
            owner=self.owner()
            with self.subTest(ended=ended),self.assertRaises(NativeUIError):owner.retain(original)
            owner.abandon()
            if not ended:self.qt.boundary.touch('touch-end')

    def test_pointer_snapshot_before_the_actual_public_observation_cannot_qualify_final_retirement(self):
        from adapters.script_feature.history import unpack,pack
        original=deepcopy(self.original);value=deepcopy(original['pointers']);state=unpack(value['payload'])[0]
        state['records'].pop();value['payload']=pack([state]);original['pointers']=value
        with self.assertRaises(NativeUIError):self.owner().retain(original)

    def test_native_pointer_owner_is_mandatory_even_when_input_ack_owners_are_empty(self):
        original=deepcopy(self.original);original['pointers']=None
        with self.assertRaises((NativeUIError,TypeError)):self.owner().retain(original)

    def test_hash_or_native_original_rewrite_cannot_borrow_a_cleanup_ack(self):
        owner=self.owner();ref=owner.retain(self.original)
        with self.assertRaises(NativeUIError):owner.derive(dict(ref,sha256='f'*64))
        old=owner.record_store(1).read();changed=deepcopy(old);changed['binding']['processIdentity']='32'
        owner.record_store(1).write(changed,old)
        with self.assertRaises(NativeUIError):self.owner()


if __name__=='__main__':unittest.main()
