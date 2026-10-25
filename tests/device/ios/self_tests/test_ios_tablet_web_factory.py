"""Actual factory to existing-admission path, without input/session creation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_feature import IOSTabletWebFeature
from ios.self_tests import test_ios_tablet_web_runtime as fixtures
from ios.self_tests.test_ios_tablet_web_sources import RUN
from ios.self_tests.test_ios_tablet_web_documents import ORIGINS


class TabletFactoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.TabletWebRuntimeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;self.values=dict(artifactRoot=str(f.root),imagePolicy=dict(source='native-screen',marker=[0,0,128,32],subject=[0,40,160,90]),
            physicalBinding=deepcopy(f.fixture.binding),setupNative=deepcopy(f.fixture.setup),origins=deepcopy(ORIGINS))
    def make(self,value=None):
        return self.fixture.runtime._tablet_web_feature('private-existing-selector',RUN,role='primary',client=self.fixture.client,settings=value or self.values)
    def test_factory_performs_no_send_and_ordinary_entry_uses_actual_existing_admission(self):
        f=self.fixture;count=len(f.fixture.native.commands);feature=self.make()
        self.assertIsInstance(feature,IOSTabletWebFeature);self.assertEqual(count,len(f.fixture.native.commands))
        self.assertIsNone(feature.store.read())
        with feature.parts() as observer:
            self.assertEqual(f.fixture.binding,observer.admission['binding']);self.assertEqual(feature.screen['policy'],self.values['imagePolicy'])
            self.assertEqual('returned',observer.bootstrap.state['status'])
        self.assertEqual(count+1,len(f.fixture.native.commands));self.assertIsNone(feature.store.read())
    def test_foreign_policy_origin_candidate_and_setup_do_not_create_a_feature_owner(self):
        f=self.fixture;count=len(f.fixture.native.commands)
        for fault in ('source','origin','setup','binding'):
            value=deepcopy(self.values)
            if fault=='source':value['imagePolicy']['source']='world-render-target'
            elif fault=='origin':value['origins']['primary']='http://foreign.invalid'
            elif fault=='setup':value['setupNative']['processId']=43
            else:value['physicalBinding']['generation']+=1
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                feature=self.make(value)
                with feature.parts():pass
        self.assertEqual(count,len(f.fixture.native.commands));self.assertEqual([],list(f.root.glob('tabletweb-feature-*.json')))


if __name__=='__main__':unittest.main()
