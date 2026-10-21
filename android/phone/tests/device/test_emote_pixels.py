"""Real PNG/projection logic with synthetic native frames; no avatar rendering."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from PIL import Image,ImageDraw
from adapters.normal_ui import NativeUIError
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.fixtures import marker_bytes
from overte_phone_emote_pixels import measure,original,_stride
from overte_phone_graphics_effects import projected_box
from self_tests.test_native_avatar_render import Boundary

RUN='a'*32
TICKET='b'*32
POLICY=dict(source='world-render-target',marker=[14,14,142,46],subject=[240,100,400,380])


class Pair:
    def __init__(self):
        b=Boundary();before,after,capture,draws,_pid,_epoch=b.join()
        self.first=dict(ticket=TICKET,avatarBefore=before,avatarAfter=after,capture=capture,draws=draws)
        for frame in (self.first,):
            for packet in (frame['avatarBefore'],frame['avatarAfter']):packet['source']['view']['position']=[0,.9,0]
            source=frame['capture']['source'];source.update(sourceExtent=[640,480],sourceViewport=[0,0,640,480],targetExtent=[640,480])
            source['renderTrace']['recordedView']['position']=[0,.9,0]
            source['image'].update(width=640,height=480)
            row=frame['draws']['source']['modelTrace']['models'][0];row.update(minimum=[-.5,0,-3.2],maximum=[.5,1.8,-2.8])
        self.second=deepcopy(self.first);self.second['ticket']='c'*32
        self.second['avatarBefore'].update(sequence=3,requestedEpochMs=21000,capturedEpochMs=21000,requestId='3'*32)
        self.second['avatarAfter'].update(sequence=4,requestedEpochMs=21006,capturedEpochMs=21006,requestId='4'*32)
        capture=self.second['capture'];capture.update(sequence=2,requestId='5'*32,requestedEpochMs=21000,capturedEpochMs=21005)
        source=capture['source'];source.update(acquisitionSequence=2,recordedEpochMs=21001,startedEpochMs=21003,capturedEpochMs=21004)
        source['image']['name']='world-render-image-'+capture['requestId']+'.png'
        source['renderTrace'].update(frameId='2'*32,recordedEpochMs=21001,begunEpochMs=21002,completedEpochMs=21002)
        draws=self.second['draws'];draws.update(sequence=2,requestId='6'*32,requestedEpochMs=21006,capturedEpochMs=21006)
        draws['source'].update(captureSequence=2,captureRequestId=capture['requestId'],acquisitionSequence=2,captureCapturedEpochMs=21004)
        draws['source']['modelTrace'].update(frameId='2'*32,recordedEpochMs=21001,begunEpochMs=21002,completedEpochMs=21002)
        self.clock=0.;self.epoch=21006;self.okay=True
        self.left=self.paint(self.first);self.right=self.paint(self.second,changed=True)

    def paint(self,frame,*,changed=False,background=False,marker_ticket=None,uniform=False,outside_body=False):
        image=Image.new('RGBA',(640,480),(35,40,45,255));draw=ImageDraw.Draw(image)
        if not uniform:
            draw.rectangle((250,115,389,369),fill=(190,200,205,255))
            for y in range(115,370,20):draw.rectangle((250,y,319,y+9),fill=(90,100,120,255))
            if changed:draw.rectangle((320,160,389,310),fill=(40,125,230,255))
        if background:draw.rectangle((450,150,639,479),fill=(200,120,20,255))
        if outside_body:draw.rectangle((240,100,244,379),fill=(250,10,10,255))
        with Image.open(io.BytesIO(marker_bytes(RUN,marker_ticket or frame['ticket']))) as card:image.paste(card,(10,10))
        output=io.BytesIO();image.save(output,format='PNG');raw=output.getvalue()
        source=frame['capture']['source'];source['image'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
        frame['draws']['source'].update(imageSha256=source['image']['sha256'],pixelSha256=source['image']['pixelSha256'])
        return raw

    def measure(self,*,previous=True,policy=None):
        return measure(RUN,self.second,self.right,policy or POLICY,31,lambda:self.epoch,lambda:self.okay,
            previous=dict(frame=self.first,png=self.left) if previous else None,monotonic=lambda:self.clock)


class EmotePixelTests(unittest.TestCase):
    def test_current_challenge_actual_projected_body_and_stable_controls_join_original_png_pair(self):
        pair=Pair();result=pair.measure()
        self.assertEqual(1,result['emotePixelsVersion']);self.assertGreater(result['bodyChangedFraction'],.05)
        self.assertGreater(result['subjectChangedFraction'],.05);self.assertEqual(0,result['controlChangedFraction'])
        self.assertEqual(pair.second['capture']['source']['image']['sha256'],result['imageSha256'])
        self.assertEqual(pair.first['ticket'],result['beforeTicket']);self.assertNotIn('passed',result)
        row=pair.second['draws']['source']['modelTrace']['models'][0]
        box=projected_box(dict(position=[0,.9,-3],dimensions=[1,1.8,.4],rotation=[0,0,0,1]),
            pair.second['capture']['source']['renderTrace']['recordedView'],[640,480])
        self.assertEqual([math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3])],result['bodyRoi'])
        self.assertEqual(row['modelInstance'],result['modelInstance'])

    def test_single_current_image_does_not_invent_a_motion_verdict(self):
        result=Pair().measure(previous=False)
        self.assertIsNone(result['bodyChangedFraction']);self.assertIsNone(result['controlChangedFraction'])
        self.assertIsNone(result['beforeTicket']);self.assertEqual(0,result['sampledBodyPixels'])

    def test_new_marker_or_fresh_draw_ack_over_frozen_body_cannot_establish_motion(self):
        pair=Pair();pair.right=pair.paint(pair.second)
        self.assertNotEqual(pair.left,pair.right)
        with self.assertRaises(AssertionError):pair.measure()

    def test_background_or_camera_motion_cannot_supply_body_effect(self):
        pair=Pair();pair.right=pair.paint(pair.second,changed=True,background=True)
        with self.assertRaises(NativeUIError):pair.measure()
        pair=Pair()
        for packet in (pair.second['avatarBefore'],pair.second['avatarAfter']):packet['source']['view']['position'][0]=.01
        pair.second['capture']['source']['renderTrace']['recordedView']['position'][0]=.01
        with self.assertRaises(NativeUIError):pair.measure()

    def test_old_or_foreign_ticket_marker_cannot_be_refreshed_by_native_envelope(self):
        for ticket in (TICKET,'d'*32):
            pair=Pair();pair.right=pair.paint(pair.second,changed=True,marker_ticket=ticket)
            with self.subTest(ticket=ticket),self.assertRaises(MarkerNotReady):pair.measure()

    def test_wrong_original_png_digest_or_native_model_table_is_rejected(self):
        for fault in ('png','pixel','model','geometry','source','foreign-png','absent-draw'):
            pair=Pair();row=pair.second['draws']['source']['modelTrace']['models'][0]
            if fault=='png':pair.right+=b'foreign'
            elif fault=='pixel':pair.second['capture']['source']['image']['pixelSha256']='f'*64
            elif fault=='model':row['modelInstance']='b'*32
            elif fault=='geometry':row['geometryInstance']='b'*32
            elif fault=='source':row['loadedSourceSha256']='f'*64
            elif fault=='foreign-png':pair.right=pair.left
            else:row['skinnedDrawCommands']=0
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):pair.measure()

    def test_tiny_offscreen_behind_camera_or_flat_actual_bounds_do_not_get_fallback_roi(self):
        for low,high in (([-.01,.8,-20],[.01,1,-19]),([-.5,0,3],[.5,1.8,3.5]),
                ([50,0,-3],[51,1.8,-2.8]),([0,0,-3],[0,1.8,-2.8])):
            pair=Pair();pair.second['draws']['source']['modelTrace']['models'][0].update(minimum=low,maximum=high)
            with self.subTest(low=low),self.assertRaises(NativeUIError):pair.measure()

    def test_subject_roi_must_cover_actual_body_without_widening_into_whole_background(self):
        for rectangle in ([0,0,640,480],[240,100,300,380],[0,200,400,480]):
            pair=Pair()
            with self.subTest(rectangle=rectangle),self.assertRaises(NativeUIError):pair.measure(policy=POLICY|dict(subject=rectangle))

    def test_marker_and_body_cannot_overlap_or_be_substituted_with_screen_capture_policy(self):
        for policy in (POLICY|dict(marker=[250,200,378,232]),POLICY|dict(source='native-screen'),POLICY|dict(expectedBody=True)):
            with self.subTest(policy=policy),self.assertRaises(NativeUIError):Pair().measure(policy=policy)

    def test_blank_or_uniform_projected_subject_cannot_qualify_even_with_actual_draw_counts(self):
        pair=Pair();pair.right=pair.paint(pair.second,uniform=True)
        with self.assertRaises(AssertionError):pair.measure()

    def test_frame_context_pid_birth_and_acquisition_must_advance_as_originals(self):
        for fault in ('capture-context','capture-sequence','native-birth','native-cursor','same-frame','same-ticket','pid','replaced-avatar'):
            pair=Pair();frame=pair.second
            if fault=='capture-context':frame['capture']['instance']='f'*32;frame['draws']['instance']='f'*32
            elif fault=='capture-sequence':frame['capture']['sequence']=1;frame['draws']['source']['captureSequence']=1
            elif fault=='native-birth':
                for packet in (frame['avatarBefore'],frame['avatarAfter']):packet['instance']='b'*32
            elif fault=='native-cursor':frame['avatarBefore']['sequence']=2
            elif fault=='same-frame':
                frame['capture']['source']['renderTrace']['frameId']=pair.first['capture']['source']['renderTrace']['frameId']
                frame['draws']['source']['modelTrace']['frameId']=frame['capture']['source']['renderTrace']['frameId']
            elif fault=='same-ticket':frame['ticket']=TICKET;pair.right=pair.paint(frame,changed=True)
            elif fault=='pid':frame['avatarBefore']['processId']=32
            else:
                for packet in (frame['avatarBefore'],frame['avatarAfter']):packet['source']['modelInstance']='a'*32
                frame['draws']['source']['modelTrace']['models'][0]['modelInstance']='a'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):pair.measure()

    def test_changed_pose_projection_or_viewport_is_not_normalized_into_success(self):
        for fault in ('pose','projection','viewport'):
            pair=Pair();frame=pair.second
            if fault=='pose':
                for packet in (frame['avatarBefore'],frame['avatarAfter']):packet['source']['pose']['feetPosition'][0]=.01
            elif fault=='projection':
                for packet in (frame['avatarBefore'],frame['avatarAfter']):packet['source']['view']['projection'][0]+=.01
                frame['capture']['source']['renderTrace']['recordedView']['projection'][0]+=.01
            else:frame['capture']['source']['sourceViewport']=[0,0,320,240]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):pair.measure()

    def test_historical_image_keeps_old_time_but_new_current_image_must_still_be_fresh(self):
        pair=Pair();self.assertGreater(pair.epoch-pair.first['capture']['capturedEpochMs'],1000)
        pair.measure();pair.epoch+=1600
        with self.assertRaises(NativeUIError):pair.measure()

    def test_frozen_device_clock_cannot_hide_late_final_guard_or_copy(self):
        for fault in ('guard','copy'):
            pair=Pair();calls=[0]
            def guard():
                calls[0]+=1
                if calls[0]==2:pair.clock+=1.6
                return True
            def copy(value):pair.clock+=1.6;return deepcopy(value)
            with self.subTest(fault=fault):
                if fault=='guard':
                    with self.assertRaises(NativeUIError):measure(RUN,pair.second,pair.right,POLICY,31,lambda:pair.epoch,
                        guard,previous=dict(frame=pair.first,png=pair.left),monotonic=lambda:pair.clock)
                else:
                    with patch('overte_phone_emote_pixels.deepcopy',side_effect=copy),self.assertRaises(NativeUIError):pair.measure()

    def test_lost_actual_guard_missing_original_or_unordered_native_time_stays_unavailable(self):
        pair=Pair();pair.okay=False
        with self.assertRaises(NativeUIError):pair.measure()
        pair=Pair();pair.first.pop('avatarAfter')
        with self.assertRaises((NativeUIError,KeyError)):pair.measure()
        pair=Pair();pair.second['avatarBefore']['capturedEpochMs']=21002
        with self.assertRaises(NativeUIError):pair.measure()

    def test_sampling_is_deterministic_and_bounded_even_for_awkward_original_extents(self):
        for width,height in ((1021,1027),(4095,2048),(640,480),(25,4096),(4096,4096)):
            stride=_stride(width,height)
            self.assertLessEqual(math.ceil(width/stride)*math.ceil(height/stride),65536)
            self.assertEqual(stride,_stride(width,height))
        pair=Pair();first=pair.measure();second=pair.measure();self.assertEqual(first,second)


if __name__=='__main__':unittest.main()
