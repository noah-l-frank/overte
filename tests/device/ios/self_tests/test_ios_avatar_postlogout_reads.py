"""Composed real native/account/model owners with explicit native producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.witness import Client
from ios.adapters.avatar_account_reads import IOSAvatarAccountReads
from ios.adapters.avatar_postlogout_reads import IOSAvatarPostLogoutReads
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_state import IOSAvatarState
from ios.self_tests.test_ios_avatar_input_owner import BINDING
from ios.self_tests.test_ios_avatar_sources import SourcesFixture
from ios.self_tests.test_ios_avatar_state_v3 import packet3
from self_tests.test_native_account_observation import account,event


class AvatarPostLogoutReadsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.artifacts=self.root/'originals';self.artifacts.mkdir(mode=0o700);self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.f=SourcesFixture();self.child='e'*32;self.ticket='f'*32;self.model_sequence=1;self.logged_out=False;self.logout_epoch=None
        self.calls=[];self.lost_model=False;self.model_value=None;self.scale=1.
        self.account_store=PrivateFeatureState(self.root/'ios-avatar-actor-primary-account-reads.json')
        self.store=PrivateFeatureState(self.root/'ios-avatar-actor-primary-postlogout.json')
        held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        before=self.accounts();row=before.read();self.logout_before=before.packet(row)
        self.baseline=packet3();self.baseline.update(runId=self.f.run)
        for field in ('clockBefore','clockAfter'):self.baseline[field]=dict(epochMs=self.f.now(),monotonicMs=round(self.f.clock*1000))
        self.f.tick();self.logged_out=True;self.logout_epoch=self.f.now()

    def owned(self,query):
        for store in (self.account_store,self.store):
            value=store.read()
            if value is None:continue
            p=unpack(value['payload'])[0]['pending']
            if p is None:continue
            if 'parts' in p:
                p=p['parts'];queries=[p.get('modelQuery')]+[row['query'] for row in p.get('clocks',[])]
            else:queries=[p['query']]+[row['query'] for row in p['clocks']]
            if query in queries:return
        raise AssertionError('Every actual native, model and native-clock query must be durably owned before transport')

    def native_parts(self):
        source=self.f.native();send=source.send
        def product(query):
            self.owned(query);self.calls.append(deepcopy(query));send(query);value=account()
            value['observation'].update(capturedEpochMs=self.f.now(),endpointSha256=hashlib.sha256(b'https://controlled.invalid').hexdigest())
            if self.logged_out:
                value['observation'].update(credentialGeneration=2,eventSequence=1,events=[event(kind='logout-complete',epoch=self.logout_epoch,generation=2)])
            else:
                value.update(loggedIn=True,principalSha256=hashlib.sha256(('e2e-'+self.child).encode()).hexdigest())
                value['observation'].update(tokenPresent=True,tokenValid=True,refreshPresent=True)
            self.f.core.sample['account']=value
        clock=NativeFeatureObservation(product,source.original,lambda:int(self.f.host()),lambda:True,42,ios=True,
            monotonic=lambda:self.f.clock,sleep=self.f.sleep)
        reader=NativeFeatureObservation(product,source.original,lambda:clock.read(clock.sequence)['capturedEpochMs'],lambda:True,42,
            ios=True,native_clock_bound=True,monotonic=lambda:self.f.clock,sleep=self.f.sleep)
        return reader,clock

    def accounts(self):
        reader,clock=self.native_parts()
        return IOSAvatarAccountReads(self.account_store,self.artifacts,BINDING,self.f.run,'actor','primary',self.lock,lambda:True,reader,
            clock_source=clock,epoch_ms=self.f.host,monotonic=lambda:self.f.clock)

    def model(self,clock=None):
        if clock is None:_native,clock=self.native_parts()
        def send(query):
            self.owned(query);self.calls.append(deepcopy(query));self.f.tick();self.model_sequence+=1;value=packet3()
            value.update(requestId=query['commandId'],runId=self.f.run,sequence=self.model_sequence)
            value['source'].update(sessionPresent=False,sessionId='00000000-0000-0000-0000-000000000000')
            value['source'].update(targetScale=self.scale,modelScale=self.scale)
            value['clockBefore']=dict(epochMs=self.f.now(),monotonicMs=round(self.f.clock*1000));self.f.tick()
            value['clockAfter']=dict(epochMs=self.f.now(),monotonicMs=round(self.f.clock*1000));self.model_value=value
            if self.lost_model:raise OSError('Synthetic lost model query return after actual source snapshot')
        reader=IOSAvatarState(send,lambda:json.dumps(self.model_value),lambda:clock.read(clock.sequence)['capturedEpochMs'],lambda:True,42,
            monotonic=lambda:self.f.clock,sleep=self.f.sleep)
        return reader,clock

    def owner(self,kind=IOSAvatarPostLogoutReads):
        return kind(self.store,self.artifacts,BINDING,self.f.run,'actor','primary',self.lock,lambda:True,self.accounts,self.model,
            child_run=self.child,fixture_url='https://controlled.invalid/feature-fixture/v1/runs/'+self.child+'/',ticket=self.ticket,
            baseline=self.baseline,logout_before=self.logout_before,epoch_ms=self.f.host,monotonic=lambda:self.f.clock)

    def archive(self,owner):return IOSAvatarPostLogoutReads.archive(owner.previous,self.store,self.artifacts,BINDING,self.f.run,'actor','primary',self.lock,
        child_run=self.child,fixture_url='https://controlled.invalid/feature-fixture/v1/runs/'+self.child+'/',ticket=self.ticket,
        baseline=self.baseline,logout_before=self.logout_before)

    def test_composed_account_model_account_capture_keeps_original_uuid_and_historical_proof_without_transport(self):
        owner=self.owner();row=owner.capture();proof=owner.proof(row);self.assertFalse(proof['sessionPresent'])
        before=deepcopy(self.calls);history=self.archive(owner);self.assertEqual(proof,history.proof(history.state['rows'][0]))
        self.assertEqual(before,self.calls)
        for operation in (history.capture,history.recover,history.save):
            with self.assertRaises(NativeUIError):operation()
        self.assertEqual(before,self.calls);self.assertEqual(0o600,owner.originals.path(row['original']).stat().st_mode&0o777)

    def test_lost_model_query_keeps_exact_nonce_and_uses_distinct_later_read_without_resend(self):
        owner=self.owner();self.lost_model=True
        with self.assertRaises(NativeUIError):owner.capture()
        original=deepcopy(owner.state['pending']);calls=deepcopy(self.calls);self.lost_model=False;again=self.owner();old=again.recover()
        self.assertEqual('abandoned',old['status']);self.assertEqual(calls,self.calls)
        row=again.capture();self.assertNotEqual(original['parts']['modelQuery'],again.row_parts(row)['modelQuery'])
        self.assertEqual(1,sum(query==original['parts']['modelQuery'] for query in self.calls))

    def test_lost_saved_record_return_is_adopted_without_query_or_rewriting_any_original(self):
        owner=self.owner();storage=owner.originals.intent
        def lost(kind,value):
            storage(kind,value)
            if value['phase']=='saved':raise OSError('Lost saved postlogout original return')
        owner.originals.intent=lost
        with self.assertRaises(OSError):owner.capture()
        calls=deepcopy(self.calls);again=self.owner();row=again.recover();self.assertEqual('observed',row['status']);again.proof(row)
        self.assertEqual(calls,self.calls)

    def test_slow_final_save_cannot_retime_or_freshly_return_the_saved_original(self):
        owner=self.owner();write=self.store.write
        def slow(value,previous):
            write(value,previous);state=unpack(value['payload'])[0]
            if state['rows'] and state['pending'] is None:self.f.clock+=1.501
        with patch.object(self.store,'write',side_effect=slow),self.assertRaises(NativeUIError):owner.capture()
        calls=deepcopy(self.calls);again=self.owner();row=again.state['rows'][0];again.proof(row);self.assertEqual(calls,self.calls)

    def test_a_real_unrestored_property_snapshot_stays_retained_before_distinct_later_passive_read(self):
        self.scale=2.;owner=self.owner()
        with self.assertRaises(NativeUIError):owner.capture()
        row=deepcopy(owner.state['rows'][0]);path=owner.originals.path(row['original']);raw=path.read_bytes();self.assertEqual(2.,owner.record(row)['model']['source']['modelScale'])
        self.scale=1.;again=self.owner();current=again.capture();self.assertEqual(1.,again.proof(current)['source']['modelScale'])
        with self.assertRaises(NativeUIError):again.proof(again.state['rows'][0])
        self.assertEqual(raw,path.read_bytes());self.assertNotEqual(again.row_parts(row)['modelQuery'],again.row_parts(current)['modelQuery'])

    def test_partial_record_writer_keeps_its_inode_and_abandons_before_distinct_queries(self):
        owner=self.owner();storage=owner.originals.intent
        def lost(kind,value):
            storage(kind,value)
            if value['phase']=='opened':raise OSError('Lost opened postlogout record writer')
        owner.originals.intent=lost
        with self.assertRaises(OSError):owner.capture()
        original=owner.state['pending']['original'];path=owner.originals.path(original);inode=path.stat().st_ino;calls=deepcopy(self.calls)
        again=self.owner();abandoned=again.recover();self.assertEqual('abandoned',abandoned['status'])
        self.assertEqual(calls,self.calls);self.assertEqual(inode,path.stat().st_ino)
        current=again.capture();again.proof(current);self.assertEqual(inode,path.stat().st_ino)
        with path.open('ab') as stream:stream.write(b'{')
        with self.assertRaises(NativeUIError):self.archive(again)

    def test_frozen_reads1_and_record1_stay_exact_after_private_parts2_continuation(self):
        from ios.self_tests.avatar_postlogout_reads_v1_producer import LegacyAvatarPostLogoutReads1
        legacy=self.owner(LegacyAvatarPostLogoutReads1);first=legacy.capture();metadata=self.store.path.read_bytes()
        path=legacy.originals.path(first['original']);original=path.read_bytes()
        proof=self.archive(legacy).proof(first);self.assertEqual(metadata,self.store.path.read_bytes());self.assertEqual(original,path.read_bytes())
        current=self.owner();second=current.capture();self.assertEqual(2,current.previous['iosAvatarPostLogoutReadsVersion'])
        self.assertEqual(proof,current.proof(first));self.assertFalse(current.proof(second)['sessionPresent']);self.assertEqual(original,path.read_bytes())

    def test_wrong_factory_subject_cannot_send_a_native_or_model_query(self):
        owner=self.owner();calls=deepcopy(self.calls);factory=owner.accounts_factory
        def foreign():
            result=factory();result.subject='actor';return result
        owner.accounts_factory=foreign
        with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(calls,self.calls)

    def test_historical_model_must_remain_inside_its_actual_native_clock_bracket(self):
        owner=self.owner();row=owner.capture();parts=deepcopy(owner.record(row))
        for edge in ('nativeRequestedEpochMs','nativeAfterEpochMs'):
            changed=deepcopy(parts);changed['modelAcquisition'][edge]=True
            with self.assertRaises(NativeUIError):owner.part(changed)
        changed=deepcopy(parts);changed['model']['clockAfter']['epochMs']=changed['modelAcquisition']['nativeAfterEpochMs']+1
        from adapters.native_clock_join import digest
        changed['modelAcquisition']['originalSha256']=digest(changed['model'])
        with self.assertRaises(NativeUIError):owner.part(changed)

    def test_actual_runtime_factory_composes_existing_bound_clock_and_model_sources(self):
        fixture=self
        class Runtime(IOSAvatarRuntime):
            def state_path(_self,_selector):return fixture.root/'session.json'
            def _sources(_self,_selector):
                _native,clock=fixture.native_parts()
                return dict(binding=BINDING,check=lambda:True,clock_source=clock,observer=SimpleNamespace(
                    bound_native_observer=lambda given:_native if given is clock else None,
                    avatar_state=lambda given:fixture.model(given)[0] if given is clock else None))
        runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True));client=Client('https://controlled.invalid/feature-fixture/v1','r'*64)
        owner=runtime._avatar_postlogout_reads('target',client,self.f.run,'actor','primary',self.artifacts,self.lock,child_run=self.child,ticket=self.ticket,
            baseline=self.baseline,logout_before=self.logout_before,epoch_ms=self.f.host,monotonic=lambda:self.f.clock)
        self.assertFalse(owner.proof(owner.capture())['sessionPresent'])


if __name__=='__main__':unittest.main()
