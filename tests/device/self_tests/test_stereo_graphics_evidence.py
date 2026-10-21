"""Independent original stereo bytes/metadata at synthetic native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
import unittest
import uuid
from PIL import Image
from adapters.normal_ui import NativeUIError
from adapters.stereo_graphics_pixels import reduce_original,measure
from feature_journeys.stereo_graphics_evidence import PROFILE,analyse,observation,original_name
from feature_journeys.graphics_resources import GraphicsResources
from feature_journeys.graphics_fixture import scene as authored_scene
from feature_journeys.fixtures import marker_bytes
from feature_journeys.engine import Journey
from feature_journeys.scenarios import VERSION
from feature_journeys.evidence import MarkerNotReady
from self_tests.test_stereo_graphics_pixels import PixelBoundary,subject,RUN,TICKET,SCENE,ROOT
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_pico_graphics_source import Boundary as UiBoundary
from self_tests.test_owned_world_render import BINDING


class JourneyPixels(PixelBoundary):
    """Literal pixels independently derived for the actual authored geometry.

    P has unit focal lengths; each target eye is 800x800. Original camera eyes
    are x=+/-0.03 at world y=1.6. Near marker z=-.25 projects to literal 320x80
    cards; the far haze board and final mirror rectangle have separate ROIs.
    """
    def __init__(self,*,haze=True,mirror=True,card_ticket=TICKET,duplicate_right=False):
        super().__init__(card_ticket=card_ticket)
        image=Image.new('RGBA',(1600,800),(100,100,100,255))
        if haze:
            image.paste((25,90,210,255),(320,365,400,425));image.paste((25,90,210,255),(1120,365,1200,425))
        if mirror:
            image.paste((255,90,0,255),(540,300,665,475));image.paste((255,90,0,255),(1335,300,1460,475))
        with Image.open(io.BytesIO(marker_bytes(RUN,card_ticket))) as original:
            card=original.resize((320,80),Image.Resampling.NEAREST).convert('RGBA')
            image.paste(card,(288,248));image.paste(card,(992,248))
        if duplicate_right:image.paste(image.crop((0,0,800,800)),(800,0))
        output=io.BytesIO();image.save(output,format='PNG');self.raw=output.getvalue();self.pixels=hashlib.sha256(image.tobytes()).hexdigest()

    def camera_source(self,packet):
        super().camera_source(packet);source=packet['source']
        projection=[1,0,0,0,0,1,0,0,0,0,-1.002,-1,0,0,-.2002,0]
        source['stereo']['cameraView'][13]=-1.6
        source['renderTrace']['recordedView'].update(position=[0,1.6,0],projection=[projection[c*4+r] for r in range(4) for c in range(4)])
        for index,eye in enumerate(source['stereo']['eyes']):
            eye['projection']=projection.copy();eye['viewOffset'][12]=-.03 if index==0 else .03
        for batch in source['renderTrace']['cameraBatches']:
            for camera in batch['cameras']:
                camera['projection']=projection.copy();camera['view'][12]=.03 if camera['eye']=='left' else -.03
                camera['view'][13]=-1.6


def authored_subject():
    first,last=subject()
    for packet in (first,last):
        source=packet['source'];source['view']['position']=[0,1.6,0];source['avatarPose']['feetPosition']=[0,0,0]
        for document in authored_scene(RUN,SCENE,ROOT)['Entities']:
            row=next(row for row in source['entities'] if row['id']==document['id'].strip('{}'))
            row['type']=document['type']
            for field,axes in (('position','xyz'),('dimensions','xyz'),('rotation','xyzw')):row[field]=[document[field][a] for a in axes]
            row['mirrorMode']=document.get('mirrorMode','none');row['sourceUrl']=document.get('sourceUrl','')
            if 'color' in document:row['color']=[document['color'][a] for a in ('red','green','blue')]
            if document['type']=='Zone':
                haze=document['haze'];row.update(hazeMode=2,haze=dict(range=haze['hazeRange'],
                    color=[haze['hazeColor'][a] for a in ('red','green','blue')],altitudeEffect=haze['hazeAltitudeEffect'],
                    glare=haze['hazeEnableGlare'],backgroundBlend=haze['hazeBackgroundBlend']))
    return first,last


class Source:
    def __init__(self):
        self.provider=GraphicsResources(ROOT.rsplit('/runs/',1)[0],clock_ms=lambda:20000)
        self.provider.provision(RUN);self.provider.activate(RUN,SCENE)
        with self.provider.response(RUN,SCENE,request_authority='controlled.invalid',request_scheme='http') as response:
            status,body,nonce,write=response;write(dict(responseId=nonce,status=status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
        self.tick=0
    def acquire(self,ticket=TICKET,*,haze=True,mirror=True,duplicate_right=False,role='primary'):
        self.tick+=10;self.provider.activate(RUN,ticket)
        source=JourneyPixels(card_ticket=ticket,duplicate_right=duplicate_right,haze=haze,mirror=mirror)
        source.frame+=self.tick;source.execution+=self.tick;source.submission+=self.tick
        capture,raw=source.reader(stereo=True,require_cameras=True).read(0)
        capture['sequence']+=self.tick;capture['source']['acquisitionSequence']+=self.tick
        for row in capture['source']['renderTrace']['cameraBatches']:row['sequence']+=self.tick
        if not haze:capture['source']['renderTrace'].update(hazeBatches=0,hazeDrawCommands=0)
        if not mirror:
            capture['source']['renderTrace'].update(mirrorBatches=0,mirrorDrawCommands=0)
            capture['source']['renderTrace']['cameraBatches']=[row for row in capture['source']['renderTrace']['cameraBatches'] if row['role']!='mirror']
        first,last=authored_subject()
        for packet in (first,last):
            packet['sequence']+=self.tick
            packet['source'].update(subjectVersion=3,
                hmd=dict(display='OpenXR',active=True,visible=True,mounted=True,sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],
                    sensorPose=[1,0,0,0,0,1,0,0,0,0,1,0,0,1.6,0,1],worldPosition=[0,1.6,0],worldRotation=[0,0,0,1]),
                framework=dict(ownershipVersion=1,tablet=dict(frame=None,screen=None,home=None,highlight=None,miniFrame=None,miniScreen=None),
                    keyboard=dict(entityIds=[],anchor=None,textDisplay=None,backPlate=None,raised=False,use3D=True),pointers=[],entities=[]))
        native=NativeBoundary();native.sequence=self.tick
        native_before=native.reader().read(0);native_after=native.reader().read(0)
        for packet in (native_before,native_after):
            packet['processId']=31;packet['graphics'].update(requestedResolutionScale=.5,applicationResolutionScale=.5,hazeSetting=haze,mirrorsSetting=mirror)
        ui=UiBoundary();ui.sequence=self.tick;ui.shown=False;ui.roots=[];ui.controls=[]
        graphics=ui.source().capture()
        body=dict(stereoGraphicsEvidenceVersion=1,runId=RUN,ticket=ticket,sceneTicket=SCENE,fixtureUrl=ROOT,
            binding=deepcopy(BINDING),role=role,stage=0,nativeBefore=native_before,nativeAfter=native_after,
            subjectBefore=first,subjectAfter=last,graphics=graphics,capture=capture,
            provider=self.provider.snapshot(RUN,uuid.uuid4().hex))
        name=original_name(body)
        state=dict(resolution=.5,renderScale=.5,haze=haze,hazePass=haze,mirror=mirror,mirrorPass=mirror,dialog=False)
        sample=dict(schemaVersion=1,contractVersion=VERSION,runId=RUN,sequence=self.tick,capturedEpochMs=20000,state=state,
            artifacts=[dict(kind='image',name=name+'.png',sequence=self.tick,capturedEpochMs=20000,ticket=ticket,source='world-render-target'),
                dict(kind='file',name=name+'.native.json',sequence=self.tick,capturedEpochMs=20000,ticket=ticket)],
            resources=[],lifecycle=deepcopy(native_after['lifecycle']))
        return raw,body,sample


def encode(body):return json.dumps(body,sort_keys=True,separators=(',',':')).encode()


def verify(raw,body,sample,**options):return observation(raw,encode(body),RUN,body['ticket'],ROOT,PROFILE,sample,**options)


class StereoGraphicsEvidenceTests(unittest.TestCase):
    def test_whole_png_and_original_native_manifest_are_verified_without_retiming_or_static_roi(self):
        raw,body,sample=Source().acquire();observed,original=verify(raw,body,sample)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),observed['sha256'])
        self.assertEqual(hashlib.sha256(encode(body)).hexdigest(),observed['metadataSha256'])
        self.assertEqual({'left','right'},set(observed['eyes']));self.assertEqual(body['capture']['requestId'],original['requestId'])
        self.assertIsNone(observed['subjectChangedFraction']);self.assertEqual(20000,original['earliestEpochMs'])

    def test_pure_archive_reduction_is_explicit_and_does_not_fake_a_current_native_clock(self):
        raw,body,sample=Source().acquire();arguments=dict(run=RUN,ticket=TICKET,scene_ticket=SCENE,fixture_url=ROOT,pid=31)
        original=reduce_original(body['capture'],raw,body['subjectBefore'],body['subjectAfter'],**arguments)
        self.assertEqual(20000,original['capturedEpochMs'])
        with self.assertRaises(NativeUIError):measure(body['capture'],raw,body['subjectBefore'],body['subjectAfter'],
            **arguments,epoch=40000,clock_ms=lambda:40000,guard=lambda:True)
        self.assertEqual(original,reduce_original(body['capture'],raw,body['subjectBefore'],body['subjectAfter'],**arguments))

    def test_both_eyes_must_show_the_actual_new_challenge(self):
        raw,body,sample=Source().acquire(duplicate_right=True)
        with self.assertRaises(MarkerNotReady):verify(raw,body,sample)
        raw,body,sample=Source().acquire();body['ticket']='e'*32
        sample['artifacts'][0]['ticket']=sample['artifacts'][1]['ticket']=body['ticket']
        with self.assertRaises((ValueError,RuntimeError,AssertionError)):verify(raw,body,sample)

    def test_missing_original_context_native_metadata_or_old_subject_profiles_fail(self):
        edits=[lambda b:b.pop('capture'),lambda b:b.update(expectedState={}),lambda b:b['nativeAfter'].update(processId=32),
            lambda b:b['nativeAfter'].update(sequence=b['nativeBefore']['sequence']),
            lambda b:b['nativeAfter'].update(instance='f'*32),lambda b:b['binding'].update(processIdentity='32:foreign'),
            lambda b:b['subjectBefore']['source'].update(subjectVersion=2),lambda b:b['capture']['source'].update(captureVersion=2),
            lambda b:b['subjectAfter'].update(requestId=b['subjectBefore']['requestId']),
            lambda b:b['nativeAfter'].update(requestId=b['nativeBefore']['requestId']),
            lambda b:b['capture'].update(requestId='ios-'+b['capture']['requestId']),lambda b:b.update(role='actor')]
        for edit in edits:
            raw,body,sample=Source().acquire();edit(body)
            with self.subTest(edit=edit),self.assertRaises((RuntimeError,ValueError,AssertionError)):verify(raw,body,sample)

    def test_legacy_photometry_cannot_claim_world_effects_behind_a_visible_vr_tablet(self):
        raw,body,sample=Source().acquire();ui=UiBoundary()
        for row in ui.controls:
            if row['id']=='graphics.resolution':row.update(value=.5,nativeValue=.5)
            if row['id'] in ('graphics.haze','graphics.mirrors'):row.update(checked=True,nativeChecked=True)
        body['graphics']=ui.source().capture();sample['state']['dialog']=True
        # The existing actual Pico tablet is a world Model/Web entity and is
        # drawn before ToneMapping. A current near-marker, geometric ROI and
        # whole-frame pass count cannot establish that an open UI did not paint
        # these effect pixels. Legacy profile has no per-surface identity proof.
        with self.assertRaises(NativeUIError):verify(raw,body,sample)

    def test_current_marker_cannot_replace_actual_authored_geometry_or_original_http_delivery(self):
        for fault in ('no-response','foreign-color','moved-subject','wrong-haze','late-response'):
            raw,body,sample=Source().acquire()
            if fault=='no-response':body['provider']['responses']=[]
            elif fault=='late-response':
                body['provider']['capturedEpochMs']+=1;body['provider']['responses'][0]['completedEpochMs']+=1
            else:
                for key in ('subjectBefore','subjectAfter'):
                    source=body[key]['source']
                    row=next(row for row in source['entities'] if row['name'].endswith('-fog-board'))
                    if fault=='foreign-color':row['color'][0]-=1
                    elif fault=='moved-subject':row['position'][0]+=.1
                    else:next(row for row in source['entities'] if row['type']=='Zone')['haze']['range']+=1
            with self.subTest(fault=fault),self.assertRaises((RuntimeError,ValueError,AssertionError)):verify(raw,body,sample)

    def test_actual_tracked_head_must_be_at_the_scene_view_independently_of_a_decodable_card(self):
        raw,body,sample=Source().acquire()
        for key in ('subjectBefore','subjectAfter'):
            body[key]['source']['hmd']['sensorPose'][13]+=.1
            body[key]['source']['hmd']['worldPosition'][1]+=.1;body[key]['source']['view']['position'][1]+=.1
        with self.assertRaises((RuntimeError,ValueError,AssertionError)):verify(raw,body,sample)

    def test_adapter_state_retimed_artifact_or_wrong_native_file_cannot_replace_original_facts(self):
        for edit in (lambda v:v['state'].update(haze=False),lambda v:v.update(capturedEpochMs=20001),
            lambda v:v['artifacts'][0].update(capturedEpochMs=20001),lambda v:v['artifacts'][1].update(name='foreign.native.json'),
            lambda v:v['artifacts'][1].update(ticket='e'*32),lambda v:v['artifacts'].pop()):
            raw,body,sample=Source().acquire();edit(sample)
            with self.subTest(edit=edit),self.assertRaises((RuntimeError,ValueError,AssertionError)):verify(raw,body,sample)

    def test_effect_change_requires_actual_blue_change_in_each_original_eye(self):
        source=Source();raw_before,before,sample=source.acquire(haze=False)
        _evidence,previous=verify(raw_before,before,sample)
        raw,body,sample=source.acquire('e'*32,haze=True)
        evidence,_current=verify(raw,body,sample,previous=previous,changed=True)
        self.assertEqual('haze',evidence['change']['feature'])
        for value in evidence['change']['eyes'].values():
            self.assertGreater(value['blueDominanceDelta'],10);self.assertGreaterEqual(value['histogramChangeLowerBound'],.05)
        with Image.open(io.BytesIO(raw)) as original:
            image=original.copy();image.paste((100,100,100,255),(1120,365,1200,425))
            output=io.BytesIO();image.save(output,format='PNG');bad=output.getvalue()
        body['capture']['source']['image'].update(bytes=len(bad),sha256=hashlib.sha256(bad).hexdigest(),
            pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
        with self.assertRaises((RuntimeError,ValueError,AssertionError)):verify(bad,body,sample,previous=previous,changed=True)

    def test_source_frame_camera_geometry_and_native_settings_must_stay_comparable(self):
        source=Source();raw_before,before,sample=source.acquire(haze=False);_,previous=verify(raw_before,before,sample)
        raw,body,sample=source.acquire('e'*32,haze=True)
        for change in ('camera','extra-setting','frame','scene','extent','dialog'):
            old=deepcopy(previous)
            if change=='camera':old['cameras']['left'][0]['view'][12]+=.1
            elif change=='extra-setting':old['nativeGraphics']['requestedResolutionScale']=.6
            elif change=='scene':old['sceneSha256']='0'*64
            elif change=='extent':old['sourceExtent']=[400,200]
            elif change=='dialog':old['dialog']=not old['dialog']
            else:old['frameIndex']=body['capture']['source']['stereo']['frameIndex'];old['executionSequence']=body['capture']['source']['stereo']['executionSequence']
            with self.subTest(change=change),self.assertRaises((RuntimeError,ValueError,AssertionError)):verify(raw,body,sample,previous=old,changed=True)

    def journey(self,raw,body,sample):
        files={sample['artifacts'][0]['name']:raw,sample['artifacts'][1]['name']:encode(body)}
        journey=Journey('graphics',RUN,ROOT,invoke=lambda *_:None,witness=lambda *_:None,activate=lambda *_:None,
            read_artifact=files.__getitem__,image_policy=dict(screen=deepcopy(PROFILE)),continuity=lambda *_:None,
            monotonic=lambda:0.,epoch_ms=lambda:20000,sleep=lambda _:None,report=lambda _:None)
        return journey,files

    def test_common_engine_uses_original_metadata_and_refuses_reused_or_foreign_context_after_cache(self):
        raw,body,sample=Source().acquire();journey,files=self.journey(raw,body,sample)
        evidence,_=journey.artifacts(sample,TICKET,['image'])
        self.assertEqual(hashlib.sha256(encode(body)).hexdigest(),evidence[0]['observed']['metadataSha256'])
        self.assertEqual(1,len(journey.stereo_frames_seen))
        changed=deepcopy(sample);changed['sequence']+=1
        for item in changed['artifacts']:item['sequence']=changed['sequence']
        with self.assertRaises(AssertionError):journey.artifacts(changed,TICKET,['image'])
        self.assertEqual(1,len(journey.stereo_frames_seen))
        files[sample['artifacts'][1]['name']]=encode(body|dict(role='actor'))
        with self.assertRaises((RuntimeError,ValueError,AssertionError)):journey.artifacts(sample,TICKET,['image'])

    def test_successive_original_frames_advance_each_native_cursor_without_reusing_queries(self):
        source=Source();raw,body,sample=source.acquire();journey,files=self.journey(raw,body,sample)
        journey.artifacts(sample,TICKET,['image'])
        raw,body,sample=source.acquire('e'*32)
        files[sample['artifacts'][0]['name']]=raw;files[sample['artifacts'][1]['name']]=encode(body)
        journey.artifacts(sample,'e'*32,['image'])
        self.assertEqual(2,len(journey.stereo_frames_seen));self.assertEqual(14,len(journey.stereo_queries_seen))

    def test_fresh_png_cannot_hide_reused_source_queries_or_regressing_native_cursors(self):
        for corruption in ('capture','acquisition','camera','submission','native','subject','ui','query','context'):
            source=Source();raw,old,sample=source.acquire();journey,files=self.journey(raw,old,sample)
            journey.artifacts(sample,TICKET,['image']);previous=deepcopy(journey.stereo_cursors)
            raw,body,sample=source.acquire('e'*32)
            if corruption=='capture':body['capture']['sequence']=old['capture']['sequence']
            elif corruption=='acquisition':body['capture']['source']['acquisitionSequence']=old['capture']['source']['acquisitionSequence']
            elif corruption=='camera':
                for row in body['capture']['source']['renderTrace']['cameraBatches']:row['sequence']-=10
            elif corruption=='submission':body['capture']['source']['presentation']['submissionSequence']=old['capture']['source']['presentation']['submissionSequence']
            elif corruption=='native':body['nativeBefore']['sequence']=old['nativeAfter']['sequence']
            elif corruption=='subject':body['subjectBefore']['sequence']=old['subjectAfter']['sequence']
            elif corruption=='ui':body['graphics']['sourceSequence']=old['graphics']['sourceSequence']
            elif corruption=='query':body['subjectBefore']['requestId']=old['subjectBefore']['requestId']
            else:body['graphics']['instance']='f'*32
            files[sample['artifacts'][0]['name']]=raw;files[sample['artifacts'][1]['name']]=encode(body)
            with self.subTest(corruption=corruption),self.assertRaises((RuntimeError,ValueError,AssertionError)):
                journey.artifacts(sample,'e'*32,['image'])
            self.assertEqual(previous,journey.stereo_cursors)
            self.assertEqual(1,len(journey.stereo_frames_seen))

    def test_same_image_sample_cache_does_not_accept_mutated_state_or_artifact_ownership(self):
        raw,body,sample=Source().acquire();journey,files=self.journey(raw,body,sample)
        journey.artifacts(sample,TICKET,['image'])
        for change in ('state','lifecycle','artifact'):
            forged=deepcopy(sample)
            if change=='state':forged['state']['haze']=False
            elif change=='lifecycle':forged['lifecycle']['activations']+=1
            else:forged['artifacts'][0]['capturedEpochMs']+=1
            with self.subTest(change=change),self.assertRaises((RuntimeError,ValueError,AssertionError)):
                journey.artifacts(forged,TICKET,['image'])
        self.assertEqual(1,len(journey.stereo_frames_seen))

    def test_mirror_effect_requires_original_orange_change_in_both_eyes_and_pass_direction(self):
        source=Source();raw,body,sample=source.acquire(mirror=False);_,previous=verify(raw,body,sample)
        raw,body,sample=source.acquire('e'*32)
        evidence,_=verify(raw,body,sample,previous=previous,changed=True)
        self.assertEqual('mirror',evidence['change']['feature'])
        for row in evidence['change']['eyes'].values():self.assertGreater(row['orangeFractionDelta'],.005)
        with Image.open(io.BytesIO(raw)) as original:
            image=original.copy();image.paste((100,100,100,255),(1335,300,1460,475))
            output=io.BytesIO();image.save(output,format='PNG');bad=output.getvalue()
        body['capture']['source']['image'].update(bytes=len(bad),sha256=hashlib.sha256(bad).hexdigest(),
            pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
        with self.assertRaises((RuntimeError,ValueError,AssertionError)):verify(bad,body,sample,previous=previous,changed=True)

    def test_common_engine_requires_metadata_even_if_png_and_state_are_plausible(self):
        raw,body,sample=Source().acquire();journey,files=self.journey(raw,body,sample)
        sample['artifacts'].pop()
        with self.assertRaises(AssertionError):journey.artifacts(sample,TICKET,['image'])
        self.assertEqual({},journey.stereo_frames_seen)

    def test_closed_profile_and_bounded_unique_json_are_not_legacy_or_requested_evidence(self):
        raw,body,sample=Source().acquire()
        for metadata in (b'{"runId":1,"runId":2}',b'{'* (2*1024*1024+1),b'{"v":NaN}'):
            with self.subTest(size=len(metadata)),self.assertRaises((RuntimeError,ValueError,AssertionError)):
                observation(raw,metadata,RUN,TICKET,ROOT,PROFILE,sample)
        with self.assertRaises((RuntimeError,ValueError,AssertionError)):
            observation(raw,encode(body),RUN,TICKET,ROOT,PROFILE|dict(marker=[0,0,160,40]),sample)
