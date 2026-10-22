"""Owned mixer composition on explicit HTTP/native seams, without services."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.mixer import ChatMixerOwner
from adapters.chat_journey.mixer_control import FixtureMixerControl,validate
from adapters.native_chat_observation import identity
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture.messages_mixer import MessagesMixerObservation
from self_tests import test_chat_journey_samples as source_seams
from self_tests.test_native_chat_observation import RUN

URL='http://127.0.0.1:34567/v1/messages-mixer-state'
TOKEN='private-fixture-token-'+'x'*40
DOMAIN='11111111-2222-4333-8444-555555555555'


class Response:
    def __init__(self,value,url=URL):self.value,self.url=value,url;self.status=200
    def __enter__(self):return self
    def __exit__(self,*_args):pass
    def geturl(self):return self.url
    def read(self,size):return json.dumps(self.value).encode()[:size]


class Controller:
    """Explicit transport/process source seam; no product controller behavior."""
    def __init__(self,epoch):
        self.epoch=epoch;self.requests=[];self.sequence=0;self.posts=[];self.effect=None;self.lost=None;self.mutate=None
        self.value=dict(mixerControlVersion=2,instance='8'*32,sequence=0,capturedEpochMs=20000,domainId=DOMAIN,
            stackGeneration=1,processes={role:hashlib.sha256(role.encode()).hexdigest() for role in MessagesMixerObservation.ROLES},
            mixer=dict(mixerProcessVersion=1,running=True,generation=1,pending=False),mixerIdentity='9'*64,
            runId=None,offlineFenced=False,commands=[])
    def open(self,request,timeout):
        self.requests.append((request.get_method(),timeout));now=self.epoch()
        if request.get_method()=='POST':
            command=json.loads(request.data);self.posts.append(command)
            if self.effect:self.effect(command)
            if self.lost==command['action']:raise OSError('private '+TOKEN)
        self.sequence+=1;value=deepcopy(self.value);value.update(sequence=self.sequence,capturedEpochMs=now)
        if self.mutate:self.mutate(value)
        return Response(value)
    def apply(self,command):
        value=self.value;value['runId']=command['runId']
        value['commands'].append(dict(commandId=command['commandId'],action=command['action'],
            observedGeneration=command['observedGeneration'],admittedEpochMs=self.epoch(),completedEpochMs=self.epoch(),status='completed'))
        value['offlineFenced']|=command['action']=='online'
        running=command['action']=='online'
        if value['mixer']['running']!=running:
            value['mixer']['generation']+=1;value['mixerIdentity']='7'*64 if running else None
        value['mixer']['running']=running


class MixerOwnerTests(unittest.TestCase):
    def setUp(self):
        self.h=source_seams.ChatSamplesTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.actor=self.h.sampler(role='actor',store=PrivateFeatureState(self.h.root/'actor.json'))
        self.roles=(self.h.samples,self.actor);self.clock=0.;self.fault=None;self.native_mixer='d'*64
        self.controller=Controller(self.epoch);self.controller.effect=self.apply
        self.store=PrivateFeatureState(self.h.root/'mixer.json')
        for boundary,index in ((self.h.primary,1),(self.h.peer,3),(self.h.view,5),(self.h.native,7)):
            old=boundary.mutate
            def mutate(value,old=old,index=index):
                if old:old(value)
                value['capturedEpochMs']=self.epoch()
                if index==7:
                    value['requestedEpochMs']=self.epoch();value['animationFence']['requestedEpochMs']=self.epoch()
                    value['animation']['capturedEpochMs']=self.epoch();value['animation']['clip']['evaluatedEpochMs']=self.epoch()
                if index in (1,3):
                    value['chatVersion']=2;source=value['source']
                    source['mixerSha256']=self.native_mixer if source['mixerPresent'] else ''
                    source['session']=dict(domainSessionVersion=1,instance=str(index)*32,revision=2,connected=True,
                        domainSha256=identity(RUN,DOMAIN),connectionBirth=str(index+1)*32,connectedEpochMs=19000,
                        mixerActive=source['mixerPresent'])
            boundary.mutate=mutate
        for role in self.roles:
            role.monotonic=lambda:self.clock
            for reader in (role.primary,role.peer,role.view,role.lifecycle):reader.clock_ms=self.epoch
        self.owner=self.make()
    def epoch(self):return 20000+int(self.clock*1000)
    def sleep(self,seconds):
        self.clock+=seconds
        if self.fault:self.fault()
    def controls(self):
        return tuple(FixtureMixerControl(URL,TOKEN,lambda:True,readonly=readonly,opener=self.controller,
            clock_ms=self.epoch,monotonic=lambda:self.clock) for readonly in (False,True))
    def make(self):return ChatMixerOwner(self.controls(),self.roles,self.store,monotonic=lambda:self.clock,sleep=self.sleep)
    def apply(self,command):
        # Input and independently read native state are separate explicit seams.
        self.assertEqual(command,self.store.read()['commands'][-1]);self.controller.apply(command)
        self.h.primary.mixer=self.h.peer.mixer=command['action']=='online'
        if command['action']=='online':self.native_mixer='f'*64
    def test_both_native_clients_and_controller_advance_through_owned_absence_fresh_recovery_and_quiet(self):
        absent=self.owner.remove(20000);self.assertFalse(absent[0]['state']['mixerConnected'])
        restored=self.owner.restore(20000);self.assertTrue(restored[0]['state']['mixerConnected'])
        self.assertEqual(['offline','online'],[row['action'] for row in self.controller.posts])
        self.assertEqual('online',self.store.read()['phase']);self.assertTrue(self.store.read()['offlineObserved'])
        self.assertGreaterEqual(self.clock,6);self.assertTrue(self.store.path.exists())
        before=len(self.controller.requests);rebuilt=self.make();self.assertEqual(before,len(self.controller.requests))
        with self.assertRaises(NativeUIError):rebuilt.remove(20000)
        with self.assertRaises(NativeUIError):rebuilt.restore(20000)
        self.assertEqual(2,len(self.controller.posts))
        for role in self.roles:
            self.assertGreater(len(role.frames),60)
            for frame in role.frames:
                if frame.get('transition'):self.assertNotIn('state',frame)
    def test_lost_online_receipt_is_resolved_only_by_new_passive_sources_after_reconstruction(self):
        self.owner.remove(20000);self.controller.lost='online'
        with self.assertRaises(NativeUIError):self.owner.restore(20000)
        self.assertEqual('issuing-online',self.store.read()['phase']);self.controller.lost=None
        rebuilt=self.make()
        with self.assertRaises(NativeUIError):rebuilt.restore(20000)
        observed=rebuilt.inspect_restored(20000);self.assertTrue(observed[0]['state']['mixerConnected'])
        self.assertEqual(2,len(self.controller.posts));self.assertEqual('online',self.store.read()['phase'])
    def test_lost_offline_receipt_restores_once_even_when_native_source_is_unavailable(self):
        self.controller.lost='offline';ordinary=self.apply
        def apply(command):
            ordinary(command)
            if command['action']=='offline':self.h.primary.alive=False
        self.controller.effect=apply
        with self.assertRaises(NativeUIError):self.owner.remove(20000)
        self.assertEqual(['offline','online'],[row['action'] for row in self.controller.posts])
        self.assertTrue(self.controller.value['mixer']['running']);self.assertTrue(self.controller.value['offlineFenced'])
        self.assertEqual('recovery-observed',self.store.read()['phase']);self.assertFalse(self.store.read()['offlineObserved'])
        rebuilt=self.make()
        with self.assertRaises(NativeUIError):rebuilt.remove(20000)
        with self.assertRaises(NativeUIError):rebuilt.inspect_restored(20000)
        self.assertEqual(2,len(self.controller.posts))
    def test_ack_and_process_state_cannot_supply_missing_native_absence_or_unrelated_domain(self):
        self.controller.effect=self.controller.apply
        with self.assertRaises(NativeUIError):self.owner.remove(20000)
        self.assertNotEqual('offline',self.store.read()['phase']);self.assertFalse(self.store.read()['offlineObserved'])
        self.assertEqual(['offline','online'],[row['action'] for row in self.controller.posts])
        self.setUp();self.controller.value['domainId']='22222222-2222-4333-8444-555555555555'
        with self.assertRaises(NativeUIError):self.owner.remove(20000)
        self.assertEqual([],self.controller.posts)
    def test_mid_quiet_replay_and_frozen_clock_cannot_close_outage(self):
        for fault in ('replay','frozen'):
            with self.subTest(fault=fault):
                self.setUp()
                if fault=='replay':
                    def replay():
                        if self.clock>=1:self.h.peer.event();self.fault=None
                    self.fault=replay
                else:
                    old=self.h.peer.mutate
                    def frozen(value):old(value);value['capturedEpochMs']=20000
                    self.h.peer.mutate=frozen
                with self.assertRaises(NativeUIError):self.owner.remove(20000)
                self.assertFalse(self.store.read()['offlineObserved']);self.assertEqual(2,len(self.controller.posts))
    def test_original_full_journal_does_not_block_separate_once_only_recovery_admission(self):
        self.owner.remove(20000)
        exhausted=False
        for _ in range(170):
            try:self.owner.measure(20000,transition=True)
            except NativeUIError:exhausted=True;break
        self.assertTrue(exhausted);before=deepcopy(self.store.read()['transcript'])
        self.owner.recover(20000)
        self.assertEqual(['offline','online'],[row['action'] for row in self.controller.posts])
        self.assertEqual('recovery-observed',self.store.read()['phase'])
        self.assertEqual(before,self.store.read()['transcript']);self.assertEqual(2,len(self.store.read()['recoverySources']))
        rebuilt=self.make();rebuilt.recover(20000);self.assertEqual(2,len(self.controller.posts))

    def test_last_controller_guard_cannot_age_native_clock_under_frozen_host_time(self):
        controls=self.owner.controls;calls=0;delta=0
        def guarded():
            nonlocal calls,delta
            calls+=1
            if calls>=3:delta=2000
            return True
        controls[1].guard=guarded
        for role in self.roles:role.primary.clock_ms=lambda:self.epoch()+delta
        self.owner.deadline=20
        with self.assertRaises(NativeUIError):self.owner.measure(20000,transition=False)
        self.assertEqual(0,self.clock);self.assertEqual([],self.controller.posts)

    def test_journal_tampering_and_foreign_controller_cannot_be_adopted_or_send(self):
        self.owner.remove(20000);old=self.store.read();bad=deepcopy(old);bad['commands'][0]['commandId']='0'*32
        self.store.write(bad,old)
        with self.assertRaises(NativeUIError):self.make()
        self.assertEqual(1,len(self.controller.posts))
        self.store.write(old,bad);self.controller.value['instance']='0'*32
        with self.assertRaises(NativeUIError):self.owner.restore(20000)
        self.assertEqual(1,len(self.controller.posts))


class ControlTests(unittest.TestCase):
    def setUp(self):self.clock=0.;self.controller=Controller(lambda:20000+int(self.clock*1000))
    def make(self,**kwargs):return FixtureMixerControl(URL,TOKEN,lambda:True,opener=self.controller,
        monotonic=lambda:self.clock,clock_ms=lambda:20000+int(self.clock*1000),**kwargs)
    def test_only_two_distinct_gets_advance_sources_and_command_ack_is_not_a_source_cursor(self):
        source=self.make();first=source.state();command=dict(schemaVersion=2,commandId='a'*32,runId=RUN,
            instance=first['instance'],observedGeneration=1,action='offline')
        self.controller.effect=self.controller.apply;source.command(command)
        self.assertEqual(first,source.previous);actual=source.state();self.assertFalse(actual['mixer']['running'])
        self.assertEqual([('GET',1.5),('POST',10),('GET',1.5)],self.controller.requests)
        with self.assertRaises(NativeUIError):self.make(readonly=True).command(command)
        self.assertEqual(1,len(self.controller.posts))
    def test_private_endpoint_refuses_remote_alias_redirect_userinfo_and_false_capture(self):
        for url in (URL.replace('127.0.0.1','localhost'),URL.replace('http:','https:'),URL+'?secret='+TOKEN,
                    URL.replace('127.0.0.1','user@127.0.0.1'),URL.replace('34567','034567')):
            with self.subTest(url=url),self.assertRaises(NativeUIError):FixtureMixerControl(url,TOKEN,lambda:True)
        self.controller.mutate=lambda value:value.update(capturedEpochMs=19999)
        with self.assertRaises(NativeUIError) as error:self.make().state()
        self.assertNotIn(TOKEN,str(error.exception))
    def test_final_guard_wall_clock_jump_is_stale_even_when_host_monotonic_is_frozen(self):
        source=self.make();wall=20000;calls=0
        source.clock_ms=lambda:wall
        def guarded():
            nonlocal wall,calls
            calls+=1
            if calls==2:wall+=2000
            return True
        source.guard=guarded
        with self.assertRaises(NativeUIError):source.state()
        self.assertIsNone(source.previous);self.assertEqual(0,self.clock)

    def test_original_ledger_cannot_regress_rewrite_terminal_or_falsify_fence(self):
        source=self.make();source.state();self.controller.effect=self.controller.apply
        self.controller.apply(dict(commandId='a'*32,runId=RUN,observedGeneration=1,action='online'))
        source.state();self.controller.value['commands'][0]['status']='failed'
        with self.assertRaises(NativeUIError):source.state()
        self.controller.value['offlineFenced']=False
        with self.assertRaises(NativeUIError):validate(self.controller.value|dict(capturedEpochMs=20000,sequence=1),20000)


if __name__=='__main__':unittest.main()
