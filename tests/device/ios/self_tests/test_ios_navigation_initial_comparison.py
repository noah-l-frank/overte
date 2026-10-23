"""Actual same-process PNG comparisons, including an independent render fault."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
import unittest
import uuid
from PIL import Image,ImageDraw

from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_initial_comparison import compare
from ios.adapters.navigation_whole_preparation import NavigationWholePreparation
from ios.self_tests import test_ios_navigation_initial_restored_image as images


class NavigationInitialComparisonTests(unittest.TestCase):
    setUp=images.NavigationInitialRestoredImageTests.setUp
    acquire=images.NavigationInitialRestoredImageTests.acquire
    inputs=images.NavigationInitialRestoredImageTests.inputs
    owner=images.NavigationInitialRestoredImageTests.owner

    def test_same_process_original_pngs_match_but_a_real_later_background_change_fails(self):
        call=self.acquire();self.inputs();h=self.h
        with h.flow.held():
            preparation=NavigationWholePreparation(h.flow);preparation.load();baselines,admission=preparation.originals()
            current=self.owner(call,'ios-'+uuid.uuid4().hex);current.acquire(h.now())
            value=compare(baselines['primary'],current,admission)
            self.assertEqual(0,value['changedPixels']);self.assertEqual(0,value['meanChannelDelta'])
            # Change only a future modeled GPU response. Every already saved
            # PNG, frame metadata and clock remains byte-for-byte original.
            original=h.gpu.raster
            def different():
                raw,_pixels,recorded=original()
                with Image.open(BytesIO(raw)) as image:
                    image.load();ImageDraw.Draw(image).rectangle((0,0,39,39),fill=(0,0,0,255))
                    stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue(),image.tobytes(),recorded
            h.gpu.raster=different
            changed=self.owner(call,'ios-'+uuid.uuid4().hex);changed.acquire(h.now())
            with self.assertRaises(NativeUIError):compare(baselines['primary'],changed,admission)


if __name__=='__main__':unittest.main()
