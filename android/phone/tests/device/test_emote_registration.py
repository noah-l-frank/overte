"""Guarded complete operation registration with private host configuration only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch

import test_emote_feature
import test_feature_adapters as bound
from adapters.normal_feature_state import PrivateFeatureState
import test_account_fixture_launch
from test_emote_pixels import POLICY
from test_emote_sources import RUN
from self_tests.test_emote_admission import POLICY as ADMISSION


class EmoteRegistrationTests(unittest.TestCase):
    setUp=test_emote_feature.EmoteFeatureTests.setUp
    owner=test_emote_feature.EmoteFeatureTests.owner
    feature=test_emote_feature.EmoteFeatureTests.feature
    observation=test_emote_feature.EmoteFeatureTests.observation

    def adapter(self):
        setup=test_account_fixture_launch.AccountFixtureLaunchTests();setup.setUp();self.addCleanup(setup.doCleanups);return setup.f

    def configuration(self):
        root=self.model.root;settings=root/'emote-adapter-settings.json';access=root/'adapter-access.json'
        value=dict(emoteAdapterConfigurationVersion=1,imageExtent=[1000,750],markerRoi=[20,20,180,60],
            imagePolicy=deepcopy(POLICY),admissionPolicy=deepcopy(ADMISSION))
        for path,item in [(settings,value),(access,dict(fixtureAdapterAccessVersion=1,
                fixtureUrl=self.model.client.url,adapterToken='d'*64))]:
            store=PrivateFeatureState(path);store.write(item,store.read())
        return dict(OVERTE_PHONE_FEATURE_EMOTES='1',OVERTE_PHONE_EMOTE_CONFIGURATION=str(settings),
            OVERTE_DEVICE_ARTIFACT_DIR=str(root),OVERTE_E2E_FEATURE_FIXTURE_URL=self.model.client.url,
            OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(access))

    def test_explicit_configuration_registers_all_three_operations_and_invokes_actual_public_owner(self):
        f=self.adapter();config=self.configuration()
        with patch.dict(os.environ,config),patch.object(f.adapter,'_emote_feature',return_value=self.feature()) as factory:
            caps=f.adapter.advertised_capabilities(f.target)
            self.assertEqual({'feature.emotes.'+kind for kind in ('act','observe','cleanup')},
                {value for value in caps if value.startswith('feature.emotes.')})
            measured=f.adapter.invoke(bound.SELECTOR,'feature.emotes.observe',self.observation())
            self.assertFalse(measured['state']['override']);self.assertEqual(1,measured['sequence'])
            factory.assert_called_once_with(bound.SELECTOR,RUN)

    def test_default_disabled_extension_rejects_invocation_without_constructing_owner(self):
        f=self.adapter();config=self.configuration()
        with patch.dict(os.environ,config|dict(OVERTE_PHONE_FEATURE_EMOTES='0')),patch.object(f.adapter,'_emote_feature') as factory:
            self.assertFalse(any(value.startswith('feature.emotes.') for value in f.adapter.advertised_capabilities(f.target)))
            with self.assertRaisesRegex(ValueError,'PHONE_EMOTE_FEATURE_NOT_ENABLED'):
                f.adapter.invoke(bound.SELECTOR,'feature.emotes.observe',self.observation())
            factory.assert_not_called()

    def test_missing_configuration_credential_or_private_directory_cannot_advertise(self):
        f=self.adapter();config=self.configuration()
        for changed in (dict(OVERTE_PHONE_FEATURE_EMOTES='yes'),dict(OVERTE_PHONE_EMOTE_CONFIGURATION=''),
                dict(OVERTE_DEVICE_ARTIFACT_DIR=''),dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=''),
                dict(OVERTE_E2E_FEATURE_FIXTURE_URL=self.model.client.url+'/foreign')):
            with self.subTest(changed=changed),patch.dict(os.environ,config|changed),self.assertRaises((ValueError,RuntimeError)):
                f.adapter.advertised_capabilities(f.target)

    def test_foreign_or_incomplete_measurement_configuration_is_not_enabled(self):
        f=self.adapter();config=self.configuration();store=PrivateFeatureState(config['OVERTE_PHONE_EMOTE_CONFIGURATION']);original=store.read()
        for changed in (dict(emoteAdapterConfigurationVersion=True),dict(expectedAnimation='Crying'),
                dict(imageExtent=[True,750]),dict(imagePolicy=POLICY|dict(source='native-screen')),
                dict(imagePolicy=POLICY|dict(subject=POLICY['marker'])),dict(admissionPolicy=ADMISSION|dict(probeUrl='http://foreign.test/probe.js'))):
            store.write(original|changed,store.read())
            with self.subTest(changed=changed),patch.dict(os.environ,config),self.assertRaises((ValueError,RuntimeError)):
                f.adapter.advertised_capabilities(f.target)

    def test_reconstruction_uses_original_configuration_without_module_environment(self):
        f=self.adapter();config=self.configuration();feature=self.feature();feature.observe(self.observation())
        with (patch.dict(os.environ,config|dict(OVERTE_PHONE_EMOTE_CONFIGURATION='',OVERTE_DEVICE_ARTIFACT_DIR='')),
                patch.object(f.adapter,'state_path',return_value=self.model.state_path('synthetic-selector'))):
            recovered=f.adapter._emote_feature(bound.SELECTOR,RUN,retirement=True)
            self.assertEqual(self.model.root,recovered.run.root);self.assertEqual(POLICY,recovered.policy)
            self.assertEqual(ADMISSION,recovered.run.policy)


if __name__=='__main__':unittest.main()
