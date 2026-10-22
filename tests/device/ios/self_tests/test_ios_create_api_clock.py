"""Actual host budget boundaries, never native time/provenance substitutes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import create_api_clock as api,create_api_transport as channel


class CreateApiClockTests(unittest.TestCase):
    def test_nested_public_calls_share_the_original_deadline_and_reset_only_after_return(self):
        clock=[0.]
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):
            clock[0]=24.
            with api.scope(lambda:0.):api.check()
            clock[0]=25.
            api.check()
        with api.scope(lambda:clock[0]):api.check()
        api.check()
    def test_original_candidate_return_is_rechecked_before_any_following_transport(self):
        clock=[0.];calls=[]
        def candidate():clock[0]=25.;calls.append('candidate');return {'pid':42}
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):api.guarded(candidate)()
        self.assertEqual(['candidate'],calls)
    def test_boolean_nonfinite_and_backwards_host_clocks_fail_closed(self):
        for bad in (True,float('nan'),float('inf'),-1):
            with self.subTest(bad=bad),self.assertRaises(NativeUIError):
                with api.scope(lambda:bad):pass
        clock=[1.]
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):
            clock[0]=0.;api.check()
    def test_caught_expiry_cannot_relabel_the_same_operation_as_fresh(self):
        clock=[0.]
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):
            clock[0]=25.
            try:api.check()
            except NativeUIError:pass
            clock[0]=24.;api.check()

    def test_real_native_token_issued_before_slow_journal_return_is_not_sent_after_expiry(self):
        from ios.self_tests import test_ios_create_action_owner as fixture
        h=fixture.CreateActionOwnerTests();h.setUp();self.addCleanup(h.doCleanups)
        clock=[0.]
        with h.lock.held():
            owner=h.owner();owner.begin(fixture.QUERY);ui=h.ui(owner)
            ui.io.native=channel.CreateNativeInput.from_original(h.native)
            original=owner.before
            def durable(value):original(value);clock[0]=25.
            owner.before=durable
            with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):ui.input('create.tab.0')
            self.assertEqual('issued',h.owner().state['calls'][-1]['events'][-1]['phase'])
            self.assertFalse(any(row.get('operation')=='edit' for row in h.harness.native.commands))
    def test_real_native_transport_rechecks_after_slow_process_original_before_urlopen(self):
        from ios.self_tests import test_ios_create_controls as fixture
        h=fixture.IOSCreateControlsTests();h.setUp();self.addCleanup(h.doCleanups)
        native=channel.CreateNativeInput.from_original(h.flow.io.original.native);clock=[0.]
        observed=native.observe_process;before=list(h.native.commands)
        def delayed():value=observed();clock[0]=25.;return value
        native.observe_process=delayed
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):native.capture()
        self.assertEqual(before,h.native.commands)

    def test_actual_observation_hook_refuses_after_slow_serialization_before_any_http_or_afc(self):
        from unittest.mock import patch
        from ios.self_tests import test_ios_feature_observation as fixture
        h=fixture.FeatureObservationTests();h.setUp();self.addCleanup(h.doCleanups)
        clock=[0.];h.observer.before_send=api.check
        dumps=fixture.feature_observation.json.dumps
        def delayed(*args,**kwargs):value=dumps(*args,**kwargs);clock[0]=25.;return value
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]),patch.object(fixture.feature_observation.json,'dumps',side_effect=delayed):
            h.observer.read(0)
        self.assertEqual([],h.native.commands);self.assertEqual([],h.native.reads)

    def test_slow_actual_rez_intent_storage_prevents_even_the_first_control_post(self):
        from ios.self_tests import test_ios_create_rez_client as fixture
        h=fixture.CreateRezClientTests();h.setUp();self.addCleanup(h.doCleanups)
        clock=[0.]
        with h.lock.held():
            owner=h.owner();save=owner.save
            def delayed():save();clock[0]=25.
            owner.save=delayed
            with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):owner.request('set',allowed=False)
            self.assertEqual([],h.commands);self.assertEqual(0,h.harness.posts)
            self.assertIsNone(h.owner().state['commands'][-1]['original'])

    def test_create_budget_reaches_a_fresh_sdk_client_after_actual_slow_serialization(self):
        from unittest.mock import patch
        from ios.self_tests import test_ios_sdk_operation_guard as fixture
        h=fixture.SDKOperationGuardTests();h.setUp();self.addCleanup(h.doCleanups)
        clock=[0.];dumps=fixture.json.dumps
        def delayed(*args,**kwargs):value=dumps(*args,**kwargs);clock[0]=25.;return value
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]),patch('ios.adapters.appium_adapter.json.dumps',side_effect=delayed):
            fresh=fixture.WebDriver(h.driver.server_url)
            fresh.execute('existing','mobile: backgroundApp',dict(seconds=-1))
        self.assertEqual([],h.requests)
        self.assertEqual(dict(received=True),h.send());self.assertEqual(1,len(h.requests))

    def test_rez_actual_opener_preparation_cannot_deliver_after_the_original_deadline(self):
        from unittest.mock import patch
        from ios.adapters import create_rez_client
        from ios.self_tests import test_ios_create_rez_client as fixture
        h=fixture.CreateRezClientTests();h.setUp();self.addCleanup(h.doCleanups)
        clock=[0.];opened=[];build=create_rez_client.build_opener
        def delayed(*args):
            opener=build(*args);actual=opener.open;clock[0]=25.
            def opening(*args,**kwargs):opened.append(True);return actual(*args,**kwargs)
            opener.open=opening;return opener
        with h.lock.held():
            owner=h.owner()
            with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]),patch.object(create_rez_client,'build_opener',side_effect=delayed):
                owner.request('set',allowed=False)
            self.assertEqual([],opened);self.assertEqual([],h.commands);self.assertEqual(0,h.harness.posts)
            self.assertIsNone(h.owner().state['commands'][-1]['original'])

    def test_installed_entry_budget_starts_before_candidate_preflight_and_does_not_leak(self):
        from ios.self_tests import test_ios_sdk_operation_guard as fixture
        h=fixture.SDKOperationGuardTests();h.setUp();self.addCleanup(h.doCleanups)
        clock=[0.];calls=[]
        def original(adapter,selector,operation,values):
            calls.append('candidate');clock[0]=25.
            return h.send()
        wrapped=api.installed_entry(original,monotonic=lambda:clock[0])
        with self.assertRaises(NativeUIError):wrapped(object(),'existing','feature.create.act',{})
        self.assertEqual(['candidate'],calls);self.assertEqual([],h.requests)
        self.assertEqual(dict(received=True),wrapped(object(),'existing','feature.scripts.act',{}))
        self.assertEqual(1,len(h.requests))

    def test_w3c_request_at_the_expired_boundary_never_reaches_original_client(self):
        clock=[0.];calls=[]
        ui=channel.CreateNativeUI(SimpleNamespace(call=lambda *args:calls.append(args)),'original-session',lambda:True)
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):
            clock[0]=25.;ui._request('POST','/element/original/click',{})
        self.assertEqual([],calls)


if __name__=='__main__':unittest.main()
