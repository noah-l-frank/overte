"""World document/entity brackets through original stereo/file retirement owners.

Entity/DOM/Android/Qt/GPU producers and rendered pixels remain explicit host
seams. The actual consumers, original file bytes and ownership transitions run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import unittest
import uuid
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.world_browser_ray import PicoWorldBrowserIO
from adapters.pico4.browser_stereo import PicoBrowserStereo,original_name
from adapters.pico4.browser_stereo_source import validate
from feature_journeys.engine import Journey
from feature_journeys.evidence import read_private_artifact
from feature_journeys.scenarios import VERSION
from feature_journeys.stereo_browser_evidence import WORLD_PROFILE,observation,archive_sources
from self_tests.test_pico_browser_stereo import Model as TabletModel,BrowserBoundary,RuntimeBoundary,URL,FOREIGN,OWNER,SCRIPT,SCENE,RUN,TICKET
from self_tests.test_stereo_navigation_evidence import POLICY as NAVIGATION_POLICY

ENTITY='12345678-1234-1234-1234-123456789abc'
DOCUMENT=URL+'tickets/'+TICKET+'/index.html'
POLICY=dict(deepcopy(NAVIGATION_POLICY),profile=WORLD_PROFILE)
ERRORS=(AssertionError,ValueError,RuntimeError)


class WorldBrowserBoundary(BrowserBoundary):
    def __init__(self,model):super().__init__(model);self.ray_edit=None
    def send(self,request):
        if request['operation']=='observe':
            super().send(request);source=self.sample['source'];current=source['current']
            for row in source['documents']:row['url']=DOCUMENT
            current['surface']='world';view=current['source']['nativeView']
            view.update(url=DOCUMENT,sourceUrl=DOCUMENT,sourceIdentity='web-entity:'+ENTITY)
            current['source']['dom']['document'].update(href=DOCUMENT)
            current['source']['dom']['document'].pop('title')
            source.pop('deferred')
            return
        assert request['operation']=='measure-ray'
        self.sequence+=1;n=self.sequence;epoch=self.model.epoch()
        factor=39.3701*40;size=[int(2*factor),int(2*factor)];point=[size[0]/4,size[1]/4]
        geometry=dict(webGeometryVersion=1,requestId=request['commandId'],instance='d'*32,sequence=n,capturedEpochMs=epoch,
            document=dict(runId=RUN,href=DOCUMENT,responseId='f'*32,readyState='complete'),control='text',
            editor=dict(focused=False,text='',cursor=0,anchor=0),
            viewport=dict(width=640,height=480,scale=1,offsetLeft=0,offsetTop=0),
            rect=dict(x=80,y=80,width=160,height=80),center=dict(x=160,y=120),hit=True,enabled=True,connected=True)
        view=dict(handle='1',creation=1,grant=3,page=2,url=DOCUMENT)
        ray=dict(worldWebRayVersion=1,capturedEpochMs=epoch,sourceIdentity='web-entity:'+ENTITY,entityId=ENTITY,
            entityName='OVERTE_PARITY_WEB_REFERENCE',entityType='Web',hostType='local',sourceUrl=DOCUMENT,
            visible=True,ignorePickIntersection=False,position=[0,1.6,-1],rotation=[0,0,0,1],dimensions=[2,2,.01],
            registrationPoint=[.5,.5,.5],dpi=40,scenePoint=point,itemQuad=[[0,0],[size[0],0],size,[0,size[1]]],surfaceSize=size,
            worldPoint=[point[0]/factor-1,2.6-point[1]/factor,-1],
            sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],headPosition=[0,1.6,0])
        self.sample=dict(picoBrowserVersion=3,commandId=request['commandId'],runId=RUN,ownerToken=OWNER,instance='a'*32,
            sequence=n,processId=31,capturedEpochMs=epoch,status='ready',source=dict(nativeView=view,
                geometryRaw=json.dumps(json.dumps(geometry)),worldRay=ray))
        if self.ray_edit:self.ray_edit(self.sample)
    def reader(self):
        return PicoWorldBrowserIO(self.send,lambda:json.dumps(self.sample),self.model.epoch,self.model.guard,31,
            source_lock=self.model.lock,read_only=True,monotonic=lambda:self.model.clock,sleep=self.model.sleep)


class WorldRuntimeBoundary(RuntimeBoundary):
    def packet(self):
        value=super().packet();sha=hashlib.sha256(DOCUMENT.encode()).hexdigest()
        for side in ('nativeBefore','nativeAfter'):
            source=value['source'][side];source['knownHandles'][0]['sourceSha256']=sha
            source['views'][0].update(surface='world',sourceSha256=sha,documentSha256=sha,creationSha256=sha)
        value['source']['java']['views'][0].update(sourceSha256=sha,documentSha256=sha)
        value['source']['java']['renderers'][0]['sourceSha256']=sha
        return value


class Model(TabletModel):
    def __init__(self):
        super().__init__();self.ui.shown=False;self.browser=WorldBrowserBoundary(self);self.runtime=WorldRuntimeBoundary()
        self.http['responses'][0]['resource']='index.html';self.sample_sequence=0
    def browser_stereo(self,*,role='primary',journal='9'*32):
        return PicoBrowserStereo(self.arrival(),
            lambda:self._world_render_capture('owned',read_only=True,role=role,require_frame_view=True,source_lock=self.lock),
            self.artifacts/original_name(RUN,role,journal,surface='world'),self.artifacts,RUN,self.binding,self.lock,self.guard,
            fixture_url=URL,foreign_fixture_url=FOREIGN,owner_token=OWNER,script_url=SCRIPT,browser_factory=self.browser.reader,
            runtime_factory=self.runtime.reader,scripts=self.scripts,http=lambda:deepcopy(self.http),role=role,journal_id=journal,
            ui_factory=lambda:self.ui.source(),native_factory=lambda:self._native_feature_observer('owned',read_only=True),
            monotonic=lambda:self.clock,surface='world')
    def acquire(self,*,role='primary'):
        self.active=TICKET;self.sample_sequence+=1;owner=self.browser_stereo(role=role,journal=uuid.uuid4().hex)
        state=owner.acquire(TICKET);frame=state['frame'];raw=owner.image_bytes()
        facts=validate(frame,raw,RUN,self.binding,SCENE)
        sample=dict(schemaVersion=1,contractVersion=VERSION,runId=RUN,sequence=self.sample_sequence,
            capturedEpochMs=facts['earliestEpochMs'],state=facts['state'],resources=['entity:world-web'],
            lifecycle=frame['nativeBefore']['lifecycle'],artifacts=owner.artifacts(self.sample_sequence))
        return owner,raw,owner.store.path.read_bytes(),sample


class WorldBrowserStereoTests(unittest.TestCase):
    def model(self):
        value=Model()
        def close():
            evidence=os.environ.get('OVERTE_WORLD_WEB_STEREO_EVIDENCE')
            if evidence:
                root=Path(evidence);assert root.is_dir() and not root.is_symlink()
                shutil.copytree(value.root,root/('world-stereo-'+uuid.uuid4().hex))
            value.close()
        self.addCleanup(close);return value
    def test_real_owners_retain_world_document_entity_two_eyes_and_original_retirement(self):
        model=self.model();owner,raw,metadata,sample=model.acquire()
        self.assertEqual('complete',owner.state['phase']);self.assertEqual('world',sample['state']['surface'])
        self.assertFalse(owner.state['frame']['uiBefore']['tabletShown']);self.assertEqual(1,len(model.gpu.commands))
        self.assertIsNone(model.owner_store('primary').read());self.assertEqual([],list(model.native_root.iterdir()))
        evidence,subject=observation(raw,metadata,RUN,TICKET,URL,POLICY,sample)
        self.assertEqual({'left','right'},set(evidence['eyes']));self.assertEqual('world',subject['state']['surface'])
        self.assertGreater(subject['cursors']['browserWorldAfter'],subject['cursors']['browserWorldBefore'])
        self.assertEqual(metadata,owner.store.path.read_bytes())
    def test_actual_pico_factory_selects_world_reader_and_canonical_capture_lock(self):
        import sys
        root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        fixture=native_fixture.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter=fixture.instance();model=self.model();selected=[]
        adapter._script_runtime=lambda target:(None,model.scripts,model.binding)
        adapter._native_feature_observer=lambda target:model._native_feature_observer(target,read_only=True)
        adapter._graphics_subject_observer=lambda target:model.subject_reader()
        adapter.read_probe_snapshot=lambda target,package,after:model.probe(after)
        adapter._browser_world_render_capture=lambda target,role,source_lock:model._world_render_capture(target,
            read_only=True,role=role,require_frame_view=True,source_lock=source_lock)
        def browser(target,*,source_lock,tablet=True):
            self.assertIs(source_lock,model.lock);selected.append(tablet);return model.browser.reader()
        adapter._browser_originals=browser
        adapter._web_runtime_observer=lambda target:model.runtime.reader()
        adapter._graphics_ui_observer=lambda target:model.ui.source()
        def lock(_self,target,provided=None):
            self.assertEqual('owned',target);self.assertIs(provided,model.lock);return provided
        journal='9'*32
        with patch('adapters.pico4.script_journey.PicoScriptJourney._lock',lock),model.lock.held():
            owner=adapter._browser_stereo('owned',model.artifacts/original_name(RUN,'primary',journal,surface='world'),
                model.artifacts,RUN,SCENE,role='primary',source_lock=model.lock,journal_id=journal,
                fixture_url=URL,foreign_fixture_url=FOREIGN,owner_token=OWNER,script_url=SCRIPT,
                http=lambda:deepcopy(model.http),surface='world')
            state=owner.acquire(TICKET)
        self.assertEqual([False],selected);self.assertEqual('complete',state['phase']);self.assertIs(owner.lock,model.lock)
    def test_common_world_journey_admits_exact_world_profile_and_rejects_capture_reuse(self):
        model=self.model();owner,raw,metadata,sample=model.acquire()
        journey=Journey('world-web',RUN,URL,invoke=lambda *_:None,witness=lambda *_:None,activate=lambda *_:None,
            read_artifact=lambda name:read_private_artifact(model.artifacts,name),image_policy=dict(screen=POLICY),
            continuity=lambda *_:None,monotonic=lambda:0.,epoch_ms=lambda:20000,sleep=lambda _:None,report=lambda _:None)
        measured,subject=journey.artifacts(sample,TICKET,['image'])
        self.assertTrue(journey.stereo_browser);self.assertEqual(1,len(measured));self.assertEqual('world',subject['state']['surface'])
        changed=deepcopy(sample);changed['sequence']+=1
        for artifact in changed['artifacts']:artifact['sequence']=changed['sequence']
        with self.assertRaises(ERRORS):journey.artifacts(changed,TICKET,['image'])
        with self.assertRaises(ERRORS):Journey('tablet-web',RUN,URL,invoke=lambda *_:None,witness=lambda *_:None,
            activate=lambda *_:None,image_policy=dict(screen=POLICY),
            read_artifact=lambda name:read_private_artifact(model.artifacts,name),continuity=lambda *_:None,
            monotonic=lambda:0.,epoch_ms=lambda:20000,sleep=lambda _:None,report=lambda _:None)
    def test_world_and_tablet_envelopes_profiles_and_artifact_names_cannot_be_relabelled(self):
        model=self.model();owner,raw,metadata,sample=model.acquire();body=json.loads(metadata)
        with self.assertRaises(ERRORS):archive_sources(metadata,raw,RUN,TICKET,SCENE)
        wrong=deepcopy(body);wrong['picoBrowserStereoOwnerVersion']=wrong.pop('picoWorldBrowserStereoOwnerVersion')
        with self.assertRaises(ERRORS):archive_sources(json.dumps(wrong).encode(),raw,RUN,TICKET,SCENE)
        body['picoWorldBrowserStereoOwnerVersion']=True
        with self.assertRaises(ERRORS):archive_sources(json.dumps(body).encode(),raw,RUN,TICKET,SCENE,surface='world')
        self.assertNotEqual(original_name(RUN,'primary','9'*32),original_name(RUN,'primary','9'*32,surface='world'))
        wrong=deepcopy(owner.state);frame=wrong['frame']
        frame['picoBrowserStereoSourceVersion']=frame.pop('picoWorldBrowserStereoSourceVersion')
        with model.lock.held(),self.assertRaises(NativeUIError):owner.save(wrong)
    def test_foreign_entity_current_geometry_or_changed_original_position_refuses_capture(self):
        for fault in ('entity','position','document','head'):
            with self.subTest(fault=fault):
                model=self.model()
                def edit(packet):
                    ray=packet['source']['worldRay']
                    if fault=='entity':
                        ray['entityId']='22345678-1234-1234-1234-123456789abc';ray['sourceIdentity']='web-entity:'+ray['entityId']
                    elif fault=='position' and packet['sequence']>2:ray['position'][0]+=.25;ray['worldPoint'][0]+=.25
                    elif fault=='head':ray['headPosition'][1]+=.25
                    elif fault=='document':
                        geometry=json.loads(json.loads(packet['source']['geometryRaw']));geometry['document']['responseId']='e'*32
                        packet['source']['geometryRaw']=json.dumps(json.dumps(geometry))
                model.browser.ray_edit=edit
                owner=model.browser_stereo()
                with self.assertRaises(NativeUIError):owner.acquire(TICKET)
                self.assertIsNotNone(owner.store.read())
                if model.gpu.commands:self.assertIsNotNone(model.owner_store('primary').read())
    def test_lost_original_capture_keeps_ownership_and_never_captures_again(self):
        model=self.model();model.capture_error=True
        with self.assertRaises(NativeUIError):model.browser_stereo().acquire(TICKET)
        before=len(model.gpu.commands)
        with self.assertRaises(NativeUIError):model.browser_stereo().acquire(TICKET)
        self.assertEqual(before,len(model.gpu.commands));self.assertIsNotNone(model.owner_store('primary').read())


if __name__=='__main__':unittest.main()
