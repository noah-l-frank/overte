"""Actual two-ticket host transport originals; GPU execution remains modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
import unittest
from PIL import Image
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame,absent
from adapters.normal_ui import NativeUIError
from ios.self_tests.assets_image_removal_fixture import RemovalImageGpu
from ios.self_tests.assets_reply_fixture import EPOCH
from ios.self_tests.test_ios_assets_removal_images import emitted_pair


class Clock:
    elapsed=0
    def monotonic(self):return self.elapsed/1000
    def clock(self):return EPOCH+self.elapsed
    def sleep(self,seconds):self.elapsed+=round(seconds*1000)


class AssetsRemovalGpuTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock();frame,raw,*_=emitted_pair();image=Image.open(BytesIO(raw)).convert('RGBA')
        source=SimpleNamespace(b=self.clock,render=lambda:(raw,image.tobytes(),2),view=lambda:deepcopy(frame['capture']['source']['renderTrace']['recordedView']))
        self.gpu=RemovalImageGpu(source);self.counter=0
        self.reader=NativeVulkanWorldFrame(self.gpu.send,self.gpu.original,self.clock.clock,lambda:True,42,lambda _q:True,
            monotonic=self.clock.monotonic,sleep=self.clock.sleep)
    def query(self,request,operation):
        self.counter+=1
        return dict(schemaVersion=1,action='feature-vulkan-world-frame',commandId='ios-'+format(self.counter,'032x'),requestId='ios-'+request*32,operation=operation)
    def test_new_request_is_not_retired_by_the_previous_request_and_source_sequence_stays_global(self):
        first=self.reader.perform(self.query('a','inspect'));self.assertFalse(first['source']['retired'])
        before=self.reader.perform(self.query('a','read'));self.reader.image(before)
        self.reader.perform(self.query('a','release'));self.clock.sleep(.2)
        retired=self.reader.perform(self.query('a','inspect'));self.assertTrue(absent(retired))
        old=self.gpu.slots['ios-'+'a'*32];old_commands=deepcopy(old.commands)
        initial=self.reader.perform(self.query('b','inspect'));self.assertFalse(initial['source']['retired']);self.assertFalse(initial['source']['present'])
        after=self.reader.perform(self.query('b','read'));self.reader.image(after)
        self.assertEqual(before['instance'],after['instance']);self.assertGreater(after['sequence'],retired['sequence'])
        self.assertNotEqual(before['source']['renderTrace']['frameId'],after['source']['renderTrace']['frameId'])
        self.assertEqual(old_commands,old.commands);self.assertTrue(old.retired)
    def test_new_ticket_cannot_hide_an_old_active_or_undrained_holder(self):
        self.reader.perform(self.query('a','read'))
        with self.assertRaises(NativeUIError):self.reader.perform(self.query('b','read'))
        old=self.gpu.slots['ios-'+'a'*32];self.assertTrue(old.held);self.assertFalse(old.retired)
        self.assertIsNone(self.gpu.slots['ios-'+'b'*32].request)
        self.reader.perform(self.query('a','release'))
        with self.assertRaises(NativeUIError):self.reader.perform(self.query('c','read'))
        self.assertTrue(old.held);self.assertIsNone(self.gpu.slots['ios-'+'c'*32].request)
