"""Declared callback lifetime/lock counterexamples; no native bridge execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import gc
import threading
import unittest
import weakref


class TrackedMutex:
    def __init__(self):
        self.lock = threading.Lock()
        self.owner = None

    def __enter__(self):
        self.lock.acquire()
        self.owner = threading.get_ident()
        return self

    def __exit__(self, *unused):
        self.owner = None
        self.lock.release()


class State:
    def __init__(self):
        self.mutex = TrackedMutex()
        self.records = ['prior-good-prefix']


class Registry:
    """Python strong local references model an atomic shared_ptr pin, not its ABI."""
    def __init__(self):
        self.published = State()
        self.failed = False
        self.qt_disabled = False
        self.slot_lock = threading.Lock()

    def acquire(self):
        with self.slot_lock:
            return self.published

    def disarm(self):
        self.failed = True
        with self.slot_lock:
            retired, self.published = self.published, None
        if retired and retired.mutex.owner == threading.get_ident():
            raise AssertionError('Qt API under registry mutex')
        self.qt_disabled = True
        # No waiting/drain; in-flight callbacks own their independent local pin.

    def callback(self, pinned, proceed, outputs):
        pin = self.acquire()
        pinned.set()
        if not pin:
            outputs.append(False)
            return
        with pin.mutex:
            if not proceed.wait(1):
                outputs.append('model harness did not release callback')
                return
            if self.failed:
                outputs.append(False)
                return
            pin.records.append('callback')
        outputs.append(not self.failed)


class TeardownModels(unittest.TestCase):
    def finish(self, thread):
        thread.join(1)
        self.assertFalse(thread.is_alive(), 'Bounded model thread did not terminate')

    def test_disarm_preserves_already_running_callback_state_until_it_returns(self):
        registry = Registry()
        original = weakref.ref(registry.published)
        pinned, proceed = threading.Event(), threading.Event()
        outputs = []
        thread = threading.Thread(target=registry.callback, args=(pinned, proceed, outputs))
        thread.start()
        self.assertTrue(pinned.wait(1))
        registry.disarm()
        gc.collect()
        self.assertIsNotNone(original(), 'In-flight callback lost its State pin')
        self.assertTrue(registry.qt_disabled)
        self.assertIsNone(registry.published)
        proceed.set()
        self.finish(thread)
        gc.collect()
        self.assertIsNone(original())
        self.assertEqual(outputs, [False])

    def test_callback_waiting_for_mutex_owns_pin_before_disarm_without_drain(self):
        registry = Registry()
        original = weakref.ref(registry.published)
        mutex = registry.published.mutex
        held, release_holder = threading.Event(), threading.Event()
        def holder():
            with mutex:
                held.set()
                release_holder.wait(1)
        holder_thread = threading.Thread(target=holder)
        holder_thread.start()
        self.assertTrue(held.wait(1))
        pinned, proceed = threading.Event(), threading.Event()
        proceed.set()
        outputs = []
        callback_thread = threading.Thread(target=registry.callback, args=(pinned, proceed, outputs))
        callback_thread.start()
        self.assertTrue(pinned.wait(1))
        registry.disarm()  # Must return while holder still holds the Bridge mutex.
        gc.collect()
        self.assertIsNotNone(original())
        self.assertTrue(holder_thread.is_alive())
        release_holder.set()
        self.finish(holder_thread)
        self.finish(callback_thread)
        gc.collect()
        self.assertIsNone(original())
        self.assertEqual(outputs, [False])

    def test_callback_starting_after_disarm_sees_no_state_or_old_good_receipt(self):
        registry = Registry()
        registry.disarm()
        outputs = []
        pinned, proceed = threading.Event(), threading.Event()
        proceed.set()
        registry.callback(pinned, proceed, outputs)
        self.assertEqual(outputs, [False])
        self.assertTrue(registry.failed)

    def test_disarm_under_callers_own_mutex_is_rejected_by_declared_contract(self):
        registry = Registry()
        pin = registry.acquire()
        with pin.mutex:
            with self.assertRaisesRegex(AssertionError, 'Qt API under registry mutex'):
                registry.disarm()
        self.assertTrue(registry.failed)

    def test_snapshot_with_old_good_copy_racing_disarm_cannot_return_authority(self):
        registry = Registry()
        original = weakref.ref(registry.published)
        copied, proceed = threading.Event(), threading.Event()
        output = []
        def snapshot():
            pin = registry.acquire()
            with pin.mutex:
                value = tuple(pin.records)
            copied.set()
            proceed.wait(1)
            output.append(None if registry.failed else value)
        thread = threading.Thread(target=snapshot)
        thread.start()
        self.assertTrue(copied.wait(1))
        registry.disarm()
        gc.collect()
        self.assertIsNotNone(original())
        proceed.set()
        self.finish(thread)
        gc.collect()
        self.assertIsNone(original())
        self.assertEqual(output, [None])


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
