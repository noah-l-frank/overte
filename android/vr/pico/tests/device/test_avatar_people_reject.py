"""Normal two-Pal rejection through the original Parent/People owner.

The separate Pal VM originals execute; SDK/QML, clocks and transport remain
the existing explicitly modeled boundaries. No account/backend proof is made.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest

from test_avatar_people_owner import AvatarPeopleOwnerTests
from adapters.normal_ui import NativeUIError
from adapters.pico4.avatar_originals import AvatarOriginalFrames


class AvatarPeopleRejectTests(AvatarPeopleOwnerTests):
    def test_request_reject_both_close_and_original_role_quiet(self):
        self.act(self.request('connection-request'))
        original = self.rpc(operation='capture')
        request_id = original['primary']['state']['requestId']
        self.assertEqual(request_id, original['peer']['state']['requestId'])
        self.act(self.request('peer-reject'))
        final = self.rpc(operation='capture')
        self.assertEqual(['idle', 'idle'], [final[r]['state']['phase'] for r in ('primary', 'peer')])
        self.assertEqual([], final['posts'])
        self.assertEqual(0, final['timers'])
        actions = [r for r in final['controls'] if r['control'] in
                   ('people.ConnectionDecline', 'people.ConnectionCancel')]
        self.assertEqual([dict(role='peer', control='people.ConnectionDecline'),
                          dict(role='primary', control='people.ConnectionCancel'),
                          dict(role='peer', control='people.ConnectionCancel')], actions)
        owner = self.parent.people_instance
        self.assertEqual(request_id, owner.state['calls'][-1]['requestId'])
        self.assertIsNone(owner.state['pending'])
        self.assertEqual(2, owner.store.read()['picoAvatarPeopleVersion'])
        self.assertEqual(3, self.parent.store.read()['picoAvatarParentVersion'])
        owner.quiet_original(owner.state, owner.state['calls'][-1])
        before = {p: (p.read_bytes(), AvatarOriginalFrames.frame_stamp(p.stat()))
                  for p in self.f.root.glob('avatar-*.json')}
        reads = len(self.sent); parent = self.parent
        with self.f.lock.held():
            cold = type(parent)(parent.store, parent.binding, parent.phase, parent.lock,
                parent.urls, parent.favorites, parent.sources, parent.guard,
                people=parent.people_factory, monotonic=parent.monotonic)
        self.assertEqual(3, cold.version)
        self.assertEqual(2, cold.people_instance.version)
        self.assertEqual(parent.state, cold.state)
        self.assertEqual(reads, len(self.sent))
        self.assertEqual(before, {p: (p.read_bytes(), AvatarOriginalFrames.frame_stamp(p.stat()))
                                 for p in self.f.root.glob('avatar-*.json')})

    def test_lost_reject_result_remains_pending_without_a_second_input(self):
        self.act(self.request('connection-request'))
        self.ignore = 'people.ConnectionDecline'; self.stall_on_wait = True
        request = self.request('peer-reject')
        with self.assertRaises((ValueError, RuntimeError)):
            self.act(request)
        owner = self.parent.people_instance
        issued = list(owner.state['inputs'])
        self.assertEqual(1, sum(row['role'] == 'peer' and row['intent']['controlId'] ==
                               'people.ConnectionDecline' for row in issued))
        with self.assertRaises((ValueError, RuntimeError)):
            self.parent.execute_people(request)
        self.assertEqual(issued, owner.state['inputs'])
        self.assertEqual(request['ticket'], self.parent.state['pending'])
        self.assertEqual(request['ticket'], owner.state['pending'])

    def test_foreign_request_before_rejection_cannot_issue_peer_decline(self):
        self.act(self.request('connection-request'))
        self.replace_request_id = True
        request = self.request('peer-reject')
        with self.assertRaises((ValueError, RuntimeError)):
            self.act(request)
        self.assertFalse(any(row['ticket'] == request['ticket']
                             for row in self.parent.people_instance.state['inputs']))
        self.assertEqual(request['ticket'], self.parent.state['pending'])

    def test_delivered_decline_with_lost_ack_stays_owned_without_resending(self):
        self.act(self.request('connection-request'))
        original_rpc = self.rpc
        def lose_reply(**command):
            value = original_rpc(**command)
            if command.get('operation') == 'input' and command.get('control') == 'people.ConnectionDecline':
                self.rpc = original_rpc
                raise NativeUIError('Actual delivered normal peer input lost its acknowledgment')
            return value
        self.rpc = lose_reply
        request = self.request('peer-reject')
        with self.assertRaises((ValueError, RuntimeError)):
            self.act(request)
        owner = self.parent.people_instance
        original = original_rpc(operation='capture')
        self.assertEqual(['declined', 'declined'], [original[r]['state']['phase'] for r in ('primary', 'peer')])
        with self.f.lock.held():
            record = owner.role_record('peer')
        self.assertEqual(1, sum(row['ticket'] == request['ticket'] for row in record['inputs']))
        self.assertIsNotNone(record['inputs'][-1]['command'])
        self.assertFalse(any(row['ticket'] == request['ticket'] for row in owner.state['inputs']))
        with self.assertRaises((ValueError, RuntimeError)):
            self.parent.execute_people(request)
        final = original_rpc(operation='capture')
        self.assertEqual(1, sum(row['control'] == 'people.ConnectionDecline' for row in final['controls']))
        self.assertEqual(request['ticket'], owner.state['pending'])


def load_tests(loader, tests, pattern):
    # Keep inherited legacy tests in their existing selector exactly once.
    names = sorted(name for name in AvatarPeopleRejectTests.__dict__ if name.startswith('test_'))
    return unittest.TestSuite(AvatarPeopleRejectTests(name) for name in names)
