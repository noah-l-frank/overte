"""Whole preparation through real HTTPS, owned originals and Node marker code.

This qualifies preparation; it does not qualify the entire Avatar journey or
native execution. Qt/OS/renderer producers are explicitly modeled boundaries.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from ios.self_tests.avatar_prepare_fixture import PrepareDomain,RUN,TICKET
from self_tests import test_account_provider as tls


class AvatarPrepareComposedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    def test_actual_both_owned_accounts_then_both_untouched_frames_and_normal_scripts(self):
        d=PrepareDomain(self);primary,actor=d.owners['primary'],d.owners['actor']
        # The independent worker first signs in through its own normal login.
        with actor.held():actor.initialize();actor.login()
        original_sleep=primary.sleep;started=[]
        def schedule(seconds):
            if not started and primary.state is not None and primary.state['initial'] is not None:started.append(True);actor.prepare()
            original_sleep(seconds)
        primary.sleep=schedule
        primary.prepare()
        for role,owner in d.owners.items():
            with owner.held(paired=True):
                owner.load();self.assertEqual('ready',owner.state['phase']);self.assertEqual('bound',owner.state['sessions']['phase'])
                frame=owner.initial_original();self.assertLessEqual(frame['clockJoin']['hostAfterMonotonic'],d.scenes[role].scope.frames[0]['clockJoin']['hostBeforeMonotonic'])
                self.assertIsNotNone(owner.state['initialBarrier']);self.assertEqual('observed',owner.state['preparationClose']['phase'])
                self.assertFalse(owner.preparation_closed_original()['ui']['open'])
                self.assertTrue(d.natives[role].account['loggedIn']);self.assertEqual(1,d.natives[role].input_log.count('login.submit'))
                self.assertEqual(1,len(d.scenes[role].domain.vm['added']));self.assertEqual('local',d.scenes[role].domain.vm['added'][0]['host'])
        self.assertEqual('ready',d.server.avatar_accounts.snapshot(RUN)['phase'])
        self.assertEqual(2,sum(row['accountExists'] for row in d.server.avatar_accounts.snapshot(RUN)['accounts'].values()))
    def test_lost_actual_uikit_close_return_keeps_issued_ownership_without_replaying_login_or_close(self):
        from adapters.normal_ui import NativeUIError
        from ios.adapters.avatar_feature import AvatarFeaturePending
        d=PrepareDomain(self);owner=d.owners['primary'];native=d.natives['primary'];call=native.call;lost=[]
        def request(method,path,body=None):
            result=call(method,path,body)
            if method=='POST' and path.endswith('/click') and native.input_log[-1:] == ['OverteTabletClose'] and not lost:
                lost.append(True);raise OSError('Lost actual completed UIKit close return')
            return result
        native.call=request
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertFalse(native.shown);before=list(native.input_log)
        with owner.held():owner.load();self.assertEqual('issued',owner.state['preparationClose']['phase'])
        with self.assertRaises(AvatarFeaturePending):owner.prepare()
        self.assertEqual(before,native.input_log);self.assertEqual(1,before.count('login.submit'));self.assertEqual(1,before.count('OverteTabletClose'))

    def test_original_unowned_open_tablet_prevents_login_and_cannot_be_claimed_as_our_close(self):
        from adapters.normal_ui import NativeUIError
        d=PrepareDomain(self);owner=d.owners['primary'];native=d.natives['primary'];native.shown=True
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual([],native.input_log)
        with owner.held():owner.load();self.assertIsNone(owner.state['preparationClose']);self.assertEqual('preparing',owner.state['phase'])


if __name__=='__main__':unittest.main()
