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

    def test_first_process_journey_returns_via_owned_bookmark_on_a_new_actual_page_root(self):
        from ios.self_tests.navigation_feature_missing_fixture import MissingWidget
        h=self.h;MissingWidget(h,self);ctx=context(h.run);sequence=self.before['sequence']
        def action(verb,**inputs):
            nonlocal sequence
            ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,verb,inputs);h.gpu.marker=ticket
            call=dict(contractVersion=16,runId=h.run,ticket=ticket,verb=verb,inputs=inputs,fixtureUrl=h.fixture.fixture_url)
            self.assertEqual({'performed':True},h.flow.act(call))
            actual=h.flow.observe_active(sequence);sequence=actual['sequence'];return actual
        for verb,name in (('bookmark-add-cancel',ctx['name']),('bookmark-add',ctx['name']),
                ('bookmark-rename-cancel',ctx['renamed']),('bookmark-rename',ctx['renamed'])):
            actual=action(verb,name=name)
        self.assertEqual(ctx['renamed'],actual['state']['bookmarkName'])
        action('directory-search',query=ctx['hidden']);action('directory-search',query=ctx['name'])
        self.assertEqual('B',action('directory-select',destination=ctx['destination'])['state']['location'])
        self.assertEqual('not-found',action('navigate-missing')['state']['error'])
        self.assertFalse(action('dismiss-error')['state']['addressDialog'])
        h.flow_fixture.f.root_id='00000000-0000-4000-8000-000000000503'
        actual=action('bookmark-visit',name=ctx['renamed'])
        self.assertEqual('A',actual['state']['location']);self.assertFalse(actual['state']['panel'])
        self.assertEqual(ctx['renamed'],actual['state']['bookmarkName'])
        with h.flow.held():
            observer=h.observer();owner=observer.owners()[-1]
            self.assertEqual(actual['requestId'],owner.request)
            changed=observer.images.changed(owner.state['imageRow']['requestId'])
            self.assertGreaterEqual(changed['image']['subjectChangedFraction'],.05)
        self.assertEqual(1,h.flow_fixture.b.inputs.count('PhoneAddressCancelButton'))

    def test_replaced_open_root_without_new_surface_admission_cannot_authorize_an_input(self):
        h=self.h;before=deepcopy(h.widget.edits)
        h.model.pages[0]['rootId']='00000000-0000-4000-8000-000000000503'
        inputs=dict(name=context(h.run)['name']);ticket=uuid.uuid4().hex
        h.harness.client.activate(ticket,'bookmark-add',inputs)
        call=dict(contractVersion=16,runId=h.run,ticket=ticket,verb='bookmark-add',inputs=inputs,fixtureUrl=h.fixture.fixture_url)
        with self.assertRaises(NativeUIError):h.flow.act(call)
        self.assertEqual(before,h.widget.edits)


if __name__=='__main__':unittest.main()
