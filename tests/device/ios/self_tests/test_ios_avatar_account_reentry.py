"""Completed account reentry uses real HTTPS/login originals without a new runtime.

Only the unrelated paired scene scheduling admission is explicitly modeled.
The stored login, OAuth/logout and preference restoration use their real owners.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters import avatar_operation_clock
from ios.self_tests import test_ios_avatar_login_owner as login


class AvatarAccountReentryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):login.AvatarLoginOwnerTests.setUpClass()
    @classmethod
    def tearDownClass(cls):login.AvatarLoginOwnerTests.tearDownClass()
    def setUp(self):
        self.f=login.AvatarLoginOwnerTests();self.addCleanup(self.f.doCleanups);self.f.setUp()

    def reentry(self,role):
        f=self.f
        if role=='actor':f.runtime=IOSAvatarRuntime(f.native.base())._avatar_login('owned',f.authority,role)
        owner=f.owner();owner.prepare();owner.login('1'*32)
        admitted=f.authority.read();f.client.activate('2'*32);owner.logout('2'*32)
        incomplete=deepcopy(owner.previous);owner.restore_preferences('2'*32);restored=deepcopy(owner.previous)
        self.assertEqual('revoking',f.server.avatar_accounts.revoke(f.run)['phase'])
        self.assertEqual('revoking',f.authority.read()['phase'])
        flow=object.__new__(IOSAvatarFeature);flow.runtime=IOSAvatarRuntime(f.native.base())
        flow.role,flow.selector,flow.run,flow.authority,flow.client=role,'owned',f.run,f.authority,f.client
        flow.lock=f.lock;flow.monotonic=lambda:f.native.clock;flow.epoch_ms=f.native.host_epoch;flow.sleep=f.native.sleep
        flow.requested_cleanup_clock=avatar_operation_clock.begin(flow.epoch_ms(),flow.monotonic());flow.final_read_clock=None
        flow.state=dict(bindings={role:deepcopy(owner.state['binding'])},sessions=dict(authority=admitted),
            cleanup=[dict(kind='scene',operationClock=deepcopy(flow.requested_cleanup_clock)),dict(kind='actor-scene',owner='modeled-paired-scheduling')])
        @contextmanager
        def held():
            with f.lock.held():yield
        flow.held=held;flow.load=lambda:f.lock.assert_held()
        flow.kept=lambda ref:ref
        flow.reader_history=lambda value,stage:self.assertEqual('modeled-paired-scheduling',value)
        ordering=[];flow.wait_primary_logout=lambda:ordering.append('modeled-prior-primary-logout')
        commands=list(f.native.commands);inputs=list(f.native.input_log)
        with patch.object(flow.runtime,'_avatar_login',side_effect=AssertionError('A restored original must not reconstruct live login')) as factory:
            flow.cleanup_account();flow.cleanup_account();factory.assert_not_called()
            self.assertEqual([],ordering)
            self.assertEqual(restored,owner.store.read())
            bad=deepcopy(owner.state);bad['binding']['processIdentity']=str(int(bad['binding']['processIdentity'])+1)
            corrupt=owner.envelope(bad);owner.store.write(corrupt,restored)
            with self.assertRaises(NativeUIError):flow.cleanup_account()
            factory.assert_not_called();owner.store.write(incomplete,corrupt)
        # A real earlier logged-out original is not upgraded by scheduling state.
        # The existing live factory still checks the actual revoked authority.
        with patch.object(flow.runtime,'_avatar_login',wraps=flow.runtime._avatar_login) as factory:
            with self.assertRaises(NativeUIError):flow.cleanup_account()
            factory.assert_called_once()
        self.assertEqual(commands,f.native.commands);self.assertEqual(inputs,f.native.input_log)

    def test_primary_actual_restored_original_survives_revocation_without_live_runtime_or_input(self):self.reentry('primary')
    def test_actor_actual_restored_original_survives_revocation_without_repeated_ordering_query(self):self.reentry('actor')


if __name__=='__main__':unittest.main()
