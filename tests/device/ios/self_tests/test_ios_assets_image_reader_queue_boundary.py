"""Declared bridge identity/order/gate boundaries; native C++ remains unexecuted."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import weakref


class Resource:
    pass


class Context:
    def __init__(self, owner, task, dispatch, resource_id, receiver):
        self.owner, self.task, self.dispatch = owner, task, dispatch
        self.resource_id, self.receiver = resource_id, weakref.ref(receiver)


class Bridge:
    def __init__(self, api=True, marker=True, runtime=True, limit=256):
        self.available = api and marker and runtime
        self.failed = not self.available
        self.limit = limit
        self.entries = {}
        self.source1_owner = None

    def begin(self, context, actual_target, method):
        if self.failed:
            return False
        if (context.receiver() is not actual_target or method != 37 or len(self.entries) == self.limit
                or not context.owner or (self.source1_owner is not None and self.source1_owner != context.owner)):
            self.failed = True
            return False
        if context.dispatch in self.entries:
            self.failed = True
            return False
        self.entries[context.dispatch] = dict(context=context, method=method, event=None,
                                             phases=[], receiver_id=None, accepted=None)
        self.source1_owner = context.owner
        return True

    def snapshot(self):
        if self.failed or self.source1_owner is None:
            return None
        return dict(source1Instance=self.source1_owner, dispatches=tuple(self.entries))

    def phase(self, dispatch, event, method, phase, actual_target=None):
        if self.failed:
            return False
        row = self.entries.get(dispatch)
        if not row or row['method'] != method or phase in row['phases']:
            self.failed = True
            return False
        if phase == 'created':
            if row['event'] is not None or any(r['event'] == event for r in self.entries.values()):
                self.failed = True
                return False
            row['event'] = event
        elif row['event'] != event:
            self.failed = True
            return False
        if phase == 'destroyed':
            if actual_target is not None or ('entered' in row['phases'] and 'returned' not in row['phases']):
                self.failed = True
                return False
        elif row['context'].receiver() is None or row['context'].receiver() is not actual_target:
            self.failed = True
            return False
        if phase == 'entered' and ('created' not in row['phases'] or 'destroyed' in row['phases']):
            self.failed = True
            return False
        if phase == 'returned' and 'entered' not in row['phases']:
            self.failed = True
            return False
        row['phases'].append(phase)
        return True

    def receive(self, event, actual_target, owner, resource_id, receiver_id):
        if self.failed or not event:
            return False
        found = [r for r in self.entries.values() if r['event'] == event]
        if len(found) != 1:
            self.failed = True
            return False
        row = found[0]
        context = row['context']
        if (context.receiver() is not actual_target or context.owner != owner
                or context.resource_id != resource_id or row['receiver_id'] is not None
                or 'entered' not in row['phases']):
            self.failed = True
            return False
        row['receiver_id'] = receiver_id
        return True

    def invoke_returned(self, dispatch, event, accepted):
        row = self.entries[dispatch]
        if self.failed or row['event'] != event or (event and not accepted) or row['accepted'] is not None:
            self.failed = True
            return False
        row['accepted'] = accepted
        return True


class BridgeBoundaryModels(unittest.TestCase):
    def test_standalone_cpp_gets_public_qt_platform_detection_before_its_gate(self):
        # Static integration guard only: no C++ preprocessing/compilation is run.
        from pathlib import Path
        root = Path(__file__).resolve().parents[4]
        directory = root / 'libraries/material-networking/src/material-networking'
        header = (directory / 'IOSAssetsImageReaderQueueObservation.h').read_text()
        cpp = (directory / 'IOSAssetsImageReaderQueueObservation.cpp').read_text()
        first_include = next(line for line in cpp.splitlines() if line.startswith('#include'))
        self.assertEqual(first_include, '#include "IOSAssetsImageReaderQueueObservation.h"')
        platform_gate = header.index('#if defined(Q_OS_IOS)')
        self.assertIn('#include <QtCore/qglobal.h>', header[:platform_gate])
        self.assertNotIn('QtCore/private/', header[:platform_gate])
        old_header = header.replace('#include <QtCore/qglobal.h>\n', '', 1)
        self.assertNotIn('#include <QtCore/qglobal.h>', old_header[:old_header.index('#if defined(Q_OS_IOS)')])

    def setup_entry(self, bridge=None, dispatch='native-dispatch-A', receiver=None):
        bridge = bridge or Bridge()
        receiver = receiver or Resource()
        context = Context('native-owner', 'native-task', dispatch, 'native-resource', receiver)
        self.assertTrue(bridge.begin(context, receiver, 37))
        return bridge, context, receiver

    def test_absent_api_marker_runtime_or_unknown_source1_parent_stays_unavailable(self):
        admitted = Bridge()
        self.assertTrue(admitted.available)
        self.assertIsNone(admitted.snapshot(), 'Admission alone is not a complete Source1 parent')
        receiver = Resource()
        actual = Context('native-owner', 'native-task', 'native-dispatch', 'native-resource', receiver)
        self.assertTrue(admitted.begin(actual, receiver, 37))
        self.assertEqual(admitted.snapshot()['source1Instance'], 'native-owner')
        old = dict(assetImageReaderHistoryVersion=1, queuedReceiverAttributionAvailable=False)
        for kwargs in ({'api': False}, {'marker': False}, {'runtime': False}):
            with self.subTest(kwargs=kwargs):
                bridge = Bridge(**kwargs)
                receiver = Resource()
                context = Context('owner', 'task', 'dispatch', 'resource', receiver)
                self.assertFalse(bridge.begin(context, receiver, 37))
                self.assertEqual(bridge.entries, {})
                self.assertIsNone(bridge.snapshot())
                self.assertEqual(old, dict(assetImageReaderHistoryVersion=1, queuedReceiverAttributionAvailable=False))

    def test_actual_event_distinguishes_reversed_equal_payload_sources(self):
        bridge, first, receiver = self.setup_entry()
        second = Context(first.owner, first.task, 'native-dispatch-B', first.resource_id, receiver)
        self.assertTrue(bridge.begin(second, receiver, 37))
        self.assertTrue(bridge.phase(first.dispatch, 1, 37, 'created', receiver))
        self.assertTrue(bridge.phase(second.dispatch, 2, 37, 'created', receiver))
        # Payload equality is intentionally not an input to any bridge method.
        for context, event in ((second, 2), (first, 1)):
            self.assertTrue(bridge.phase(context.dispatch, event, 37, 'entered', receiver))
            self.assertTrue(bridge.receive(event, receiver, context.owner, context.resource_id, str(event)))
        self.assertEqual(bridge.entries[first.dispatch]['receiver_id'], '1')
        self.assertEqual(bridge.entries[second.dispatch]['receiver_id'], '2')

    def test_actual_foreign_receiver_method_resource_or_owner_refuses(self):
        for kind in ('receiver', 'method', 'resource', 'owner'):
            with self.subTest(kind=kind):
                bridge, context, receiver = self.setup_entry()
                foreign = Resource()
                if kind == 'method':
                    self.assertFalse(bridge.phase(context.dispatch, 1, 38, 'created', receiver))
                else:
                    self.assertTrue(bridge.phase(context.dispatch, 1, 37, 'created', receiver))
                    self.assertTrue(bridge.phase(context.dispatch, 1, 37, 'entered', receiver))
                    self.assertFalse(bridge.receive(1, foreign if kind == 'receiver' else receiver,
                        'foreign' if kind == 'owner' else context.owner,
                        'foreign' if kind == 'resource' else context.resource_id, 'actual-receiver'))
                self.assertTrue(bridge.failed)

    def test_queue_can_return_and_destroy_arguments_before_invoke_method_returns(self):
        bridge, context, receiver = self.setup_entry()
        for phase in ('created', 'entered', 'returned'):
            self.assertTrue(bridge.phase(context.dispatch, 1, 37, phase, receiver))
        self.assertTrue(bridge.phase(context.dispatch, 1, 37, 'destroyed'))
        self.assertIsNone(bridge.entries[context.dispatch]['accepted'])
        self.assertTrue(bridge.invoke_returned(context.dispatch, 1, True))
        self.assertFalse(bridge.failed)

    def test_cancelled_event_destruction_does_not_invent_receiver_or_delivery(self):
        bridge, context, receiver = self.setup_entry()
        self.assertTrue(bridge.phase(context.dispatch, 1, 37, 'created', receiver))
        self.assertTrue(bridge.phase(context.dispatch, 1, 37, 'destroyed'))
        self.assertEqual(bridge.entries[context.dispatch]['phases'], ['created', 'destroyed'])
        self.assertIsNone(bridge.entries[context.dispatch]['receiver_id'])

    def test_unobserved_nested_event_is_not_rebound_and_duplicate_receiver_fails(self):
        bridge, context, receiver = self.setup_entry()
        self.assertTrue(bridge.phase(context.dispatch, 1, 37, 'created', receiver))
        self.assertTrue(bridge.phase(context.dispatch, 1, 37, 'entered', receiver))
        self.assertFalse(bridge.receive(0, receiver, context.owner, context.resource_id, 'unobserved'))
        self.assertFalse(bridge.failed)
        self.assertTrue(bridge.receive(1, receiver, context.owner, context.resource_id, 'actual'))
        self.assertFalse(bridge.receive(1, receiver, context.owner, context.resource_id, 'second'))
        self.assertTrue(bridge.failed)

    def test_capacity_failure_is_sticky_and_weak_resource_cannot_resurrect(self):
        for kind in ('cap', 'weak'):
            with self.subTest(kind=kind):
                bridge, context, receiver = self.setup_entry(Bridge(limit=1))
                if kind == 'cap':
                    other = Context(context.owner, context.task, 'other', context.resource_id, receiver)
                    self.assertFalse(bridge.begin(other, receiver, 37))
                else:
                    self.assertTrue(bridge.phase(context.dispatch, 1, 37, 'created', receiver))
                    original = weakref.ref(receiver)
                    del receiver
                    self.assertIsNone(original())
                    self.assertFalse(bridge.phase(context.dispatch, 1, 37, 'entered', Resource()))
                self.assertTrue(bridge.failed)


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
