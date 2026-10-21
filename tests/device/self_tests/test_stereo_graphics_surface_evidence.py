"""Independent v2 artifact verifier with synthetic source/UI/GPU boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
import uuid
from adapters.normal_ui import NativeUIError
from feature_journeys.graphics_fixture import PICO_PROFILE,PICO_RESOURCE
from feature_journeys.graphics_resources import GraphicsResources
from feature_journeys.graphics_surface_cues import RESOURCES
from feature_journeys.stereo_graphics_evidence import SURFACE_PROFILE,PROFILE,observation,original_name,advance
from feature_journeys.evidence import MarkerNotReady
from self_tests.test_stereo_graphics_evidence import Source as LegacySource
from self_tests.test_stereo_graphics_surfaces import originals,SurfacePixels
from self_tests.test_stereo_graphics_pixels import RUN,TICKET,SCENE,ROOT
from self_tests.test_pico_graphics_composition import composition
from self_tests.test_pico_graphics_source import Boundary as UiBoundary
from self_tests.test_vr_graphics_subject import entity


class Source(LegacySource):
    def __init__(self):
        self.provider=GraphicsResources(ROOT.rsplit('/runs/',1)[0],clock_ms=lambda:20000)
        self.provider.provision(RUN,profile=PICO_PROFILE);self.provider.activate(RUN,SCENE);self.tick=0
        for resource in (PICO_RESOURCE,*[stem+'.html' for stem in RESOURCES.values()]):self.deliver(SCENE,resource)
    def deliver(self,ticket,resource):
        with self.provider.response(RUN,ticket,request_authority='controlled.invalid',request_scheme='http',resource=resource) as response:
            status,body,nonce,write=response;write(dict(responseId=nonce,status=status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
    def acquire(self,ticket=TICKET,*,haze=True,mirror=True,render_haze=None,render_mirror=None):
        _raw,body,sample=super().acquire(ticket,haze=haze,mirror=mirror)
        pixels=SurfacePixels(ticket=ticket,haze=haze if render_haze is None else render_haze,
            mirror=mirror if render_mirror is None else render_mirror)
        pixels.frame+=self.tick;pixels.execution+=self.tick;pixels.submission+=self.tick
        capture,raw=pixels.reader(stereo=True,require_cameras=True).read(0)
        capture['sequence']+=self.tick;capture['source']['acquisitionSequence']+=self.tick
        for batch in capture['source']['renderTrace']['cameraBatches']:batch['sequence']+=self.tick
        prior=body['capture']['source']
        for field in ('hazeBatches','hazeDrawCommands','mirrorBatches','mirrorDrawCommands'):
            capture['source']['renderTrace'][field]=prior['renderTrace'][field]
        if not mirror:capture['source']['renderTrace']['cameraBatches']=[b for b in capture['source']['renderTrace']['cameraBatches'] if b['role']!='mirror']
        template=originals()[2]['source']
        comp=composition();screen,frame=comp['screen']['id'],comp['screen']['parentId']
        for packet in (body['subjectBefore'],body['subjectAfter']):
            packet['source']=deepcopy(template);framework=packet['source']['framework'];framework['tablet'].update(screen=screen,frame=frame)
            framework['entities']=[entity(key) for key in sorted((screen,frame))]
            next(row for row in framework['entities'] if row['id']==screen).update(type='Web',parentId=frame)
            packet['source']['scan']['unowned']=[dict(id=key,sha256='d'*64) for key in sorted((screen,frame))]
            packet['source']['scan']['scannedEntities']=9
        ui=UiBoundary();ui.sequence=self.tick
        for row in ui.controls:
            if row['id']=='graphics.resolution':row.update(value=.5,nativeValue=.5)
            if row['id'] in ('graphics.haze','graphics.mirrors'):
                actual=haze if row['id']=='graphics.haze' else mirror;row.update(checked=actual,nativeChecked=actual)
        ui.edit=lambda packet:packet.update(graphicsObservationVersion=2,composition=deepcopy(comp))
        reader=ui.source();before,after=reader.capture(),reader.capture()
        for stem in RESOURCES.values():self.deliver(ticket,stem+'.png')
        body.update(stereoGraphicsEvidenceVersion=2,capture=capture,graphics=before,graphicsAfter=after,
            provider=self.provider.snapshot(RUN,uuid.uuid4().hex))
        name=original_name(body)
        sample['state']['dialog']=True;sample['resources']=['panel:graphics','panel:graphics-tablet']
        for item,suffix in zip(sample['artifacts'],('.png','.native.json')):item['name']=name+suffix
        return raw,body,sample


def verify(values,**options):
    raw,body,sample=values
    return observation(raw,json.dumps(body,sort_keys=True,separators=(',',':')).encode(),RUN,body['ticket'],ROOT,SURFACE_PROFILE,sample,**options)


class StereoGraphicsSurfaceEvidenceTests(unittest.TestCase):
    def test_open_actual_tablet_requires_original_composition_and_both_world_codes_in_both_eyes(self):
        values=Source().acquire();value,subject=verify(values)
        self.assertEqual(2,value['stereoGraphicsEvidenceVersion']);self.assertTrue(subject['dialog'])
        self.assertEqual({'left','right'},set(value['eyes']));self.assertIn('uiAfter',subject['requests'])

    def test_haze_and_mirror_changes_require_original_direction_with_one_setting_change(self):
        for feature in ('haze','mirror'):
            source=Source();before=verify(source.acquire())[1]
            _value,current=verify(source.acquire('e'*32,**{feature:False}),previous=before,changed=True)
            advance(before,current)
            self.assertFalse(current['nativeGraphics']['hazeSetting' if feature=='haze' else 'mirrorsSetting'])

    def test_ignored_haze_pixels_or_ignored_mirror_render_cannot_pass_changed_state(self):
        for feature in ('haze','mirror'):
            source=Source();before=verify(source.acquire())[1]
            values=source.acquire('e'*32,**{feature:False,'render_'+feature:True})
            with self.subTest(feature=feature),self.assertRaises((NativeUIError,MarkerNotReady)):verify(values,previous=before,changed=True)

    def test_translucent_unknown_foreign_or_changed_composition_and_old_or_reused_ui_fail(self):
        edits=[lambda b:b['graphics']['composition']['screen'].update(alpha=.5),
            lambda b:b['graphics']['composition']['root']['color'].__setitem__(3,.8),
            lambda b:b['graphics']['composition'].update(complete=False),
            lambda b:b['graphics']['composition']['screen'].update(parentId='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
            lambda b:b['graphicsAfter']['composition']['root'].update(id='a'*32),
            lambda b:b['graphicsAfter'].update(commandId=b['graphics']['commandId']),
            lambda b:b['graphicsAfter'].update(sourceSequence=b['graphics']['sourceSequence']),
            lambda b:b['graphicsAfter'].update(graphicsObservationVersion=1)]
        for edit in edits:
            values=Source().acquire();edit(values[1])
            with self.subTest(edit=edit),self.assertRaises((ValueError,RuntimeError,AssertionError)):verify(values)

    def test_missing_original_http_code_delivery_wrong_profile_and_policy_version_cannot_be_substituted(self):
        for field in ('html','png','scene','profile'):
            values=Source().acquire();body=values[1]
            if field=='profile':body['provider']['profile']='legacy-v2'
            else:body['provider']['responses']=[r for r in body['provider']['responses'] if not r['resource'].endswith('.'+field if field!='scene' else '.json')]
            # A separate hypothetical provider never delivered this resource;
            # its remaining ledger is structurally valid, not a broken prefix.
            for index,row in enumerate(body['provider']['responses'],1):row['sequence']=index
            with self.subTest(field=field),self.assertRaises((ValueError,RuntimeError,AssertionError)):verify(values)
        raw,body,sample=Source().acquire()
        with self.assertRaises(NativeUIError):observation(raw,json.dumps(body).encode(),RUN,TICKET,ROOT,PROFILE,sample)


if __name__=='__main__':unittest.main()
