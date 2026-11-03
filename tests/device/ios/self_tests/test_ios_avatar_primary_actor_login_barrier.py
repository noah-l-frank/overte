"""Original peer login/Close ordering before fresh paired session acquisition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.avatar_feature import IOSAvatarFeature,AvatarFeaturePending
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.self_tests.test_ios_avatar_bilateral_initial_barrier import AvatarBilateralInitialBarrierTests,InitialStageStopped
from ios.self_tests.avatar_installed_full15_fixture import NativeInstalledFrontdoor

class AvatarPrimaryActorLoginBarrierTests(AvatarBilateralInitialBarrierTests):
    def primary_logged(self):
        f=NativeInstalledFrontdoor(self);d=f.domain;runtime=IOSAvatarRuntime(f.adapter);owners={}
        for role in ('primary','actor'):
            old=d.owners[role];config=dict(artifactRoot=str(old.root),imagePolicy=deepcopy(old.policy))
            config['actorTarget' if role=='primary' else 'primaryTarget']='actor' if role=='primary' else 'primary'
            if role=='actor':config['authorityRead']=dict(mode='adapter',token=d.adapter)
            owners[role]=IOSAvatarFeature(runtime,role,d.client,d.owners[role].run,role,config)
        primary,actor=owners['primary'],owners['actor']
        with primary.held(paired=True):primary.initialize()
        with primary.held():primary.login();primary.close_preparation_tablet()
        return f,d,runtime,primary,actor
    def test_actual_missing_actor_preparation_returns_pending_without_native_source_or_duplicate_primary_login(self):
        f,d,runtime,primary,actor=self.primary_logged();commands=self.commands(d)
        with patch.object(primary,'initialize',side_effect=AssertionError('Repeated initialization')):
            with patch.object(primary,'login',side_effect=AssertionError('Repeated login')):
                with patch.object(runtime,'_sources',side_effect=AssertionError('Premature paired native source')):
                    with self.assertRaises(AvatarFeaturePending):primary.prepare(components=False)
        self.assertEqual(commands,self.commands(d))
        self.assertEqual(1,d.natives['primary'].input_log.count('login.submit'))
        self.assertEqual(0,d.natives['actor'].input_log.count('login.submit'))
    def test_actual_actor_original_login_and_close_unblock_primary_fresh_native_session_admission(self):
        f,d,runtime,primary,actor=self.primary_logged()
        with self.assertRaises(AvatarFeaturePending):primary.prepare(components=False)
        with actor.held(paired=True):actor.initialize()
        with actor.held():actor.login();actor.close_preparation_tablet()
        stop=InitialStageStopped('Stop after actual paired source/session admission and original initial')
        with patch.object(primary,'wait_peer_initial',side_effect=stop),self.assertRaises(InitialStageStopped):primary.prepare(components=False)
        with primary.held():
            primary.load();self.assertEqual('bound',primary.state['sessions']['phase']);self.assertIsNotNone(primary.state['initial'])
        for native in d.natives.values():self.assertEqual(1,native.input_log.count('login.submit'))
    def test_foreign_actor_header_refuses_and_uncertain_original_close_remains_pending_before_native_source(self):
        f,d,runtime,primary,actor=self.primary_logged()
        with actor.held(paired=True):actor.initialize()
        with actor.held():actor.login();actor.close_preparation_tablet();actor.load();original=deepcopy(actor.previous)
        PrivateFeatureState(f.root/'counter-original-actor-before-ordering-fault.json').write(original,None)
        with actor.held():
            state=unpack(original['payload'])[0];state['preparationClose'].update(phase='issued',after=None)
            changed=dict(original,payload=pack([state]));actor.store.write(changed,original)
        commands=self.commands(d)
        with patch.object(runtime,'_sources',side_effect=AssertionError('Uncertain peer queried native source')):
            with self.assertRaises(AvatarFeaturePending):primary.prepare(components=False)
        with actor.held():
            value=actor.store.read();PrivateFeatureState(f.root/'counter-original-actor-close-uncertain.json').write(value,None)
            foreign=dict(original,runId='f'*32);actor.store.write(foreign,value)
        with patch.object(runtime,'_sources',side_effect=AssertionError('Foreign peer queried native source')):
            with self.assertRaises(NativeUIError) as caught:primary.prepare(components=False)
        self.assertNotIsInstance(caught.exception,AvatarFeaturePending)
        self.assertEqual(commands,self.commands(d))
