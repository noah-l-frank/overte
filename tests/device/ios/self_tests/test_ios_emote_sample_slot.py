"""An occupied native slot grants no capture or release authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_sample_recovery import IOSEmoteSampleRecovery
from ios.self_tests import test_ios_emote_sample_recovery as fixture
from ios.self_tests.test_ios_graphics_measurements import TICKET


class SampleSlotTests(unittest.TestCase):
    def test_preexisting_slot_remains_untouched_through_failed_capture_drain_and_recovery(self):
        current=fixture.SampleRecoveryTests();current.setUp();self.addCleanup(current.doCleanups)
        gpu=current.fixture.gpu;gpu.request=dict(commandId='ios-'+'e'*32);gpu.started=gpu.clock;gpu.metadata=True
        original=(deepcopy(gpu.request),gpu.png,gpu.metadata,gpu.retired,gpu.gpu_pending)
        owner=current.owner()
        with self.assertRaises(NativeUIError):owner.capture(TICKET)
        with self.assertRaises(NativeUIError):current.owner().drain()
        with self.assertRaises(NativeUIError):IOSEmoteSampleRecovery(current.owner()).recover()
        self.assertEqual(['inspect'],[query['operation'] for query in gpu.commands])
        self.assertEqual(original,(gpu.request,gpu.png,gpu.metadata,gpu.retired,gpu.gpu_pending))
        self.assertEqual('reading',current.owner().state['phase'])
        self.assertIsNotNone(IOSEmoteSampleRecovery(current.owner()).state['pending'])


if __name__=='__main__':unittest.main()
