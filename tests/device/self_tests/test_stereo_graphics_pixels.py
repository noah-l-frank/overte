"""Analytical two-eye pixel fixtures; no rendered product or device qualification.

The PNG uses literal analytical rectangles, independently of the reducer's
projection code. Original simulated producer hashes include the whole image.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import unittest

from PIL import Image
from adapters.normal_ui import NativeUIError
from adapters.stereo_graphics_pixels import measure
from feature_journeys.fixtures import marker_bytes
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.graphics_fixture import NAMES
from self_tests.test_native_graphics_subject import Boundary as SubjectBoundary,RUN
from self_tests.test_stereo_camera_uniforms import CameraBoundary

TICKET='c'*32
SCENE='d'*32
ROOT='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'


class PixelBoundary(CameraBoundary):
    def __init__(self,*,technique='doubled',card_ticket=TICKET,duplicate_right=False,black_right=False):
        super().__init__(technique);self.mutate=self.camera_source
        image=Image.new('RGBA',(1600,800),(100,100,100,255))
        image.paste((25,90,210,255),(0,450,1600,800))
        image.paste((255,90,0,255),(380,275,480,325))
        image.paste((255,90,0,255),(1120,275,1220,325))
        with Image.open(io.BytesIO(marker_bytes(RUN,card_ticket))) as card:
            # P=identity perspective, left/right V translations +/-0.1,
            # actual late view Y=+0.05, carrier (.8,.2) at z=-1.
            # Each source pixel spans exactly 2 original target pixels.
            card=card.resize((320,80),Image.Resampling.NEAREST).convert('RGBA')
            image.paste(card,(280,340));image.paste(card,(1000,340))
        if duplicate_right:image.paste(image.crop((0,0,800,800)),(800,0))
        if black_right:image.paste((0,0,0,255),(800,0,1600,800))
        output=io.BytesIO();image.save(output,format='PNG');self.raw=output.getvalue()
        self.pixels=hashlib.sha256(image.tobytes()).hexdigest()

    def camera_source(self,packet):
        self.uniforms(packet);s=packet['source'];s.update(sourceExtent=[800,400],sourceViewport=[0,0,800,400],targetExtent=[1600,800])
        s['image'].update(width=1600,height=800)
        for eye,view in enumerate(s['stereo']['eyes']):
            view.update(sourceViewport=[eye*400,0,400,400],targetViewport=[eye*800,0,800,800])
            view['viewOffset'][12]=-.1 if eye==0 else .1
        for view in s['presentation']['views']:view['imageRect']=[0,0,800,800]
        for batch in s['renderTrace']['cameraBatches']:
            for camera in batch['cameras']:
                eye=0 if camera['eye']=='left' else 1
                camera['projection'][8]=0;camera['view'][14]=0
                camera['view'][12]=(.3 if batch['role']=='mirror' else .1)*(1 if eye==0 else -1)
                camera['view'][13]=0 if batch['role']=='mirror' else .05
                camera.update(viewport=[0,0,800,400],stereoInfo=[1,eye,1/800,1/400],
                    drawViewport=[0,0,800,400] if batch['technique']=='instanced' else [eye*400,0,400,400])


def subject():
    boundary=SubjectBoundary();boundary.source.update(subjectVersion=2,sceneUrl=ROOT+'tickets/'+SCENE+'/graphics-scene.v1.json',
        avatarPose=dict(feetPosition=[0,-1.6,0],orientation=[0,0,0,1],modelScale=1))
    boundary.source['view']['position']=[0,0,0]
    for name in NAMES:
        row=boundary.add(name)
        if name=='marker':row.update(type='Web',position=[0,0,-1],dimensions=[.8,.2,.01],
            sourceUrl=ROOT+'tickets/'+SCENE+'/graphics-marker.v1.html',mirrorMode='none')
        elif name=='fog-board':row.update(position=[0,-1,-4.005],dimensions=[2,1,.01],mirrorMode='none')
        elif name=='reflector':row.update(position=[0,1,-4.005],dimensions=[2,1,.01])
    reader=boundary.reader();return reader.read(RUN,require_avatar=True),reader.read(RUN,require_avatar=True)


def measured(boundary=None,*,mutate_capture=None,mutate_subject=None,**options):
    boundary=boundary or PixelBoundary();capture,raw=boundary.reader(stereo=True,require_cameras=True).read(0)
    before,after=subject()
    if mutate_capture:mutate_capture(capture)
    if mutate_subject:mutate_subject(before,after)
    settings=dict(guard=lambda:True,clock_ms=lambda:20000);settings.update(options)
    return measure(capture,raw,before,after,run=RUN,ticket=TICKET,scene_ticket=SCENE,fixture_url=ROOT,
        pid=31,epoch=20000,**settings)


class StereoGraphicsPixelTests(unittest.TestCase):
    def close_pixels(self,expected,actual):
        # Float GPU matrices and conservative floor/ceil may remove one border
        # pixel. Do not expand the reducer ROI to satisfy an idealized fixture.
        self.assertEqual(len(expected),len(actual))
        self.assertTrue(all(abs(a-b)<=1 for a,b in zip(expected,actual)),(expected,actual))

    def test_both_eyes_decode_actual_original_card_using_late_gpu_views_and_preserve_whole_png_identity(self):
        for technique in ('doubled','instanced'):
            boundary=PixelBoundary(technique=technique);value=measured(boundary)
            self.assertEqual(hashlib.sha256(boundary.raw).hexdigest(),value['sha256'])
            self.assertEqual(boundary.pixels,value['pixelSha256'])
            self.assertEqual({'left','right'},set(value['eyes']))
            self.close_pixels([292,356],value['eyes']['left']['marker']['samplePixels'][0])
            self.close_pixels([1012,356],value['eyes']['right']['marker']['samplePixels'][0])
            self.assertNotEqual(value['eyes']['left']['marker']['samplePixels'],value['eyes']['right']['marker']['samplePixels'])

    def test_original_haze_and_mirror_pixel_statistics_use_their_distinct_actual_camera_roles(self):
        value=measured();self.assertEqual('mirror',value['mirrorCameraRole'])
        self.close_pixels([360,470,460,520],value['eyes']['left']['haze']['roi'])
        self.close_pixels([380,275,480,325],value['eyes']['left']['mirror']['roi'])
        self.close_pixels([1120,275,1220,325],value['eyes']['right']['mirror']['roi'])
        for eye in value['eyes'].values():
            self.assertEqual([25,90,210],eye['haze']['meanRgb']);self.assertEqual(185,eye['haze']['blueDominance'])
            self.assertEqual([255,90,0],eye['mirror']['meanRgb']);self.assertEqual(1,eye['mirror']['orangeFraction'])
            self.assertEqual(eye['mirror']['pixels'],sum(eye['mirror']['histogram']))

    def test_original_forward_geometry_is_explicit_only_when_no_mirror_draw_executed(self):
        def off(packet):
            trace=packet['source']['renderTrace'];trace.update(mirrorDrawCommands=0,mirrorBatches=0)
            trace['cameraBatches']=[row for row in trace['cameraBatches'] if row['role']=='forward']
        value=measured(mutate_capture=off);self.assertEqual('forward',value['mirrorCameraRole'])
        self.close_pixels([360,270,460,320],value['eyes']['left']['mirror']['roi'])
        self.assertLess(value['eyes']['left']['mirror']['orangeFraction'],1)

    def test_copied_or_black_right_eye_cannot_borrow_the_left_eyes_current_challenge(self):
        for options in (dict(duplicate_right=True),dict(black_right=True)):
            with self.subTest(options=options),self.assertRaises(MarkerNotReady):measured(PixelBoundary(**options))

    def test_stale_card_is_rejected_even_with_fresh_original_capture_hashes_and_frame_metadata(self):
        with self.assertRaises(MarkerNotReady):measured(PixelBoundary(card_ticket='f'*32))

    def test_no_convenient_camera_slot_or_recording_pose_can_replace_actual_inconsistent_used_cameras(self):
        def ambiguous(packet):
            for camera in packet['source']['renderTrace']['cameraBatches'][1]['cameras']:camera['projection'][8]=.5
        with self.assertRaises((NativeUIError,MarkerNotReady)):measured(mutate_capture=ambiguous)
        def recording(packet):
            for batch in packet['source']['renderTrace']['cameraBatches']:
                if batch['role']=='forward':
                    for camera in batch['cameras']:camera['view'][13]=0
        with self.assertRaises(MarkerNotReady):measured(mutate_capture=recording)

    def test_changed_foreign_absent_or_reused_subject_source_cannot_supply_geometry(self):
        changes=[lambda a,b:b.update(sequence=a['sequence']),lambda a,b:b.update(instance='f'*32),
            lambda a,b:b['source'].update(sceneUrl=ROOT+'foreign.json'),
            lambda a,b:b['source']['entities'][0].update(position=[9,9,9]),
            lambda a,b:b.update(runId='f'*32)]
        for change in changes:
            with self.subTest(change=change),self.assertRaises((NativeUIError,ValueError)):measured(mutate_subject=change)

    def test_legacy_trace_and_foreign_frame_cannot_supply_required_original_stereo_pixel_mapping(self):
        changes=[lambda p:p['source']['renderTrace'].update(frameIndex=9),
            lambda p:p['source'].update(captureVersion=3),lambda p:p.update(processId=9)]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(NativeUIError):measured(mutate_capture=change)

    def test_candidate_loss_or_native_clock_rollback_after_processing_cannot_publish_pixels(self):
        calls=[]
        def guard():calls.append(True);return len(calls)==1
        with self.assertRaises(NativeUIError):measured(guard=guard)
        for epoch in (19999,22000):
            with self.subTest(epoch=epoch),self.assertRaises(NativeUIError):measured(clock_ms=lambda:epoch)

    def test_too_small_offscreen_or_backfacing_card_is_not_enlarged_relocated_or_invented(self):
        for change in (dict(dimensions=[.01,.01,.01]),dict(position=[0,0,1]),dict(position=[100,0,-1])):
            def moved(a,b):
                for value in (a,b):
                    next(row for row in value['source']['entities'] if row['type']=='Web').update(deepcopy(change))
            with self.subTest(change=change),self.assertRaises(NativeUIError):measured(mutate_subject=moved)

    def test_slow_processing_cannot_borrow_a_frozen_native_clock(self):
        calls=[0]
        def clock():
            calls[0]+=1
            return 0 if calls[0]<4 else 1.6
        with self.assertRaises(NativeUIError):measured(monotonic=clock)


if __name__=='__main__':unittest.main()
