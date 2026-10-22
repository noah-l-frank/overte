"""Real decoded challenge/changed PNG pixels, native and GPU sources modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import unittest

from PIL import Image,ImageDraw
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.fixtures import marker_bytes
from feature_journeys.navigation_scene import scene,PROFILE
from ios.adapters import navigation_state, navigation_challenge as challenge
from ios.self_tests.test_ios_navigation_state import Boundary as State,RUN,URL
from ios.self_tests.test_ios_navigation_world_measurements import global_packet,rebind
from self_tests.test_native_vulkan_world_frame import World,request
from self_tests.test_native_completed_frame import view
from self_tests.test_completed_frame_lease import BINDING
from navigation_observation import viewpoint_urls

ROOT='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
PROVIDER='7'*32
SCENE_TICKET='8'*32


def marker_original(ticket=SCENE_TICKET):
    entry=scene(RUN,ticket,ROOT)['Entities'][-1]
    return dict(id=entry['id'].strip('{}'),present=True,entity=dict(name=entry['name'],type='Web',hostType='domain',
        sourceUrl=entry['sourceUrl'],position=[entry['position'][axis] for axis in 'xyz'],
        rotation=[entry['rotation'][axis] for axis in 'xyzw'],dimensions=[entry['dimensions'][axis] for axis in 'xyz'],
        visible=True,collisionless=True,lastEditedEpochUs=1700000000000000))


class MarkerState(State):
    def __init__(self):
        super().__init__();self.version=2;self.source['challengeMarker']=marker_original()


def bundle(label='A',ticket='9'*32,*,offset=0.,index=0,pixel_ticket=None):
    # New synthetic SDK packets only. No production evidence is converted,
    # repainted, retimed or wrapped as a fresh capture by this test builder.
    state=MarkerState();state.clock+=offset;state.sequence=4*index;reader=state.reader();epoch_before=state.epoch()
    x=0 if label=='A' else 2;url=viewpoint_urls(URL)[label]
    state.source['sceneUrl']=url;state.source['avatar']['feetPosition']=[x,0,4]
    state.source['view'].update(position=[x,1.6,4],aspectRatio=1.6)
    before=reader.read(RUN);gpu=World();gpu.clock=state.clock+.005;gpu.sequence=10*index
    gpu.source_extent=gpu.target_extent=[640,400];recorded=view();recorded['position']=[x,1.6,4]
    image=Image.new('RGBA',(640,400),(120,120,120,255));draw=ImageDraw.Draw(image)
    def screen(point):
        camera=[a-b for a,b in zip(point,recorded['position'])]+[1]
        clip=[sum(recorded['projection'][row*4+col]*camera[col] for col in range(4)) for row in range(4)]
        return [(clip[0]/clip[3]+1)*320,(1-clip[1]/clip[3])*200]
    wall=[screen(point) for point in [[-4,0,.75],[-4,4,.75],[4,4,.75],[4,0,.75]]]
    draw.polygon([tuple(point) for point in wall],fill=(180,80,180,255))
    actual=state.source['challengeMarker']['entity'];cx,cy,cz=actual['position'];w,h,_=actual['dimensions']
    left,top=screen([cx-w/2,cy+h/2,cz]);right,bottom=screen([cx+w/2,cy-h/2,cz]);left,top,right,bottom=map(round,(left,top,right,bottom))
    card=Image.open(BytesIO(marker_bytes(RUN,pixel_ticket or ticket))).convert('RGBA')
    image.paste(card.resize((right-left,bottom-top),Image.Resampling.NEAREST),(left,top))
    output=BytesIO();image.save(output,format='PNG');gpu.png=output.getvalue();gpu.raw_pixels=image.tobytes()
    def record(value):
        if 'source' in value and 'renderTrace' in value['source']:
            value['source']['renderTrace']['recordedView']=deepcopy(recorded)
            value['source']['renderTrace']['frameId']=str(index+1)*32
    def dimensions(value):
        if 'vulkanWorldFrameVersion' in value:value['source']['image'].update(width=640,height=400)
    gpu.change=record;gpu.fault=dimensions;frames=gpu.reader()
    query=dict(request(),requestId='ios-'+str(index+4)*32);capture=frames.perform(query);raw=frames.image(capture)
    frames.perform(dict(request('release','e'),requestId=query['requestId']));gpu.sleep(.2)
    retired=frames.perform(dict(request('inspect','f'),requestId=query['requestId']))
    state.clock=gpu.clock+.001;after=reader.read(RUN);epoch_after=state.epoch()+1
    frame=dict(navigationBefore=before,capture=capture,retirement=retired,navigationAfter=after,
        clockJoin=dict(clockJoinVersion=1,hostBeforeEpochMs=1_000_000.+offset*1000,
            hostAfterEpochMs=1_000_000.+offset*1000+epoch_after-epoch_before,hostBeforeMonotonic=10.+offset,
            hostAfterMonotonic=10.+offset+(epoch_after-epoch_before)/1000,
            nativeBefore=global_packet(epoch_before,1+index*2),nativeAfter=global_packet(epoch_after,2+index*2)))
    rebind(frame);body=json.dumps(scene(RUN,SCENE_TICKET,ROOT),separators=(',',':'),ensure_ascii=False).encode()
    provider=dict(navigationSceneVersion=1,instance=PROVIDER,runId=RUN,profile=PROFILE,sceneUrl=URL.split('?')[0],
        active=True,ticket=ticket,capturedEpochMs=123456,complete=True,responses=[dict(sequence=1,responseId='a'*32,
            ticket=SCENE_TICKET,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),completedEpochMs=123450)])
    return dict(frame=frame,raw=raw,captureQuery=query,url=url,label=label,ticket=ticket,provider=provider,
                providerInstance=PROVIDER,fixtureUrl=ROOT)


class NavigationChallengeTests(unittest.TestCase):
    def measure(self,sample,**options):return challenge.evaluate(RUN,BINDING,sample,**options)

    def test_native_v2_keeps_original_marker_type_source_geometry_and_explicit_absence(self):
        source=MarkerState();reader=source.reader();value=reader.read(RUN)
        self.assertEqual(2,value['iosNavigationStateVersion']);self.assertEqual(marker_original(),value['source']['challengeMarker'])
        source.source['challengeMarker'].update(present=False,entity=None);absent=reader.read(RUN)
        self.assertFalse(absent['source']['challengeMarker']['present']);self.assertIsNone(absent['source']['challengeMarker']['entity'])
        self.assertEqual(marker_original(),value['source']['challengeMarker'])

    def test_original_current_ticket_is_decoded_inside_measured_marker_and_real_scene(self):
        sample=bundle();original=deepcopy(sample);result,subject=self.measure(sample)
        self.assertEqual(original,sample);self.assertEqual(SCENE_TICKET,result['sceneTicket'])
        self.assertNotEqual(result['sceneTicket'],result['ticket']);self.assertEqual(sample['ticket'],result['ticket'])
        self.assertEqual(hashlib.sha256(sample['raw']).hexdigest(),result['image']['sha256'])
        self.assertEqual((128,96),subject.size);self.assertIsNone(result['image']['subjectChangedFraction'])
        self.assertEqual(digest(challenge.originals(sample)),result['originalsSha256'])

    def test_changed_ordinary_A_B_scene_uses_two_original_frames_and_not_marker_changes(self):
        for old_label,new_label in (('A','B'),('B','A')):
            a=bundle(old_label);b=bundle(new_label,'b'*32,offset=1.,index=1)
            result,_=self.measure(b,previous=a,changed=True)
            self.assertGreaterEqual(result['image']['subjectChangedFraction'],.05)
            self.assertEqual(SCENE_TICKET,result['sceneTicket'])

    def test_new_marker_ticket_without_changed_scene_subject_is_not_changed_evidence(self):
        a=bundle('A');second=bundle('A','b'*32,offset=1.,index=1)
        self.measure(second)
        with self.assertRaises(AssertionError):self.measure(second,previous=a,changed=True)

    def test_visible_old_or_foreign_ticket_fails_even_with_fresh_native_frame_metadata(self):
        with self.assertRaises(MarkerNotReady):self.measure(bundle(pixel_ticket='c'*32))
        sample=bundle();sample['ticket']='d'*32;sample['provider']['ticket']='d'*32
        with self.assertRaises(MarkerNotReady):self.measure(sample)

    def test_v1_scene_packets_cannot_invent_native_marker_observation(self):
        sample=bundle()
        for field in ('navigationBefore','navigationAfter'):
            sample['frame'][field]['iosNavigationStateVersion']=1;del sample['frame'][field]['source']['challengeMarker']
        rebind(sample['frame'])
        with self.assertRaises(NativeUIError):self.measure(sample)

    def test_foreign_marker_uuid_source_type_host_or_geometry_cannot_fill_current_run(self):
        for fault in ('uuid','source','type','host','position','hidden','absent'):
            sample=bundle()
            for field in ('navigationBefore','navigationAfter'):
                marker=sample['frame'][field]['source']['challengeMarker'];entry=marker['entity']
                if fault=='uuid':marker['id']='f'*32
                elif fault=='source':entry['sourceUrl']=entry['sourceUrl'].replace(RUN,'f'*32)
                elif fault=='type':entry['type']='Box'
                elif fault=='host':entry['hostType']='avatar'
                elif fault=='position':entry['position'][0]+=.2
                elif fault=='hidden':entry['visible']=False
                else:marker.update(present=False,entity=None)
            rebind(sample['frame'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.measure(sample)

    def test_native_v2_rejects_downgrade_unsafe_fields_and_foreign_original_marker_id(self):
        for fault in ('downgrade','absentEntity','booleanClock','foreignId'):
            source=MarkerState();reader=source.reader();first=reader.read(RUN)
            def mutate(value):
                if fault=='downgrade':value['iosNavigationStateVersion']=1;del value['source']['challengeMarker']
                elif fault=='absentEntity':value['source']['challengeMarker']['present']=False
                elif fault=='booleanClock':value['source']['challengeMarker']['entity']['lastEditedEpochUs']=True
                else:value['source']['challengeMarker']['id']='f'*32
            source.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)

    def test_marker_metadata_changed_inside_capture_is_not_one_stable_render_subject(self):
        sample=bundle();sample['frame']['navigationAfter']['source']['challengeMarker']['entity']['lastEditedEpochUs']+=1
        rebind(sample['frame'])
        with self.assertRaises(NativeUIError):self.measure(sample)

    def test_changed_images_must_preserve_native_scene_birth_and_provider_histories(self):
        for fault in ('sceneBirth','sceneHistory','providerHistory'):
            a=bundle('A');b=bundle('B','b'*32,offset=1.,index=1)
            if fault=='sceneBirth':
                for key in ('navigationBefore','navigationAfter'):b['frame'][key]['source']['sceneLoads']['instance']='f'*32
            elif fault=='sceneHistory':
                for key in ('navigationBefore','navigationAfter'):b['frame'][key]['source']['sceneLoads']['requests'][0]['id']='f'*32
            else:b['provider']['responses'][0]['responseId']='f'*32
            rebind(b['frame'])
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):self.measure(b,previous=a,changed=True)

    def test_source_delivery_receipt_is_input_and_cannot_replace_original_image_pixels(self):
        for fault in ('missing','hash','foreignProvider','retired','ticket'):
            sample=bundle();provider=sample['provider']
            if fault=='missing':provider['responses']=[]
            elif fault=='hash':provider['responses'][0]['sha256']='f'*64
            elif fault=='foreignProvider':provider['instance']='f'*32
            elif fault=='retired':provider.update(active=False,ticket=None)
            else:provider['ticket']='f'*32
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):self.measure(sample)

    def test_reused_frame_ticket_or_source_cursors_cannot_be_an_independent_previous_image(self):
        for fault in ('ticket','frame','request','sequence','nativeSequence','hostClock'):
            a=bundle('A');b=bundle('B','b'*32,offset=1.,index=1)
            if fault=='ticket':a=bundle('A','b'*32)
            elif fault=='frame':b['frame']['capture']['source']['renderTrace']['frameId']=a['frame']['capture']['source']['renderTrace']['frameId']
            elif fault=='request':
                for key in ('capture','retirement'):b['frame'][key]['requestId']=a['frame']['capture']['requestId']
                b['captureQuery']['requestId']=a['captureQuery']['requestId']
            elif fault=='sequence':b['frame']['capture']['sequence']=a['frame']['capture']['sequence']
            elif fault=='nativeSequence':
                for key in ('navigationBefore','navigationAfter'):b['frame'][key]['sequence']-=4
            else:
                b['frame']['clockJoin']['hostBeforeMonotonic']-=1;b['frame']['clockJoin']['hostAfterMonotonic']-=1
            rebind(b['frame'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.measure(b,previous=a,changed=True)


if __name__=='__main__':unittest.main()
