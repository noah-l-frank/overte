"""Actual original initial-prefix resume, no Source/archive/clock substitution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.avatar_feature import IOSAvatarFeature,AvatarFeaturePending
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.self_tests.test_ios_avatar_bilateral_initial_barrier import AvatarBilateralInitialBarrierTests,InitialStageStopped
from ios.self_tests.avatar_installed_full15_fixture import NativeInstalledFrontdoor
from ios.self_tests.avatar_prepare_fixture import RUN

class AvatarInitialPrefixPendingTests(AvatarBilateralInitialBarrierTests):
    def own_initial_without_peer(self):
        f=NativeInstalledFrontdoor(self);d=f.domain;runtime=IOSAvatarRuntime(f.adapter);owners={}
        for role in ('primary','actor'):
            prior=d.owners[role];settings=dict(artifactRoot=str(prior.root),imagePolicy=deepcopy(prior.policy))
            settings['actorTarget' if role=='primary' else 'primaryTarget']='actor' if role=='primary' else 'primary'
            if role=='actor':settings['authorityRead']=dict(mode='adapter',token=d.adapter)
            owners[role]=IOSAvatarFeature(runtime,role,d.client,RUN,role,settings)
        primary,actor=owners['primary'],owners['actor']
        with actor.held(paired=True):actor.initialize()
        with actor.held():actor.login();actor.close_preparation_tablet()
        stop=InitialStageStopped('Counter stops after actual Primary initial, before any peer or marker')
        with patch.object(primary,'wait_peer_initial',side_effect=stop),self.assertRaises(InitialStageStopped):primary.prepare()
        with primary.held():
            primary.load();self.assertIsNotNone(primary.state['initial']);self.assertIsNone(primary.state['initialBarrier'])
            before=deepcopy(primary.previous)
        return f,d,runtime,primary,actor,before
    def test_actual_saved_initial_resumes_to_typed_pending_without_reinitializing_login_or_source_and_releases_both_locks(self):
        f,d,runtime,primary,actor,before=self.own_initial_without_peer();commands=self.commands(d)
        inputs={role:list(native.input_log) for role,native in d.natives.items()};started=time.monotonic()
        with patch.object(primary,'initialize',side_effect=AssertionError('Saved initial repeated initialize')):
            with patch.object(primary,'login',side_effect=AssertionError('Saved initial repeated login')):
                with patch.object(runtime,'_sources',side_effect=AssertionError('Saved original wait queried SDK')):
                    with self.assertRaises(AvatarFeaturePending):primary.prepare(components=False)
        self.assertLess(time.monotonic()-started,5)
        with primary.held(paired=True):primary.load();self.assertEqual(before,primary.previous)
        self.assertEqual(commands,self.commands(d));self.assertEqual(inputs,{role:list(native.input_log) for role,native in d.natives.items()})
    def test_real_peer_initial_after_pending_publishes_same_original_barrier_without_duplicate_account_or_marker_inputs(self):
        f,d,runtime,primary,actor,before=self.own_initial_without_peer()
        with self.assertRaises(AvatarFeaturePending):primary.prepare(components=False)
        stop=InitialStageStopped('Actual pair admitted before the first ordinary marker')
        with patch.object(actor,'prepare_marker',side_effect=stop),self.assertRaises(InitialStageStopped):actor.prepare(components=False)
        with patch.object(primary,'prepare_marker',side_effect=stop),self.assertRaises(InitialStageStopped):primary.prepare(components=False)
        with primary.held(paired=True):
            primary.load();old=unpack(before['payload'])[0]
            self.assertEqual(old['initial'],primary.state['initial']);self.assertTrue(primary.initial_admitted())
            peer=IOSAvatarFeature.archive(runtime,actor.store.read(),d.client,primary.locks)
            self.assertEqual(primary.state['initial']['reference'],peer.state['initialBarrier']['reference'])
        for native in d.natives.values():
            self.assertEqual(1,native.input_log.count('login.submit'))
            self.assertFalse(any(str(query.get('action','')).startswith('feature-script-start') for query in native.commands))
    def test_foreign_saved_initial_and_abort_refuse_before_source_or_duplicate_input(self):
        f,d,runtime,primary,actor,before=self.own_initial_without_peer();commands=self.commands(d)
        with primary.held():
            primary.load();original=deepcopy(primary.previous);state=unpack(original['payload'])[0]
            state['initial']['reference']['sha256']='0'*64;foreign=dict(original,payload=pack([state]))
            PrivateFeatureState(f.root/'counter-original-initial-before.json').write(original,None)
            primary.store.write(foreign,original)
        with patch.object(runtime,'_sources',side_effect=AssertionError('Foreign saved initial queried SDK')):
            with self.assertRaises(NativeUIError):primary.prepare(components=False)
            with primary.held():
                changed=primary.store.read();PrivateFeatureState(f.root/'counter-original-initial-foreign.json').write(changed,None)
                primary.store.write(original,changed)
            abort=PrivateFeatureState(primary.store.path.with_name('ios-avatar-primary-'+RUN+'-abort.json'))
            abort.write(dict(declaredExistingAbortFence=True),None)
            with self.assertRaises(NativeUIError):primary.prepare(components=False)
        self.assertEqual(commands,self.commands(d))
