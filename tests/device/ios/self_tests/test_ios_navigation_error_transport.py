"""Actual SDK HTTP inside an error owner's live admission must not recurse."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.self_tests import test_ios_navigation_error_cleanup as cleanup
from ios.self_tests import test_ios_sdk_operation_guard as sdk_tests


class NavigationErrorTransportTests(unittest.TestCase):
    held=cleanup.NavigationErrorCleanupTests.held
    tick=cleanup.NavigationErrorCleanupTests.tick
    epoch=cleanup.NavigationErrorCleanupTests.epoch
    owner=cleanup.NavigationErrorCleanupTests.owner
    call=cleanup.NavigationErrorCleanupTests.call
    ready=cleanup.NavigationErrorCleanupTests.ready
    cleanup_call=cleanup.NavigationErrorCleanupTests.cleanup_call

    def setUp(self):
        cleanup.NavigationErrorCleanupTests.setUp(self)
        self.sdk=sdk_tests.SDKOperationGuardTests();self.sdk.setUp();self.addCleanup(self.sdk.doCleanups)

    def live_admission(self,owner):
        original=owner.admission.guard
        def check():
            self.sdk.send();return original()
        owner.admission.guard=check

    def test_normal_cleanup_ok_keeps_actual_nested_sdk_checks_and_remains_once_only(self):
        with self.held():
            owner=self.ready();self.live_admission(owner);call=self.cleanup_call()
            self.assertEqual({'performed':True},owner.dismiss_cleanup(call))
            self.assertTrue(owner.observe_cleared()['ownedDialogDrained']);self.assertTrue(self.sdk.requests)
            delivered=[row for row in self.b.native_boundary.requests if row['operation']=='edit']
            self.assertEqual({'performed':True},owner.dismiss_cleanup(call))
            self.assertEqual(delivered,[row for row in self.b.native_boundary.requests if row['operation']=='edit'])
            self.assertFalse(owner._transport_checking)

    def test_local_ownership_change_after_durable_intent_refuses_the_actual_ok_send(self):
        with self.held():
            owner=self.ready();self.live_admission(owner);call=self.cleanup_call();changed=[];write=owner.store.write
            owner.local_guard=lambda:not changed
            def saving(value,previous):
                write(value,previous);state=unpack(value['payload'])[0]
                if state['dismiss'] is not None and state['dismiss']['intents']:changed.append(True)
            before=[row for row in self.b.native_boundary.requests if row['operation']=='edit']
            with patch.object(owner.store,'write',side_effect=saving),self.assertRaises(NativeUIError):owner.dismiss_cleanup(call)
            self.assertTrue(changed);self.assertEqual(before,[row for row in self.b.native_boundary.requests if row['operation']=='edit'])
            self.assertEqual('issued',unpack(owner.store.read()['payload'])[0]['dismiss']['phase'])
            self.assertFalse(owner._transport_checking)


if __name__=='__main__':unittest.main()
