"""Actual retained fence PNG comparisons; synthetic native renderer only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from adapters.original_marker_restoration_image import restored
from ios.self_tests import test_ios_emote_restoration_frames as fixture
from ios.self_tests.test_ios_graphics_measurements import RUN


class RestorationImageTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.RawFramesTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.owner=self.fixture.owner();self.before=self.owner.capture('initial');self.fixture.marker(True)
        self.admission=self.fixture.fixture.world(RUN);self.marker=self.admission['source']['markers'][0]['id']
    def after(self,*,stale=False):
        f=self.fixture.fixture;self.fixture.marker(False,paint=not stale);f.scope.state.update(phase='released',pending=None)
        self.barrier=f.native(None).read(0);return self.owner.capture('cleanup')
    def measure(self,reference):return restored(self.owner,self.before,reference,self.admission,self.marker,after_native=self.barrier)
    def test_genuine_pre_marker_and_postcleanup_fences_cover_full_actual_marker_projection(self):
        after=self.after();result=self.measure(after);self.assertEqual(0,result['changedPixels']);self.assertEqual(0.,result['meanChannelDelta'])
        self.assertEqual(result['baselineSha256'],result['currentSha256']);self.assertGreater(result['pixels'],128*32)
    def test_fresh_scene_absence_gpu_retirement_and_valid_hashes_cannot_hide_stale_marker_pixels(self):
        after=self.after(stale=True);frame,_raw=self.owner.frame(after);self.assertEqual([],frame['worldAfter']['source']['markers'])
        self.assertEqual('captured',self.owner.original(after)['phase'])
        with self.assertRaises(NativeUIError):self.measure(after)
    def test_old_fence_wrong_native_barrier_or_foreign_marker_never_qualifies_restoration(self):
        after=self.after()
        with self.assertRaises(NativeUIError):self.measure(self.before)
        with self.assertRaises(NativeUIError):restored(self.owner,self.before,after,self.admission,'f'*32,after_native=self.barrier)
        self.barrier=self.fixture.fixture.native(None).read(0)
        with self.assertRaises(NativeUIError):self.measure(after)


if __name__=='__main__':unittest.main()
