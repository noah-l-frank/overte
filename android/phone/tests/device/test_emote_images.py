"""The original private world-image IO contract also applies to Emote evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import test_graphics_images as image_tests
from adapters.normal_ui import NativeUIError
from overte_phone_emote_images import PhoneEmoteImages,record
from overte_phone_graphics_images import record as graphics_record


class EmoteImageTests(image_tests.GraphicsImageTests):
    # Run the same real-filesystem counterexamples, including interrupts,
    # inode replacement, wrong scope, links, absent files and final-write age.
    def factory(self,*,role='primary',stage=1,binding=None):
        return PhoneEmoteImages(self.root,binding or image_tests.BINDING,image_tests.RUN,role,stage,lambda:self.okay,self.intent,
            monotonic=lambda:self.clock)

    def test_emote_contract_is_explicit_and_cannot_be_read_as_graphics_or_another_capture_index(self):
        value=self.save();self.assertEqual(1,value['emoteImageVersion']);self.assertNotIn('graphicsImageVersion',value)
        self.assertTrue(value['name'].startswith('emote-'+image_tests.RUN+'-primary-1-'))
        with self.assertRaises(NativeUIError):graphics_record(value)
        for change in (dict(emoteImageVersion=True),dict(emoteImageVersion=2),dict(stage=0),dict(stage=257),dict(stage=True)):
            with self.subTest(change=change),self.assertRaises(NativeUIError):record(value|change)
        with self.assertRaises(NativeUIError):self.factory(stage=2).read(value)

    def test_complete_capture_index_bound_uses_distinct_names_without_relaxing_file_or_metadata_limits(self):
        for index in (1,2,169,256):
            self.images=self.factory(stage=index);value=self.save()
            self.assertEqual(index,value['stage']);self.assertLessEqual(len(value['name']),120)
            self.assertEqual(self.raw,self.images.read(value))
        self.assertEqual(4,len(list(self.root.glob('*.png'))))
        for index in (0,257,True):
            with self.subTest(index=index),self.assertRaises(NativeUIError):self.factory(stage=index)

    def test_foreign_graphics_filename_or_emote_role_cannot_adopt_identical_png_bytes(self):
        value=self.save();original=deepcopy(value)
        for change in (dict(name=value['name'].replace('emote-','graphics-',1)),dict(role='actor')):
            with self.subTest(change=change),self.assertRaises(NativeUIError):self.images.read(value|change)
        self.assertEqual(original,value);self.assertEqual(self.raw,PhoneEmoteImages.archive(self.root,value))


if __name__=='__main__':unittest.main()
