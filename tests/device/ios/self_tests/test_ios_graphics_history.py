"""Original source floor restoration never returns or retimes fresh facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_history import restore_native
from self_tests.test_native_feature_observation import Boundary
from self_tests.test_native_account_observation import account_source
from self_tests.test_native_animation_history import history_source
from self_tests.test_recorded_preview_history import complete


def original(value):
    account_source(value);history_source(value)
    value['audio']['recordedVoice']=complete()


class GraphicsHistoryTests(unittest.TestCase):
    def source(self):
        boundary=Boundary();boundary.mutate=original
        return boundary,boundary.reader(ios=True,native_clock_bound=True)

    def test_restoration_retains_all_present_original_histories_without_transport(self):
        boundary,reader=self.source();previous=reader.read(0);saved=deepcopy(previous)
        restored=boundary.reader(ios=True,native_clock_bound=True);count=len(boundary.commands)
        self.assertIsNone(restore_native(restored,previous));self.assertEqual(count,len(boundary.commands))
        self.assertEqual(saved,previous);self.assertEqual(previous['capturedEpochMs'],restored.captured_epoch)
        self.assertIsNotNone(restored.account_history);self.assertIsNotNone(restored.animation_history)
        self.assertIsNotNone(restored.voice_history);self.assertEqual(5,restored.voice_event_sequence)
        current=restored.read(restored.sequence);self.assertGreater(current['sequence'],previous['sequence'])
        self.assertEqual(previous['animation']['history'],current['animation']['history'])

    def test_disappearing_or_rewritten_original_histories_cannot_reset_after_reconstruction(self):
        for fault in ('account','voice','animation','rewrite'):
            with self.subTest(fault=fault):
                boundary,reader=self.source();previous=reader.read(0)
                restored=boundary.reader(ios=True,native_clock_bound=True);restore_native(restored,previous)
                def changed(value):
                    original(value)
                    if fault=='account':value['account'].pop('observation')
                    elif fault=='voice':value['audio'].pop('recordedVoice')
                    elif fault=='animation':value['animation']={}
                    else:value['audio']['recordedVoice']['events'][0]['publishedEpochMs']-=1
                boundary.mutate=changed
                with self.assertRaises(NativeUIError):restored.read(restored.sequence)
                self.assertEqual(previous['sequence'],restored.sequence)

    def test_legacy_reader_wrong_pid_or_nonce_and_used_reader_are_refused(self):
        boundary,reader=self.source();previous=reader.read(0)
        for fault in ('legacy','pid','nonce','used'):
            with self.subTest(fault=fault):
                candidate=boundary.reader(ios=True,native_clock_bound=fault!='legacy');packet=deepcopy(previous)
                if fault=='pid':candidate.pid=124
                elif fault=='nonce':packet['requestId']='a'*32
                elif fault=='used':candidate.read(0)
                count=len(boundary.commands)
                with self.assertRaises(NativeUIError):restore_native(candidate,packet)
                self.assertEqual(count,len(boundary.commands))

    def test_graphics_does_not_require_an_account_or_animation_capability(self):
        boundary=Boundary();boundary.mutate=lambda value:value.update(animation={},animationFence={})
        previous=boundary.reader(ios=True,native_clock_bound=True).read(0)
        reader=boundary.reader(ios=True,native_clock_bound=True);restore_native(reader,previous)
        self.assertEqual({},reader.read(reader.sequence)['animation']);self.assertIsNone(reader.account_history)


if __name__=='__main__':unittest.main()
