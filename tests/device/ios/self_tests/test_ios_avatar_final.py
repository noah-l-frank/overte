"""Actual paired postlogout samplers/private originals with native producers.

Both SDK channels advance independently; only product/native HTTP boundaries
are modeled. No final validator, historical decoder or proof is replaced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_accounts import AvatarAccountScopes
from feature_journeys.avatar_social_provider import AvatarSocialProvider
from feature_journeys.avatar_social_http import account_authenticator
from feature_journeys.witness import Client
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_final import IOSAvatarFinal
from ios.adapters.avatar_account_reads import IOSAvatarAccountReads
from ios.adapters.avatar_postlogout_reads import IOSAvatarPostLogoutReads
from ios.adapters.avatar_postlogout_tail import IOSAvatarPostLogoutTail
from ios.adapters.avatar_pointers import IOSAvatarPointers
from ios.adapters import avatar_scripts,avatar_social_http,normal_input
from ios.self_tests import test_ios_avatar_postlogout_tail as tail_fixture
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary

RUN='a'*32
TICKET='f'*32
INSTANCE='b'*32


class AvatarFinalTests(unittest.TestCase):
    def setUp(self):
        self.clock=[5.];self.cases={};self.active=None
        account=AccountProvider(epoch_ms=self.host);social=AvatarSocialProvider(account_authenticator(account),epoch_ms=self.host)
        self.scopes=AvatarAccountScopes(account,social);self.scopes.provision(RUN);self.scopes.activate(RUN,TICKET)
        self.scopes.revoke(RUN)
        self.client=Client('https://controlled.invalid/feature-fixture/v1','r'*64)
        self.client.request=lambda _path:self.scopes.snapshot(RUN)
        self.authority=AvatarAuthorityReader(self.client,RUN,epoch_ms=self.host,monotonic=lambda:self.clock[0])
        self.inputs={};self.bindings={};self.locks={}
        for subject in ('primary','actor'):
            c=tail_fixture.AvatarPostLogoutTailTests();c.setUp();self.addCleanup(c.doCleanups);self.cases[subject]=c;f=c.f;shared=self.clock
            class Source(type(f.f)):
                @property
                def clock(_self):return shared[0]
                @clock.setter
                def clock(_self,value):shared[0]=value
            f.f.__class__=Source;f.f.run=RUN
            c.store=PrivateFeatureState(f.root/('ios-avatar-primary-'+subject+'-postlogout-tail.json'))
            child=self.scopes.snapshot(RUN)['accounts'][subject]['runId'];f.child=child
            self.bindings[subject]=dict(__import__('ios.self_tests.test_ios_avatar_input_owner',fromlist=['BINDING']).BINDING)
            self.bindings[subject].update(sessionId='actual-'+subject,targetFingerprint=('c' if subject=='primary' else 'd')*64)
            self.locks[subject]=f.lock
            # Emit a genuine prior logged-in native original for this actual
            # controlled child, then the producer performs its logout event.
            self.active=subject;f.logged_out=False
            prior=self.accounts(subject);row=prior.read();f.logout_before=prior.packet(row)
            f.logged_out=True;f.logout_epoch=f.f.now();f.baseline['runId']=RUN
            for field in ('clockBefore','clockAfter'):f.baseline[field]=dict(epochMs=f.f.now(),monotonicMs=round(self.clock[0]*1000))
            f.f.tick()
            c.baseline={name:f.f.reader(name,kind).read(RUN) for name,kind in dict(scripts=avatar_scripts.IOSAvatarScripts,http=avatar_social_http.IOSAvatarSocialHttp).items()}
            pointer=NativePointerBoundary();f.pointer=pointer
            def tick(f=f,pointer=pointer):f.f.tick();pointer.now=f.f.now();return pointer.now
            pointer.tick=tick;pointer.now=f.f.now()
            config=dict(root=str(f.artifacts),paths=dict(post=str(f.root/('ios-avatar-primary-'+subject+'-postlogout.json')),
                tail=str(c.store.path),pointers=str(f.root/'ios-avatar-primary-pointers.json')),childRunId=child,
                fixtureUrl=self.client.url+'/runs/'+child+'/',ticket=TICKET,baseline=dict(state=deepcopy(f.baseline),**deepcopy(c.baseline)),logoutBefore=deepcopy(f.logout_before))
            self.inputs[subject]=config
        def transport(request,timeout):return self.cases[self.active].f.f.widget.post(request,timeout)
        seam=patch.object(normal_input,'urlopen',transport);seam.start();self.addCleanup(seam.stop)
        self.root=self.cases['primary'].f.artifacts;self.store=PrivateFeatureState(self.cases['primary'].f.root/'ios-avatar-primary-final.json')

    def host(self):return 1800000000000+round(self.clock[0]*1000)
    def owned(self,subject,query):
        c=self.cases[subject];f=c.f
        for name in ('ios-avatar-primary-'+subject+'-account-reads.json','ios-avatar-primary-'+subject+'-postlogout.json',
                'ios-avatar-primary-'+subject+'-postlogout-tail.json','ios-avatar-primary-pointers.json'):
            raw=PrivateFeatureState(f.root/name).read()
            if raw is None:continue
            p=__import__('adapters.script_feature.history',fromlist=['unpack']).unpack(raw['payload'])[0]['pending']
            if p is None:continue
            if 'parts' in p:p=p['parts']
            queries=[p.get('query'),p.get('modelQuery')]+[r['query'] for r in p.get('nativeQueries',[])]+[r['query'] for r in p.get('clocks',[])]
            if query in queries:return
        self.fail('Every native/model/pointer query must be owned before its transport')

    def accounts(self,subject):
        c=self.cases[subject];f=c.f;f.owned=lambda query:self.owned(subject,query);reader,clock=f.native_parts()
        return IOSAvatarAccountReads(PrivateFeatureState(f.root/('ios-avatar-primary-'+subject+'-account-reads.json')),f.artifacts,self.bindings[subject],RUN,
            'primary',subject,f.lock,lambda:True,reader,clock_source=clock,epoch_ms=self.host,monotonic=lambda:self.clock[0])

    def factory(self,subject):
        self.active=subject;c=self.cases[subject];f=c.f;config=self.inputs[subject];binding=self.bindings[subject]
        post=IOSAvatarPostLogoutReads(PrivateFeatureState(config['paths']['post']),f.artifacts,binding,RUN,'primary',subject,f.lock,lambda:True,
            lambda:self.accounts(subject),f.model,child_run=f.child,fixture_url=config['fixtureUrl'],ticket=TICKET,baseline=config['baseline']['state'],
            logout_before=f.logout_before,epoch_ms=self.host,monotonic=lambda:self.clock[0])
        def actual():
            result=c.factory();result['binding']=binding;return result
        tail=IOSAvatarPostLogoutTail(c.store,f.artifacts,binding,RUN,'primary',subject,f.lock,lambda:True,actual,child_run=f.child,
            fixture_url=config['fixtureUrl'],ticket=TICKET,baseline=config['baseline'],logout_before=f.logout_before,epoch_ms=self.host,monotonic=lambda:self.clock[0])
        _,clock=f.native_parts();reader=f.pointer.reader();reader.clock_ms=lambda:clock.read(clock.sequence)['capturedEpochMs']
        reader.monotonic=lambda:self.clock[0]
        pointer=IOSAvatarPointers(PrivateFeatureState(config['paths']['pointers']),f.artifacts,binding,RUN,'primary',f.lock,lambda:True,
            native=clock,pointer=reader,epoch_ms=self.host,monotonic=lambda:self.clock[0])
        return dict(post=post,tail=tail,pointers=pointer)

    def owner(self):return IOSAvatarFinal(self.store,self.root,self.bindings,RUN,'primary',self.locks,lambda:True,self.factory,self.authority,self.inputs,
        epoch_ms=self.host,monotonic=lambda:self.clock[0],sleep=lambda n:self.clock.__setitem__(0,self.clock[0]+n))
    def archive(self,owner):return IOSAvatarFinal.archive(owner.previous,store=self.store,root=self.root,bindings=self.bindings,run=RUN,role='primary',
        locks=self.locks,authority=self.authority,inputs=self.inputs)
    def capture(self,owner,sequence):return owner.capture(ticket=TICKET,phase_instance=INSTANCE,sequence=sequence)

    def test_both_actual_subjects_need_original_native_host_pointer_and_http_quiet(self):
        owner=self.owner();refs=[self.capture(owner,1)];self.clock[0]+=1.6;refs.append(self.capture(owner,2));self.clock[0]+=1.6;refs.append(self.capture(owner,3))
        proof=owner.quiet(refs,sequence=4);self.assertNotIn('public',proof);self.assertEqual({'primary','actor'},set(proof['bilateralQuiet']))
        self.assertGreaterEqual(proof['bilateralQuiet']['primary']['nativeBeforeLastMonotonicMs']-proof['bilateralQuiet']['primary']['nativeAfterFirstMonotonicMs'],3000)
        actual=owner.group(owner.record(refs[-1]))['primary']
        self.assertEqual(actual['tail'].keys(actual['ui'])['source']['instance'],proof['bilateralQuiet']['primary']['nativeInstance'])
        before={role:len(case.f.calls) for role,case in self.cases.items()};archived=self.archive(owner)
        self.assertEqual(proof,archived.quiet(refs,sequence=4));self.assertEqual(before,{r:len(c.f.calls) for r,c in self.cases.items()})
        with self.assertRaises(NativeUIError):archived.capture(ticket=TICKET,phase_instance=INSTANCE,sequence=5)

    def test_three_fast_reads_and_one_subject_retained_contact_cannot_retire(self):
        owner=self.owner();refs=[self.capture(owner,n) for n in (1,2,3)]
        with self.assertRaises(NativeUIError):owner.quiet(refs,sequence=4)
        self.cases['primary'].f.pointer.touch('touch-begin')
        self.clock[0]+=3.2
        bad=self.capture(owner,4)
        with self.assertRaises(NativeUIError):owner.quiet([*refs,bad],sequence=5)

    def test_lost_completed_final_file_is_adopted_without_a_single_sdk_query(self):
        owner=self.owner();write=PrivateFeatureState.write;lost=[]
        def writing(store,value,previous):
            write(store,value,previous)
            if store.path==owner.file(1).path and not lost:lost.append(True);raise OSError('Lost completed original return')
        with patch.object(PrivateFeatureState,'write',writing),self.assertRaises(OSError):self.capture(owner,1)
        counts={s:len(c.f.calls) for s,c in self.cases.items()};metadata=deepcopy(owner.state['pending']['value'])
        rebuilt=self.owner();reference=rebuilt.recover()
        self.assertEqual(metadata,rebuilt.file(1).read());self.assertEqual(counts,{s:len(c.f.calls) for s,c in self.cases.items()})
        rebuilt.group(rebuilt.record(reference))

    def test_missing_planned_component_uses_only_exact_current_metadata_and_no_resend(self):
        owner=self.owner();write=PrivateFeatureState.write;lost=[]
        def writing(store,value,previous):
            if 'avatar-final-component-' in store.path.name and not lost:
                lost.append(True);raise OSError('Lost local write before component creation')
            return write(store,value,previous)
        with patch.object(PrivateFeatureState,'write',writing),self.assertRaises(OSError):self.capture(owner,1)
        counts={s:len(c.f.calls) for s,c in self.cases.items()};rebuilt=self.owner();self.assertIsNone(rebuilt.recover())
        self.assertEqual(counts,{s:len(c.f.calls) for s,c in self.cases.items()});self.assertIsNone(rebuilt.state['rows'][0]['reference'])
        self.assertTrue(rebuilt.state['rows'][0]['components'])

    def test_slow_final_owner_save_cannot_retime_the_original_but_retains_history(self):
        owner=self.owner();write=self.store.write
        def slow(value,previous):
            write(value,previous)
            if owner.state['rows'] and owner.state['pending'] is None:self.clock[0]+=1.501
        with patch.object(self.store,'write',side_effect=slow),self.assertRaises(NativeUIError):self.capture(owner,1)
        counts={s:len(c.f.calls) for s,c in self.cases.items()};historical=self.archive(self.owner())
        historical.group(historical.record(historical.state['rows'][0]['reference']))
        self.assertEqual(counts,{s:len(c.f.calls) for s,c in self.cases.items()})


if __name__=='__main__':unittest.main()
