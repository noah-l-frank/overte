"""Completed login originals resume before the initial-image stage."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.self_tests.test_ios_avatar_primary_actor_login_barrier import AvatarPrimaryActorLoginBarrierTests
from ios.adapters.avatar_feature import AvatarFeaturePending
from ios.self_tests.test_ios_avatar_bilateral_initial_barrier import InitialStageStopped

class AvatarCompletedLoginPrefixResumeTests(AvatarPrimaryActorLoginBarrierTests):
    def test_actual_saved_login_and_close_skip_duplicate_preparation_but_acquire_fresh_paired_native_sessions(self):
        f,d,runtime,primary,actor=self.primary_logged()
        with actor.held(paired=True):actor.initialize()
        with actor.held():actor.login();actor.close_preparation_tablet()
        before=self.commands(d);inputs={r:list(n.input_log) for r,n in d.natives.items()}
        stop=InitialStageStopped('Actual fresh paired source/session initial captured')
        with patch.object(primary,'initialize',side_effect=AssertionError('Repeated completed initialization')):
            with patch.object(primary,'login',side_effect=AssertionError('Repeated completed login')):
                with patch.object(primary,'close_preparation_tablet',side_effect=AssertionError('Repeated completed Close')):
                    with patch.object(primary,'wait_peer_initial',side_effect=stop),self.assertRaises(InitialStageStopped):primary.prepare(components=False)
        with primary.held():primary.load();self.assertEqual('bound',primary.state['sessions']['phase']);self.assertIsNotNone(primary.state['initial'])
        self.assertNotEqual(before,self.commands(d));self.assertEqual(inputs,{r:list(n.input_log) for r,n in d.natives.items()})
        for native in d.natives.values():self.assertEqual(1,native.input_log.count('login.submit'))
    def test_original_uncertain_close_keeps_normal_recovery_instead_of_saved_prefix_resume(self):
        f,d,runtime,primary,actor=self.primary_logged()
        with primary.held():
            primary.load();old=deepcopy(primary.previous);state=unpack(old['payload'])[0]
            PrivateFeatureState(f.root/'counter-original-primary-completed-close.json').write(old,None)
            state['preparationClose'].update(phase='issued',after=None);primary.store.write(dict(old,payload=pack([state])),old)
        stop=InitialStageStopped('Uncertain original Close retains normal initialization/recovery')
        with patch.object(primary,'initialize',side_effect=stop),self.assertRaises(InitialStageStopped):primary.prepare(components=False)
    def test_foreign_saved_login_original_refuses_before_native_source_and_cannot_authorize_resume(self):
        f,d,runtime,primary,actor=self.primary_logged()
        with actor.held(paired=True):actor.initialize()
        with actor.held():actor.login();actor.close_preparation_tablet()
        path=primary.store.path.with_name('ios-avatar-primary-login.json');store=PrivateFeatureState(path)
        with primary.held():
            original=store.read();PrivateFeatureState(f.root/'counter-original-login-before-foreign.json').write(original,None)
            changed=dict(original,childRunId='f'*32);store.write(changed,original)
        before=self.commands(d)
        with patch.object(runtime,'_sources',side_effect=AssertionError('Foreign login acquired fresh SDK')):
            with self.assertRaises(NativeUIError) as caught:primary.prepare(components=False)
        self.assertNotIsInstance(caught.exception,AvatarFeaturePending)
        self.assertEqual(before,self.commands(d))
