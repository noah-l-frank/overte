"""Real capture/file/retirement owners; DOM, Qt, Java, HMD and GPU are explicit seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import patch
import unittest
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_stereo import PicoBrowserStereo,original_name
from adapters.pico4.browser_source import PicoBrowserIO
from adapters.pico4.tablet_browser_source import PicoTabletBrowserIO
from adapters.pico4.browser_stereo_source import validate
from self_tests.test_navigation_arrival import Model as ArrivalModel,SCENE
from self_tests.test_pico_graphics_samples import RUN,TICKET
from self_tests.test_pico_graphics_composition import composition
from self_tests.test_stereo_graphics_surface_evidence import Source
from self_tests.test_native_web_renderers import RendererBoundary

URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
FOREIGN='http://foreign.invalid/feature-fixture/v1/runs/'+RUN+'/'
OWNER='e'*32
SCRIPT=URL+'tickets/'+TICKET+'/client.js'
DOCUMENT=URL+'tickets/'+TICKET+'/reference.html'
SHA=hashlib.sha256(DOCUMENT.encode()).hexdigest()


class BrowserBoundary:
    def __init__(self,model):self.model=model;self.sequence=0;self.sample=None;self.edit=None
    def send(self,request):
        self.sequence+=1;n=self.sequence;nonce=request['commandId']
        view=dict(handle='1',creation=1,grant=3,page=2,url=DOCUMENT,nativeFinished=True,httpErrorStatus=0,
            inlineLease=False,sourceUrl=DOCUMENT,sourceIdentity='tablet:original')
        dom=dict(webDOMVersion=1,requestId=nonce,instance='d'*32,sequence=n,capturedEpochMs=20000,
            document=dict(runId=RUN,href=DOCUMENT,responseId='f'*32,readyState='complete',title='Overte web parity reference'),
            editor=dict(text='',focused=False),attempts=[],echoes=[])
        current=dict(webNativeVersion=1,commandId=nonce,runId=RUN,surface='tablet',instance='a'*32,
            sequence=n,processId=31,capturedEpochMs=20000,status='ready',source=dict(nativeView=view,dom=dom))
        document={key:view[key] for key in ('handle','creation','grant','page','url')};document['finishedEpochMs']=19000
        self.sample=dict(picoBrowserVersion=2,commandId=nonce,runId=RUN,ownerToken=OWNER,instance='a'*32,
            sequence=n,processId=31,capturedEpochMs=20000,status='ready',source=dict(retired=False,documents=[document],
            requests=[],replies=[],inputs=[],domHistory={'1:1:3:2':current},current=current,
            deferred=dict(armed=False,pending=False,held=None,deliveries=[])))
        if self.edit:self.edit(self.sample)
    def reader(self):return PicoTabletBrowserIO(self.send,lambda:json.dumps(self.sample),self.model.epoch,self.model.guard,31,
        source_lock=self.model.lock,read_only=True,monotonic=lambda:self.model.clock,sleep=self.model.sleep)


class RuntimeBoundary(RendererBoundary):
    def packet(self):
        value=super().packet()
        for side in ('nativeBefore','nativeAfter'):
            source=value['source'][side];source['knownHandles'][0]['sourceSha256']=SHA
            source['views'][0].update(surface='tablet',sourceSha256=SHA,documentSha256=SHA,creationSha256=SHA)
        value['source']['java']['views'][0].update(sourceSha256=SHA,documentSha256=SHA)
        value['source']['java']['renderers'][0]['sourceSha256']=SHA
        return value


class Model(ArrivalModel):
    def __init__(self):
        super().__init__();self.ui.shown=True;self.ui.controls=[]
        self.ui.edit=lambda packet:packet.update(graphicsObservationVersion=2,composition=composition())
        _raw,body,_images=Source().acquire();self.source['framework']=deepcopy(body['subjectBefore']['source']['framework'])
        self.browser=BrowserBoundary(self);self.runtime=RuntimeBoundary();self.script_sequence=0
        self.http=dict(browserFixtureVersion=1,instance='f'*32,ready=False,sequence=1,responses=[dict(sequence=1,responseId='f'*32,
            capturedEpochMs=19000,ticket=TICKET,resource='reference.html',origin='primary',status=200,bytes=10,sha256='1'*64)])
    def scripts(self,after):
        self.script_sequence=max(self.script_sequence+1,after+1)
        return dict(schemaVersion=1,instance='a'*32,sampleSequence=self.script_sequence,sampleEpochMs=20000,complete=True,
            scripts=[dict(url=SCRIPT,path=SCRIPT)]),20000
    def browser_stereo(self,*,role='primary',journal='9'*32):
        return PicoBrowserStereo(self.arrival(),
            lambda:self._world_render_capture('owned',read_only=True,role=role,require_frame_view=True,source_lock=self.lock),
            self.artifacts/original_name(RUN,role,journal),self.artifacts,RUN,self.binding,self.lock,self.guard,
            fixture_url=URL,foreign_fixture_url=FOREIGN,owner_token=OWNER,script_url=SCRIPT,browser_factory=self.browser.reader,
            runtime_factory=self.runtime.reader,scripts=self.scripts,http=lambda:deepcopy(self.http),role=role,journal_id=journal,
            ui_factory=lambda:self.ui.source(),native_factory=lambda:self._native_feature_observer('owned',read_only=True),monotonic=lambda:self.clock)


class PicoBrowserStereoTests(unittest.TestCase):
    def model(self):
        value=Model();self.addCleanup(value.close);return value
    def test_actual_pico_factory_uses_root_lock_and_passive_sources_without_default_manager_adoption(self):
        root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        fixture=native_fixture.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter=fixture.instance();m=self.model()
        adapter._script_runtime=lambda target:(None,m.scripts,m.binding)
        adapter._scripts=lambda target:(_ for _ in ()).throw(AssertionError('Default manager adoption'))
        adapter._native_feature_observer=lambda target:m._native_feature_observer(target,read_only=True)
        adapter._graphics_subject_observer=lambda target:m.subject_reader()
        adapter.read_probe_snapshot=lambda target,package,after:m.probe(after)
        adapter._browser_world_render_capture=lambda target,role,source_lock:m._world_render_capture(target,
            read_only=True,role=role,require_frame_view=True,source_lock=source_lock)
        adapter._browser_originals=lambda target,source_lock:m.browser.reader()
        adapter._web_runtime_observer=lambda target:m.runtime.reader()
        adapter._graphics_ui_observer=lambda target:m.ui.source()
        def lock(_self,target,provided=None):
            self.assertEqual('owned',target);self.assertIs(m.lock,provided);return provided
        journal='9'*32
        with patch('adapters.pico4.script_journey.PicoScriptJourney._lock',lock),m.lock.held():
            owner=adapter._browser_stereo('owned',m.artifacts/original_name(RUN,'primary',journal),m.artifacts,RUN,SCENE,
                role='primary',source_lock=m.lock,journal_id=journal,fixture_url=URL,foreign_fixture_url=FOREIGN,
                owner_token=OWNER,script_url=SCRIPT,http=lambda:deepcopy(m.http))
            state=owner.acquire(TICKET)
        self.assertEqual('complete',state['phase']);self.assertEqual(1,len(m.gpu.commands));self.assertIs(m.lock,owner.lock)

    def test_open_original_tablet_has_two_actual_eyes_and_retired_memory_and_files(self):
        model=self.model();owner=model.browser_stereo();state=owner.acquire(TICKET)
        self.assertEqual('complete',state['phase']);self.assertTrue(state['frame']['uiBefore']['tabletShown'])
        facts=validate(state['frame'],owner.image_bytes(),RUN,model.binding,SCENE)
        self.assertEqual('',facts['state']['text']);self.assertEqual(2,len(owner.artifacts(1)))
        self.assertIsNone(model.owner_store('primary').read());self.assertEqual([],list(model.native_root.iterdir()))
        model.browser_stereo().acquire(TICKET);self.assertEqual(1,len(model.gpu.commands))
    def test_independent_roles_use_separate_original_capture_and_artifact_journals(self):
        model=self.model();a=model.browser_stereo();first=a.acquire(TICKET)
        b=model.browser_stereo(role='actor');second=b.acquire(TICKET)
        self.assertNotEqual(first['captureIntent'],second['captureIntent']);self.assertNotEqual(first['image']['name'],second['image']['name'])
        self.assertEqual('actor',second['proof']['owner']['role']);self.assertEqual(2,len(model.gpu.commands))
    def test_missing_document_renderer_or_shown_actual_tablet_cannot_supply_pixels(self):
        for fault in ('hidden','document','renderer','mono','late'):
            with self.subTest(fault=fault):
                model=self.model()
                if fault=='hidden':model.ui.shown=False
                elif fault=='document':model.browser.edit=lambda packet:packet['source'].update(current={})
                elif fault=='renderer':model.runtime.renderer['threadAlive']=False
                elif fault=='late':model.features.mutate=lambda packet:packet.update(processId=31,capturedEpochMs=22000)
                else:
                    original=model.gpu.mutate
                    def mutate(packet):original(packet);packet['source']['view']='main-mono'
                    model.gpu.mutate=mutate
                with self.assertRaises(NativeUIError):model.browser_stereo().acquire(TICKET)
    def test_changed_document_effect_or_actual_root_during_exposure_refuses_original_frame(self):
        for fault in ('text','root','page'):
            with self.subTest(fault=fault):
                model=self.model()
                if fault=='root':
                    def edit(packet):
                        packet.update(graphicsObservationVersion=2,composition=composition())
                        if packet['sourceSequence']>1:packet['composition']['root']['id']='8'*32
                    model.ui.edit=edit
                else:
                    def edit(packet):
                        if packet['sequence']>1:
                            if fault=='text':packet['source']['current']['source']['dom']['editor']['text']='changed during capture'
                            else:packet['source']['current']['source']['nativeView']['page']+=1
                    model.browser.edit=edit
                with self.assertRaises(NativeUIError):model.browser_stereo().acquire(TICKET)
                self.assertIsNotNone(model.owner_store('primary').read())
    def test_lost_capture_or_release_result_retains_owner_without_resending(self):
        for fault in ('capture','release'):
            with self.subTest(fault=fault):
                model=self.model()
                if fault=='capture':model.capture_error=True
                else:model.storage.callbacks=1
                with self.assertRaises(NativeUIError):model.browser_stereo().acquire(TICKET)
                count=len(model.gpu.commands);commands=len(model.storage.commands)
                with self.assertRaises(NativeUIError):model.browser_stereo().acquire(TICKET)
                self.assertEqual(count,len(model.gpu.commands));self.assertEqual(commands,len(model.storage.commands))
                self.assertIsNotNone(model.owner_store('primary').read())


if __name__=='__main__':unittest.main()
