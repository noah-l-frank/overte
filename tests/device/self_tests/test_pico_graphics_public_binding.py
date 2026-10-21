"""Actual Pico public operation router with synthetic candidate/target SDKs.

The existing candidate fixture creates mock ZIP/JSON/tool output only. No build,
compiler, installation, device or service is invoked. Product/package/GUI/OS
boundaries remain simulations; the public dispatch and real owners execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import partial
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'android/vr/pico/tests/device'))
import test_native_execution_binding as native_fixture
from adapters.android.adapter import AndroidAdapter
from adapters.pico4 import graphics_journey as binding
from adapters.graphics_journey.feature import GraphicsFeature
from adapters.graphics_journey.fixture import GraphicsFixtureReader
from adapters.pico4.graphics_binding import PicoGraphicsBinding
from self_tests.test_pico_graphics_feature_stereo import Model,RUN


class PublicFixture:
    def __init__(self,test):
        self.model=Model();test.addCleanup(self.model.close);m=self.model
        self.native=native_fixture.NativeExecutionBindingTest();self.native.setUp();test.addCleanup(self.native.doCleanups)
        self.native.navigation_setup();self.original=self.native.instance()
        # Synthetic target SDKs replace only the existing package/GUI/OS/native
        # boundaries. The PicoBoundAdapter invoke/capability logic is unchanged.
        sdk=m.original_adapter;sdk.pico_configuration=(5038,m.root)
        for name,value in vars(sdk).items():
            if name!='invoke':setattr(self.original,name,value)
        m.original_adapter=self.original;m.flow=PicoGraphicsBinding(self.original,fixture_profile=binding.PICO_PROFILE)
        m.flow._script_file_io=m.script_io
        access=m.root/'adapter-access.json';access.write_text(json.dumps(dict(fixtureAdapterAccessVersion=1,
            fixtureUrl=m.client.url,adapterToken='b'*64)));access.chmod(0o600)
        self.environment=dict(OVERTE_PICO_FEATURE_GRAPHICS='1',OVERTE_PICO_FEATURE_SCRIPTS='0',OVERTE_PICO_FEATURE_AUTHENTICATION='0',
            OVERTE_PICO_NORMAL_SCRIPTS='1',OVERTE_DEVICE_ARTIFACT_DIR=str(m.root/'artifacts'),
            OVERTE_PICO_FEATURE_FIXTURE_CONFIG=str(access),OVERTE_E2E_FEATURE_FIXTURE_URL=m.client.url)
        test.enterContext(patch.dict(os.environ,self.environment))
        test.enterContext(patch.object(binding,'GraphicsFixtureReader',
            side_effect=lambda client,run:GraphicsFixtureReader(client,run,epoch_ms=lambda:m.native.epoch)))
        test.enterContext(patch.object(binding,'GraphicsFeature',partial(GraphicsFeature,
            monotonic=lambda:m.native.clock,sleep=m.native.sleep)))
        test.enterContext(patch('adapters.feature_fixture_access.client',side_effect=lambda *args,**kwargs:m.client))
        test.enterContext(patch.object(binding.PicoGraphicsJourney,'_script_file_io',side_effect=m.script_io))
        test.enterContext(patch.object(AndroidAdapter,'invoke',side_effect=m.invoke))
    def invoke(self,operation,values):return self.original.invoke('owned',operation,values)


class PicoGraphicsPublicBindingTests(unittest.TestCase):
    def setUp(self):self.fixture=PublicFixture(self);self.model=self.fixture.model
    def test_public_operations_are_an_explicit_three_operation_group_and_default_off(self):
        operations=set(self.fixture.original.capabilities('owned'))
        self.assertTrue(binding.OPERATIONS<=operations)
        with patch.dict(os.environ,dict(OVERTE_PICO_FEATURE_GRAPHICS='0')):
            self.assertFalse(binding.OPERATIONS&set(self.fixture.original.capabilities('owned')))
    def test_actual_public_router_uses_normal_controls_and_original_stereo_observation(self):
        m=self.model;observe=dict(contractVersion=16,runId=RUN,afterSequence=0)
        original=self.fixture.invoke('feature.graphics.observe',observe)
        self.fixture.invoke('feature.graphics.act',m.activate('open'))
        current=self.fixture.invoke('feature.graphics.observe',observe|dict(afterSequence=original['sequence']))
        self.assertFalse(original['state']['dialog']);self.assertTrue(current['state']['dialog'])
        self.assertEqual(2,len(current['artifacts']));self.assertTrue(m.native.inputs)
    def test_bad_configuration_and_replaced_candidate_stop_before_public_input(self):
        m=self.model;before=list(m.native.inputs)
        with patch.dict(os.environ,dict(OVERTE_E2E_FEATURE_READER_TOKEN='x'*64)),self.assertRaises(ValueError):
            self.fixture.invoke('feature.graphics.act',m.activate('open'))
        m.candidate=False
        with self.assertRaises(ValueError):self.fixture.invoke('feature.graphics.observe',dict(contractVersion=16,runId=RUN,afterSequence=0))
        self.assertEqual(before,m.native.inputs)


if __name__=='__main__':unittest.main()
