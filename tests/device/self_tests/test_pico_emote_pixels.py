"""Synthetic original stereo PNG/camera/body counterexamples; no renderer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import unittest
from unittest.mock import patch

from PIL import Image,ImageDraw
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_pixels import measure,model_cameras,projected_body
from feature_journeys.fixtures import challenge
from self_tests.test_pico_emote_model_draws import ModelBoundary
from self_tests.test_stereo_camera_uniforms import CameraBoundary

RUN='a'*32
POLICY=dict(picoEmotePixelPolicyVersion=1,source='world-render-target',eyes={
    'left':dict(marker=[8,450,136,482],subject=[175,10,335,270]),
    'right':dict(marker=[520,450,648,482],subject=[675,10,835,270])})


def fixture(ticket,*,second=False,moved_eye=None,background=False,marker_eye=None,ignored=False):
    boundary=CameraBoundary();produce=boundary.mutate
    boundary.frame+=int(second);boundary.execution+=int(second);boundary.submission+=int(second);boundary.uniform_sequence+=3*int(second)
    image=Image.new('RGBA',(1024,512),(20,35,50,255));draw=ImageDraw.Draw(image)
    for eye,offset in (('left',0),('right',512)):
        # A nonuniform original avatar body, with separate original eye colors.
        for y in range(20,265,8):
            color=(190 if eye=='left' else 80,100,60)
            if second and not ignored and moved_eye in (None,eye):color=(40,180 if y%16 else 100,200)
            draw.rectangle((180+offset,y,310+offset,y+3),fill=color)
        marker=POLICY['eyes'][eye]['marker'];bits=''.join(f'{byte:08b}' for byte in challenge(RUN,ticket if marker_eye in (None,eye) else 'f'*32))
        for index,bit in enumerate(bits):
            x=marker[0]+(index%32)*4;y=marker[1]+(index//32)*8
            draw.rectangle((x,y,x+3,y+7),fill=(240,240,240) if bit=='1' else (0,0,0))
        if second and background:draw.rectangle((10+offset,5,170+offset,430),fill=(250,0,0))
    output=io.BytesIO();image.save(output,format='PNG');boundary.raw=output.getvalue();boundary.pixels=hashlib.sha256(image.tobytes()).hexdigest()
    def producer(packet):
        produce(packet);source=packet['source']
        source.update(sourceExtent=[1024,512],sourceViewport=[0,0,1024,512],targetExtent=[1024,512])
        source['image'].update(width=1024,height=512)
        for index,row in enumerate(source['stereo']['eyes']):row.update(sourceViewport=[index*512,0,512,512],targetViewport=[index*512,0,512,512])
        for row in source['presentation']['views']:row['imageRect']=[0,0,512,512]
        for batch in source['renderTrace']['cameraBatches']:
            for camera in batch['cameras']:
                index=0 if camera['eye']=='left' else 1
                camera.update(viewport=[0,0,1024,512],drawViewport=[index*512,0,512,512],stereoInfo=[1,index,1/1024,1/512])
    boundary.mutate=producer;model=ModelBoundary(capture_boundary=boundary)
    if second:
        model.capture['sequence']=2;model.capture['source']['acquisitionSequence']=2
    row=model.trace['models'][0];row.update(minimum=[-.5,0,-3],maximum=[.5,1.8,-2])
    views=model.capture['source']['renderTrace']['cameraBatches'][0]['cameras']
    for use,camera in zip(row['cameraUses'],views):use['drawViewport']=deepcopy(camera['drawViewport'])
    before,after=model.avatars()
    if second:before['sequence']=3;after['sequence']=4
    # These are producer-owned original native sources at one explicit clock.
    before['requestedEpochMs']=before['capturedEpochMs']=20000
    frame=dict(ticket=ticket,avatarBefore=before,avatarAfter=after,capture=model.capture,draws=model.reader().read(model.capture))
    return frame,boundary.raw


class PicoEmotePixelTests(unittest.TestCase):
    def test_original_per_eye_model_projection_and_current_challenge_without_crop_or_eye_duplication(self):
        frame,raw=fixture('b'*32);value=measure(RUN,frame,raw,POLICY,31,lambda:20000,lambda:True)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),value['imageSha256']);self.assertEqual({'left','right'},set(value['eyes']))
        self.assertNotEqual(value['eyes']['left']['bodyRoi'],value['eyes']['right']['bodyRoi'])
        self.assertNotIn('passed',value);self.assertNotIn('animation',value)

    def test_both_original_eyes_have_body_changes_and_independent_quiet_controls(self):
        previous=fixture('b'*32);frame,raw=fixture('c'*32,second=True)
        value=measure(RUN,frame,raw,POLICY,31,lambda:20000,lambda:True,previous=dict(frame=previous[0],png=previous[1]))
        for eye in ('left','right'):
            row=value['eyes'][eye];self.assertGreater(row['bodyChangedFraction'],.05);self.assertLessEqual(row['controlChangedFraction'],.01)
            self.assertGreaterEqual(row['sampledBodyPixels'],1024);self.assertLessEqual(row['sampledControlPixels'],65536)

    def test_one_missing_or_foreign_current_challenge_cannot_borrow_the_other_eye(self):
        for eye in ('left','right'):
            frame,raw=fixture('b'*32,marker_eye=eye)
            with self.subTest(eye=eye),self.assertRaises(AssertionError):measure(RUN,frame,raw,POLICY,31,lambda:20000,lambda:True)

    def test_ignored_body_motion_one_eye_only_or_changed_background_fail(self):
        old,old_png=fixture('b'*32)
        for options in (dict(ignored=True),dict(moved_eye='left'),dict(moved_eye='right'),dict(background=True)):
            frame,raw=fixture('c'*32,second=True,**options)
            with self.subTest(options=options),self.assertRaises(NativeUIError):measure(RUN,frame,raw,POLICY,31,lambda:20000,lambda:True,previous=dict(frame=old,png=old_png))

    def test_foreign_png_swapped_eye_policy_and_unbounded_subject_are_refused(self):
        frame,raw=fixture('b'*32)
        with self.assertRaises(NativeUIError):measure(RUN,frame,raw+b'foreign',POLICY,31,lambda:20000,lambda:True)
        for edit in (lambda p:p['eyes'].update(left=p['eyes']['right']),lambda p:p['eyes']['left'].update(subject=[0,0,512,400]),
            lambda p:p.update(source='native-screen'),lambda p:p.update(picoEmotePixelPolicyVersion=True)):
            policy=deepcopy(POLICY);edit(policy)
            with self.subTest(edit=edit),self.assertRaises((NativeUIError,ValueError)):measure(RUN,frame,raw,policy,31,lambda:20000,lambda:True)

    def test_unrelated_forward_cameras_cannot_change_the_model_specific_projection(self):
        frame,raw=fixture('b'*32);value=measure(RUN,frame,raw,POLICY,31,lambda:20000,lambda:True)
        frame['capture']['source']['renderTrace']['cameraBatches'][1]['cameras'][0]['view'][12]+=.5
        measured=measure(RUN,frame,raw,POLICY,31,lambda:20000,lambda:True)
        self.assertEqual(value,measured)

    def test_large_headset_motion_reused_frame_or_replaced_geometry_cannot_be_body_motion(self):
        old,old_png=fixture('b'*32)
        for edit in (lambda f:f['capture']['source']['stereo'].update(executionSequence=200),
            lambda f:f['avatarBefore']['source']['geometry'].update(instance='e'*32),
            lambda f:f['capture']['source']['renderTrace']['cameraBatches'][0]['cameras'][0]['view'].__setitem__(12,.2)):
            frame,raw=fixture('c'*32,second=True);edit(frame)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):measure(RUN,frame,raw,POLICY,31,lambda:20000,lambda:True,previous=dict(frame=old,png=old_png))

    def test_small_original_headset_late_pose_is_reported_without_replacing_either_camera(self):
        old,old_png=fixture('b'*32);frame,raw=fixture('c'*32,second=True)
        frame['capture']['source']['renderTrace']['cameraBatches'][0]['cameras'][0]['view'][12]+=.0005
        value=measure(RUN,frame,raw,POLICY,31,lambda:20000,lambda:True,previous=dict(frame=old,png=old_png))
        self.assertAlmostEqual(.0005,value['eyes']['left']['maximumViewElementChange'])
        self.assertEqual(0,value['eyes']['right']['maximumViewElementChange'])

    def test_time_spent_revalidating_original_pngs_cannot_hide_behind_a_frozen_native_clock(self):
        from adapters.pico4 import emote_pixels
        frame,raw=fixture('b'*32);clock=[0.];observe=emote_pixels.image_observation
        def expensive(*args,**kwargs):
            value=observe(*args,**kwargs);clock[0]+=.4;return value
        with patch.object(emote_pixels,'image_observation',side_effect=expensive),self.assertRaises(NativeUIError):
            measure(RUN,frame,raw,POLICY,31,lambda:20000,lambda:True,monotonic=lambda:clock[0])
        self.assertGreaterEqual(clock[0],1.6)

    def test_last_guard_native_clock_and_png_revalidation_are_inside_original_age(self):
        frame,raw=fixture('b'*32)
        for mode in ('candidate','clock'):
            calls=[0];epoch=[20000]
            def guard():
                calls[0]+=1
                if calls[0]==3:
                    if mode=='candidate':return False
                    epoch[0]+=2000
                return True
            with self.subTest(mode=mode),self.assertRaises(NativeUIError):measure(RUN,frame,raw,POLICY,31,lambda:epoch[0],guard,monotonic=lambda:0.)


if __name__=='__main__':unittest.main()
