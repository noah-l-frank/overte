"""Whole call deadlines include real final HTTP/W3C transport boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_api_clock as api


class WorldWebAPIClockTests(unittest.TestCase):
    def test_scope_teardown_cannot_escape_the_original_deadline(self):
        from ios.adapters import world_web_keys
        clock=[0.]
        @contextmanager
        def delayed_exit():
            yield
            clock[0]=25.
        with patch.object(world_web_keys,'validation_round',delayed_exit):
            with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):api.check()
        self.assertFalse(api.active())
    def test_nested_calls_share_original_deadline_and_expiry_is_sticky(self):
        clock=[0.]
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):
            clock[0]=24.
            with api.scope(lambda:0.):api.check()
            clock[0]=25.
            try:api.check()
            except NativeUIError:pass
            clock[0]=24.;api.check()
        with api.scope(lambda:clock[0]):api.check()
    def test_actual_fresh_sdk_client_cannot_send_after_slow_serialization(self):
        from ios.self_tests import test_ios_sdk_operation_guard as fixture
        test=fixture.SDKOperationGuardTests();test.setUp();self.addCleanup(test.doCleanups);clock=[0.];dumps=fixture.json.dumps
        def delayed(*args,**kwargs):value=dumps(*args,**kwargs);clock[0]=25.;return value
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]),patch('ios.adapters.appium_adapter.json.dumps',side_effect=delayed):
            fixture.WebDriver(test.driver.server_url).execute('existing','mobile: backgroundApp',dict(seconds=-1))
        self.assertEqual([],test.requests);self.assertEqual(dict(received=True),test.send())
    def test_actual_observation_hook_refuses_after_slow_original_candidate_before_post(self):
        from ios.self_tests import test_ios_feature_observation as fixture
        test=fixture.FeatureObservationTests();test.setUp();self.addCleanup(test.doCleanups);clock=[0.]
        process=test.observer.observe_process
        def delayed():value=process();clock[0]=25.;return value
        test.observer.observe_process=delayed;test.observer.before_send=api.check
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):test.observer.read(0)
        self.assertEqual([],test.native.commands);self.assertEqual([],test.native.reads)
    def test_installed_entry_starts_before_candidate_preflight_and_unrelated_feature_is_unaffected(self):
        from ios.self_tests import test_ios_sdk_operation_guard as fixture
        test=fixture.SDKOperationGuardTests();test.setUp();self.addCleanup(test.doCleanups);clock=[0.]
        def original(*args):clock[0]=25.;return test.send()
        wrapped=api.installed_entry(original,monotonic=lambda:clock[0])
        with self.assertRaises(NativeUIError):wrapped(object(),'existing','feature.world-web.act',{})
        self.assertEqual([],test.requests);self.assertEqual(dict(received=True),wrapped(object(),'existing','feature.scripts.act',{}))
    def test_boolean_nonfinite_backward_and_slow_candidate_original_refuse(self):
        for value in (True,float('nan'),float('inf'),-1):
            with self.subTest(value=value),self.assertRaises(NativeUIError),api.scope(lambda:value):pass
        clock=[1.]
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):clock[0]=0.;api.check()
        def slow():clock[0]=26.;return {'pid':42}
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):api.guarded(slow)()


if __name__=='__main__':unittest.main()
