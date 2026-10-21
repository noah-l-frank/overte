"""Explicit owned VR surface fixture over short-lived loopback HTTP only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch
from feature_journeys.graphics_fixture import PICO_PROFILE,PICO_RESOURCE,LEGACY_PROFILE,pico_scene,scene
from feature_journeys.graphics_surface_cues import RESOURCES,png_bytes,document
from feature_journeys.graphics_resources import RESOURCE,resource_body,validate_status
from self_tests import test_graphics_resources as existing

TICKET=existing.TICKET
NEXT=existing.NEXT


class GraphicsSurfaceResourceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=existing.GraphicsResourcesTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.client=self.fixture.client;self.provider=self.fixture.provider
    def open(self):
        self.run,self.root=self.client.register('graphics',graphics_profile=PICO_PROFILE);self.client.activate(TICKET)
    def path(self,name,ticket=TICKET):return '/feature-fixture/v1/runs/'+self.run+'/tickets/'+ticket+'/'+name
    def validate(self,value,previous=None):return validate_status(value,instance=self.provider.instance,run=self.run,
        url=self.client.url,request=value['requestId'],previous=previous)

    def test_explicit_profile_has_seven_authored_entities_and_original_scene_html_png_receipts(self):
        self.open();before=self.client.graphics_status();self.assertEqual(2,before['graphicsProviderVersion']);self.assertEqual(PICO_PROFILE,before['profile'])
        status,body,_headers=self.fixture.fetch(self.path(PICO_RESOURCE));self.assertEqual(200,status)
        value=json.loads(body);self.assertEqual(pico_scene(self.run,TICKET,self.root),value);self.assertEqual(7,len(value['Entities']))
        web=[entity for entity in value['Entities'] if entity['type']=='Web'];self.assertEqual(3,len(web))
        self.assertTrue(all(entity['sourceUrl'].startswith(self.root+'tickets/'+TICKET+'/') for entity in web))
        for surface,stem in RESOURCES.items():
            status,body,headers=self.fixture.fetch(self.path(stem+'.html'));self.assertEqual(200,status);self.assertIn('text/html',headers['Content-Type'])
            self.assertEqual(document(self.run,TICKET,self.root,surface),body)
            status,body,headers=self.fixture.fetch(self.path(stem+'.png'));self.assertEqual(200,status);self.assertEqual('image/png',headers['Content-Type'])
            self.assertEqual(png_bytes(self.run,TICKET,surface),body)
        after=self.client.graphics_status();self.validate(after,before);self.assertEqual(5,len(after['responses']))
        self.assertEqual({PICO_RESOURCE}|{stem+suffix for stem in RESOURCES.values() for suffix in ('.html','.png')},{r['resource'] for r in after['responses']})
        self.client.close()

    def test_default_legacy_profile_and_reader_shape_remain_exactly_unchanged(self):
        run,root=self.client.register('graphics');self.client.activate(TICKET)
        value=self.client.graphics_status();self.assertEqual(1,value['graphicsProviderVersion']);self.assertNotIn('profile',value)
        status,body,_=self.fixture.fetch('/feature-fixture/v1/runs/'+run+'/tickets/'+TICKET+'/'+RESOURCE)
        self.assertEqual(200,status);self.assertEqual(scene(run,TICKET,root),json.loads(body))
        self.assertEqual(1,len([e for e in json.loads(body)['Entities'] if e['type']=='Web']))
        status,_body,_=self.fixture.fetch('/feature-fixture/v1/runs/'+run+'/tickets/'+TICKET+'/'+PICO_RESOURCE);self.assertEqual(404,status)
        self.client.close()

    def test_immutable_old_ticket_png_is_a_receipt_of_old_bytes_and_never_relabelled_current(self):
        self.open();name=RESOURCES['haze']+'.png';first=self.fixture.fetch(self.path(name))[1];self.client.activate(NEXT,'open')
        status,old,_=self.fixture.fetch(self.path(name));self.assertEqual(200,status);self.assertEqual(first,old)
        status,new,_=self.fixture.fetch(self.path(name,NEXT));self.assertEqual(200,status);self.assertNotEqual(old,new)
        value=self.client.graphics_status();self.validate(value)
        self.assertEqual([TICKET,TICKET,NEXT],[row['ticket'] for row in value['responses']])
        self.assertEqual([TICKET,NEXT,NEXT],[row['activeTicket'] for row in value['responses']]);self.assertEqual(TICKET,value['sceneTicket'])
        status,_body,_=self.fixture.fetch(self.path(PICO_RESOURCE,NEXT));self.assertEqual(404,status)
        self.client.close()

    def test_wrong_profile_area_unknown_fields_or_foreign_resource_fail_before_a_run_or_write(self):
        for area,profile in (('chat',PICO_PROFILE),('graphics','unknown'),('graphics',True)):
            with self.subTest(area=area,profile=profile),patch.object(self.client,'request') as request,self.assertRaises(ValueError):
                self.client.register(area,graphics_profile=profile)
            self.assertFalse(request.called)
        for body in (dict(area='graphics',graphicsProfile='unknown'),dict(area='chat',graphicsProfile=PICO_PROFILE),
                     dict(area='graphics',graphicsProfile=PICO_PROFILE,expectedState={})):
            status,_body,_=self.fixture.fetch('/feature-fixture/v1/runs',token=self.fixture.reader,value=body)
            self.assertEqual(400,status);self.assertEqual({},self.fixture.server.journal.runs)
        self.open();status,_body,_=self.fixture.fetch(self.path(RESOURCE));self.assertEqual(404,status)
        self.assertEqual([],self.client.graphics_status()['responses']);self.client.close()

    def test_profile_or_resource_hash_rewrite_and_downgrade_cannot_replace_original_history(self):
        self.open();self.fixture.fetch(self.path(PICO_RESOURCE));value=self.client.graphics_status()
        for change in ('profile','version','hash','resource','ticket'):
            bad=deepcopy(value)
            if change=='profile':bad['profile']=LEGACY_PROFILE
            elif change=='version':bad['graphicsProviderVersion']=1;bad.pop('profile')
            elif change=='hash':bad['responses'][0]['sha256']='0'*64
            elif change=='resource':bad['responses'][0]['resource']=RESOURCE
            else:bad['responses'][0]['ticket']='f'*32
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate(bad)
        self.client.close()

    def test_retired_profile_keeps_original_hashes_but_cannot_serve_more_world_cues(self):
        self.open();name=RESOURCES['reflection']+'.png';self.fixture.fetch(self.path(name));before=self.client.graphics_status();self.client.close()
        after=self.client.graphics_status();self.validate(after,before);self.assertFalse(after['active']);self.assertEqual(PICO_PROFILE,after['profile'])
        self.assertEqual(404,self.fixture.fetch(self.path(name))[0]);self.assertEqual(before['responses'],after['responses'])


if __name__=='__main__':unittest.main()
