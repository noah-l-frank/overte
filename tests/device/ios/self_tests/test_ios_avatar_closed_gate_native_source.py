"""Plain production Runtime/native transport under the unchanged closed gate.

Direct component admission uses the legacy Reader authority intentionally. It
qualifies neither public Avatar capability nor Final/End nor Actor OS exit.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import VERSION
from ios.adapters import feature_configuration
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.self_tests.avatar_installed_full15_fixture import NativeInstalledFrontdoor,OriginalAvatarActor
from ios.self_tests.avatar_prepare_fixture import RUN
from ios.self_tests import test_ios_avatar_prepare_composed as preparation


class AvatarClosedGateNativeSourceTests(unittest.TestCase):
    retain_originals=True
    @classmethod
    def setUpClass(cls):preparation.AvatarPrepareComposedTests.setUpClass()
    @classmethod
    def tearDownClass(cls):preparation.AvatarPrepareComposedTests.tearDownClass()

    def test_direct_original_Runtime_uses_normal_native_channels_while_config8_public_gate_stays_closed(self):
        f=NativeInstalledFrontdoor(self);d=f.domain
        config=f.configuration(8);f.set_configuration(config)
        with self.assertRaises(NativeUIError):feature_configuration.capabilities(d.natives['primary'].target)
        primary=d.owners['primary'];actor=d.owners['actor']
        runtime=IOSAvatarRuntime(f.adapter)
        owner=IOSAvatarFeature(runtime,'primary',d.client,RUN,'primary',dict(artifactRoot=str(primary.root),
            imagePolicy=deepcopy(primary.policy),actorTarget='actor'))
        actor_config=dict(iosAvatarObserverVersion=1,target='actor',primaryTarget='primary',runId=RUN,
            candidateArguments=['declared-host-runtime-only'],fixtureUrl=d.client.url,actorToken=d.actor,
            authorityRead=dict(mode='adapter',token=d.adapter),durationSeconds=1800,
            artifactRoot=str(actor.root),imagePolicy=deepcopy(actor.policy))
        worker=OriginalAvatarActor(IOSAvatarRuntime(type(f.adapter)()),actor_config,f.root,self)
        sample=owner.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0));worker.check()
        self.assertEqual(RUN,sample['runId']);self.assertGreater(sample['sequence'],0)
        self.assertTrue(sample['artifacts']);self.assertFalse(sample['resources'])
        with owner.held(paired=True):
            owner.load();self.assertEqual('ready',owner.state['phase']);self.assertEqual('bound',owner.state['sessions']['phase'])
            self.assertIsNotNone(owner.initial_original())
        families={'feature-ios-avatar-state','feature-ios-avatar-renderers','feature-ios-avatar-social-http',
            'feature-ios-people-model','feature-ios-avatar-scripts','feature-ios-avatar-entities','feature-avatar-receive-observe'}
        for role,native in d.natives.items():
            actual={query['action'] for query in native.avatar_channels.requests}
            self.assertLessEqual(families,actual)
            self.assertEqual(1,native.input_log.count('login.submit'))
            self.assertTrue(native.account['loggedIn']);self.assertNotIn('app.stop',native.lifecycle_inputs)
        # No Config10 or public capability is needed for this genuine producer
        # prerequisite. The returned sample came from normal Source/PNG owners.
        with self.assertRaises(NativeUIError):feature_configuration.capabilities(d.natives['primary'].target)
        self.assertEqual(config,f.config_store.read())
        worker.close();self.assertFalse(worker.thread.is_alive())


if __name__=='__main__':unittest.main()
