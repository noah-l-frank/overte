"""Closed, default-off World Web public registration and separate actor binding."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import secrets
import unittest
from unittest.mock import patch

import test_world_web_feature as world
import test_account_fixture_launch
import test_feature_adapters as bound
from adapters.normal_feature_state import PrivateFeatureState
from appium_adapter import readonly_feature_command


class WorldWebRegistrationTests(unittest.TestCase):
    setUp=world.WorldWebFeatureTests.setUp
    stop=world.WorldWebFeatureTests.stop
    flow=world.WorldWebFeatureTests.flow
    activate=world.WorldWebFeatureTests.activate
    observe=world.WorldWebFeatureTests.observe

    def adapter(self):
        fixture=test_account_fixture_launch.AccountFixtureLaunchTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        return fixture.f

    def config(self):
        settings=self.path/'world-web-settings.json';access=self.path/'world-web-access.json'
        PrivateFeatureState(settings).write(dict(worldWebConfigurationVersion=1,artifactRoot=str(self.path),foreignFixtureUrl=self.foreign),None)
        PrivateFeatureState(access).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=self.url,adapterToken=self.adapter_token),None)
        return dict(OVERTE_PHONE_FEATURE_WORLD_WEB='1',OVERTE_PHONE_WORLD_WEB_CONFIGURATION=str(settings),
            OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(access),OVERTE_E2E_FEATURE_FIXTURE_URL=self.url)

    def test_all_three_operations_are_registered_only_when_explicitly_bound(self):
        fixture=self.adapter();config=self.config();self.activate()
        with patch.dict(os.environ,config),patch.object(fixture.adapter,'_world_web_feature',return_value=self.primary) as make:
            caps=fixture.adapter.advertised_capabilities(fixture.target)
            self.assertEqual({'feature.world-web.'+kind for kind in ('act','observe','cleanup')},
                {value for value in caps if value.startswith('feature.world-web.')})
            value=fixture.adapter.invoke(bound.SELECTOR,'feature.world-web.observe',dict(contractVersion=world.VERSION,runId=self.run,afterSequence=0))
            self.assertFalse(value['state']['open']);make.assert_called_once_with(bound.SELECTOR,self.run)

    def test_default_disabled_does_not_construct_or_dispatch_an_owner(self):
        fixture=self.adapter();config=self.config()
        with patch.dict(os.environ,config|dict(OVERTE_PHONE_FEATURE_WORLD_WEB='0')),patch.object(fixture.adapter,'_world_web_feature') as make:
            self.assertFalse(any(value.startswith('feature.world-web.') for value in fixture.adapter.advertised_capabilities(fixture.target)))
            with self.assertRaisesRegex(ValueError,'PHONE_WORLD_WEB_FEATURE_NOT_ENABLED'):
                fixture.adapter.invoke(bound.SELECTOR,'feature.world-web.observe',dict(contractVersion=world.VERSION,runId=self.run,afterSequence=0))
            make.assert_not_called()

    def test_unknown_or_absent_configuration_cannot_advertise_partial_capabilities(self):
        fixture=self.adapter();config=self.config()
        for changed in (dict(OVERTE_PHONE_FEATURE_WORLD_WEB='yes'),dict(OVERTE_PHONE_WORLD_WEB_CONFIGURATION=''),
                        dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=''),dict(OVERTE_E2E_FEATURE_FIXTURE_URL=self.url+'/wrong')):
            with self.subTest(changed=changed),patch.dict(os.environ,config|changed),self.assertRaises((ValueError,RuntimeError)):
                fixture.adapter.advertised_capabilities(fixture.target)
        store=PrivateFeatureState(config['OVERTE_PHONE_WORLD_WEB_CONFIGURATION']);original=store.read()
        for value in (original|{'worldWebConfigurationVersion':True},original|{'expectedState':{}},original|{'artifactRoot':str(self.path/'absent')},
                      original|{'foreignFixtureUrl':'file:///tmp/foreign'}):
            store.write(value,store.read())
            with patch.dict(os.environ,config),self.assertRaises((ValueError,RuntimeError,OSError)):
                fixture.adapter.advertised_capabilities(fixture.target)

    def test_actor_reconstruction_uses_original_configuration_without_product_input(self):
        fixture=self.adapter();self.activate();self.observe()
        client=world.Client(self.url,self.actor_token)
        with patch.dict(os.environ,{'OVERTE_PHONE_WORLD_WEB_CONFIGURATION':''}),patch.object(fixture.adapter,'state_path',return_value=self.target.state_path('target')):
            actor=fixture.adapter._world_web_feature(bound.SELECTOR,self.run,role='actor',client=client)
            self.assertEqual(self.path,actor.artifact_root);self.assertEqual(self.foreign+'/runs/'+self.run+'/',actor.foreign_url)
            self.assertEqual('actor',actor.role)
        self.assertEqual([],self.target.inputs)

    def test_read_only_source_gate_cannot_reserve_retire_or_send_input(self):
        request=dict(schemaVersion=1,commandId=secrets.token_hex(16),action='phone-world-web',operation='observe',
            runId=self.run,fixtureUrl=self.fixture_url,ownerToken=secrets.token_hex(16))
        readonly_feature_command(request)
        for operation in ('reserve','retire'):
            with self.assertRaises(ValueError):readonly_feature_command(request|dict(operation=operation))
        with self.assertRaises(ValueError):readonly_feature_command(request|dict(operation='input',handle='42',creation=1,grant=1,page=1,control='bridge',text=''))


if __name__=='__main__':unittest.main()
