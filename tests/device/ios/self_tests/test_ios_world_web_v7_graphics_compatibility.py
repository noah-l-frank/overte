"""Actual v6/v7/v8 config and canonical Graphics cleanup route; native end is a spy.

The typed Graphics end has its own original-file tests. This test proves only
that a valid new shared configuration reaches that existing owner/finalizer;
its declared return supplies no Scene, OS, SDK or Graphics retirement fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import feature_configuration
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.self_tests import test_ios_installed_adapter as installed_fixture


class WorldWebV7GraphicsCompatibilityTests(unittest.TestCase):
    def test_valid_v7_and_preserved_v6_graphics_config_reach_original_canonical_cleanup_owner(self):
        fixture=installed_fixture.InstalledAdapterTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        path=fixture.root/'feature-configuration.json';access=fixture.root/'fixture-reader.json'
        PrivateFeatureState(access).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl='http://127.0.0.1:1/feature-fixture/v1',adapterToken='d'*64),None)
        selected=dict(artifactRoot=str(fixture.root),imagePolicy=dict(source='world-render-target',marker=[0,0,128,32],subject=[0,40,128,100]))
        value=dict(iosFeatureAdapterVersion=7,areas=['graphics'],fixtureConfig=str(access),graphics=selected,create=None,emotes=None,
            worldNavigation=None,worldWeb=None,avatarPeople=None,tabletWeb=None,emoteCoordinatorVersion=None,worldWebCoordinatorVersion=None)
        # This opaque private responsibility triggers dispatch only; no body is
        # accepted as a typed Graphics proof by the declared constructor spy.
        store=PrivateFeatureState(fixture.adapter.state_path('test-only').with_name('ios-graphics-feature.json'))
        original=dict(declaredDispatchMetadataOnly=True);store.write(original,None)
        before=deepcopy(fixture.commands);configuration_store=PrivateFeatureState(path)
        with patch.dict(os.environ,OVERTE_IOS_FEATURE_ADAPTER_CONFIG=str(path)):
            for version in (6,7,8):
                with self.subTest(version=version):
                    config=deepcopy(value);config['iosFeatureAdapterVersion']=version
                    if version==6:config.pop('worldWebCoordinatorVersion')
                    if version>=8:config['emoteTargets']=None
                    feature_configuration.validate(config);configuration_store.write(config,configuration_store.read())
                    with (patch('ios.adapters.graphics_session_retirement.IOSGraphicsSessionRetirement') as owner,
                          patch.object(fixture.adapter,'cleanup_components',return_value=True),
                          patch.object(fixture.adapter,'component_owners_absent',return_value=True)):
                        owner.return_value.finalize.return_value=dict(declaredDispatchOnly=True)
                        self.assertEqual(dict(declaredDispatchOnly=True),fixture.adapter._cleanup_other_features('test-only'))
                        owner.assert_called_once();args=owner.call_args.args
                        self.assertIsInstance(args[0],IOSGraphicsRuntime);self.assertIs(args[0].adapter,fixture.adapter)
                        self.assertEqual('test-only',args[1]);self.assertEqual('http://127.0.0.1:1/feature-fixture/v1',args[2].url)
                        self.assertEqual(selected,args[3]);self.assertEqual(original,args[4])
                        owner.return_value.finalize.assert_called_once_with()
                    self.assertEqual(original,store.read());self.assertEqual(before,fixture.commands)


if __name__=='__main__':unittest.main()
