"""Composed real Pico feature/sampler owners with analytical stereo SDK originals.

The synthetic renderer derives literal eye images from independently maintained
widget/render state. It receives no expected result or adapter action packet.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from adapters.graphics_journey.fixture import GraphicsPhasePending,GraphicsRunRetired
from adapters.normal_ui import NativeUIError
from adapters.native_scene_loads import resource_hash
from adapters.owned_world_render import WorldRenderOwner
from adapters.pico4.graphics_binding import SerializedWorldCapture
from adapters.world_render_evidence import NativeWorldRenderCapture
from adapters.world_render_storage import NativeWorldRenderStorage,receipt_file
from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles
from feature_journeys.graphics_surface_cues import RESOURCES
from feature_journeys.scenarios import SCENARIOS
from self_tests.test_pico_graphics_feature import Model as Base,RUN,TICKET
from self_tests.test_pico_graphics_composition import composition
from self_tests.test_stereo_graphics_surfaces import SurfacePixels
from self_tests.test_world_render_storage import Boundary as StorageBoundary
from self_tests.test_world_render_receipt_inventory import Boundary as InventoryBoundary
from self_tests.test_vr_graphics_subject import entity


class Model(Base):
    def __init__(self):
        super().__init__();self.native_root=self.root/'native-captures';self.native_root.mkdir(mode=0o700)
        self.inventory=InventoryBoundary(self.native_root)
        for path in self.native_root.iterdir():path.unlink()
        self.inventory.issued.clear();self.storage=StorageBoundary();self.gpu=SurfacePixels()
        self.delivered=set();self.render_haze=self.render_mirror=self.render_resolution=None;self.ui_root=None
        # This SDK case starts with the ordinary already-created native tablet
        # screen. Its exact registration belongs to the original framework,
        # including during later normal tablet opens and final restoration.
        for original in (self.original,self.subject.source):
            framework=original['framework'];screen='cccccccc-cccc-4ccc-8ccc-cccccccccccc'
            framework['tablet']['screen']=screen;row=entity(screen)
            row.update(type='Web',parentId=framework['tablet']['frame']);framework['entities'].append(row)
            framework['entities'].sort(key=lambda value:value['id'])
            original['scan']['unowned'].append(dict(id=screen,sha256='d'*64));original['scan']['unowned'].sort(key=lambda value:value['id'])
            original['scan']['scannedEntities']+=1
        self.ui_edit=self.composed_ui;self.original_adapter._world_render_capture=self.capture
        self.gpu.mutate=self.render_packet
    def deliver(self,ticket,resource):
        if (ticket,resource) in self.delivered:return
        with self.provider.response(RUN,ticket,resource=resource,request_authority='controlled.invalid',request_scheme='http') as response:
            status,body,nonce,write=response
            write(dict(responseId=nonce,status=status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
            assert status==200
        self.delivered.add((ticket,resource))
    def controlled(self):
        value=super().controlled()
        if hasattr(self,'delivered'):
            for resource in (stem+'.html' for stem in RESOURCES.values()):self.deliver(TICKET,resource)
            self.deliver_codes(self.journal.active(RUN)['ticket'])
        return value
    def deliver_codes(self,ticket):
        for resource in (stem+'.png' for stem in RESOURCES.values()):self.deliver(ticket,resource)
    def activate(self,verb,inputs=None):
        call=super().activate(verb,inputs);self.deliver_codes(call['ticket']);return call
    def load(self,url):
        super().load(url)
        if resource_hash(url)==resource_hash(self.original['sceneUrl']):
            self.web.close()
            if not self.http.rows[0]['replies'][0]['destroyed']:self.http.retire_reply()
    def composed_ui(self,packet):
        if packet['tabletShown']:
            value=composition();tablet=self.subject.source['framework']['tablet']
            value['screen'].update(id=tablet['screen'],parentId=tablet['frame']);packet['composition']=value
    def graphics_reader(self,target):
        reader=super().graphics_reader(target);send=reader.send
        def current(request):
            shown=self.native.opened;graphics=shown and self.native.page=='graphics'
            if graphics and self.ui_root is None:self.ui_root=uuid.uuid4().hex
            if not graphics and self.ui_root is not None:
                self.ui_boundary.retired.append(self.ui_root);self.ui_boundary.retired.sort();self.ui_root=None
            self.ui_boundary.shown=shown;self.ui_boundary.focused=self.native.focused
            self.ui_boundary.controls=deepcopy(self.native.graph.capture()['controls']) if graphics else []
            for row in self.ui_boundary.controls:row['focused']=False
            self.ui_boundary.roots=([dict(id=self.ui_root,profile='graphics-generic-v1',visible=True,inCurrentTree=True,
                callbackRunning=True,callbackItemPresent=False)] if graphics else [])
            send(request)
        reader.send=current;return reader
    def render_packet(self,packet):
        self.gpu.camera_source(packet);packet.update(instance=self.instance,processId=self.pid)
        def epochs(value):
            if type(value) is dict:
                for key,child in value.items():
                    if key.endswith('EpochMs'):value[key]=self.native.epoch
                    else:epochs(child)
            elif type(value) is list:
                for child in value:epochs(child)
        epochs(packet);source=packet['source'];scale=self.native.graph.resolution if self.render_resolution is None else self.render_resolution
        width,height=round(1600*scale),round(800*scale)
        source.update(sourceExtent=[width,height],sourceViewport=[0,0,width,height])
        for index,eye in enumerate(source['stereo']['eyes']):eye['sourceViewport']=[index*width//2,0,width//2,height]
        trace=source['renderTrace'];haze=self.native.graph.haze if self.render_haze is None else self.render_haze
        mirror=self.native.graph.mirrors if self.render_mirror is None else self.render_mirror
        if not haze:trace.update(hazeBatches=0,hazeDrawCommands=0)
        if not mirror:
            trace.update(mirrorBatches=0,mirrorDrawCommands=0)
            trace['cameraBatches']=[batch for batch in trace['cameraBatches'] if batch['role']!='mirror']
        for batch in trace['cameraBatches']:
            for index,camera in enumerate(batch['cameras']):
                camera.update(viewport=[0,0,width,height],stereoInfo=[1,index,1/width,1/height],
                    drawViewport=[index*width//2,0,width//2,height])
    def capture(self,target,*,read_only,role,require_frame_view,source_lock):
        assert read_only and require_frame_view;source_lock.assert_held();pid=self.pid
        def guard():
            source_lock.assert_held();self.guard()
            assert self.flow.world_render_store(target,role='actor' if role=='primary' else 'primary').read() is None
            return True
        owner=WorldRenderOwner(self.flow.world_render_store(target,role=role),self.binding(),guard,role=role)
        def send_storage(command):
            self.storage.intents.append(deepcopy(command));self.storage.send(command)
            name=receipt_file(command['commandId']);path=self.native_root/name
            path.write_text(self.storage.files[name]);path.chmod(0o600)
            self.inventory.issued[command['commandId']]=(command['requestId'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.inventory.owner=deepcopy(owner.owned());self.inventory.retired=not self.storage.present
            self.inventory.present=self.storage.present;self.inventory.callbacks=self.storage.callbacks
            self.inventory.png_bytes=len(self.storage.raw) if self.storage.present else 0
        self.storage.mutate=lambda packet:packet.update(instance=self.instance,processId=self.pid,capturedEpochMs=self.native.epoch)
        self.inventory.mutate=lambda packet:packet.update(instance=self.instance,processId=self.pid,capturedEpochMs=self.native.epoch)
        storage=NativeWorldRenderStorage(send_storage,self.storage.read,lambda:self.native.epoch,guard,pid,
            receipt_intent=owner.receipt_intent,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        def send_capture(command):
            self.gpu.intents.append(deepcopy(command));self.gpu.advance()
            ticket=self.journal.active(RUN)['ticket']
            haze=self.native.graph.haze if self.render_haze is None else self.render_haze
            mirror=self.native.graph.mirrors if self.render_mirror is None else self.render_mirror
            pixels=SurfacePixels(ticket=ticket,haze=haze,mirror=mirror)
            self.gpu.raw,self.gpu.pixels=pixels.raw,pixels.pixels;self.storage.raw=pixels.raw;self.storage.present=True
            self.gpu.send(command);self.receipts[command['commandId']]=self.inventory
        capture=NativeWorldRenderCapture(send_capture,self.gpu.original,storage,lambda:self.native.epoch,guard,pid,
            intent=owner.intent,stereo=True,require_cameras=True,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        inventory=NativeWorldReceiptInventory(self.inventory.send,self.inventory.original,lambda:self.native.epoch,guard,pid,
            owner.owned,lambda:storage.instance,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        files=NativeWorldReceiptBatchFiles(SimpleNamespace(read=lambda name:(self.native_root/name).read_text()),inventory)
        return SerializedWorldCapture(capture,storage,owner,files,source_lock=source_lock)


class PicoGraphicsFeatureStereoTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def test_prepared_normal_scene_produces_original_baseline_and_separate_actor_frame(self):
        m=self.model;primary=m.feature();primary.prepare()
        call=dict(contractVersion=16,runId=RUN,afterSequence=0)
        value=primary.observe(call);self.assertEqual(2,len(value['artifacts']))
        actor=m.feature('actor');actor.publish();self.assertEqual(1,len(m.journal.snapshot(RUN)['entries']))
        self.assertGreaterEqual(len(m.gpu.commands),4);self.assertEqual([],list(m.native_root.iterdir()))
    def test_ignored_renderer_resolution_is_returned_from_original_frame_extents(self):
        m=self.model;primary=m.feature();primary.prepare()
        original=primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        primary.act(m.activate('open'));m.render_resolution=.6
        primary.act(m.activate('set-resolution',dict(value=.5)))
        actual=primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=original['sequence']))
        self.assertEqual(.5,actual['state']['resolution']);self.assertEqual(.6,actual['state']['renderScale'])
    def journey(self):
        m=self.model;primary=m.feature();primary.prepare();sequence=0
        call=dict(contractVersion=16,runId=RUN,afterSequence=sequence)
        original=primary.observe(call);sequence=original['sequence'];m.feature('actor').publish()
        for step in SCENARIOS['graphics']['steps']:
            call=m.activate(step['verb'],deepcopy(step['inputs']));primary=m.feature();primary.act(call)
            value=primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=sequence));sequence=value['sequence']
            m.feature('actor').publish()
        return primary,original,value
    def test_all_fifteen_shared_phases_use_normal_inputs_and_independent_original_stereo_frames(self):
        m=self.model
        with patch('adapters.android_process_query.subprocess.run',side_effect=m.query):primary,original,last=self.journey()
        self.assertEqual(32,m.pid);self.assertEqual(original['state'],last['state'])
        self.assertEqual(16,len(m.journal.snapshot(RUN)['entries']))
        self.assertEqual(['lifecycle.background','app.launch','app.stop','app.launch'],m.events)
        self.assertEqual([],list(m.native_root.iterdir()))
    def test_full_normal_journey_and_independent_final_actor_quiet_windows_retire_all_live_metadata(self):
        m=self.model
        with patch('adapters.android_process_query.subprocess.run',side_effect=m.query):primary,_original,_last=self.journey()
        call=m.activate('cleanup');primary.cleanup(dict(contractVersion=16,runId=RUN))
        primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0));m.feature('actor').publish()
        m.provider.retire(RUN);m.journal.close(RUN)
        actor_done=False
        def actor_progress(seconds):
            nonlocal actor_done
            if not actor_done:
                actor=m.feature('actor')
                try:actor.publish()
                except GraphicsRunRetired:actor_done=True
            m.native.sleep(seconds)
        primary.sleep=actor_progress
        self.assertEqual(dict(performed=True),primary.finalize())
        self.assertTrue(all(store.read() is None for store in primary.child_stores().values()))
        self.assertIsNone(primary.store.read());self.assertIsNone(primary.retirement_store.read())
        self.assertFalse(primary.store.path.with_name('graphics-final-runtime.json').exists())
        self.assertEqual([],list(m.native_root.iterdir()))


if __name__=='__main__':unittest.main()
