"""Actual SDK locks and original-file session admission at explicit SDK seams.

These tests exercise coordination, not native execution or complete retirement.
The session producer emits existing native DTOs; account provisioning and the
private source/peer archives are real host implementations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from feature_journeys.avatar_accounts import AvatarAccountScopes
from feature_journeys.avatar_social_provider import AvatarSocialProvider
from feature_journeys.avatar_social_http import account_authenticator
from feature_journeys.witness import Client
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_feature import IOSAvatarFeature,AvatarFeaturePending
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.self_tests import test_ios_avatar_facts as fixture


class AvatarFeatureLocksTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        for role in ('primary','actor'):(self.root/role).mkdir(mode=0o700)
        class Runtime(IOSAvatarRuntime):
            def state_path(_self,selector):return self.root/selector/'session.json'
            def _sources(_self,_selector):raise AssertionError('Configuration/serialization must not query an SDK')
        self.runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True))
        self.client=Client('https://controlled.invalid/feature-fixture/v1','r'*64)
    def owner(self,role):
        peer='actor' if role=='primary' else 'primary';config=dict(artifactRoot=str(self.root/role),
            imagePolicy=dict(source='world-render-target',marker=[0,0,32,32],subject=[64,64,96,96]),
            **{('actorTarget' if role=='primary' else 'primaryTarget'):peer})
        if role=='actor':config['authorityRead']=dict(mode='adapter',token='s'*64)
        return IOSAvatarFeature(self.runtime,role,self.client,'a'*32,role,config)
    def test_paired_roles_take_actual_locks_in_the_same_order_without_deadlock(self):
        a,b=self.owner('primary'),self.owner('actor');barrier=threading.Barrier(2);events=[];errors=[]
        def run(owner):
            try:
                barrier.wait(timeout=2)
                with owner.held(paired=True):
                    for lock in owner.locks.values():lock.assert_held()
                    events.append(owner.role);time.sleep(.02)
            except Exception as error:errors.append(error)
        threads=[threading.Thread(target=run,args=(owner,)) for owner in (a,b)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=3)
        self.assertTrue(all(not thread.is_alive() for thread in threads));self.assertEqual([],errors)
        self.assertEqual({'primary','actor'},set(events))
    def test_primary_action_does_not_hold_actor_lock_while_waiting_for_consent(self):
        primary,actor=self.owner('primary'),self.owner('actor');errors=[];consented=threading.Event()
        def consent():
            try:
                with actor.held():consented.set()
            except Exception as error:errors.append(error)
        with primary.held():
            thread=threading.Thread(target=consent);thread.start()
            self.assertTrue(consented.wait(timeout=1));thread.join(timeout=2)
        self.assertEqual([],errors);self.assertFalse(thread.is_alive())
    def test_private_read_authority_is_never_serialized_in_feature_envelope(self):
        actor=self.owner('actor');self.assertNotEqual(actor.client.token,actor.authority.client.token)
        self.assertNotIn('s'*64,str(actor.envelope(dict(phase='preparing'))))


class AvatarSessionAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarFactsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        social=AvatarSocialProvider(account_authenticator(self.f.account),epoch_ms=self.f.host)
        self.scopes=AvatarAccountScopes(self.f.account,social);self.scopes.provision(fixture.RUN);self.scopes.activate(fixture.RUN,fixture.TICKET)
        self.client=Client(self.f.client.url,'r'*64);self.posts=[];self.lost=False
        for subject in ('primary','actor'):
            core=self.f.fixtures[subject].core;original=core.send
            principal=hashlib.sha256(('e2e-'+self.scopes.snapshot(fixture.RUN)['accounts'][subject]['runId']).encode()).hexdigest()
            def send(query,c=core,base=original,identity=principal):
                base(query);c.sample['account']['principalSha256']=identity
            core.send=send
            def read(subject=subject):
                self.f.read_peer(subject);return deepcopy(self.f.peers[subject].frames[-1])
            self.f.peers[subject].read=read
        self.owner=object.__new__(IOSAvatarFeature)
        self.owner.lock=self.f.sources['primary'].lock;self.owner.run=fixture.RUN;self.owner.role='primary';self.owner.client=self.client
        self.owner.authority=AvatarAuthorityReader(self.client,fixture.RUN,epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0])
        # The explicit preparation seam excludes login/input/installed-code
        # admission here. Its real session input journal precedes any POST.
        self.state=PrivateFeatureState(self.f.g.root/'avatar-session-preparation-test.json');self.owner.state=dict(sessions=None)
        def save():self.state.write(deepcopy(self.owner.state),self.state.read())
        self.owner.save=save
        def request(path,value=None,method=None):
            if path.endswith('/accounts'):return self.scopes.snapshot(fixture.RUN)
            self.assertEqual('/runs/'+fixture.RUN+'/avatar/sessions',path);self.assertEqual('POST',method)
            self.assertEqual('issued',self.state.read()['sessions']['phase']);self.posts.append(deepcopy(value))
            self.scopes.bind_sessions(fixture.RUN,value['sessions'],value['domain'])
            if self.lost:raise OSError('Synthetic socket loss after genuine backend session binding')
            return {}
        self.client.request=request;self.parts=dict(sources=self.f.sources,peers=self.f.peers)
    def test_actual_native_sessions_are_bound_once_and_historically_reopened_after_reconstruction(self):
        self.owner.sessions(self.parts);self.assertEqual(1,len(self.posts));self.assertEqual('bound',self.owner.state['sessions']['phase'])
        self.assertEqual(fixture.NODES,self.posts[0]['sessions']);old=deepcopy(self.owner.state)
        self.owner.state=self.state.read();self.owner.sessions(self.parts)
        self.assertEqual(old,self.owner.state);self.assertEqual(1,len(self.posts))
        altered=deepcopy(old);altered['sessions']['input']['sessions']['actor']='00000000-0000-4000-8000-000000000007'
        self.owner.state=altered
        with self.assertRaises(NativeUIError):self.owner.sessions(self.parts)
        self.assertEqual(1,len(self.posts))
    def test_lost_actual_binding_reply_resolves_original_get_and_never_reposts(self):
        self.lost=True
        with self.assertRaises(OSError):self.owner.sessions(self.parts)
        self.assertEqual('issued',self.owner.state['sessions']['phase']);self.assertEqual('ready',self.scopes.snapshot(fixture.RUN)['phase'])
        refs=deepcopy(self.owner.state['sessions']);reads={key:len(value.frames) for key,value in self.f.sources.items()}
        self.owner.state=self.state.read();self.owner.sessions(self.parts)
        self.assertEqual('bound',self.owner.state['sessions']['phase']);self.assertEqual(1,len(self.posts))
        self.assertEqual(reads,{key:len(value.frames) for key,value in self.f.sources.items()})
        self.assertEqual(refs['sources'],self.owner.state['sessions']['sources'])
    def test_missing_or_foreign_actual_native_account_never_submits_session_inputs(self):
        core=self.f.fixtures['actor'].core;original=core.send
        def wrong(query):original(query);core.sample['account']['principalSha256']='f'*64
        core.send=wrong
        with self.assertRaises(AvatarFeaturePending):self.owner.sessions(self.parts)
        self.assertEqual([],self.posts);self.assertIsNone(self.owner.state['sessions'])


if __name__=='__main__':unittest.main()
