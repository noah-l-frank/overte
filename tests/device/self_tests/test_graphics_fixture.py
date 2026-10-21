"""Controlled subject construction; no product render/effect qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import math
from pathlib import Path
import sys
import unittest
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_journeys.graphics_fixture import scene, VIEW
from feature_journeys.fixtures import payload

RUN='a'*32
TICKET='b'*32
ROOT='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'


class GraphicsFixtureTests(unittest.TestCase):
    def test_actual_entity_property_shapes_define_separate_fog_mirror_and_resolution_subjects(self):
        value=scene(RUN,TICKET,ROOT)
        self.assertEqual(3,value['DataVersion']);rows=value['Entities']
        self.assertEqual(7,len(rows));self.assertEqual(7,len({r['id'] for r in rows}))
        for row in rows:
            uuid.UUID(row['id']);self.assertTrue(row['name'].startswith('e2e-'+RUN+'-graphics-'))
        zone=next(r for r in rows if r['type']=='Zone')
        self.assertEqual('enabled',zone['hazeMode']);self.assertEqual(18,zone['haze']['hazeRange'])
        self.assertTrue(any(r.get('mirrorMode')=='mirror' for r in rows))
        self.assertTrue(any(r['dimensions']['x']==0.05 for r in rows))
        marker=next(r for r in rows if r['type']=='Web')
        self.assertEqual(ROOT+'tickets/'+TICKET+'/graphics-marker.v1.html',marker['sourceUrl'])
        self.assertNotIn('expected',json.dumps(value));self.assertNotIn('renderScale',json.dumps(value))

    def test_generator_is_deterministic_run_scoped_and_returns_independent_documents(self):
        first=scene(RUN,TICKET,ROOT);second=scene(RUN,TICKET,ROOT)
        self.assertEqual(first,second);first['Entities'].clear();self.assertEqual(7,len(second['Entities']))
        other='c'*32
        different=scene(other,TICKET,ROOT.replace(RUN,other))
        self.assertTrue({r['id'] for r in second['Entities']}.isdisjoint(r['id'] for r in different['Entities']))
        self.assertEqual(1.6,VIEW['position']['y'])

    def test_foreign_run_credentialed_or_queried_sources_are_rejected(self):
        for root in (ROOT.replace(RUN,'d'*32),ROOT+'?expected=on',ROOT+'#fragment',
                     ROOT.replace('controlled.invalid','user:secret@controlled.invalid'),'file:///private'):
            with self.subTest(root=root),self.assertRaises(ValueError):scene(RUN,TICKET,root)
        for run,ticket in (('wrong',TICKET),(RUN,True)):
            with self.assertRaises(ValueError):scene(run,ticket,ROOT)

    def test_world_marker_page_polls_only_actual_active_ticket_and_original_png(self):
        mime,body=payload('graphics-marker.v1.html',RUN,TICKET)
        self.assertTrue(mime.startswith('text/html'));text=body.decode()
        self.assertIn('/runs/'+RUN+'/current',text);self.assertIn('/marker.png',text)
        self.assertNotIn('EventBridge',text);self.assertNotIn('expected',text)
        self.assertNotIn('renderScale',text);self.assertNotIn('<input',text)

    def test_reflected_color_ray_crosses_the_actual_mirror_rectangle(self):
        rows={r['name'].split('-graphics-',1)[1]:r for r in scene(RUN,TICKET,ROOT)['Entities']}
        mirror,color=rows['reflector'],rows['reflected-color'];camera=VIEW['position']
        def crossing(position):
            virtual_z=2*mirror['position']['z']-position['z']
            fraction=(mirror['position']['z']-camera['z'])/(virtual_z-camera['z'])
            return {axis:camera[axis]+fraction*(position[axis]-camera[axis]) for axis in ('x','y')}
        def inside(point):
            return all(abs(point[axis]-mirror['position'][axis])<mirror['dimensions'][axis]/2 for axis in ('x','y'))
        self.assertTrue(inside(crossing(color['position'])))
        self.assertAlmostEqual(2,crossing(color['position'])['x'])
        self.assertFalse(inside(crossing(dict(x=0,y=1.6,z=2)))) # The old center never appeared in this mirror.
        self.assertGreater(color['position']['z'],camera['z']) # The primary view cannot see the real subject.

    def test_complete_marker_card_fits_declared_phone_landscape_projection(self):
        marker=next(r for r in scene(RUN,TICKET,ROOT)['Entities'] if r['type']=='Web')
        def inside(vertical_fov,aspect,position):
            half_height=math.tan(math.radians(vertical_fov/2))*(-position['z'])
            half_width=half_height*aspect
            return (abs(position['x'])+marker['dimensions']['x']/2<half_width
                and abs(position['y']-VIEW['position']['y'])+marker['dimensions']['y']/2<half_height)
        for fov,aspect in ((45,1.3),(55,16/9),(75,2.2)):
            with self.subTest(fov=fov,aspect=aspect):self.assertTrue(inside(fov,aspect,marker['position']))
        old=dict(x=-.5,y=2.7,z=-2)
        old_top=(old['y']-VIEW['position']['y']+.4/2)/(-old['z'])
        self.assertGreater(old_top,math.tan(math.radians(55/2))) # The old full-size card clipped at its top.

    def test_marker_geometry_retains_nominal_black_white_contrast_under_owned_haze(self):
        rows=scene(RUN,TICKET,ROOT)['Entities'];marker=next(r for r in rows if r['type']=='Web')
        haze=next(r for r in rows if r['type']=='Zone')['haze']
        distance=math.sqrt(sum((abs(marker['position'][axis]-VIEW['position'][axis])+marker['dimensions'][axis]/2)**2 for axis in 'xyz'))
        alpha=1-math.exp(math.log(.05)*distance/haze['hazeRange'])
        def srgb(linear):return 255*(12.92*linear if linear<=.0031308 else 1.055*linear**(1/2.4)-.055)
        black=[srgb(alpha*haze['hazeColor'][channel]/255) for channel in ('red','green','blue')]
        white=[srgb(1-alpha+alpha*haze['hazeColor'][channel]/255) for channel in ('red','green','blue')]
        self.assertLess(max(black),70);self.assertGreater(min(white),185)
        far_alpha=1-math.exp(math.log(.05)*2.5/haze['hazeRange'])
        self.assertGreater(srgb(far_alpha*haze['hazeColor']['blue']/255),70)


if __name__=='__main__':unittest.main()
