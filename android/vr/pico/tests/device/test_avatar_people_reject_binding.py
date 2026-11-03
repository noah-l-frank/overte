"""Canonical private reject route and retained Parent-3 peer resolution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch

from test_avatar_people_binding import AvatarPeopleBindingTests
from adapters.pico4.avatar_parent import PicoAvatarParent


class AvatarPeopleRejectBindingTests(AvatarPeopleBindingTests):
    def test_original_canonical_reject_and_parent3_history_keep_independent_peer(self):
        self.assertEqual(dict(performed=True), self.invoke(self.request('connection-request')))
        self.assertEqual(dict(performed=True), self.invoke(self.request('peer-reject')))
        final = self.original.rpc(operation='capture')
        self.assertEqual(['idle', 'idle'], [final[r]['state']['phase'] for r in ('primary', 'peer')])
        self.assertEqual([], final['posts'])
        record = self.original.parent.store.read()
        self.assertEqual(3, record['picoAvatarParentVersion'])
        self.assertTrue(self.adapter._avatar_parent_owned(self.f.target))
        self.assertFalse(any(c.startswith('feature.avatar-people.') for c in self.adapter.capabilities(self.f.target)))
        observed = []; original = PicoAvatarParent.observe
        def unavailable(parent, request):
            observed.append(parent.version)
            return original(parent, request)
        self.resolutions.clear()
        with patch.object(PicoAvatarParent, 'observe', unavailable), self.assertRaises(ValueError):
            self.adapter.invoke(self.f.target, 'feature.avatar-people.observe',
                dict(contractVersion=16, runId=self.original.parent.run, afterSequence=0))
        self.assertEqual([3], observed)
        self.assertEqual(['primary', 'peer'], self.resolutions[:2])
        self.assertEqual(record, self.original.parent.store.read())


def load_tests(loader, tests, pattern):
    # Existing canonical counters retain their existing selector exactly once.
    return unittest.TestSuite([AvatarPeopleRejectBindingTests(
        'test_original_canonical_reject_and_parent3_history_keep_independent_peer')])
