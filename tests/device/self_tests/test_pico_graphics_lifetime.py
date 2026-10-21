"""Original multi-source Pico quiet windows at synthetic native/SDK boundaries.

Normal Go To, durable restoration, native Web/HTTP/UI and receipt protocols run;
all device transports are synthetic and no compiler/service/device is invoked.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch
import uuid

from adapters.graphics_journey.fixture import GraphicsFixtureReader
from adapters.graphics_journey.lifetime import GraphicsLifetime
from adapters.graphics_journey.preferences import GraphicsPreferences
from adapters.native_web_runtime import NativeWebRuntime
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_scene import PicoGraphicsSurfaceScenePolicy
from adapters.script_journey.history import unpack
from feature_journeys.graphics_fixture import PICO_PROFILE,pico_scene
from feature_journeys.graphics_resources import GraphicsResources
from self_tests.test_pico_graphics_restart import Model as Base,RUN
from self_tests.test_native_web_renderers import RendererBoundary
from self_tests.test_native_web_runtime import BLANK
from self_tests.test_native_tablet_http import Boundary as HttpBoundary
from self_tests.test_world_render_receipt_inventory import Boundary as ReceiptBoundary
from self_tests.test_pico_graphics_scene import BASE,TICKET


class WebBoundary(RendererBoundary):
    def __init__(self,model):super().__init__();self.model=model
    def now(self):return self.model.native.epoch
    def packet(self):
        packet=super().packet();packet['runId']=RUN
        packet.update(processId=self.model.pid,instance=self.model.instance)
        packet['source']['java'].update(processId=self.model.pid,instance=self.model.instance)
        urls=self.model.web_urls;native=deepcopy(packet['source']['nativeAfter']['views'][0])
        java=deepcopy(packet['source']['java']['views'][0]);renderer=deepcopy(packet['source']['java']['renderers'][0])
        views=[];javas=[];renderers=[];known=[]
        for index,url in enumerate(urls,1):
            handle=str(index);digest=hashlib.sha256(url.encode()).hexdigest()
            row=deepcopy(native);row.update(handle=handle,sourceSha256=BLANK if self.revoked else digest,
                documentSha256=BLANK if self.revoked else digest,creationSha256=digest);views.append(row)
            row=deepcopy(java);row.update(handle=handle,sourceSha256=BLANK if self.revoked else digest,
                documentSha256=BLANK if self.revoked else digest);javas.append(row)
            row=deepcopy(renderer);row.update(id=handle*32,handle=handle,sourceSha256=digest);renderers.append(row)
            known.append(dict(handle=handle,firstObservedEpochMs=20000,sourceSha256=digest))
        for key in ('nativeBefore','nativeAfter'):packet['source'][key].update(views=deepcopy(views),knownHandles=deepcopy(known))
        packet['source']['java'].update(views=javas,renderers=renderers)
        return packet
    def reader(self):
        return NativeWebRuntime(self.send,self.original,self.now,self.model.guard,self.model.pid,require_renderers=True,
            monotonic=lambda:self.model.native.clock,sleep=self.model.native.sleep)


class Model(Base):
    graphics_scene_policy=PicoGraphicsSurfaceScenePolicy()
    def __init__(self):
        super().__init__();self.flow.fixture_profile=PICO_PROFILE
        self.provider=GraphicsResources(BASE,clock_ms=lambda:self.native.epoch)
        self.provider.provision(RUN,profile=PICO_PROFILE);self.provider.activate(RUN,TICKET);self.client.graphics_instance=self.provider.instance
        self.client.graphics_previous=None;self.source=GraphicsFixtureReader(self.client,RUN,epoch_ms=lambda:self.native.epoch)
        self.web_urls=[];self.web=WebBoundary(self);self.http=HttpBoundary();self.receipts={};self.last_receipt=None
        self.original_adapter._web_runtime_observer=lambda _target:self.web.reader()
        self.original_adapter._tablet_http_observer=self.http_reader
        self.original_adapter._world_render_store=lambda _target:PrivateFeatureState(self.root/'legacy-world-owner.json')
        self.original_adapter._native_feature_observer=self.native_reader
        self.original_adapter._graphics_ui_observer=self.graphics_reader
        self.original_adapter.adb.read_debug_app_file=self.receipt_original
    def controlled(self):
        with patch('self_tests.test_pico_graphics_scene.scene_document',pico_scene):value=super().controlled()
        self.web_urls=[row['sourceUrl'] for row in value['entities'] if row['type']=='Web'];return value
    def http_reader(self,_target):
        reader=self.http.reader();send=reader.send
        def current(request):
            self.http.epoch=self.native.epoch;send(request)
            self.http.sample.update(processId=self.pid,instance=self.instance)
        reader.send=current;reader.clock_ms=lambda:self.native.epoch;reader.guard=self.guard
        reader.pid=self.pid
        reader.monotonic=lambda:self.native.clock;reader.sleep=self.native.sleep;return reader
    def graphics_reader(self,target):
        reader=super().graphics_reader(target);send=reader.send
        def current(request):
            self.ui_boundary.clock=self.native.clock;self.ui_boundary.epoch=self.native.epoch;send(request)
        reader.send=current;return reader
    def native_reader(self,target):
        reader=super().native_reader(target);send=reader.send
        def dispatch(request):
            if request['action']=='feature-world-render-receipts':
                source=self.receipts[request['requestId']];self.last_receipt=source
                source.epoch=self.native.epoch;source.send(request)
            else:send(request)
        reader.send=dispatch;return reader
    def receipt_original(self,target,package,path,**options):
        assert (target,package,path)==('owned','org.overte.pico','files/overte-e2e/world-render-receipts-result.json')
        assert options==dict(attempts=1);return self.last_receipt.original()
    def captures(self):
        proofs={}
        for role in ('primary','actor'):
            root=self.root/('receipts-'+role);root.mkdir(mode=0o700)
            source=ReceiptBoundary(root);source.epoch=self.native.epoch
            capture=uuid.uuid4().hex
            for path in root.iterdir():path.unlink()
            source.issued.clear();source.owner=dict(ownershipVersion=2,binding=self.binding(),role=role,
                capture=dict(schemaVersion=1,commandId=capture,action='feature-world-render-observe'),
                receipts=[uuid.uuid4().hex,uuid.uuid4().hex])
            for receipt in source.owner['receipts']:source.issue(receipt)
            source.mutate=lambda value:value.update(instance=self.instance,processId=self.pid)
            source.native.native_instance=lambda:self.instance;source.native.pid=self.pid
            files=source.native.retire()
            memory=dict(storageVersion=1,commandId=source.owner['receipts'][0],requestId=capture,instance=self.instance,
                sequence=1,processId=self.pid,capturedEpochMs=self.native.epoch,present=False,callbacks=0,pngBytes=0)
            proofs[role]=dict(owner=deepcopy(source.owner),memory=memory,files=files);self.receipts[capture]=source
        return proofs
    def lifetime(self,role='primary',stage=0):
        return GraphicsLifetime(self.flow,'owned',self.source,role,stage,self.lock,artifact_root=self.root/'artifacts',
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def ready(self,*,release_http=True):
        scene=self.scene();scene.prepare();owner=self.lifetime();owner.observe_active();proofs=self.captures()
        scene.restore();scene.retire();self.web.close()
        if release_http:self.http.retire_reply()
        self.provider.retire(RUN)
        return owner,deepcopy(scene.previous),proofs


class PicoGraphicsLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.model=Model();self.addCleanup(self.model.close);self.enterContext(self.model.lock.held())
        self.model.flow._script_file_io=self.model.script_io
    def test_three_original_web_surfaces_and_fresh_full_three_second_quiet_window(self):
        m=self.model;owner,scene,proofs=m.ready();value=owner.wait_released(scene,proofs)
        self.assertEqual('released',owner.state['phase']);window=owner.state['windows'][-1]
        self.assertGreaterEqual(window['elapsedMs'],3000);self.assertGreaterEqual(len(window['samples']),3)
        self.assertEqual(3,len(owner.state['activeProofs'][0]['web']['source']['java']['renderers']))
        self.assertTrue(all(request['operation']=='inspect' for source in m.receipts.values() for request in source.commands[2:]))
        count=len(m.native.inputs)
        state=GraphicsLifetime.archive(value,adapter=m.flow,selector='owned',client=m.client,run=RUN,
            provider_instance=m.provider.instance,role='primary',stage=0,binding=m.binding(),artifact_root=m.root/'artifacts')
        self.assertEqual('released',state['phase']);self.assertEqual(count,len(m.native.inputs))
        self.assertEqual('released',m.lifetime().state['phase'])
    def test_retained_worker_is_rejected_and_a_retry_starts_a_whole_new_local_window(self):
        m=self.model;owner,scene,proofs=m.ready();m.web.renderer['threadAlive']=True
        with self.assertRaises(NativeUIError):owner.wait_released(scene,proofs)
        self.assertFalse(owner.state['windows'][-1]['complete']);m.web.renderer['threadAlive']=False
        before=m.native.clock;recreated=m.lifetime();recreated.wait_released(scene,proofs)
        self.assertGreaterEqual(m.native.clock-before,3);self.assertEqual(2,len(recreated.state['windows']))
    def test_original_live_reply_prevents_release_despite_restored_world_and_absent_graphics_page(self):
        m=self.model;owner,scene,proofs=m.ready(release_http=False)
        # Retain a real original reply rather than deriving lifetime from entity absence.
        with self.assertRaises(NativeUIError):owner.wait_released(scene,proofs)
        self.assertFalse(owner.state['windows'][-1]['complete'])
    def test_an_original_capture_callback_in_either_role_prevents_quiet_retirement(self):
        m=self.model;owner,scene,proofs=m.ready();source=m.receipts[proofs['actor']['owner']['capture']['commandId']]
        source.callbacks=1
        with self.assertRaises(NativeUIError):owner.wait_released(scene,proofs)
        self.assertFalse(owner.state['windows'][-1]['complete'])
    def test_retained_ui_root_is_observed_without_hiding_it_or_resending_scene_input(self):
        m=self.model;owner,scene,proofs=m.ready()
        def retained(value):value['graphicsInventory']['roots']=[dict(id='d'*32,profile='graphics-generic-v1',
            visible=False,inCurrentTree=False,callbackRunning=False,callbackItemPresent=False)]
        m.ui_edit=retained;count=len(m.native.inputs)
        with self.assertRaises(NativeUIError):owner.wait_released(scene,proofs)
        self.assertEqual(count,len(m.native.inputs))
    def test_missing_original_group_archive_prevents_recreation_without_native_queries(self):
        m=self.model;owner,scene,proofs=m.ready();owner.wait_released(scene,proofs)
        reference=unpack(owner.previous['payload'])[0]['activeProofs'][0]
        (m.root/'artifacts'/reference['name']).unlink();count=len(m.subject.commands)
        with self.assertRaises(NativeUIError):m.lifetime()
        self.assertEqual(count,len(m.subject.commands))
    def test_unfinished_native_scene_callback_cannot_be_a_released_world(self):
        m=self.model;owner,scene,proofs=m.ready()
        m.loads.rows[-1].update(pending=True,releasedEpochMs=None)
        with self.assertRaises(NativeUIError):owner.wait_released(scene,proofs)
        self.assertFalse(owner.state['windows'][-1]['complete'])
    def test_a_partial_quiet_window_is_retained_but_never_accumulated_into_a_new_window(self):
        m=self.model;owner,scene,proofs=m.ready();started=m.native.clock
        def interrupted(seconds):
            m.native.sleep(seconds)
            if m.native.clock-started>=1.5:raise OSError('Synthetic interrupted local quiet wait')
        owner.sleep=interrupted
        with self.assertRaises(OSError):owner.wait_released(scene,proofs)
        self.assertGreater(len(owner.state['windows'][0]['samples']),1)
        before=m.native.clock;recreated=m.lifetime();recreated.wait_released(scene,proofs)
        self.assertGreaterEqual(m.native.clock-before,3)
        self.assertFalse(recreated.state['windows'][0]['complete']);self.assertTrue(recreated.state['windows'][1]['complete'])
    def test_foreign_or_unresolved_capture_owner_prevents_original_inspection(self):
        m=self.model;owner,scene,proofs=m.ready();store=m.flow.world_render_store('owned',role='actor')
        store.write(proofs['actor']['owner'],None);source=m.receipts[proofs['primary']['owner']['capture']['commandId']]
        before=len(source.commands)
        with self.assertRaises(NativeUIError):owner.wait_released(scene,proofs)
        self.assertEqual(before,len(source.commands))
    def test_changed_current_framework_cannot_borrow_the_archived_restoration(self):
        m=self.model;owner,scene,proofs=m.ready()
        m.subject.source['framework']['entities'][0]['appearanceSha256']='e'*64
        with self.assertRaises(NativeUIError):owner.wait_released(scene,proofs)
        self.assertFalse(owner.state['windows'][-1]['complete'])
    def test_advancing_local_time_cannot_replace_a_frozen_original_quiet_epoch(self):
        m=self.model;owner,scene,proofs=m.ready()
        frozen=m.native.epoch;owner.sleep=lambda seconds:m.native.sleep(3)
        with patch.object(type(m.native),'epoch',property(lambda _self:frozen)),self.assertRaises(NativeUIError):
            owner.wait_released(scene,proofs)
        self.assertEqual('releasing',owner.state['phase']);self.assertFalse(owner.state['windows'][-1]['complete'])
    def test_reused_original_query_cannot_be_made_fresh_with_a_new_source_cursor(self):
        m=self.model;owner,_scene,_proofs=m.ready();value=deepcopy(owner.state['http']);value['sequence']+=1
        with self.assertRaises(NativeUIError):owner.accept('http',value)
        self.assertEqual(1,len(owner.state['queries']['http']))
    def test_gaps_in_original_quiet_observations_cannot_qualify_continuous_release(self):
        m=self.model;owner,scene,proofs=m.ready();owner.sleep=lambda seconds:m.native.sleep(2)
        with self.assertRaises(NativeUIError):owner.wait_released(scene,proofs)
        self.assertEqual('releasing',owner.state['phase']);self.assertFalse(owner.state['windows'][-1]['complete'])
    def test_active_scope_cannot_borrow_one_renderer_for_three_owned_world_surfaces(self):
        m=self.model;m.scene().prepare();owner=m.lifetime()
        m.web.edit=lambda packet:packet['source']['java']['renderers'].pop()
        with self.assertRaises(NativeUIError):owner.observe_active()
        self.assertEqual([],owner.state['activeProofs'])
    def test_actor_acquires_its_own_source_groups_and_a_new_quiet_window(self):
        m=self.model;scene=m.scene();scene.prepare();primary=m.lifetime();actor=m.lifetime('actor')
        p=primary.observe_active();a=actor.observe_active()
        self.assertNotEqual(p['web']['commandId'],a['web']['commandId'])
        proofs=m.captures();scene.restore();scene.retire();m.web.close();m.http.retire_reply();m.provider.retire(RUN)
        primary.wait_released(scene.previous,proofs);before=m.native.clock
        actor=m.lifetime('actor');actor.wait_released(scene.previous,proofs)
        self.assertGreaterEqual(m.native.clock-before,3)
        self.assertNotEqual(primary.state['windows'][0]['samples'][0]['subject']['requestId'],
            actor.state['windows'][0]['samples'][0]['subject']['requestId'])
    def test_new_process_quiet_window_uses_the_qualified_framework_baseline_and_keeps_old_originals(self):
        m=self.model;scene=m.scene();scene.prepare();old=m.lifetime();old.observe_active()
        preferences=GraphicsPreferences(scene,monotonic=lambda:m.native.clock,sleep=m.native.sleep);preferences.prepare()
        call=dict(contractVersion=16,runId=RUN,ticket=uuid.uuid4().hex,fixtureUrl=m.source.fixture_url,
            verb='restart-app',inputs={})
        with patch('adapters.android_process_query.subprocess.run',side_effect=m.query):m.restart().act(call)
        m.web=WebBoundary(m);m.http=HttpBoundary()
        owner=m.lifetime(stage=1);owner.observe_active();proofs=m.captures()
        scene=m.scene();preferences=GraphicsPreferences(scene,monotonic=lambda:m.native.clock,sleep=m.native.sleep)
        preferences.retire();final_preferences=deepcopy(preferences.previous);scene.restore();scene.retire()
        m.restart().retire(scene.previous,final_preferences)
        m.web.close();m.http.retire_reply();m.provider.retire(RUN);owner.wait_released(scene.previous,proofs)
        self.assertEqual(32,owner.pid);self.assertEqual('released',owner.state['phase'])
        self.assertEqual(31,old.state['activeProofs'][0]['subject']['processId'])
        self.assertNotEqual(old.state['web']['instance'],owner.state['web']['instance'])


if __name__=='__main__':unittest.main()
