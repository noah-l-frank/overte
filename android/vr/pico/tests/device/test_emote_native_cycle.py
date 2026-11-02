"""Actual Pico cleanup preflight; existing explicit app/SDK/native fixtures."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch

import test_normal_emote as normal
from adapters.pico4.emote_native_cycle_state import cycle_store


class NativeCycleBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = normal.PicoEmoteTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)

    def test_rootless_prepared_frame_or_child_refuses_cleanup_before_every_native_query_and_input(self):
        f = self.fixture; adapter, native = f.instance, f.native
        store = cycle_store(adapter, native.target)
        for suffix in ('.pending-intent', '.frame-000.json', '.child-original'):
            with self.subTest(suffix=suffix):
                orphan = store.path.with_name(store.path.name + suffix)
                orphan.write_bytes(b'actual retained Emote original\n'); orphan.chmod(0o600)
                before = (list(native.events), list(native.inputs), list(native.controllers), native.running)
                with patch.object(native, 'read_debug_app_file', side_effect=AssertionError('Native query is forbidden')) as read, \
                     patch.object(native, 'write_debug_app_file', side_effect=AssertionError('Native input is forbidden')) as write:
                    with self.assertRaises(ValueError): adapter.cleanup(native.target)
                    self.assertEqual(0, read.call_count); self.assertEqual(0, write.call_count)
                self.assertEqual(before, (native.events, native.inputs, native.controllers, native.running))
                self.assertFalse(store.path.exists()); self.assertEqual(b'actual retained Emote original\n', orphan.read_bytes())
                orphan.unlink()  # Only this test-created artifact.


def load_tests(loader, _tests, _pattern):
    # Select the composed cases once; imported fixture TestCases are not tests.
    return loader.loadTestsFromNames([
        'self_tests.test_pico_emote_native_cycle.NativeCycleTests',
        __name__ + '.NativeCycleBindingTests'])


if __name__ == '__main__': unittest.main()
