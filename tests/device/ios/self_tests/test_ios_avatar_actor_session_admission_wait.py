"""Actual account/Close originals and independent Primary-owned admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import threading,time
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_feature import IOSAvatarFeature,AvatarFeaturePending
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.self_tests.test_ios_avatar_bilateral_initial_barrier import AvatarBilateralInitialBarrierTests,InitialStageStopped
from ios.self_tests.avatar_installed_full15_fixture import NativeInstalledFrontdoor
from ios.self_tests.avatar_prepare_fixture import RUN

class AvatarActorSessionAdmissionWaitTests(AvatarBilateralInitialBarrierTests):
    def logged_actor(self):
        f=NativeInstalledFrontdoor(self);d=f.domain;runtime=IOSAvatarRuntime(f.adapter);owners={}
        for role in ('primary','actor'):
            prior=d.owners[role];settings=dict(artifactRoot=str(prior.root),imagePolicy=deepcopy(prior.policy))
            settings['actorTarget' if role=='primary' else 'primaryTarget']='actor' if role=='primary' else 'primary'
            if role=='actor':settings['authorityRead']=dict(mode='adapter',token=d.adapter)
            owners[role]=IOSAvatarFeature(runtime,role,d.client,RUN,role,settings)
        primary,actor=owners['primary'],owners['actor']
        with actor.held(paired=True):actor.initialize()
        with actor.held():
            actor.login();actor.close_preparation_tablet();actor.load()
            self.assertIsNotNone(actor.state['protected']);self.assertEqual('observed',actor.state['preparationClose']['phase'])
            self.assertIsNone(actor.state['sessions']);self.assertEqual('allocated',actor.authority.read()['phase'])
        return f,d,runtime,primary,actor
    def test_actual_allocated_authority_returns_actor_pending_without_primary_lock_source_or_duplicate_login(self):
        f,d,runtime,primary,actor=self.logged_actor();commands=self.commands(d)
        entered=threading.Event();release=threading.Event();errors=[]
        def hold():
            try:
                with ScriptSourceLock(primary.lock.path).held():entered.set();release.wait(6)
            except BaseException as error:errors.append(type(error).__name__);entered.set()
        worker=threading.Thread(target=hold,name='avatar-counter-real-primary-sdk-owner');worker.start()
        self.assertTrue(entered.wait(2));started=time.monotonic()
        try:
            with patch.object(actor,'initialize',side_effect=AssertionError('Actor repeated initialization')):
                with patch.object(actor,'login',side_effect=AssertionError('Actor repeated login')):
                    with patch.object(runtime,'_sources',side_effect=AssertionError('Actor acquired a pending Primary SDK')):
                        with self.assertRaises(AvatarFeaturePending):actor.prepare(components=False)
            self.assertLess(time.monotonic()-started,5)
        finally:release.set();worker.join(timeout=3)
        self.assertFalse(worker.is_alive());self.assertEqual([],errors);self.assertEqual(commands,self.commands(d))
        self.assertEqual(1,d.natives['actor'].input_log.count('login.submit'))
        self.assertEqual(0,d.natives['primary'].input_log.count('login.submit'))
    def test_actual_primary_native_admission_unblocks_actor_and_retains_original_bilateral_initials(self):
        f,d,runtime,primary,actor=self.logged_actor()
        with self.assertRaises(AvatarFeaturePending):actor.prepare(components=False)
        stop=InitialStageStopped('Actual normal initial before first marker')
        with patch.object(primary,'wait_peer_initial',side_effect=stop),self.assertRaises(InitialStageStopped):primary.prepare(components=False)
        with actor.held():self.assertEqual('ready',actor.authority.read()['phase'])
        with patch.object(actor,'prepare_marker',side_effect=stop),self.assertRaises(InitialStageStopped):actor.prepare(components=False)
        with actor.held(paired=True):
            actor.load();self.assertEqual('bound',actor.state['sessions']['phase']);self.assertTrue(actor.initial_admitted())
        for native in d.natives.values():self.assertEqual(1,native.input_log.count('login.submit'))
    def test_foreign_actual_authority_response_refuses_before_source_and_is_not_converted_to_pending(self):
        f,d,runtime,primary,actor=self.logged_actor();commands=self.commands(d);actual=actor.authority.client.request;seen=[]
        def foreign(path,**kwargs):
            value=actual(path,**kwargs)
            if path=='/runs/'+RUN+'/avatar/accounts':
                seen.append(deepcopy(value));PrivateFeatureState(f.root/'counter-original-authority-before-foreign.json').write(value,None)
                value=deepcopy(value);value['runId']='f'*32
            return value
        with patch.object(actor.authority.client,'request',side_effect=foreign):
            with patch.object(runtime,'_sources',side_effect=AssertionError('Foreign authority acquired SDK')):
                with self.assertRaises(NativeUIError) as caught:actor.prepare(components=False)
        self.assertNotIsInstance(caught.exception,AvatarFeaturePending)
        self.assertEqual(1,len(seen));self.assertEqual(commands,self.commands(d))
    def test_original_uncertain_Close_is_not_skipped_by_actor_scheduling_cue(self):
        f,d,runtime,primary,actor=self.logged_actor();commands=self.commands(d)
        with actor.held():
            actor.load();old=deepcopy(actor.previous);state=unpack(old['payload'])[0]
            PrivateFeatureState(f.root/'counter-original-actor-close-observed.json').write(old,None)
            state['preparationClose'].update(phase='issued',after=None)
            changed=dict(old,payload=pack([state]));actor.store.write(changed,old)
        stop=InitialStageStopped('Uncertain original Close still requires normal preparation/recovery')
        with patch.object(actor,'initialize',side_effect=stop),self.assertRaises(InitialStageStopped) as caught:actor.prepare(components=False)
        self.assertIs(stop,caught.exception);self.assertEqual(commands,self.commands(d))
