"""Default-off complete Audio registration, mandatory foundations and actor gate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import unittest
from unittest.mock import patch
import test_audio_feature as audio
import test_account_fixture_launch
import test_feature_adapters as bound
from adapters.normal_feature_state import PrivateFeatureState
from appium_adapter import readonly_feature_command
from feature_journeys.scenarios import VERSION,FOUNDATIONS


class AudioRegistrationTests(unittest.TestCase):
    setUp=audio.AudioFeatureTests.setUp
    stop=audio.AudioFeatureTests.stop
    publish=audio.AudioFeatureTests.publish
    def adapter_fixture(self):
        fixture=test_account_fixture_launch.AccountFixtureLaunchTests();fixture.setUp();self.addCleanup(fixture.doCleanups);return fixture.f
    def settings(self):
        settings=self.state/'audio-settings.json';access=self.state/'audio-access.json'
        PrivateFeatureState(settings).write(self.config,None)
        token=self.server.adapter_token;PrivateFeatureState(access).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=self.url,adapterToken=token),None)
        return dict(OVERTE_PHONE_FEATURE_AUDIO='1',OVERTE_E2E_VOICE_TESTS='1',OVERTE_E2E_RECORDED_PREVIEW_TESTS='1',
            OVERTE_PHONE_AUDIO_CONFIGURATION=str(settings),OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(access),
            OVERTE_E2E_FEATURE_FIXTURE_URL=self.url,OVERTE_DEVICE_ARTIFACT_DIR=str(self.artifacts),OVERTE_E2E_VOICE_PEER_STATE=str(self.pc))

    def test_public_triple_and_all_four_mandatory_foundations_are_registered_and_dispatched(self):
        fixture=self.adapter_fixture();settings=self.settings()
        with patch.dict(os.environ,settings),patch.object(fixture.adapter,'_audio_feature',return_value=self.primary) as make:
            caps=set(fixture.adapter.advertised_capabilities(fixture.target))
            self.assertEqual({'feature.audio.'+kind for kind in ('act','observe','cleanup')},{value for value in caps if value.startswith('feature.audio.')})
            catalog=json.loads((audio.ROOT/'tests/device/catalog.json').read_text())
            for name in FOUNDATIONS['audio']:
                row=next(row for row in catalog['modules'] if row['id']==name);self.assertLessEqual(set(row['requires']),caps)
            actual=fixture.adapter.invoke(bound.SELECTOR,'feature.audio.observe',dict(contractVersion=VERSION,runId=self.run,afterSequence=0))
            self.assertEqual('idle',actual['state']['phase']);make.assert_called_once_with(bound.SELECTOR,self.run)

    def test_disabled_or_missing_foundation_never_creates_a_partial_owner(self):
        fixture=self.adapter_fixture();settings=self.settings()
        with patch.dict(os.environ,settings|dict(OVERTE_PHONE_FEATURE_AUDIO='0')),patch.object(fixture.adapter,'_audio_feature') as make:
            self.assertFalse(any(value.startswith('feature.audio.') for value in fixture.adapter.advertised_capabilities(fixture.target)))
            with self.assertRaisesRegex(ValueError,'PHONE_AUDIO_FEATURE_NOT_ENABLED'):fixture.adapter.invoke(bound.SELECTOR,'feature.audio.observe',dict(contractVersion=VERSION,runId=self.run,afterSequence=0))
            make.assert_not_called()
        for change in (dict(OVERTE_E2E_VOICE_TESTS='0'),dict(OVERTE_E2E_RECORDED_PREVIEW_TESTS='0'),dict(OVERTE_PHONE_FEATURE_AUDIO='yes'),dict(OVERTE_PHONE_AUDIO_CONFIGURATION=''),dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG='')):
            with self.subTest(change=change),patch.dict(os.environ,settings|change),self.assertRaises((ValueError,RuntimeError,OSError)):fixture.adapter.advertised_capabilities(fixture.target)

    def test_configuration_cannot_learn_expected_facts_or_replace_its_original_private_source(self):
        fixture=self.adapter_fixture();settings=self.settings();store=PrivateFeatureState(Path(settings['OVERTE_PHONE_AUDIO_CONFIGURATION']));original=store.read()
        for value in (original|dict(audioConfigurationVersion=True),original|dict(expectedState={'phase':'completed'}),original|dict(peerClientSha256='bad'),original|dict(peerRunnerSha256=None),original|dict(domainId=str(__import__('uuid').UUID(int=0)))):
            store.write(value,store.read())
            with patch.dict(os.environ,settings),self.assertRaises((ValueError,RuntimeError,TypeError,OSError)):fixture.adapter.advertised_capabilities(fixture.target)

    def test_actor_read_only_gate_cannot_arm_release_toggle_prepare_voice_or_export_desired_state(self):
        request=secrets.token_hex(16)
        def call(action,inner=None):return dict(schemaVersion=1,commandId=request,action=action,**({} if inner is None else {'request':inner}))
        readonly_feature_command(call('phone-audio-fixture',dict(schemaVersion=1,commandId=request,operation='observe')))
        readonly_feature_command(call('phone-audio-ui',dict(schemaVersion=1,commandId=request,action='observe')))
        readonly_feature_command(call('voice-test',dict(schemaVersion=1,commandId=request,action='status')))
        for action in ('feature-recorded-audio-observe','feature-recorded-audio-files'):readonly_feature_command(call(action))
        cases=[call('phone-audio-fixture',dict(schemaVersion=1,commandId=request,operation='release')),
            call('phone-audio-ui',dict(schemaVersion=1,commandId=request,action='activate')),
            call('voice-test',dict(schemaVersion=1,commandId=request,action='reset')),call('feature-recorded-audio-release')]
        for value in cases:
            with self.subTest(action=value['action']),self.assertRaises((ValueError,RuntimeError)):readonly_feature_command(value)


if __name__=='__main__':unittest.main()
