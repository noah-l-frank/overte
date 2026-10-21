"""Literal synthetic eye rasters; no GPU, UI, native or device qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import math
import unittest
from PIL import Image
from adapters.normal_ui import NativeUIError
from adapters.stereo_graphics_surfaces import reduce_original,reflected
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.graphics_fixture import pico_scene,PICO_RESOURCE
from feature_journeys.graphics_surface_cues import cells,PALETTES
from feature_journeys.fixtures import marker_bytes
from self_tests.test_stereo_graphics_evidence import JourneyPixels,Source
from self_tests.test_stereo_graphics_pixels import RUN,TICKET,SCENE,ROOT


class SurfacePixels(JourneyPixels):
    def __init__(self,*,mirror=True,haze=True,stale_haze=False,stale_reflection=False,duplicate=False,obscure=False,ticket=TICKET):
        super().__init__();image=Image.new('RGBA',(1600,800),(100,100,100,255))
        for index in range(2):
            # Independent closed-form raster of the authored axis-aligned Web
            # planes. Unit focal lengths, 800px eye, eye x=-/+0.03, head y=1.6.
            offset=800*index;eye_x=-.03 if index==0 else .03
            for surface in ('haze','reflection'):
                if surface=='reflection' and not mirror:continue
                stale=(stale_haze if surface=='haze' else stale_reflection) and (index==1 or stale_reflection=='all')
                grid=cells(RUN,'e'*32 if stale else ticket,surface)
                palette=PALETTES[surface]
                if surface=='haze' and haze:palette=((25,75,160),(165,180,230))
                for row in range(8):
                    for column in range(26):
                        if surface=='haze':
                            xs=[offset+400+400*(-14+14*u-eye_x)/28 for u in (column/26,(column+1)/26)]
                            ys=[400-400*(3.4-6*v)/28 for v in (row/8,(row+1)/8)]
                        else:
                            # Reflection of yaw-180 Web about actual z=-4:
                            # virtual z=-10, x=7.3-4.6*u, y=2.75-2.3*v.
                            xs=[offset+400+40*(7.3-4.6*u-eye_x) for u in (column/26,(column+1)/26)]
                            ys=[400-40*(1.15-2.3*v) for v in (row/8,(row+1)/8)]
                        image.paste(palette[grid[row][column]]+(255,),
                            (math.ceil(min(xs)-.5),math.ceil(min(ys)-.5),math.ceil(max(xs)-.5),math.ceil(max(ys)-.5)))
        with Image.open(io.BytesIO(marker_bytes(RUN,ticket))) as marker:
            card=marker.resize((320,80),Image.Resampling.NEAREST).convert('RGBA')
            image.paste(card,(288,248));image.paste(card,(992,248))
        if duplicate:image.paste(image.crop((0,0,800,800)),(800,0))
        if obscure:image.paste((25,90,210,255),(215,350,295,440))
        output=io.BytesIO();image.save(output,format='PNG')
        self.raw=output.getvalue();self.pixels=hashlib.sha256(image.tobytes()).hexdigest()


def originals(**options):
    body=Source().acquire()[1];source=SurfacePixels(**options)
    capture,raw=source.reader(stereo=True,require_cameras=True).read(0)
    for packet in (body['subjectBefore'],body['subjectAfter']):
        packet['source']['sceneUrl']=ROOT+'tickets/'+SCENE+'/'+PICO_RESOURCE
        for doc in pico_scene(RUN,SCENE,ROOT)['Entities']:
            row=next(row for row in packet['source']['entities'] if row['id']==doc['id'].strip('{}'))
            row['type']=doc['type'];row['sourceUrl']=doc.get('sourceUrl','')
            for field,axes in (('position','xyz'),('rotation','xyzw'),('dimensions','xyz')):row[field]=[doc[field][a] for a in axes]
            if 'color' in doc:row['color']=[doc['color'][a] for a in ('red','green','blue')]
            if doc['type']=='Zone':row['haze']['range']=doc['haze']['hazeRange']
    if options.get('mirror') is False:
        capture['source']['renderTrace'].update(mirrorBatches=0,mirrorDrawCommands=0)
        capture['source']['renderTrace']['cameraBatches']=[b for b in capture['source']['renderTrace']['cameraBatches'] if b['role']!='mirror']
    return capture,raw,body['subjectBefore'],body['subjectAfter']


def read(values,**options):
    return reduce_original(*values,run=RUN,ticket=TICKET,scene_ticket=SCENE,fixture_url=ROOT,pid=31,**options)


class StereoGraphicsSurfaceTests(unittest.TestCase):
    def test_both_original_eyes_decode_the_far_and_actual_virtual_reflection_planes(self):
        values=originals();value=read(values)
        self.assertEqual(hashlib.sha256(values[1]).hexdigest(),value['sha256'])
        for eye in value['eyes'].values():
            for surface in ('haze','mirror'):
                self.assertTrue(eye[surface]['current']);self.assertGreaterEqual(eye[surface]['minimumContrast'],40)
                self.assertEqual(8,len(eye[surface]['calibrationRows']))
            self.assertEqual([165,180,230],eye['haze']['meanRgb'])
            self.assertEqual([255,90,0],eye['mirror']['meanRgb'])
        self.assertNotEqual(value['eyes']['left']['haze']['polygons'],value['eyes']['right']['haze']['polygons'])

    def test_original_haze_color_changes_are_measured_after_identity_without_declaring_an_effect(self):
        clear,hazy=read(originals(haze=False)),read(originals(haze=True))
        for eye in ('left','right'):
            self.assertEqual(0,clear['eyes'][eye]['haze']['blueDominance'])
            self.assertEqual(65,hazy['eyes'][eye]['haze']['blueDominance'])
        self.assertNotIn('hazeEnabled',hazy)

    def test_missing_or_foreign_right_surface_and_duplicated_eye_are_rejected(self):
        for options in (dict(stale_haze=True),dict(stale_reflection=True),dict(duplicate=True),dict(obscure=True)):
            with self.subTest(options=options),self.assertRaises(MarkerNotReady):read(originals(**options))

    def test_native_mirror_off_rejects_any_remaining_valid_reflection_including_a_foreign_ticket(self):
        value=read(originals(mirror=False));self.assertTrue(all(not eye['mirror']['current'] for eye in value['eyes'].values()))
        for options in ({},dict(stale_reflection='all')):
            values=list(originals(**options));trace=values[0]['source']['renderTrace']
            trace.update(mirrorBatches=0,mirrorDrawCommands=0);trace['cameraBatches']=[b for b in trace['cameraBatches'] if b['role']!='mirror']
            with self.subTest(options=options),self.assertRaises(MarkerNotReady):read(values)

    def test_wrong_executed_root_mirror_camera_cannot_substitute_for_the_reflected_target(self):
        values=list(originals())
        for batch in values[0]['source']['renderTrace']['cameraBatches']:
            if batch['role']=='mirror':
                for camera in batch['cameras']:camera['view'][12]+=1
        with self.assertRaises((NativeUIError,MarkerNotReady)):read(values)
        self.assertEqual([5,1.6,-10],reflected([5,1.6,2],dict(position=[2,1.7,-4],rotation=[0,0,0,1])))

    def test_legacy_scene_geometry_missing_original_bytes_and_slow_archive_reduction_fail(self):
        values=list(originals());values[2]['source']['entities'][0]['dimensions'][0]+=1
        with self.assertRaises(NativeUIError):read(values)
        values=list(originals());values[1]=values[1][:-8]
        with self.assertRaises((ValueError,RuntimeError,AssertionError)):read(values)
        ticks=iter((0.,6.))
        with self.assertRaises(NativeUIError):read(originals(),monotonic=lambda:next(ticks))


if __name__=='__main__':unittest.main()
