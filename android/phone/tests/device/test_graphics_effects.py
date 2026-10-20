"""Original host image pairs and explicit synthetic native facts; no GPU/device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from PIL import Image,ImageDraw
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import challenge
from feature_journeys.graphics_fixture import subject_ids
from overte_phone_graphics_effects import compare,projected_box
from self_tests.test_world_render_evidence import frame_view
from test_graphics_samples import Originals
from test_graphics_images import BINDING
from test_graphics_measurements import RUN,TICKET,FIXTURE

POLICY=dict(source='world-render-target',marker=[208,70,432,114],subject=[0,150,640,360])


class Pair:
    def __init__(self,root,feature='haze',*,after_fog=(30,110,210),after_orange=True):
        self.source=Originals(root);self.feature=feature;self.clock=0.;self.epoch=20000;self.okay=True
        scene=self.source.scene;scene.subject_before['source']['view']['aspectRatio']=16/9
        scene.capture['source'].update(sourceExtent=[416,234],sourceViewport=[0,0,416,234],targetExtent=[640,360])
        scene.capture['source']['renderTrace']['recordedView']=frame_view(16/9)
        self.paint(TICKET,(230,230,230),False)
        with self.source.lock.held():
            before=self.source.factory(image_policy=POLICY);before.read(TICKET,20000)
            self.before=deepcopy(before.state['frame']);self.raw_before=(root/self.before['image']['name']).read_bytes()
            self.source.change_phase()
            changed='hazeSetting' if feature=='haze' else 'mirrorsSetting'
            scene.before['graphics'][changed]=True
            for row in scene.ui['controls']:
                if row['id']==('graphics.haze' if feature=='haze' else 'graphics.mirrors'):row.update(checked=True,nativeChecked=True)
            trace=scene.capture['source']['renderTrace']
            if feature=='haze':trace.update(hazeBatches=2,hazeDrawCommands=8)
            else:trace.update(mirrorBatches=1,mirrorDrawCommands=1)
            self.paint('7'*32,after_fog if feature=='haze' else (230,230,230),after_orange if feature=='mirror' else False)
            after=self.source.factory(image_policy=POLICY);after.read('7'*32,20000)
            self.after=deepcopy(after.state['frame']);self.raw_after=(root/self.after['image']['name']).read_bytes()

    def paint(self,ticket,fog,orange):
        # These are explicit synthetic observed pixels, supplied independently
        # of requested inputs. Native flags and trace are configured separately.
        image=Image.new('RGBA',(640,360),(12,12,12,255));draw=ImageDraw.Draw(image)
        draw.rectangle((247,153,326,198),fill=tuple(fog)+(255,))
        draw.rectangle((398,55,554,289),fill=(120,120,120,255))
        if orange:draw.rectangle((460,168,492,192),fill=(240,90,0,255))
        draw.rectangle((190,56,450,126),fill=(240,240,240,255))
        bits=''.join(format(value,'08b') for value in challenge(RUN,ticket))
        for index,bit in enumerate(bits):
            x=208+(index%32)*7;y=70+(index//32)*11
            draw.rectangle((x,y,x+6,y+10),fill=(255,255,255,255) if bit=='1' else (0,0,0,255))
        output=io.BytesIO();image.save(output,format='PNG');raw=output.getvalue()
        self.source.scene.pixels=raw;self.source.storage.raw=raw
        self.source.scene.capture['source']['image'].update(width=640,height=360,bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())

    def check(self,**options):
        arguments=dict(epoch_ms=lambda:self.epoch,guard=lambda:self.okay,monotonic=lambda:self.clock)
        arguments.update(options)
        return compare(RUN,self.feature,FIXTURE,BINDING,'primary',self.before,self.raw_before,self.after,self.raw_after,POLICY,**arguments)

    def replace_after(self,mutate):
        with Image.open(io.BytesIO(self.raw_after)) as original:image=original.copy()
        mutate(image);output=io.BytesIO();image.save(output,format='PNG');self.raw_after=output.getvalue()
        self.after['capture']['source']['image'].update(bytes=len(self.raw_after),sha256=hashlib.sha256(self.raw_after).hexdigest(),
            pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
        self.after['image']['capture']=deepcopy(self.after['capture'])


class GraphicsEffectsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-graphics-effects-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
    def pair(self,feature='haze',**options):return Pair(self.root,feature,**options)

    def test_haze_requires_measured_blue_shift_in_the_projected_distant_board(self):
        pair=self.pair();value=pair.check()
        self.assertEqual(subject_ids(RUN)['fog-board'],value['targetId']);self.assertGreater(value['changedFraction'],.9)
        self.assertGreater(value['blueDominanceAfter']-value['blueDominanceBefore'],10)
        self.assertEqual(hashlib.sha256(pair.raw_after).hexdigest(),value['afterSha256'])
        self.assertEqual([268,165,306,186],value['roi']);self.assertEqual(798,value['pixels'])

    def test_mirror_requires_measured_owned_orange_reflection_in_the_actual_mirror(self):
        value=self.pair('mirror').check()
        self.assertEqual(subject_ids(RUN)['reflector'],value['targetId'])
        self.assertGreater(value['orangeFractionAfter']-value['orangeFractionBefore'],.005)
        self.assertGreater(value['changedFraction'],.05);self.assertLess(value['changedFraction'],.3)
        roi=value['roi'];self.assertLess(value['pixels'],(roi[2]-roi[0])*(roi[3]-roi[1]))
        self.assertEqual(POLICY['marker'],value['excluded'][1])

    def test_executed_batch_flags_and_fresh_challenge_do_not_replace_visible_effects(self):
        for feature in ('haze','mirror'):
            root=self.root/feature;root.mkdir(mode=0o700)
            pair=Pair(root,feature,after_fog=(230,230,230),after_orange=False)
            with self.subTest(feature=feature),self.assertRaises(NativeUIError):pair.check()

    def test_visible_pixels_do_not_replace_missing_original_executed_batches(self):
        pair=self.pair();pair.after['capture']['source']['renderTrace'].update(hazeBatches=0,hazeDrawCommands=0)
        pair.after['image']['capture']=deepcopy(pair.after['capture'])
        with self.assertRaises(NativeUIError):pair.check()

    def test_wrong_haze_hue_or_exposure_change_is_not_a_blue_fog_effect(self):
        for index,color in enumerate(((210,90,30),(100,100,100))):
            root=self.root/str(index);root.mkdir(mode=0o700);pair=Pair(root,after_fog=color)
            with self.subTest(color=color),self.assertRaises(NativeUIError):pair.check()

    def test_changed_mirror_pixels_with_no_owned_orange_reflection_fail(self):
        pair=self.pair('mirror',after_orange=False)
        pair.replace_after(lambda image:ImageDraw.Draw(image).rectangle((460,168,492,192),fill=(20,90,240,255)))
        with self.assertRaises(NativeUIError):pair.check()

    def test_unrelated_world_changes_cannot_replace_a_target_effect(self):
        pair=self.pair(after_fog=(230,230,230))
        pair.replace_after(lambda image:ImageDraw.Draw(image).rectangle((0,240,300,359),fill=(240,80,10,255)))
        with self.assertRaises(NativeUIError):pair.check()

    def test_same_image_wrong_hash_stale_marker_and_borrowed_frame_are_rejected(self):
        for fault in ('same','hash','frame','ticket'):
            root=self.root/fault;root.mkdir(mode=0o700);pair=Pair(root)
            if fault=='same':pair.raw_after=pair.raw_before
            elif fault=='hash':pair.after['capture']['source']['image']['sha256']='f'*64
            elif fault=='frame':pair.after['capture']['source']['renderTrace']['frameId']=pair.before['capture']['source']['renderTrace']['frameId'];pair.after['image']['capture']=deepcopy(pair.after['capture'])
            else:pair.after['ticket']=pair.before['ticket']
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,AssertionError)):pair.check()

    def test_original_view_lens_scale_scene_or_other_setting_changes_make_a_pair_incomparable(self):
        for fault in ('view','resolution','setting','scene','stage'):
            root=self.root/fault;root.mkdir(mode=0o700);pair=Pair(root)
            if fault=='view':pair.after['capture']['source']['renderTrace']['recordedView']['projection'][2]=.01;pair.after['image']['capture']=deepcopy(pair.after['capture'])
            elif fault=='resolution':pair.after['capture']['source']['sourceViewport'][2]-=1;pair.after['image']['capture']=deepcopy(pair.after['capture'])
            elif fault=='setting':
                for key in ('nativeBefore','nativeAfter'):pair.after[key]['graphics']['shadowsSetting']=not pair.after[key]['graphics']['shadowsSetting']
            elif fault=='scene':pair.after['subjectAfter']['source']['entities'][0]['lastEditedEpochUs']+=1
            else:pair.after['image']['stage']=1;pair.after['image']['name']=pair.after['image']['name'].replace('-primary-0-','-primary-1-')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):pair.check()

    def test_native_setting_must_actually_change_and_direction_must_match_measured_pixels(self):
        pair=self.pair()
        for frame in (pair.before,pair.after):
            for key in ('nativeBefore','nativeAfter'):frame[key]['graphics']['hazeSetting']=False
            for row in frame['graphics']['controls']:
                if row['id']=='graphics.haze':row.update(nativeChecked=False,checked=False)
        with self.assertRaises(NativeUIError):pair.check()

    def test_visible_effect_in_the_wrong_measured_native_direction_fails(self):
        pair=self.pair()
        for frame,enabled in ((pair.before,True),(pair.after,False)):
            for key in ('nativeBefore','nativeAfter'):frame[key]['graphics']['hazeSetting']=enabled
            for row in frame['graphics']['controls']:
                if row['id']=='graphics.haze':row.update(nativeChecked=enabled,checked=enabled)
            frame['capture']['source']['renderTrace'].update(hazeBatches=2 if enabled else 0,hazeDrawCommands=8 if enabled else 0)
            frame['image']['capture']=deepcopy(frame['capture'])
        with self.assertRaises(NativeUIError):pair.check()

    def test_an_individually_valid_old_reference_outside_the_pair_window_is_refused(self):
        pair=self.pair()
        def shift(value):
            if type(value) is dict:
                for key,item in value.items():
                    if key.endswith('EpochMs') and type(item) is int:value[key]=item+50000
                    else:shift(item)
            elif type(value) is list:
                for item in value:shift(item)
        for key in ('nativeBefore','nativeAfter','subjectBefore','subjectAfter','graphics','tablet','capture','retirement'):
            shift(pair.after[key])
        pair.after['afterEpochMs']+=50000;pair.after['provider']['capturedEpochMs']+=50000
        pair.after['image']['capture']=deepcopy(pair.after['capture']);pair.epoch=70000
        with self.assertRaises(NativeUIError):pair.check()

    def test_stale_current_image_clock_rollback_lost_guard_or_slow_final_query_cannot_return_metrics(self):
        pair=self.pair()
        for epoch in (19999,22000):
            pair.epoch=epoch
            with self.subTest(epoch=epoch),self.assertRaises(NativeUIError):pair.check()
        pair.epoch=20000;pair.okay=False
        with self.assertRaises(NativeUIError):pair.check()
        pair.okay=True;calls=[]
        def delayed():
            calls.append(True)
            if len(calls)>1:pair.clock+=1.6
            return 20000
        with self.assertRaises(NativeUIError):pair.check(epoch_ms=delayed)

    def test_projection_uses_the_original_matrix_with_conservative_geometry_and_refuses_clipping(self):
        pair=self.pair();view=pair.before['capture']['source']['renderTrace']['recordedView']
        row=next(row for row in pair.before['subjectAfter']['source']['entities'] if row['id']==subject_ids(RUN)['fog-board'])
        actual=projected_box(row,view,[640,360]);f=1/math.tan(math.pi/6)
        expected=[320*(1-f/(16/9)*6.5/27.95),180*(1-f*2.4/27.95),320*(1+f/(16/9)*.5/27.95),180*(1+f*1.6/27.95)]
        for a,b in zip(actual,expected):self.assertAlmostEqual(a,b)
        shifted=deepcopy(view);shifted['projection'][2]=.1
        changed=projected_box(row,shifted,[640,360]);self.assertAlmostEqual(actual[0]-32,changed[0])
        shifted['position'][0]=100
        with self.assertRaises(NativeUIError):projected_box(row,shifted,[640,360])

    def test_slow_decode_cannot_hide_behind_a_frozen_native_clock(self):
        pair=self.pair();original=Image.open;calls=[]
        def slow(*args,**kwargs):
            calls.append(True)
            if len(calls)==1:pair.clock+=1.6
            return original(*args,**kwargs)
        with patch.object(Image,'open',side_effect=slow),self.assertRaises(NativeUIError):pair.check()
