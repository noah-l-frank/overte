"""Original active 404/modal/OK/address closure across full source capture."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from ios.self_tests.navigation_feature_observer_fixture import Whole
from ios.self_tests.navigation_feature_missing_fixture import MissingWidget


class NavigationFeatureMissingTests(unittest.TestCase):
    def setUp(self):
        self.h=Whole(self);self.widget=MissingWidget(self.h,self);self.h.flow.prepare()
        self.first=self.h.flow.observe_active(0)
    def call(self,verb):
        h=self.h;ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,verb,{});h.gpu.marker=ticket
        return dict(contractVersion=16,runId=h.run,ticket=ticket,verb=verb,inputs={},fixtureUrl=h.fixture.fixture_url)
    def missing(self):
        self.h.flow.act(self.call('navigate-missing'));return self.h.flow.observe_active(self.first['sequence'])
    def test_real_missing_and_ok_keep_owned_error_original_then_cancel_same_address_root(self):
        h=self.h;measured=self.missing();self.assertEqual('not-found',measured['state']['error'])
        self.assertTrue(measured['state']['addressDialog']);call=self.call('dismiss-error')
        self.assertEqual({'performed':True},h.flow.act(call));actual=h.flow.observe_active(measured['sequence'])
        self.assertEqual('none',actual['state']['error']);self.assertFalse(actual['state']['addressDialog'])
        again=h.flow_fixture.flow().observe_active(actual['sequence']);self.assertEqual('none',again['state']['error'])
        self.assertEqual(1,h.flow_fixture.b.inputs.count('PhoneAddressCancelButton'))
        before=list(h.flow_fixture.b.inputs);commands=deepcopy(h.flow_fixture.b.native_boundary.requests)
        self.assertEqual({'performed':True},h.flow_fixture.flow().act(call))
        self.assertEqual(before,h.flow_fixture.b.inputs);self.assertEqual(commands,h.flow_fixture.b.native_boundary.requests)
    def test_ignored_go_never_derives_requested_failure_or_permits_dismissal(self):
        self.widget.ignore=True;h=self.h;actual=self.missing()
        self.assertEqual('none',actual['state']['error']);self.assertFalse(actual['state']['addressDialog'])
        before=list(h.flow_fixture.b.inputs)
        with self.assertRaises(NativeUIError):h.flow.act(self.call('dismiss-error'))
        self.assertEqual(before,h.flow_fixture.b.inputs)
    def test_retained_listener_prevents_address_cancel_after_acknowledged_ok(self):
        h=self.h;self.missing();self.widget.partial_destroy=True;call=self.call('dismiss-error')
        with self.assertRaises(NativeUIError):h.flow.act(call)
        self.assertNotIn('PhoneAddressCancelButton',h.flow_fixture.b.inputs)
        edits=[row for row in h.flow_fixture.b.native_boundary.requests if row['operation']=='edit']
        self.widget.partial_destroy=False;h.dialogs.destroy(dialog=False,listener=True)
        self.assertEqual({'performed':True},h.flow_fixture.flow().act(call))
        after=[row for row in h.flow_fixture.b.native_boundary.requests if row['operation']=='edit']
        self.assertEqual(edits,after);self.assertEqual(1,h.flow_fixture.b.inputs.count('PhoneAddressCancelButton'))

    def test_lost_ok_return_keeps_issued_input_and_uses_genuine_drained_outcome_without_resend(self):
        from adapters.script_feature.history import unpack
        from adapters.normal_feature_state import PrivateFeatureState
        h=self.h;self.missing();native=h.sources['ui'];send=native.navigation_error_input
        def lost(**kwargs):send(**kwargs);raise OSError('Lost real OK return')
        native.navigation_error_input=lost;call=self.call('dismiss-error')
        with self.assertRaises(OSError):h.flow.act(call)
        edits=[row for row in h.flow_fixture.b.native_boundary.requests if row['operation']=='edit']
        self.assertEqual({'performed':True},h.flow_fixture.flow().act(call))
        self.assertEqual(edits,[row for row in h.flow_fixture.b.native_boundary.requests if row['operation']=='edit'])
        state=unpack(PrivateFeatureState(h.root/'ios-navigation-missing-actions.json').read()['payload'])[0]
        self.assertEqual('issued',state['dismiss']['phase']);self.assertIsNotNone(state['cleared'])
        self.assertEqual(1,h.flow_fixture.b.inputs.count('PhoneAddressCancelButton'))


if __name__=='__main__':unittest.main()
