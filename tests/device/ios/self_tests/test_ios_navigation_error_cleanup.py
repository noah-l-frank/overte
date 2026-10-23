"""Ordinary owned error dismissal under original cleanup phase authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.self_tests import test_ios_navigation_missing_actions as fixture


class NavigationErrorCleanupTests(unittest.TestCase):
    setUp=fixture.NavigationMissingActionsTests.setUp
    held=fixture.NavigationMissingActionsTests.held
    tick=fixture.NavigationMissingActionsTests.tick
    epoch=fixture.NavigationMissingActionsTests.epoch
    owner=fixture.NavigationMissingActionsTests.owner
    call=fixture.NavigationMissingActionsTests.call

    def ready(self):
        owner=self.owner();owner.navigate(self.call('navigate-missing'));owner.observe_missing();return owner

    def cleanup_call(self):return dict(self.call('cleanup'),iosNavigationCleanupCallVersion=1)

    def test_normal_ok_uses_real_cleanup_authority_and_preserves_legacy_active_writer(self):
        with self.held():
            owner=self.ready();self.assertEqual(2,owner.previous['iosNavigationMissingActionsVersion'])
            call=self.cleanup_call();self.assertEqual({'performed':True},owner.dismiss_cleanup(call))
            self.assertEqual(3,owner.previous['iosNavigationMissingActionsVersion'])
            self.assertEqual('cleanup',owner.state['dismiss']['fixture']['verb'])
            self.assertTrue(owner.observe_cleared()['ownedDialogDrained'])
            before=deepcopy(self.b.native_boundary.requests)
            self.assertEqual({'performed':True},self.owner().dismiss_cleanup(call))
            self.assertEqual(before,self.b.native_boundary.requests)

    def test_foreign_phase_prevents_even_the_first_cleanup_native_input(self):
        with self.held():
            owner=self.ready();call=self.cleanup_call();self.call('open');before=deepcopy(self.b.native_boundary.requests)
            with self.assertRaises(NativeUIError):owner.dismiss_cleanup(call)
            self.assertEqual(before,self.b.native_boundary.requests)

    def test_phase_cross_after_durable_ok_intent_cannot_send_a_pointer_command(self):
        with self.held():
            owner=self.ready();call=self.cleanup_call();write=owner.store.write;crossed=[]
            def save(value,previous):
                write(value,previous);state=unpack(value['payload'])[0]
                if state['dismiss'] is not None and state['dismiss']['intents'] and not crossed:
                    crossed.append(True);self.call('open')
            before=len(self.b.native_boundary.requests)
            with patch.object(owner.store,'write',side_effect=save),self.assertRaises(NativeUIError):owner.dismiss_cleanup(call)
            self.assertTrue(crossed)
            self.assertEqual([], [row for row in self.b.native_boundary.requests[before:] if row['operation']=='edit'])
            self.assertEqual('issued',unpack(owner.store.read()['payload'])[0]['dismiss']['phase'])

    def test_lost_ok_return_is_observed_drained_without_resending_cleanup_input(self):
        with self.held():
            owner=self.ready();call=self.cleanup_call();send=self.h.native.navigation_error_input
            def lost(**options):send(**options);raise OSError('Actual owned OK return lost')
            with patch.object(self.h.native,'navigation_error_input',side_effect=lost),self.assertRaises(OSError):owner.dismiss_cleanup(call)
            before=[row for row in self.b.native_boundary.requests if row['operation']=='edit'];again=self.owner()
            with self.assertRaises(NativeUIError):again.dismiss_cleanup(call)
            self.assertTrue(again.observe_cleared()['ownedDialogDrained'])
            self.assertEqual(before,[row for row in self.b.native_boundary.requests if row['operation']=='edit'])
