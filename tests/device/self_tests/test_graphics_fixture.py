"""Controlled subject construction; no product render/effect qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
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


if __name__=='__main__':unittest.main()
