"""Actual runtime receipt factory with explicit native/Web producer models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.avatar_final_domain import FinalDomain
from ios.self_tests.avatar_prepare_fixture import RUN
from self_tests import test_account_provider as tls


class AvatarRuntimeWorldlessWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):
        tls.AccountProviderTests.tearDownClass()
    def setUp(self):
        self.d = FinalDomain(self)
    def receipt(self, role):
        d = self.d
        owner = d.owners[role]
        return d.runtime._avatar_marker_web_receipts(role, d.client, RUN, role,
            d.scenes[role].root, owner.lock, fixture_url=owner.phase.fixture_url,
            epoch_ms=d.host, monotonic=lambda: d.clock[0])
    def test_both_actual_runtime_factories_observe_anonymous_web_without_a_world_getter(self):
        d = self.d
        for role in ('primary', 'actor'):
            with self.subTest(role=role), d.owners[role].held():
                self.assertFalse(d.natives[role].account['loggedIn'])
                def forbidden(*_args, **_kwargs):
                    raise AssertionError('Postlogout Web must not request a World/Avatar getter')
                with patch.object(d.scenes[role].domain, 'world', forbidden):
                    owner = self.receipt(role)
                    row = owner.capture()
                    packet = owner.packet(row)
                self.assertEqual('observed', row['status'])
                self.assertEqual(5, packet['packet']['iosWebClosureVersion'])
                self.assertEqual(RUN, packet['packet']['runId'])
                self.assertEqual(row['partial']['query']['commandId'], packet['packet']['commandId'])

    def test_missing_web_return_remains_owned_and_fresh_factory_does_not_resend_it(self):
        d = self.d
        with d.owners['primary'].held():
            owner = self.receipt('primary')
            with patch.object(owner.reader, 'original', side_effect=OSError('Explicit lost native Web return')), self.assertRaises(NativeUIError):
                owner.capture()
            query = deepcopy(owner.state['pending']['query'])
            self.assertIsNotNone(query)
            self.assertEqual([query], d.worldless_web_queries['primary'])
            owner = self.receipt('primary')
            owner.recover()
            self.assertEqual([query], d.worldless_web_queries['primary'])
            self.assertEqual('abandoned', owner.state['rows'][-1]['status'])
            self.assertEqual(query, owner.state['rows'][-1]['partial']['query'])
            fresh = owner.capture()
            self.assertNotEqual(query['commandId'], fresh['partial']['query']['commandId'])
            self.assertEqual(2, len(d.worldless_web_queries['primary']))


if __name__ == '__main__':
    unittest.main()
