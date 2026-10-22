"""Actual PNG/native chunks with modeled fenced-renderer and scene SDKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import unittest
from PIL import Image,ImageDraw
from adapters.normal_ui import NativeUIError
from ios.adapters.create_restoration_image import restored
from ios.self_tests import test_ios_create_sample as sample_fixture
from ios.self_tests.test_ios_create_world_measurements import RUN,TICKET


class RestorationImageTests(unittest.TestCase):
    def setUp(self):
        self.h=sample_fixture.CreateSampleTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.marker=deepcopy(next(row for row in self.h.template['source']['entities'] if row['type']=='Web'))
        self.marker_wire=deepcopy(next(row for row in self.h.template['source']['tree']['entities'] if row['id']==self.marker['id']))
        self.stale=self.h.sdk.png;self.scene([])
        image=Image.new('RGBA',(640,400),(80,90,100,255));draw=ImageDraw.Draw(image)
        for y in range(0,400,10):
            for x in range(0,640,10):draw.rectangle((x,y,x+9,y+9),fill=((80,90,100) if (x//10+y//10)%2 else (110,100,90))+(255,))
        out=BytesIO();image.save(out,format='PNG');self.background=out.getvalue();self.pixels(self.background)
    def scene(self,rows):
        source=self.h.template['source'];source['tabletShown']=False;source['entities']=deepcopy(rows)
        source['tree'].update(totalEntities=len(rows),entities=[deepcopy(self.marker_wire)] if rows else [])
    def pixels(self,raw):self.h.sdk.png=raw;self.h.sdk.raw_pixels=Image.open(BytesIO(raw)).convert('RGBA').tobytes()
    def pair(self,*,stale=False,counter=False,view=False):
        before=self.h.owner();before.capture(TICKET,self.h.sdk.epoch())
        self.scene([self.marker]);admission=before.source.read(RUN);self.scene([]);barrier=self.h.sdk.epoch()
        self.h.next_gpu_request(sequence=before.state['originals']['capture']['sequence']-2 if counter else None)
        self.pixels(self.stale if stale else self.background)
        if view:self.h.template['source']['view']['position'][0]+=.2
        current=self.h.owner('ios-'+'8'*32);current.capture(TICKET,self.h.sdk.epoch())
        return before,current,admission,barrier
    def test_actual_post_retirement_fenced_pixels_match_original_pre_marker_scene_without_an_expected_image(self):
        with self.h.held():
            before,current,admission,barrier=self.pair();commands=deepcopy(self.h.sdk.commands)
            actual=restored(before,current,admission,self.marker['id'],after_native=barrier)
            self.assertEqual(0,actual['changedPixels']);self.assertEqual(before.request,actual['baselineRequest'])
            self.assertNotEqual(actual['baselineRequest'],actual['currentRequest']);self.assertEqual(commands,self.h.sdk.commands)
            self.assertTrue((self.h.root/before.frame_owner.name).exists());self.assertTrue((self.h.root/current.frame_owner.name).exists())
    def test_gone_entity_and_native_release_ack_cannot_hide_stale_actual_marker_pixels(self):
        with self.h.held():
            before,current,admission,barrier=self.pair(stale=True)
            self.assertEqual([],current.state['originals']['createAfter']['source']['entities'])
            self.assertFalse(current.state['originals']['retirement']['source']['present'])
            with self.assertRaises(NativeUIError):restored(before,current,admission,self.marker['id'],after_native=barrier)
    def test_reused_gpu_counter_and_changed_camera_do_not_supply_restored_world_evidence(self):
        for fault in ('counter','view'):
            if fault=='view':self.doCleanups();self.setUp()
            with self.subTest(fault=fault),self.h.held():
                before,current,admission,barrier=self.pair(counter=fault=='counter',view=fault=='view')
                with self.assertRaises(NativeUIError):restored(before,current,admission,self.marker['id'],after_native=barrier)
    def test_original_replacement_and_retirement_from_before_the_owned_marker_are_rejected(self):
        with self.h.held():
            before,current,admission,barrier=self.pair()
            with self.assertRaises(NativeUIError):restored(before,current,admission,self.marker['id'],after_native=before.state['originals']['capture']['capturedEpochMs'])
            (self.h.root/current.frame_owner.name).write_bytes(self.stale)
            with self.assertRaises(NativeUIError):restored(before,current,admission,self.marker['id'],after_native=barrier)


if __name__=='__main__':unittest.main()
