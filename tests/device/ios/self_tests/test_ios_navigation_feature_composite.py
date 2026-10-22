"""Ordinary directory selection closes only after actual new native arrival."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack
from feature_journeys.fixtures import context
from ios.self_tests.navigation_feature_observer_fixture import Whole


class NavigationFeatureCompositeTests(unittest.TestCase):
    def setUp(self):
        self.h=Whole(self);self.h.flow.prepare();self.h.flow.observe_active(0)
        self.h.open_directory();self.before=self.h.flow.observe_active(1)
    def call(self):
        h=self.h;inputs=dict(destination=context(h.run)['destination']);ticket=uuid.uuid4().hex
        h.harness.client.activate(ticket,'directory-select',inputs);h.gpu.marker=ticket
        return dict(contractVersion=16,runId=h.run,ticket=ticket,verb='directory-select',inputs=inputs,fixtureUrl=h.fixture.fixture_url)
    def test_directory_select_uses_normal_token_actual_B_pose_and_then_normal_tablet_close(self):
        h=self.h;call=self.call();self.assertEqual({'performed':True},h.flow.act(call))
        actual=h.flow.observe_active(self.before['sequence']);self.assertEqual('B',actual['state']['location'])
        self.assertFalse(actual['state']['panel']);self.assertEqual([],actual['state']['searchResults'])
        self.assertEqual(1,len([item for item in h.widget.edits if item['fieldToken']==
            next(item['token'] for item in h.widget.rows if item['id'].startswith('places.visit.'))]))
        edits=deepcopy(h.widget.edits);inputs=list(h.flow_fixture.b.inputs)
        self.assertEqual({'performed':True},h.flow_fixture.flow().act(call));self.assertEqual(edits,h.widget.edits)
        self.assertEqual(inputs,h.flow_fixture.b.inputs)
    def test_ignored_actual_motion_retains_original_not_ready_frame_and_never_reselects_on_recovery(self):
        h=self.h;h.ignore_motion=True;call=self.call()
        with self.assertRaises(NativeUIError):h.flow.act(call)
        self.assertEqual('places',h.flow_fixture.b.screen);edits=deepcopy(h.widget.edits)
        state=unpack(PrivateFeatureState(h.root/'ios-navigation-composite-actions.json').read()['payload'])[0]
        self.assertFalse(state['actions'][-1]['frames'][-1]['ready'])
        with self.assertRaises(NativeUIError):h.flow_fixture.flow().act(call)
        self.assertEqual(edits,h.widget.edits);self.assertEqual('places',h.flow_fixture.b.screen)
        h.ignore_motion=False;h.sync_navigation()
        self.assertEqual({'performed':True},h.flow_fixture.flow().act(call))
        self.assertEqual(edits,h.widget.edits);self.assertIsNone(h.flow_fixture.b.screen)
        after=unpack(PrivateFeatureState(h.root/'ios-navigation-composite-actions.json').read()['payload'])[0]
        self.assertEqual(state['actions'][0]['frames'][0],after['actions'][0]['frames'][0])
        self.assertTrue(after['actions'][-1]['frames'][-1]['ready'])


if __name__=='__main__':unittest.main()
