"""Original PNG/scene/recorded-view/real GPU-absence Create joins at SDK seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import unittest

from PIL import Image
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.graphics_fixture import subject_ids
from ios.adapters import create_world_measurements as measurement
from ios.self_tests.test_ios_create_state import packet,version2,add_model,ID
from ios.self_tests.test_ios_graphics_world_measurements import world_bundle
from ios.self_tests.test_ios_graphics_measurements import RUN,TICKET,NATIVE,HOST,BINDING


def bundle():
    gpu,raw,policy,_=world_bundle();capture=gpu['capture'];view=capture['source']['renderTrace']['recordedView']
    before=version2(packet());before.update(iosCreateStateVersion=3,runId=RUN,instance='c'*32)
    before['clockBefore']=dict(epochMs=NATIVE+20,monotonicMs=20);before['clockAfter']=dict(epochMs=NATIVE+21,monotonicMs=21)
    source=before['source'];source['view'].update(position=view['position'],rotation=view['rotation'],fieldOfViewDegrees=view['fieldOfViewDegrees'],aspectRatio=view['aspectRatio'],uiWidth=640,uiHeight=400)
    marker_id=subject_ids(RUN)['marker'];original=next(row for row in gpu['subjectBefore']['source']['entities'] if row['id']==marker_id)
    marker=add_model(before);marker.update(id=marker_id,type='Web',model={},name='e2e-'+RUN+'-script',hostType='local',sourceUrl=original['sourceUrl'],
        userData=json.dumps(dict(kind='create-marker-v1',runId=RUN,nonce='d'*32)),collisionless=True,
        position=original['position'],rotation=original['rotation'],dimensions=original['dimensions'])
    model=deepcopy(marker);model.update(id=ID,type='Model',hostType='domain',name='e2e-'+RUN+'-model',sourceUrl='',userData='',
        model=dict(present=True,loaded=True,addedToScene=True,failed=False,textures=[]),position=[0,1,-3],dimensions=[1,1,1],modelURL='http://actual/model.gltf')
    source['entities'].append(model);source['entities'].sort(key=lambda row:row['id']);entries=[]
    for row in source['entities']:
        row.setdefault('position',[0,0,-3]);row.setdefault('rotation',[0,0,0,1]);row.setdefault('collisionless',False)
        wire=json.dumps(row,sort_keys=True).encode();entries.append(dict(id=row['id'],hostType=row['hostType'],ready=True,
            createdEpochUs=row['createdEpochUs'],lastEditedEpochUs=row['lastEditedEpochUs'],lastEditedAfterEpochUs=row['lastEditedEpochUs'],
            semanticBytes=len(wire),semanticSha256=hashlib.sha256(wire).hexdigest()))
    source['tree'].update(entities=entries,totalEntities=2,revisionBefore=1,revisionAfter=1)
    after=deepcopy(before);after.update(sequence=2,requestId='ios-'+'f'*32)
    after['clockBefore']=dict(epochMs=NATIVE+450,monotonicMs=450);after['clockAfter']=dict(epochMs=NATIVE+451,monotonicMs=451)
    frame=dict(createBefore=before,createAfter=after,capture=capture,retirement=gpu['retirement'],clockJoin=deepcopy(gpu['clockJoin']))
    rebind(frame)
    return frame,raw,policy,dict(nonce='d'*32,sourceUrl=original['sourceUrl'],id=marker_id)


def rebind(frame):
    raw=measurement.originals(frame);frame['clockJoin']['originalsSha256']=digest(raw)
    frame['clockJoin']['sourceTimes']=[dict(source=name,field=key,epochMs=packet[key]) for name,packet in raw.items()
        for key in ('capturedEpochMs','sampleEpochMs') if key in packet]


class CreateWorldMeasurementsTests(unittest.TestCase):
    def measure(self,sample,**kwargs):
        frame,raw,policy,marker=sample
        return measurement.compose(RUN,TICKET,BINDING,frame,raw,policy,[ID],marker,after_epoch=HOST,**kwargs)
    def test_original_png_actual_rendered_entity_geometry_and_retired_gpu_source_are_distinct_from_ui_ack(self):
        sample=bundle();original=deepcopy(sample[0]);observed,subject=self.measure(sample)
        self.assertEqual(['model'],observed['state']['objects']);self.assertEqual(HOST,observed['capturedEpochMs']);self.assertEqual(NATIVE+20,observed['nativeEpochMs'])
        self.assertEqual(original,sample[0]);self.assertEqual((128,96),subject.size)
    def test_wrong_gpu_target_clock_texture_hash_marker_identity_or_original_view_cannot_prove_pixels(self):
        for fault in ('callbacks','gpu','png','hash','source','view','order','foreignMarker','missingEntity'):
            frame,raw,policy,marker=bundle()
            if fault=='callbacks':frame['retirement']['source']['callbacks']=1
            elif fault=='gpu':frame['retirement']['source']['gpuBufferBytes']=4096
            elif fault=='png':frame['retirement']['source']['pngBytes']=10
            elif fault=='hash':frame['capture']['source']['image']['pixelSha256']='0'*64
            elif fault=='source':frame['capture']['source']['backend']='opengl'
            elif fault=='view':frame['createAfter']['source']['view']['position'][0]+=1
            elif fault=='order':frame['createBefore']['clockAfter']['epochMs']=frame['capture']['capturedEpochMs']+1
            elif fault=='foreignMarker':marker['id']=ID
            else:frame['createAfter']['source']['entities'].pop();frame['createAfter']['source']['tree']['entities'].pop();frame['createAfter']['source']['tree']['totalEntities']-=1
            rebind(frame)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.measure((frame,raw,policy,marker))
    def test_blank_stale_or_same_subject_originals_never_become_current_changed_evidence(self):
        sample=bundle();_,subject=self.measure(sample)
        with self.assertRaises(AssertionError):self.measure(sample,previous=subject,changed=True)
        frame,raw,policy,marker=bundle();image=Image.open(BytesIO(raw)).convert('RGBA')
        image.paste((128,128,128,255),tuple(policy['marker']));stream=BytesIO();image.save(stream,format='PNG');raw=stream.getvalue()
        frame['capture']['source']['image'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),pixelSha256=hashlib.sha256(image.tobytes()).hexdigest());rebind(frame)
        with self.assertRaises(MarkerNotReady):self.measure((frame,raw,policy,marker))
    def test_subject_crop_outside_marker_bits_must_also_exclude_the_actual_web_entity_surface(self):
        frame,raw,policy,marker=bundle();policy['subject']=[0,135,640,400]
        self.assertLess(policy['marker'][3],policy['subject'][1])
        from adapters.graphics_subject_geometry import projected_box
        row=next(row for row in frame['createAfter']['source']['entities'] if row['id']==marker['id'])
        actual=projected_box(row,frame['capture']['source']['renderTrace']['recordedView'],frame['capture']['source']['targetExtent'])
        self.assertLess(policy['subject'][1],actual[3])
        with self.assertRaises(NativeUIError):self.measure((frame,raw,policy,marker))

    def test_external_marker_and_subject_regions_must_correspond_to_actual_original_geometry(self):
        for field,rectangle in (('marker',[0,0,128,32]),('subject',[600,0,640,40]),('marker',[-1,0,128,32])):
            frame,raw,policy,marker=bundle();policy[field]=rectangle
            with self.subTest(field=field,rectangle=rectangle),self.assertRaises((NativeUIError,ValueError)):self.measure((frame,raw,policy,marker))


if __name__=='__main__':unittest.main()
