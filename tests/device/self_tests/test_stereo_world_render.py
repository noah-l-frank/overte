"""Stereo acquisition counterexamples using original synthetic PNG bytes.

No renderer, compiler, OpenXR service, device or external process is started.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import unittest

from PIL import Image
from adapters.normal_ui import NativeUIError
from adapters.world_render_evidence import validate, measured_scale
from self_tests.test_world_render_evidence import Boundary


def identity():return [1 if row==column else 0 for column in range(4) for row in range(4)]


class StereoBoundary(Boundary):
    def __init__(self):
        super().__init__();self.frame=100;self.execution=200;self.submission=300
        self.mutate=self.stereo_packet
        image=Image.new('RGBA',(16,12),(200,20,10,255))
        image.paste((10,30,210,255),(8,0,16,12))
        buffer=io.BytesIO();image.save(buffer,format='PNG')
        self.raw=buffer.getvalue();self.pixels=hashlib.sha256(image.tobytes()).hexdigest()

    def stereo_packet(self,packet):
        source=packet['source'];source.update(captureVersion=2,view='main-stereo')
        eyes=[]
        for index in range(2):
            projection=identity();projection[10]=-1.01;projection[11]=-1;projection[14]=-.2;projection[15]=0
            offset=identity();offset[12]=-.032 if index==0 else .032
            eyes.append(dict(eye=('left','right')[index],projection=projection,viewOffset=offset,
                sourceViewport=[index*4,0,4,6],targetViewport=[index*8,0,8,12]))
        source['stereo']=dict(frameIndex=self.frame,executionSequence=self.execution,layout='side-by-side',
            matrixLayout='column-major',cameraView=identity(),eyes=eyes)
        source['presentation']=dict(backend='openxr',frameIndex=self.frame,submissionSequence=self.submission,
            submittedEpochMs=20000,views=[dict(eye=name,imageRect=[0,0,8,12],arrayIndex=0) for name in ('left','right')])

    def advance(self):self.frame+=1;self.execution+=1;self.submission+=1


class StereoWorldRenderTests(unittest.TestCase):
    def test_original_two_eye_pixels_frame_and_successful_submission_are_bound(self):
        boundary=StereoBoundary();reader=boundary.reader(stereo=True)
        packet,raw=reader.read(0)
        self.assertEqual(raw,boundary.raw);self.assertEqual(dict(x=.5,y=.5),measured_scale(packet))
        with Image.open(io.BytesIO(raw)) as image:
            self.assertEqual((200,20,10,255),image.getpixel((3,6)))
            self.assertEqual((10,30,210,255),image.getpixel((11,6)))
        boundary.advance();next_packet,_=reader.read(packet['sequence'])
        self.assertEqual(101,next_packet['source']['stereo']['frameIndex'])

    def test_mono_default_never_accepts_stereo_and_stereo_never_accepts_mono(self):
        for boundary,options in ((StereoBoundary(),{}),(Boundary(),dict(stereo=True))):
            with self.subTest(options=options),self.assertRaises(NativeUIError):boundary.reader(**options).read(0)
            self.assertEqual([],boundary.reads)

    def test_relabelled_mono_missing_original_frame_or_missing_submission_cannot_read_pixels(self):
        def missing(source):source.pop('presentation')
        def relabel(source):source.update(captureVersion=1)
        def pending(source):source['presentation']['submittedEpochMs']=0
        def foreign(source):source['presentation']['frameIndex']+=1
        def old(source):source['presentation']['submittedEpochMs']=19999
        def rewritten(source):source['stereo']['executionSequence']=0
        def unsupported(source):source['presentation']['backend']='desktop'
        for fault in (missing,relabel,pending,foreign,old,rewritten,unsupported):
            with self.subTest(fault=fault.__name__):
                boundary=StereoBoundary();original=boundary.mutate
                boundary.mutate=lambda packet:(original(packet),fault(packet['source']))
                with self.assertRaises(NativeUIError):boundary.reader(stereo=True).read(0)
                self.assertEqual([],boundary.reads)

    def test_represented_old_frame_or_reused_execution_and_submission_cursors_are_rejected(self):
        for retained in ('frame','execution','submission'):
            with self.subTest(retained=retained):
                boundary=StereoBoundary();reader=boundary.reader(stereo=True);packet,_=reader.read(0)
                previous=getattr(boundary,retained);boundary.advance();setattr(boundary,retained,previous)
                with self.assertRaises(NativeUIError):reader.read(packet['sequence'])
                self.assertEqual(1,len(boundary.reads))

    def test_duplicated_swapped_overlapping_boolean_or_missing_eye_descriptors_are_rejected(self):
        def duplicate(s):s['stereo']['eyes'][1]=deepcopy(s['stereo']['eyes'][0])
        def swapped(s):s['stereo']['eyes'].reverse()
        def overlap(s):s['stereo']['eyes'][1]['targetViewport'][0]=0
        def singular(s):s['stereo']['eyes'][0]['projection']=[0]*16
        def central(s):s['stereo']['eyes'][1]['viewOffset']=deepcopy(s['stereo']['eyes'][0]['viewOffset'])
        def bool_rect(s):s['stereo']['eyes'][0]['targetViewport'][0]=False
        def bool_matrix(s):s['stereo']['cameraView'][0]=True
        def nan(s):s['stereo']['cameraView'][12]=float('nan')
        def no_right_submit(s):s['presentation']['views'].pop()
        def bool_frame(s):s['stereo']['frameIndex']=True
        for fault in (duplicate,swapped,overlap,singular,central,bool_rect,bool_matrix,nan,no_right_submit,bool_frame):
            with self.subTest(fault=fault.__name__):
                boundary=StereoBoundary();original=boundary.mutate
                boundary.mutate=lambda packet:(original(packet),fault(packet['source']))
                with self.assertRaises(NativeUIError):boundary.reader(stereo=True).read(0)
                self.assertEqual([],boundary.reads)

    def test_each_eye_requires_its_whole_original_png_not_a_reencoded_or_swapped_image(self):
        boundary=StereoBoundary();boundary.read=lambda name:Boundary().raw
        with self.assertRaises(NativeUIError):boundary.reader(stereo=True).read(0)

    def test_stereo_extent_is_bounded_and_mono_limits_are_preserved(self):
        boundary=StereoBoundary();packet,_=boundary.reader(stereo=True).read(0)
        source=packet['source'];source.update(sourceExtent=[4320,2160],sourceViewport=[0,0,4320,2160],targetExtent=[4320,2160])
        source['image'].update(width=4320,height=2160)
        for index,eye in enumerate(source['stereo']['eyes']):
            eye.update(sourceViewport=[index*2160,0,2160,2160],targetViewport=[index*2160,0,2160,2160])
        validate(packet,packet['requestId'],31,20000,stereo=True)
        source['sourceExtent']=[8192,4096]
        with self.assertRaises(RuntimeError):validate(packet,packet['requestId'],31,20000,stereo=True)

    def test_uncertain_input_is_not_retried_or_native_ownership_forgotten(self):
        boundary=StereoBoundary();boundary.ignore=True
        with self.assertRaises(NativeUIError):boundary.reader(stereo=True).read(0)
        self.assertEqual(1,len(boundary.commands));self.assertEqual(boundary.intents,boundary.commands)


if __name__=='__main__':unittest.main()
