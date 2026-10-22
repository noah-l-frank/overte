"""Original owners/files and common engine; GPU/Qt/OS boundaries are synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack
from feature_journeys.engine import Journey
from feature_journeys.navigation_fixture import NavigationResources
from feature_journeys.navigation_scene import PROFILE as SCENE_PROFILE
from self_tests.test_navigation_resources import INPUTS
from feature_journeys.evidence import read_private_artifact
from feature_journeys.scenarios import SCENARIOS,VERSION
from feature_journeys.stereo_navigation_evidence import PROFILE,original_name,observation
from self_tests.test_navigation_arrival import Model as NativeModel,SCENE,RUN,TICKET
from self_tests.test_stereo_graphics_evidence import JourneyPixels

POLICY=dict(source='world-render-target',profile=PROFILE,sceneUrl=SCENE,
    eyes=dict(left=dict(marker=[296,256,552,320],subject=[300,345,500,500]),
              right=dict(marker=[1000,256,1256,320],subject=[1100,345,1300,500])))
NEXT='9'*32
ERRORS=(AssertionError,ValueError,NativeUIError)

class Source(NativeModel):
    def __init__(self):
        super().__init__();self.fault='';self.sample_sequence=0;self.fixture_url=self.client.url+'/runs/'+RUN+'/'
        self.navigation_provider=NavigationResources(dict(INPUTS,sceneUrl=SCENE,sourceRevision=self.binding['sourceRevision']),scene_profile=SCENE_PROFILE,clock_ms=self.epoch)
        self.navigation_provider.provision(RUN);self.navigation_provider.activate(RUN,TICKET)
        with self.navigation_provider.scene_response('/scene.json','',request_authority='controlled.invalid',request_scheme='http') as r:
            status,body,nonce,write=r;write(dict(status=status,responseId=nonce,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
        original=self.gpu.send
        def send(command):
            ticket=TICKET if self.fault=='stale-both' else self.active
            pixels=JourneyPixels(card_ticket=ticket,haze=self.position=='B')
            with Image.open(io.BytesIO(pixels.raw)) as old:
                image=old.copy()
                if self.position=='A':
                    image.paste((220,40,170,255),(320,365,400,425));image.paste((220,40,170,255),(1120,365,1200,425))
                if self.fault=='stale-right':
                    with Image.open(io.BytesIO(JourneyPixels(card_ticket=TICKET).raw)) as stale:image.paste(stale.crop((800,0,1600,800)),(800,0))
                elif self.fault=='duplicated-eye':image.paste(image.crop((0,0,800,800)),(800,0))
                elif self.fault=='unchanged-subject':
                    with Image.open(io.BytesIO(JourneyPixels(card_ticket=self.active,haze=True).raw)) as unchanged:
                        for roi in (POLICY['eyes']['left']['subject'],POLICY['eyes']['right']['subject']):image.paste(unchanged.crop(roi),tuple(roi[:2]))
                elif self.fault=='unchanged-right':image.paste((25,90,210,255),(1120,365,1200,425))
                elif self.fault=='blank-left':image.paste((100,100,100,255),tuple(POLICY['eyes']['left']['subject']))
                out=io.BytesIO();image.save(out,format='PNG');self.gpu.raw=out.getvalue()
                self.gpu.pixels=hashlib.sha256(image.tobytes()).hexdigest();self.storage.raw=self.gpu.raw
            return original(command)
        self.gpu.send=send
    def acquire(self,ticket=TICKET,position='B'):
        self.active=ticket;self.position=position;self.sample_sequence+=1;self.navigation_provider.activate(RUN,ticket)
        journal_id=uuid.uuid4().hex
        owner=self.stereo(self.artifacts/original_name(RUN,'primary',journal_id),journal_id=journal_id);owner.acquire(ticket)
        sample=dict(schemaVersion=1,contractVersion=VERSION,runId=RUN,sequence=self.sample_sequence,capturedEpochMs=20000,
            state=dict(SCENARIOS['world-navigation']['baseline'],location=position),resources=[],
            lifecycle=dict(backgrounds=0,activations=1,launches=1),artifacts=owner.artifacts(self.sample_sequence))
        return owner.image_bytes(),owner.store.path.read_bytes(),sample

class NavigationStereoEvidenceTests(unittest.TestCase):
    def setUp(self):self.source=Source();self.addCleanup(self.source.close)
    def verify(self,raw,metadata,sample,ticket=TICKET,**kw):
        return observation(raw,metadata,RUN,ticket,self.source.fixture_url,POLICY,sample,**kw)
    def journey(self):
        journey=Journey('world-navigation',RUN,self.source.fixture_url,invoke=lambda *_:None,witness=lambda *_:None,activate=lambda *_:None,
            read_artifact=lambda name:read_private_artifact(self.source.artifacts,name),image_policy=dict(screen=deepcopy(POLICY)),
            continuity=lambda *_:None,monotonic=lambda:0.,epoch_ms=lambda:20000,sleep=lambda _:None,report=lambda _:None,navigation_source=lambda:self.source.navigation_provider.snapshot(RUN))
        journey.navigation(TICKET,20000);return journey
    def test_original_journal_and_png_decode_fresh_challenge_and_changed_subject_in_both_eyes(self):
        raw,metadata,sample=self.source.acquire();evidence,previous=self.verify(raw,metadata,sample)
        self.assertEqual('B',evidence['location']);self.assertEqual({'left','right'},set(evidence['eyes']))
        self.assertTrue(all(v['subjectChangedFraction'] is None for v in evidence['eyes'].values()))
        raw,metadata,sample=self.source.acquire(NEXT,'A');evidence,_=self.verify(raw,metadata,sample,NEXT,previous=previous,changed=True)
        self.assertTrue(all(v['subjectChangedFraction']>=.05 for v in evidence['eyes'].values()))
        self.assertEqual([],list(self.source.native_root.iterdir()));self.assertIsNone(self.source.owner_store('primary').read())
    def test_stale_right_eye_duplicated_mono_or_uniform_subject_fails_independently(self):
        for fault in ('stale-right','duplicated-eye','blank-left','stale-both'):
            source=Source()
            try:
                source.fault=fault;raw,metadata,sample=source.acquire(NEXT)
                with self.subTest(fault=fault),self.assertRaises(ERRORS):observation(raw,metadata,RUN,NEXT,source.fixture_url,POLICY,sample)
            finally:source.close()
    def test_changing_only_current_marker_or_only_one_world_eye_cannot_prove_navigation_change(self):
        raw,metadata,sample=self.source.acquire();_,previous=self.verify(raw,metadata,sample)
        for fault in ('unchanged-subject','unchanged-right'):
            source=Source()
            try:
                source.fault=fault;raw,metadata,sample=source.acquire(NEXT,'A')
                old=deepcopy(previous);old['cursors']={k:v-100 for k,v in old['cursors'].items()}
                with self.subTest(fault=fault),self.assertRaises(ERRORS):
                    observation(raw,metadata,RUN,NEXT,source.fixture_url,POLICY,sample,previous=old,changed=True)
            finally:source.close()
    def test_regions_must_be_inside_actual_original_eye_and_disjoint_from_marker(self):
        raw,metadata,sample=self.source.acquire()
        for change in ('cross-eye','overlap','version','boolean','scene'):
            bad=deepcopy(POLICY)
            if change=='cross-eye':bad['eyes']['right']['marker']=deepcopy(bad['eyes']['left']['marker'])
            elif change=='overlap':bad['eyes']['left']['subject']=[300,260,400,300]
            elif change=='version':bad['profile']='pico-stereo-navigation-v2'
            elif change=='boolean':bad['eyes']['left']['marker'][0]=True
            else:bad['sceneUrl']='http://foreign.invalid/scene.json'
            with self.subTest(change=change),self.assertRaises(ERRORS):observation(raw,metadata,RUN,TICKET,self.source.fixture_url,bad,sample)
    def test_original_pose_frame_role_ticket_and_native_retirement_cannot_be_replaced(self):
        raw,metadata,sample=self.source.acquire()
        for change in ('pose','frame','mono','memory','files','role','ticket','image','extra'):
            disk=json.loads(metadata);state=unpack(disk['payload'])[0]
            if change=='pose':state['frame']['after']['probe']['avatar']['feetPosition']['x']=0
            elif change=='frame':state['frame']['capture']['source']['presentation']['frameIndex']+=1
            elif change=='mono':state['frame']['capture']['source']['view']='main-mono'
            elif change=='memory':state['memory']['present']=True
            elif change=='files':state['proof']['files']['absent']['source']['complete']=False
            elif change=='role':disk['role']='actor'
            elif change=='ticket':state['ticket']=NEXT
            elif change=='image':state['image']['name']='foreign.png'
            else:state['requestedLocation']='B'
            disk['payload']=pack([state])
            with self.subTest(change=change),self.assertRaises(ERRORS):self.verify(raw,json.dumps(disk).encode(),sample)
    def test_current_sample_keeps_original_epoch_location_and_artifact_identity(self):
        raw,metadata,sample=self.source.acquire()
        for change in ('time','location','lifecycle','ticket','metadata','image'):
            bad=deepcopy(sample)
            if change=='time':bad['capturedEpochMs']+=1
            elif change=='location':bad['state']['location']='A'
            elif change=='lifecycle':bad['lifecycle']['launches']+=1
            elif change=='ticket':bad['artifacts'][0]['ticket']=NEXT
            elif change=='metadata':bad['artifacts'][1]['name']='foreign.json'
            else:bad['artifacts'][0]['name']='foreign.png'
            with self.subTest(change=change),self.assertRaises(ERRORS):self.verify(raw,metadata,bad)
        for invalid in (b'{"payload":1,"payload":2}',b'{'*(65536+1),b'{"value":NaN}'):
            with self.subTest(size=len(invalid)),self.assertRaises(ERRORS):self.verify(raw,invalid,sample)
    def test_common_engine_rejects_republication_with_fresh_sample_sequence_and_accepts_new_frames(self):
        raw,metadata,sample=self.source.acquire();journey=self.journey()
        evidence,previous=journey.artifacts(sample,TICKET,['image']);self.assertEqual(1,len(journey.navigation_stereo_frames))
        self.assertEqual(hashlib.sha256(metadata).hexdigest(),evidence[0]['observed']['metadataSha256'])
        replay=deepcopy(sample);replay['sequence']+=1
        for item in replay['artifacts']:item['sequence']=replay['sequence']
        with self.assertRaises(ERRORS):journey.artifacts(replay,TICKET,['image'])
        self.assertEqual(1,len(journey.navigation_stereo_frames))
        journey.previous_subject=previous;raw,metadata,sample=self.source.acquire(NEXT,'A');journey.navigation(NEXT,20000)
        evidence,_=journey.artifacts(sample,NEXT,['changed']);self.assertEqual(2,len(journey.navigation_stereo_frames))
        self.assertTrue(all(row['subjectChangedFraction']>=.05 for row in evidence[0]['observed']['eyes'].values()))
    def test_source_query_cursors_and_birth_cannot_be_reused_under_new_image(self):
        raw,metadata,sample=self.source.acquire();journey=self.journey();journey.artifacts(sample,TICKET,['image'])
        raw,metadata,sample=self.source.acquire(NEXT,'A');journey.navigation(NEXT,20000);filename=self.source.artifacts/sample['artifacts'][1]['name']
        for fault in ('query','capture','native','camera','probe','frame-id','ui-query','native-query','ui-cursor'):
            disk=json.loads(metadata);state=unpack(disk['payload'])[0];old=next(iter(journey.navigation_stereo_cursors.values()))[1]
            if fault=='frame-id':state['frame']['capture']['source']['renderTrace']['frameId']=old['frameId']
            elif fault=='ui-query':state['frame']['uiBefore']['commandId']=old['requests']['uiBefore']
            elif fault=='native-query':state['frame']['nativeBefore']['requestId']=old['requests']['nativeBefore']
            elif fault=='ui-cursor':state['frame']['uiBefore']['sourceSequence']=1
            elif fault=='query':state['frame']['before']['subject']['requestId']=old['requests']['subjectBefore'];state['before']=deepcopy(state['frame']['before'])
            elif fault=='native':state['frame']['before']['subject']['instance']='8'*32;state['frame']['after']['subject']['instance']='8'*32;state['before']=deepcopy(state['frame']['before'])
            elif fault=='capture':state['frame']['capture']['sequence']=old['cursors']['capture']
            elif fault=='probe':state['frame']['before']['probe']['sampleSequence']=1;state['before']=deepcopy(state['frame']['before'])
            else:
                for row in state['frame']['capture']['source']['renderTrace']['cameraBatches']:row['sequence']-=3
            state['image']['capture']=deepcopy(state['frame']['capture']);disk['payload']=pack([state]);filename.write_text(json.dumps(disk))
            with self.subTest(fault=fault),self.assertRaises(ERRORS):journey.artifacts(sample,NEXT,['image'])
            self.assertEqual(1,len(journey.navigation_stereo_frames))
    def test_multiple_fresh_frames_under_one_action_keep_distinct_original_journals(self):
        journey=self.journey();paths=set()
        for _ in range(3):
            raw,metadata,sample=self.source.acquire();journey.artifacts(sample,TICKET,['image'])
            paths.add(sample['artifacts'][1]['name'])
        self.assertEqual(3,len(paths));self.assertEqual(3,len(journey.navigation_stereo_frames))
        self.assertEqual(21,len(journey.navigation_stereo_queries))
    def test_visible_tablet_keyboard_or_focused_editor_is_refused_before_world_capture(self):
        for fault in ('tablet','keyboard','editor'):
            source=Source()
            try:
                if fault=='tablet':source.ui.shown=True
                elif fault=='keyboard':source.ui.keyboard=True
                else:source.ui.focused=True
                with self.subTest(fault=fault),self.assertRaises(ERRORS):source.acquire()
                self.assertEqual(0,len(source.gpu.commands));self.assertIsNone(source.owner_store('primary').read())
            finally:source.close()
    def test_ui_reappearance_or_source_replacement_during_capture_cannot_supply_world_evidence(self):
        for fault in ('shown','generation','input','cursor'):
            source=Source()
            try:
                original=source.gpu.send
                def changed(command):
                    result=original(command)
                    if fault=='shown':source.ui.shown=True
                    elif fault=='generation':source.ui.edit=lambda v:v.update(generation='8'*32)
                    elif fault=='input':source.ui.edit=lambda v:v.update(lastCommandSequence=1)
                    else:source.ui.edit=lambda v:v.update(sourceSequence=1)
                    return result
                source.gpu.send=changed
                with self.subTest(fault=fault),self.assertRaises(ERRORS):source.acquire()
                self.assertIsNotNone(source.owner_store('primary').read())
            finally:source.close()

    def test_engine_requires_prior_original_scene_write_and_matching_candidate_revision(self):
        raw,metadata,sample=self.source.acquire();journey=self.journey()
        source=deepcopy(journey.navigation_previous)
        for fault in ('none','absent','future','build'):
            journey.navigation_previous=deepcopy(source)
            if fault=='none':journey.navigation_previous=None
            elif fault=='absent':journey.navigation_previous['responses']=[]
            elif fault=='future':journey.navigation_previous['responses'][0]['completedEpochMs']+=1
            else:journey.navigation_previous['inputs']['sourceRevision']='8'*40
            with self.subTest(fault=fault),self.assertRaises(AssertionError):journey.artifacts(sample,TICKET,['image'])
            self.assertEqual({},journey.navigation_stereo_frames)
        journey.navigation_previous=source;journey.artifacts(sample,TICKET,['image'])
    def test_actual_pico_factory_acquires_original_ui_pose_lifecycle_and_world_source_under_same_lock(self):
        root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        fixture=native_fixture.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter=fixture.instance();m=self.source;m.position='B'
        adapter._scripts=lambda target:SimpleNamespace(binding=m.binding)
        adapter._native_feature_observer=lambda target:m._native_feature_observer(target,read_only=True)
        adapter._graphics_subject_observer=lambda target:m.subject_reader()
        adapter.read_probe_snapshot=lambda target,package,after:m.probe(after)
        adapter._world_render_capture=m._world_render_capture
        def write(target,package,path,raw):
            self.assertEqual('owned',target);m.ui.write('synthetic',package,path,raw)
        def read(target,package,path,**options):
            self.assertEqual('owned',target);return m.ui.read('synthetic',package,path,**options)
        adapter.adb.write_debug_app_file=write;adapter.adb.read_debug_app_file=read
        def lock(_self,target,provided=None):
            self.assertEqual('owned',target);self.assertIs(m.lock,provided);return provided
        journal_id=uuid.uuid4().hex;path=m.artifacts/original_name(RUN,'primary',journal_id)
        with patch('adapters.pico4.graphics_binding.PicoGraphicsBinding._lock',lock):
            owner=adapter._navigation_stereo('owned',path,m.artifacts,RUN,SCENE,source_lock=m.lock,journal_id=journal_id)
            state=owner.acquire(TICKET)
        self.assertEqual(2,state['frame']['navigationStereoSourceVersion']);self.assertEqual(2,len(m.ui.requests))
        self.assertEqual(2,len(m.features.commands));self.assertEqual(2,len(m.subject.commands));self.assertEqual(1,len(m.gpu.commands))
        self.assertEqual(2,len(owner.artifacts(1)));self.assertFalse(list(m.native_root.iterdir()))

    def test_monotonic_budget_and_missing_metadata_fail_without_cache_success(self):
        raw,metadata,sample=self.source.acquire();tick=iter([0.,0.,6.])
        with self.assertRaises(ERRORS):self.verify(raw,metadata,sample,monotonic=lambda:next(tick))
        journey=self.journey();sample['artifacts'].pop()
        with self.assertRaises(AssertionError):journey.artifacts(sample,TICKET,['image'])
        self.assertEqual({},journey.navigation_stereo_frames)

if __name__=='__main__':unittest.main()
