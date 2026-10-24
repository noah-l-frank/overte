"""Original pre-send freshness stays strict without timing an already sent effect."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import check as transport_check
from ios.self_tests import test_ios_world_web_input as fixture


class WorldWebInputDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.test=fixture.WorldWebInputTests();self.test.setUp();self.addCleanup(self.test.doCleanups)
    def test_actual_final_transport_refuses_a_slow_before_send_without_issuing_or_replaying(self):
        t=self.test
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source);t.sdk.before_post=lambda:t.sdk.sleep(1.6)
            with self.assertRaises(NativeUIError):owner.perform(t.sdk.ticket,'late','tap','text')
            self.assertEqual([],t.sdk.posted);self.assertEqual('issued',owner.state['records'][0]['phase'])
            t.sdk.before_post=None;fresh=t.owner(t.sdk.owner(t.source_store,t.lock))
            with self.assertRaises(NativeUIError):fresh.perform(t.sdk.ticket,'late','tap','text')
            self.assertEqual([],t.sdk.posted)
    def test_successful_ordinary_post_that_returns_later_is_not_relabelled_as_unsent(self):
        t=self.test
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source);t.sdk.after_post=lambda:t.sdk.sleep(2.)
            row=owner.perform(t.sdk.ticket,'delivered','tap','text');self.assertEqual('returned',row['phase']);self.assertEqual(1,len(t.sdk.posted))
            current=source.frame(source.capture('fresh-independent-dom'))
            self.assertTrue(current['originals']['document']['source']['dom']['editor']['focused'])
    def test_final_transport_guard_has_no_candidate_io_recursion(self):
        t=self.test
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock)
            def candidate():transport_check();return True
            source.guard=candidate;owner=t.owner(source);owner.guard=candidate
            owner.perform(t.sdk.ticket,'guarded','tap','text');self.assertEqual(1,len(t.sdk.posted))


if __name__=='__main__':unittest.main()
