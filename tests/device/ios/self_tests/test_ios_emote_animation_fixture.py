"""Bounded bundled asset metadata, not modeled clip lengths or Rig effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from functools import partial
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests.emote_animation_fixture import bundled_frames,frame_count,NAMES


class AnimationMetadataTests(unittest.TestCase):
    def test_actual_bundled_curve_counts_are_not_the_generic_120_frame_model(self):
        frames=bundled_frames();self.assertEqual(set(NAMES),set(frames))
        self.assertEqual(401,frames['Crying']);self.assertEqual(44,frames['Waving'])
        self.assertEqual(64,frames['Clapping']);self.assertEqual((365,367,367),tuple(frames[key] for key in ('Sit1','Sit2','Sit3')))
    def test_truncated_non_fbx_and_unsupported_header_cannot_supply_loaded_frames(self):
        for raw in (b'',b'not-fbx'*100,b'Kaydara FBX Binary  \x00\x1a\x00'+(7500).to_bytes(4,'little')+bytes(20)):
            with self.subTest(length=len(raw)),self.assertRaises(NativeUIError):frame_count(raw)
    def test_explicit_fresh_vm_uses_actual_loaded_metadata_in_unchanged_pinned_callbacks(self):
        from ios.self_tests import emote_script_vm_fixture as source
        frames=bundled_frames()
        with patch.object(source,'ActualEmoteVM',partial(source.ActualEmoteVM,frame_counts=frames)):
            vm,native,ui=source.normal_ui(self)
        ui.open();ui.play('Waving');event=vm.state['events'][-1]
        self.assertEqual(44,event['request']['lastFrame']);self.assertEqual(44,vm.loaded_frames(event['request']['url']))
        self.assertAlmostEqual(44/60*1000,vm.state['timers'][0]['due']-event['epochMs'])


if __name__=='__main__':unittest.main()
