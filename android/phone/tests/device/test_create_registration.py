"""Closed default-off public Create registration and independent actor config."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_feature_adapters as bound
import test_account_fixture_launch
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_create_feature import configuration
from script_observer import configuration as observer_configuration


class CreateRegistrationTests(unittest.TestCase):
    def setUp(self):
        setup=test_account_fixture_launch.AccountFixtureLaunchTests();setup.setUp();self.addCleanup(setup.doCleanups);self.f=setup.f
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.settings=self.root/'create-configuration.json';self.access=self.root/'adapter-access.json'
        self.config=dict(createFeatureVersion=1,artifactRoot=str(self.root),imageExtent=[1000,750],markerRoi=[20,20,180,60],
            imagePolicy=dict(source='world-render-target',marker=[24,24,152,56],subject=[280,155,720,595]),
            domainId='12345678-1234-4234-8234-123456789abc',permissionsControlUrl='http://127.0.0.1:40123/v1/create-permissions',permissionsControlToken='z'*64)
        PrivateFeatureState(self.settings).write(self.config,None)
        PrivateFeatureState(self.access).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl='http://controlled.invalid/feature-fixture/v1',adapterToken='d'*64),None)
        self.environment=dict(OVERTE_PHONE_FEATURE_CREATE='1',OVERTE_PHONE_CREATE_CONFIGURATION=str(self.settings),
            OVERTE_E2E_FEATURE_FIXTURE_URL='http://controlled.invalid/feature-fixture/v1',OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(self.access))
    def test_explicit_private_configuration_adds_exact_public_triple(self):
        with patch.dict(os.environ,self.environment):
            values=self.f.adapter.advertised_capabilities(self.f.target)
            self.assertEqual({'feature.create.'+key for key in ('act','observe','cleanup')},{value for value in values if value.startswith('feature.create.')})
    def test_default_off_and_invalid_enable_reject_before_owner_construction(self):
        for flag in ('0',''):
            with patch.dict(os.environ,self.environment|dict(OVERTE_PHONE_FEATURE_CREATE=flag)),patch.object(self.f.adapter,'_create_feature') as owner:
                if flag=='0':
                    self.assertFalse(any(value.startswith('feature.create.') for value in self.f.adapter.advertised_capabilities(self.f.target)))
                    with self.assertRaisesRegex(ValueError,'PHONE_CREATE_FEATURE_NOT_ENABLED'):
                        self.f.adapter.invoke(bound.SELECTOR,'feature.create.observe',dict(contractVersion=18,runId='a'*32,afterSequence=0))
                else:
                    with self.assertRaises(ValueError):self.f.adapter.advertised_capabilities(self.f.target)
                owner.assert_not_called()
    def test_missing_fixture_access_private_path_and_bound_candidate_fail_closed(self):
        for change in (dict(OVERTE_PHONE_CREATE_CONFIGURATION=''),dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=''),dict(OVERTE_E2E_FEATURE_FIXTURE_URL='http://foreign.invalid/feature-fixture/v1')):
            with self.subTest(change=change),patch.dict(os.environ,self.environment|change),self.assertRaises((ValueError,RuntimeError)):
                self.f.adapter.advertised_capabilities(self.f.target)
        with patch.dict(os.environ,self.environment),patch.object(self.f.adapter,'candidate',None),self.assertRaises(ValueError):self.f.adapter.advertised_capabilities(self.f.target)
    def test_unknown_expected_fields_coercion_foreign_permission_origin_or_image_overlap_fail(self):
        for change in (dict(createFeatureVersion=True),dict(expectedObjects=[]),dict(imageExtent=[True,750]),
                dict(permissionsControlUrl='http://foreign.invalid:40123/v1/create-permissions'),dict(permissionsControlUrl='http://127.0.0.1:40123/v1/create-permissions?token=secret'),
                dict(imagePolicy=self.config['imagePolicy']|dict(subject=[24,24,152,56]))):
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):configuration(self.config|change)
    def test_v4_actor_config_is_separately_credentialed_and_has_no_primary_permission_or_reader_token(self):
        path=self.root/'actor.json';store=PrivateFeatureState(path)
        value=dict(featureObserverVersion=4,area='create',target='synthetic',candidateArguments=['--record','private'],
            fixtureUrl='http://controlled.invalid/feature-fixture/v1',actorToken='a'*64,durationSeconds=120)
        store.write(value,None);self.assertEqual(value,observer_configuration(path))
        for change in (dict(featureObserverVersion=3),dict(readerToken='r'*64),dict(permissionsControlToken='z'*64),dict(imagePolicy=self.config['imagePolicy'])):
            store.write(value|change,store.read())
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):observer_configuration(path)


if __name__=='__main__':unittest.main()
