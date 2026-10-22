"""Actual retained fenced PNGs; modeled world renderer, no device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
import unittest
from PIL import ImageDraw
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_rendered_retirement import world_pixels
from ios.self_tests import test_ios_emote_restoration_frames as fixture


class RestoredWorldTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.RawFramesTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.owner=self.fixture.owner();self.before=self.owner.capture('initial')

    def current(self,stale=False):
        f=self.fixture.fixture;f.scope.state.update(phase='released',pending=None)
        if stale:
            image=self.fixture.background.copy();ImageDraw.Draw(image).rectangle((0,0,40,40),fill=(220,60,10,255))
            stream=BytesIO();image.save(stream,format='PNG');f.raw=stream.getvalue()
        return self.owner.capture('cleanup')

    def test_original_world_target_is_unchanged_after_actual_new_fence(self):
        current=self.current();before,old=self.owner.frame(self.before);after,new=self.owner.frame(current)
        result=world_pixels(before,after,old,new);self.assertEqual(0,result['changedPixels'])
        self.assertEqual(640*400,result['pixels'])

    def test_stale_pose_pixels_outside_former_marker_region_are_not_ignored(self):
        current=self.current(stale=True);before,old=self.owner.frame(self.before);after,new=self.owner.frame(current)
        self.assertEqual([],after['worldAfter']['source']['markers'])
        self.assertEqual('captured',self.owner.original(current)['phase'])
        with self.assertRaises(NativeUIError):world_pixels(before,after,old,new)


if __name__=='__main__':unittest.main()
