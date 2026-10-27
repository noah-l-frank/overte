"""Declared event-boundary counterexamples; this does not execute Qt/C++."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import gc
import unittest
import weakref


class Receiver:
    pass


class Payload:
    pass


class Event:
    def __init__(self, identity, invocation, receiver, method, payload):
        self.identity = identity
        self.invocation = invocation
        self.receiver = weakref.ref(receiver)
        self.method = method
        self.arguments = [payload]
        self.destroyed = False


class DeclaredBoundary:
    """Counterexample model only; it supplies no authority for native C++ results."""
    def __init__(self, observer=lambda record: True, limit=256):
        self.observer, self.limit = observer, limit
        self.failed = False
        self.bindings = []
        self.current = None
        self.records = []
        self.sequence = 0
        self.inside_callback = False

    def emit(self, event, phase, actual_receiver=None):
        if self.failed or not event.identity:
            return
        if self.inside_callback:
            self.failed = True
            return
        self.inside_callback = True
        record = (event.identity, event.invocation, phase, actual_receiver)
        try:
            if not self.observer(record):
                self.failed = True
            else:
                self.records.append(record[:3] + (weakref.ref(actual_receiver)
                                    if actual_receiver is not None else None,))
        except Exception:
            self.failed = True
        finally:
            self.inside_callback = False

    @contextmanager
    def bind(self, receiver, method, invocation):
        if len(self.bindings) == 16:
            self.failed = True
            yield
            return
        value = [weakref.ref(receiver), method, invocation, False, False]
        self.bindings.append(value)
        try:
            yield
        finally:
            if not self.bindings or self.bindings[-1] is not value:
                self.failed = True
            else:
                self.bindings.pop()

    def create(self, receiver, method, payload, copy_arguments=lambda: None):
        identity, invocation = 0, None
        claimed = None
        if not self.failed and self.bindings:
            binding = self.bindings[-1]
            if binding[0]() is receiver and binding[1] == method and not binding[4]:
                binding[4] = True
                claimed = binding
        # Actual Qt model boundary: metatype registration/copy can call product code.
        copy_arguments()
        if not self.failed and claimed is not None:
            binding = claimed
            if self.bindings and self.bindings[-1] is binding:
                if binding[3] or self.sequence == self.limit:
                    self.failed = True
                else:
                    binding[3] = True
                    self.sequence += 1
                    identity, invocation = self.sequence, binding[2]
        event = Event(identity, invocation, receiver, method, payload)
        self.emit(event, 'created', receiver)
        return event

    @contextmanager
    def delivery(self, event, receiver):
        previous = self.current
        self.current = event if event.identity and event.receiver() is receiver else None
        if event.identity and event.receiver() is not receiver:
            self.failed = True
        self.emit(event, 'entered', receiver)
        try:
            yield
        except Exception:
            self.emit(event, 'unwound', receiver)
            raise
        else:
            self.emit(event, 'returned', receiver)
        finally:
            self.current = previous

    def identity(self, receiver):
        if self.failed or self.inside_callback or not self.current:
            return 0
        return self.current.identity if self.current.receiver() is receiver else 0

    def destroy_arguments(self, event):
        event.arguments.clear()
        event.destroyed = True
        self.emit(event, 'argumentsDestroyed')

    def snapshot(self):
        return None if self.failed else tuple(self.records)


class DeclaredBoundaryTests(unittest.TestCase):
    def make_event(self, model, receiver, invocation, payload=None):
        with model.bind(receiver, 37, invocation):
            return model.create(receiver, 37, payload)

    def test_reversed_equal_payload_events_keep_actual_distinct_identity(self):
        model, receiver, payload = DeclaredBoundary(), Receiver(), Payload()
        first = self.make_event(model, receiver, 'native-invocation-A', payload)
        second = self.make_event(model, receiver, 'native-invocation-B', payload)
        self.assertIs(first.arguments[0], second.arguments[0])
        observed = []
        for event in (second, first):
            with model.delivery(event, receiver):
                observed.append((model.identity(receiver), event.invocation))
        self.assertEqual(observed, [(2, 'native-invocation-B'), (1, 'native-invocation-A')])

    def test_foreign_target_or_method_cannot_consume_actual_binding(self):
        model, receiver, foreign = DeclaredBoundary(), Receiver(), Receiver()
        with model.bind(receiver, 37, 'actual'):
            self.assertEqual(model.create(foreign, 37, None).identity, 0)
            self.assertEqual(model.create(receiver, 38, None).identity, 0)
            self.assertEqual(model.create(receiver, 37, None).identity, 1)

    def test_nested_unobserved_metacall_masks_outer_identity(self):
        model, receiver = DeclaredBoundary(), Receiver()
        observed = self.make_event(model, receiver, 'actual')
        unrelated = model.create(receiver, 37, None)
        with model.delivery(observed, receiver):
            self.assertEqual(model.identity(receiver), 1)
            with model.delivery(unrelated, receiver):
                self.assertEqual(model.identity(receiver), 0)
            self.assertEqual(model.identity(receiver), 1)

    def test_cancelled_event_argument_destruction_does_not_imply_delivery(self):
        model, receiver = DeclaredBoundary(), Receiver()
        event = self.make_event(model, receiver, 'cancelled')
        model.destroy_arguments(event)
        self.assertEqual([item[2] for item in model.snapshot()], ['created', 'argumentsDestroyed'])

    def test_slot_return_keeps_real_python_payload_alive_until_argument_drop(self):
        model, receiver, payload = DeclaredBoundary(), Receiver(), Payload()
        original = weakref.ref(payload)
        event = self.make_event(model, receiver, 'actual', payload)
        del payload
        with model.delivery(event, receiver):
            pass
        self.assertIsNotNone(original())
        self.assertFalse(event.destroyed)
        self.assertNotIn('argumentsDestroyed', [item[2] for item in model.snapshot()])
        model.destroy_arguments(event)
        gc.collect()
        self.assertIsNone(original())
        self.assertTrue(event.destroyed)

    def test_receiver_weak_expiry_and_product_unwind_are_not_normal_return(self):
        model, receiver = DeclaredBoundary(), Receiver()
        event = self.make_event(model, receiver, 'actual')
        with self.assertRaisesRegex(RuntimeError, 'product failure'):
            with model.delivery(event, receiver):
                raise RuntimeError('product failure')
        self.assertEqual([item[2] for item in model.snapshot()], ['created', 'entered', 'unwound'])
        original = weakref.ref(receiver)
        del receiver
        gc.collect()
        self.assertIsNone(original())
        self.assertIsNone(event.receiver())

    def test_callback_false_or_throw_hides_previously_good_receipt_forever(self):
        for kind in ('false', 'throw'):
            with self.subTest(kind=kind):
                model, receiver = DeclaredBoundary(), Receiver()
                event = self.make_event(model, receiver, 'first-good')
                self.assertTrue(model.snapshot())
                def reject(record):
                    if kind == 'throw':
                        raise MemoryError('diagnostic allocation failed')
                    return False
                model.observer = reject
                with model.delivery(event, receiver):
                    self.assertEqual(model.identity(receiver), 0)
                model.observer = lambda record: True
                self.assertIsNone(model.snapshot())

    def test_event_cap_and_reentrant_callback_fail_closed(self):
        for kind in ('cap', 'reentrant'):
            with self.subTest(kind=kind):
                model, receiver = DeclaredBoundary(limit=1), Receiver()
                if kind == 'cap':
                    self.make_event(model, receiver, 'A')
                    self.make_event(model, receiver, 'B')
                else:
                    def observer(record):
                        model.emit(event, 'reentrant', receiver)
                        return True
                    event = self.make_event(model, receiver, 'A')
                    model.observer = observer
                    with model.delivery(event, receiver):
                        pass
                self.assertIsNone(model.snapshot())

    def test_reentrant_metatype_copy_cannot_steal_outer_claim_even_if_outer_copy_throws(self):
        for throws in (False, True):
            with self.subTest(throws=throws):
                model, receiver, payload = DeclaredBoundary(), Receiver(), Payload()
                nested = []
                def copy_arguments():
                    nested.append(model.create(receiver, 37, payload))
                    if throws:
                        raise MemoryError('product metatype copy failed')
                with model.bind(receiver, 37, 'actual-outer-invocation'):
                    if throws:
                        with self.assertRaisesRegex(MemoryError, 'product metatype'):
                            model.create(receiver, 37, payload, copy_arguments)
                        self.assertEqual(model.snapshot(), ())
                    else:
                        outer = model.create(receiver, 37, payload, copy_arguments)
                        self.assertEqual((outer.identity, outer.invocation),
                                         (1, 'actual-outer-invocation'))
                self.assertEqual(nested[0].identity, 0)
        model, receiver = DeclaredBoundary(), Receiver()
        legitimate_inner = []
        def own_inner_scope():
            legitimate_inner.append(self.make_event(model, receiver, 'actual-inner-invocation'))
        with model.bind(receiver, 37, 'actual-outer-invocation'):
            outer = model.create(receiver, 37, None, own_inner_scope)
        self.assertEqual((legitimate_inner[0].identity, outer.identity), (1, 2))
        self.assertEqual((legitimate_inner[0].invocation, outer.invocation),
                         ('actual-inner-invocation', 'actual-outer-invocation'))


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
