"""Original role samples on actual host transports and synthetic native/GPU SDKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack
from feature_journeys.fixtures import challenge
from ios.adapters import normal_input
from feature_journeys.witness import Client
from ios.adapters.graphics_fixture import GraphicsFixtureReader
from ios.adapters.graphics_preferences import IOSGraphicsPreferences
from ios.adapters.graphics_samples import IOSGraphicsSamples,GraphicsMarkerPending
from ios.adapters.graphics_source import IOSGraphicsSource
from ios.adapters.script_ui_source import IOSScriptUISource
from ios.self_tests.test_ios_graphics_scene import SceneHarness,RUN,TICKET
from self_tests.test_native_vulkan_world_frame import World

POLICY=dict(source='world-render-target',marker=[187,70,443,134],subject=[0,170,640,400])


def raster(ticket):
    image=Image.new('RGBA',(640,400),(95,95,95,255));draw=ImageDraw.Draw(image)
    for y in range(170,400,10):
        for x in range(0,640,10):draw.rectangle((x,y,x+9,y+9),fill=(20,40,80,255) if (x//10+y//10)%2 else (180,200,220,255))
    bits=''.join(f'{byte:08b}' for byte in challenge(RUN,ticket))
    for index,bit in enumerate(bits):
        x=187+(index%32)*8;y=70+(index//32)*16
        draw.rectangle((x,y,x+7,y+15),fill='white' if bit=='1' else 'black')
    stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue(),image.tobytes()


class GPU:
    """Independent read/callback model; no adapter desired-state input is read."""
    def __init__(self,sdk):
        self.sdk,self.worlds,self.sequence,self.frames=sdk,{},0,0
        self.marker=TICKET;self.commands=[];self.lost=False;self.no_fence=False;self.birth='c'*32;self.delay=0
    def source(self,packet):
        packet['instance']=self.birth
        source=packet.get('source',{})
        if 'renderTrace' in source:
            source['renderTrace']['frameId']=format(self.frames+4000,'032x')
            source['image'].update(width=640,height=400)
    def reader(self,intent,received):
        current=[None]
        def send(query):
            self.commands.append(deepcopy(query));key=query['requestId']
            if key not in self.worlds:
                b=World();b.target_extent=[640,400];b.source_extent=[round(640*self.sdk.model.resolution),round(400*self.sdk.model.resolution)]
                b.png,b.raw_pixels=raster(self.marker);b.no_fence=self.no_fence
                b.fault=self.source;self.worlds[key]=b
            b=self.worlds[key];current[0]=b
            b.clock=self.sdk.clock;b.sequence=self.sequence;b.offset=1700000000000+86400000
            if query['operation']=='read':self.frames+=1
            b.send(query);self.sequence=b.sequence;self.sdk.clock=b.clock
            if query['operation']=='read':self.sdk.sleep(self.delay)
            if self.lost and query['operation']=='read':raise OSError('Synthetic lost original GPU return')
        def original():
            b=current[0];b.clock=self.sdk.clock;b.sequence=self.sequence
            raw=b.original();self.sequence=b.sequence;self.sdk.clock=b.clock
            return raw
        return NativeVulkanWorldFrame(send,original,self.sdk.epoch,lambda:True,42,intent,receipt=received,
                                     monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)


class SamplesTests(SceneHarness,unittest.TestCase):
    def setUp(self):
        super().setUp();self.gpu=GPU(self.sdk);(self.root/'pixels').mkdir(mode=0o700)
        def native():return normal_input.NativeInput(self.sdk,'owned-session',self.sdk.target,self.sdk.process,
            native_epoch_ms=self.sdk.epoch,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
        def graphics(*_,**__):
            original=type('Original',(),dict(native=native()))()
            return IOSGraphicsSource(original,self.sdk.epoch,lambda:True,42,read_only=True,monotonic=lambda:self.sdk.clock)
        self.adapter._graphics_ui_source=graphics
        self.adapter._script_file_io=lambda *_,**__:IOSScriptUISource(native(),self.sdk.epoch,lambda:True,42,monotonic=lambda:self.sdk.clock)
        self.adapter.graphics_samples_store=lambda _selector,role,stage:PrivateFeatureState(self.root/('ios-graphics-'+role+'-'+str(stage)+'-samples.json'))
        def owner(_selector,run,role,stage,request,root,*,source_lock):
            store=PrivateFeatureState(self.root/('graphics-world-frame-'+role+'-'+str(stage)+'-'+request[4:]+'.json'))
            from self_tests.test_completed_frame_lease import BINDING
            return VulkanWorldFrameOwner(store,root,BINDING,run,role,stage,request,self.gpu.reader,lambda:True,
                source_lock=source_lock,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
        self.adapter._vulkan_world_frame_owner=owner
    def samples(self,role='primary',cleanup=False,client=None):
        return IOSGraphicsSamples(self.adapter,'owned',client or self.client,RUN,role,0,self.lock,self.root/'pixels',POLICY,
            cleanup_only=cleanup,epoch_ms=self.sdk.host_epoch,monotonic=lambda:self.sdk.clock)

    def test_new_original_samples_survive_owner_recreation_without_changing_raw_native_clocks(self):
        with self.lock.held():
            self.scene().prepare();samples=self.samples();first=samples.read(TICKET,self.sdk.host_epoch())
            self.assertEqual(.6,first['state']['resolution']);self.assertEqual(.6,first['state']['renderScale'])
            self.assertFalse(first['state']['dialog']);self.assertLess(first['capturedEpochMs'],first['nativeEpochMs'])
            recreated=self.samples();second=recreated.read(TICKET,self.sdk.host_epoch())
            self.assertEqual(2,second['sequence']);self.assertNotEqual(first['frameId'],second['frameId'])
            row=recreated.state['owners'][0];frame,raw,history=recreated.archive(row)
            self.assertEqual(first['frameId'],history['frameId']);self.assertEqual(hashlib.sha256(raw).hexdigest(),frame['capture']['source']['image']['sha256'])
            self.assertEqual(2,len(recreated.drain()));self.assertEqual(raw,recreated.archive(row)[1])
            self.assertEqual(2,sum(c['operation']=='read' for c in self.gpu.commands))

    def test_role_samples_own_distinct_original_frames_files_and_ledgers(self):
        with self.lock.held():
            self.scene().prepare();primary=self.samples();a=primary.read(TICKET,self.sdk.host_epoch())
            separate=Client(self.client.url,self.server.adapter_token)
            GraphicsFixtureReader(separate,RUN,epoch_ms=self.sdk.host_epoch).status()
            actor=self.samples('actor',client=separate);b=actor.read(TICKET,self.sdk.host_epoch())
            self.assertNotEqual(a['imagePath'],b['imagePath']);self.assertNotEqual(a['frameId'],b['frameId'])
            self.assertNotEqual(primary.store.path,actor.store.path);self.assertEqual(1,actor.state['sequence'])
            self.assertNotEqual(primary.state['cursors']['native']['requestId'],actor.state['cursors']['native']['requestId'])
            self.assertIsNot(primary.client,actor.client)

    def test_current_marker_readiness_can_only_retry_with_a_new_owned_original_frame(self):
        self.gpu.marker='9'*32
        with self.lock.held():
            self.scene().prepare();samples=self.samples()
            with self.assertRaises(GraphicsMarkerPending):samples.read(TICKET,self.sdk.host_epoch())
            self.assertEqual(0,samples.state['sequence']);self.assertEqual('marker-pending',samples.state['owners'][0]['phase'])
            self.assertIsNone(samples.archive(samples.state['owners'][0])[2])
            self.gpu.marker=TICKET;current=self.samples();self.assertEqual(1,current.read(TICKET,self.sdk.host_epoch())['sequence'])
            self.assertEqual(2,len(current.state['seenFrames']))

    def test_lost_acquisition_remains_durable_and_reconstruction_cannot_repeat_it(self):
        self.gpu.lost=True
        with self.lock.held():
            self.scene().prepare();samples=self.samples()
            with self.assertRaises(NativeUIError):samples.read(TICKET,self.sdk.host_epoch())
            count=sum(c['operation']=='read' for c in self.gpu.commands);self.assertEqual(1,count)
            with self.assertRaises(NativeUIError):self.samples()
            self.assertEqual(count,sum(c['operation']=='read' for c in self.gpu.commands))
            self.gpu.lost=False;self.assertEqual(1,len(self.samples(cleanup=True).drain()))
            self.assertEqual('reading',samples.store.read() and unpack(samples.store.read()['payload'])[0]['phase'])

    def test_changed_gpu_birth_does_not_publish_a_second_sample(self):
        with self.lock.held():
            self.scene().prepare();samples=self.samples();samples.read(TICKET,self.sdk.host_epoch());self.gpu.birth='f'*32
            with self.assertRaises(NativeUIError):samples.read(TICKET,self.sdk.host_epoch())
            self.assertEqual(1,samples.state['sequence']);self.assertEqual('reading',samples.state['phase'])

    def test_reused_completed_frame_cannot_be_relabeled_as_a_second_owned_capture(self):
        with self.lock.held():
            self.scene().prepare();samples=self.samples();samples.read(TICKET,self.sdk.host_epoch());self.gpu.frames=0
            with self.assertRaises(NativeUIError):samples.read(TICKET,self.sdk.host_epoch())
            self.assertEqual(1,samples.state['sequence']);self.assertEqual('reading',samples.state['phase'])

    def test_actual_open_tablet_stays_visible_during_independent_world_target_sampling(self):
        with self.lock.held():
            scene=self.scene();scene.prepare();prefs=IOSGraphicsPreferences(scene,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep);prefs.prepare()
            from feature_journeys.scenarios import VERSION
            prefs.act(dict(contractVersion=VERSION,runId=RUN,ticket='3'*32,verb='open',inputs={},fixtureUrl=self.client.url+'/runs/'+RUN+'/'))
            samples=self.samples();actual=samples.read(TICKET,self.sdk.host_epoch())
            self.assertTrue(actual['state']['dialog']);self.assertEqual(['panel:graphics'],actual['resources'])
            self.assertEqual('graphics',self.sdk.stage);self.assertTrue(scene.state['leases']['tablet'])

    def test_late_capture_never_publishes_a_fresh_envelope_or_repeats_the_capture(self):
        self.gpu.delay=1.6
        with self.lock.held():
            self.scene().prepare();samples=self.samples()
            with self.assertRaises(NativeUIError):samples.read(TICKET,self.sdk.host_epoch())
            self.assertEqual(0,samples.state['sequence']);self.assertEqual('reading',samples.state['phase'])
            self.assertEqual(1,sum(c['operation']=='read' for c in self.gpu.commands))

    def test_changed_original_file_or_sample_record_cannot_be_archived(self):
        with self.lock.held():
            self.scene().prepare();samples=self.samples();samples.read(TICKET,self.sdk.host_epoch());row=samples.state['owners'][0]
            store=samples.sample_store(row);before=store.read();value=deepcopy(before);value['afterEpochMs']-=1;store.write(value,before)
            with self.assertRaises(NativeUIError):self.samples()
            store.write(before,value);owner=samples.owner(row);path=self.root/'pixels'/owner.name
            path.write_bytes(b'foreign original PNG')
            with self.assertRaises(NativeUIError):samples.archive(row)

    def test_failed_role_intent_persistence_prevents_the_native_capture(self):
        with self.lock.held():
            self.scene().prepare();samples=self.samples()
            with patch.object(samples.store,'write',side_effect=OSError('Synthetic failed role intent')),self.assertRaises(OSError):
                samples.read(TICKET,self.sdk.host_epoch())
            self.assertEqual([],self.gpu.commands)


if __name__=='__main__':unittest.main()
