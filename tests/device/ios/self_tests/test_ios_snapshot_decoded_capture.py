"""Decode actual private original artifacts over modeled native capture work."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
import unittest
from PIL import Image
from ios.adapters import snapshot_completion as source
from ios.self_tests import test_ios_snapshot_completion as fixture


class SnapshotDecodedCaptureTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.SnapshotCompletionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def encoded(self,*,uniform=False,format='PNG'):
        image=Image.new('RGB',(32,24),'red')
        if not uniform:
            for y in range(image.height):
                for x in range(image.width):image.putpixel((x,y),((x*23)%256,(y*29)%256,(x*17+y*7)%256))
        stream=BytesIO();image.save(stream,format=format);return stream.getvalue()
    def test_same_actual_native_file_and_private_bytes_decode_without_scene_or_export_claim(self):
        with self.f.ctx.lock.held():
            self.f.bytes=self.encoded();args=self.f.prepared();result=source.decoded(*args)
            self.assertEqual((32,24),(result['image']['width'],result['image']['height']))
            self.assertEqual(result['capture']['file']['sha256'],result['image']['sha256'])
            self.assertFalse(result['image']['deviceAcceptance']);self.assertTrue(result['sceneFidelityRequired'])
            self.assertTrue(result['independentWitnessRequired']);self.assertTrue(result['destinationOutcomeRequired'])
            self.assertTrue(result['quietWindowRequired']);self.assertNotIn('complete',result)
    def test_native_success_and_hash_consistent_file_do_not_hide_uniform_pixels(self):
        with self.f.ctx.lock.held():
            self.f.bytes=self.encoded(uniform=True);args=self.f.prepared();source.completed(*args)
            with self.assertRaises(ValueError):source.decoded(*args)
    def test_actual_JPEG_controls_and_original_native_filename_decode_as_JPEG(self):
        with self.f.ctx.lock.held():
            self.f.format='jpg';self.f.bytes=self.encoded(format='JPEG');args=self.f.prepared();result=source.decoded(*args)
            self.assertEqual('jpg',result['image']['format']);self.assertEqual('jpg',result['capture']['format'])
            self.assertTrue(result['capture']['file']['name'].endswith('.jpg'))
    def test_native_success_and_hash_consistent_file_do_not_hide_truncated_image(self):
        with self.f.ctx.lock.held():
            self.f.bytes=self.encoded()[:80];args=self.f.prepared();source.completed(*args)
            with self.assertRaises((ValueError,OSError,SyntaxError)):source.decoded(*args)
    def test_real_JPEG_bytes_cannot_be_relabelled_as_actual_PNG_control_and_filename(self):
        with self.f.ctx.lock.held():
            self.f.bytes=self.encoded(format='JPEG');args=self.f.prepared();source.completed(*args)
            with self.assertRaises(ValueError):source.decoded(*args)


if __name__=='__main__':unittest.main()
