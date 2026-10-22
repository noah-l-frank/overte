"""Real private files/loopback; SDK, native/GPU and acquisition clocks modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image,ImageDraw
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from adapters.script_feature.history import unpack
from feature_journeys.fixtures import marker_bytes
from ios.adapters.navigation_fixture import NavigationFixtureReader,NavigationPhasePending
from ios.adapters.navigation_sample import NavigationSampleOwner,NavigationMarkerPending
from ios.self_tests.test_ios_navigation_state import Boundary as State
from self_tests import test_navigation_scene as scene_tests
from self_tests.test_native_completed_frame import view
from self_tests.test_native_feature_observation import Boundary as Native
from self_tests.test_native_vulkan_world_frame import World
from self_tests.test_completed_frame_lease import BINDING
from navigation_observation import viewpoint_urls

REQUEST='ios-'+'a'*32


class Navigation(State):
    @property
    def clock(self):return self.gpu.clock
    @clock.setter
    def clock(self,value):self.gpu.clock=value
    def __init__(self,gpu,run,url,body):
        self.gpu=gpu;super().__init__()
        self.version=2;self.run=run;self.url=url;self.source['sceneUrl']=url;self.source['view']['aspectRatio']=1.6
        marker=body['Entities'][-1]
        self.source['challengeMarker']=dict(id=marker['id'].strip('{}'),present=True,entity=dict(name=marker['name'],
            type=marker['type'],hostType='domain',sourceUrl=marker['sourceUrl'],position=[marker['position'][v] for v in 'xyz'],
            rotation=[marker['rotation'][v] for v in 'xyzw'],dimensions=[marker['dimensions'][v] for v in 'xyz'],
            visible=True,collisionless=True,lastEditedEpochUs=1700000000000000))


class SDK:
    def __init__(self,harness,run,*,pixel_ticket=None):
        self.harness,self.run=harness,run;_,raw,_=harness.get('/navigation/scene.json');self.body=json.loads(raw)
        self.gpu=World();self.okay=True;self.requests=[];self.drop=False;self.on_read=None
        self.navigation=Navigation(self.gpu,run,viewpoint_urls(harness.inputs['sceneUrl'])['A'],self.body)
        self.gpu.source_extent=self.gpu.target_extent=[640,400]
        recorded=view();recorded['position']=[0,1.6,4]
        image=Image.new('RGBA',(640,400),(120,120,120,255));draw=ImageDraw.Draw(image)
        def screen(point):
            camera=[a-b for a,b in zip(point,recorded['position'])]+[1]
            clip=[sum(recorded['projection'][row*4+col]*camera[col] for col in range(4)) for row in range(4)]
            return [(clip[0]/clip[3]+1)*320,(1-clip[1]/clip[3])*200]
        draw.polygon([tuple(screen(point)) for point in [[-4,0,.75],[-4,4,.75],[4,4,.75],[4,0,.75]]],fill=(180,80,180,255))
        marker=self.body['Entities'][-1];cx,cy,cz=[marker['position'][v] for v in 'xyz'];w,h=[marker['dimensions'][v] for v in 'xy']
        left,top=screen([cx-w/2,cy+h/2,cz]);right,bottom=screen([cx+w/2,cy-h/2,cz]);left,top,right,bottom=map(round,(left,top,right,bottom))
        card=Image.open(BytesIO(marker_bytes(run,pixel_ticket or scene_tests.TICKET))).convert('RGBA')
        image.paste(card.resize((right-left,bottom-top),Image.Resampling.NEAREST),(left,top))
        output=BytesIO();image.save(output,format='PNG');self.gpu.png=output.getvalue();self.gpu.raw_pixels=image.tobytes()
        def record(value):
            if 'source' in value and 'renderTrace' in value['source']:value['source']['renderTrace']['recordedView']=deepcopy(recorded)
        self.gpu.change=record
        self.gpu.fault=lambda value:value['source']['image'].update(width=640,height=400) if 'vulkanWorldFrameVersion' in value else None
        self.native_boundary=Native()
        def stamp(value):
            self.gpu.clock+=.001;epoch=self.gpu.epoch()
            value.update(processId=42,requestedEpochMs=epoch,capturedEpochMs=epoch,animation={},animationFence={})
        self.native_boundary.mutate=stamp
    def native(self):return NativeFeatureObservation(self.native_boundary.send,self.native_boundary.original,self.gpu.epoch,
        lambda:self.okay,42,ios=True,monotonic=lambda:self.gpu.clock,sleep=self.gpu.sleep)
    def send(self,query):
        self.requests.append(deepcopy(query));self.gpu.send(query)
        if query['operation']=='read' and self.on_read:self.on_read()
    def original(self):
        raw=self.gpu.original()
        if self.drop and self.gpu.commands[-1]['operation']=='read':return ''
        return raw
    def factory(self,intent,receipt):return NativeVulkanWorldFrame(self.send,self.original,self.gpu.epoch,lambda:self.okay,42,
        intent,receipt=receipt,monotonic=lambda:self.gpu.clock,sleep=self.gpu.sleep)


class NavigationSampleTests(unittest.TestCase):
    def setUp(self):
        self.harness=scene_tests.NavigationSceneTests();self.harness.setUp();self.addCleanup(self.harness.doCleanups)
        self.run=self.harness.open();self.client=self.harness.client
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.store=PrivateFeatureState(self.root/('ios-navigation-primary-0-'+REQUEST[4:]+'-sample.json'))
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
    def owner(self,sdk,*,historical=False,binding=BINDING):
        fixture=None if historical else NavigationFixtureReader(self.client,self.run)
        if fixture:fixture.attach()
        return NavigationSampleOwner(self.store,self.root,binding,self.run,'primary',0,REQUEST,self.lock,lambda:sdk.okay,
            native=None if historical else sdk.native(),navigation=None if historical else sdk.navigation.reader(),fixture=fixture,
            frame_factory=None if historical else sdk.factory,historical=historical,sleep=sdk.gpu.sleep,
            monotonic=lambda:sdk.gpu.clock,epoch_ms=lambda:1_000_000+sdk.gpu.clock*1000)
    def capture(self,owner):return owner.capture(scene_tests.TICKET,viewpoint_urls(self.harness.inputs['sceneUrl'])['A'],'A',owner.epoch_ms()-1)

    def test_original_capture_and_private_file_survive_reconstruction_and_historical_no_sdk_read(self):
        sdk=SDK(self.harness,self.run)
        with self.lock.held():
            owner=self.owner(sdk);result=self.capture(owner);sample,archived=owner.archive();self.assertEqual(result,archived)
            self.assertEqual(sdk.gpu.png,sample['raw']);self.assertEqual('observed',owner.state['phase'])
            path=self.root/owner.state['frameOwner']['name'];identity=path.stat().st_ino;requests=deepcopy(sdk.requests)
            sdk.okay=False;historical=self.owner(sdk,historical=True);self.assertEqual(result,historical.archive()[1])
            self.assertEqual(requests,sdk.requests);self.assertEqual(identity,path.stat().st_ino)
            self.assertTrue(historical.owner(historical.state['frameOwner']).store.path.name.startswith('navigation-world-frame-'))
            with self.assertRaises(NativeUIError):self.capture(historical)

    def test_unknown_capture_delivery_is_retained_and_never_replayed_after_reconstruction(self):
        sdk=SDK(self.harness,self.run);sdk.drop=True
        with self.lock.held():
            owner=self.owner(sdk)
            with self.assertRaises(NativeUIError):self.capture(owner)
            self.assertEqual('reading',owner.state['phase']);sdk.drop=False;again=self.owner(sdk)
            with self.assertRaises(NativeUIError):self.capture(again)
            proof=again.drain();self.assertTrue(proof['source']['retired']);self.assertEqual('abandoned',again.state['phase'])
            self.assertEqual(1,sum(row['operation']=='read' for row in sdk.requests))
            self.assertEqual(1,sum(row['operation']=='release' for row in sdk.requests))
            self.assertTrue((self.root/again.owner().name).exists())
            with self.assertRaises(NativeUIError):again.archive()

    def test_old_visible_marker_is_retained_then_native_drain_does_not_remove_the_original_png(self):
        sdk=SDK(self.harness,self.run,pixel_ticket='c'*32)
        with self.lock.held():
            owner=self.owner(sdk)
            with self.assertRaises(NavigationMarkerPending):self.capture(owner)
            sample,result=owner.archive();self.assertIsNone(result);self.assertEqual(sdk.gpu.png,sample['raw'])
            first=owner.drain();second=owner.drain();self.assertLess(first['sequence'],second['sequence'])
            self.assertEqual(1,sum(row['operation']=='read' for row in sdk.requests));self.assertEqual(1,sum(row['operation']=='release' for row in sdk.requests))
            self.assertTrue((self.root/owner.state['frameOwner']['name']).exists());self.assertEqual(2,len(owner.state['drains']))

    def test_changed_fixture_phase_leaves_capture_responsibility_and_does_not_retry_input(self):
        sdk=SDK(self.harness,self.run);sdk.on_read=lambda:self.client.activate('c'*32,'open',{})
        with self.lock.held():
            owner=self.owner(sdk)
            with self.assertRaises(NavigationPhasePending):self.capture(owner)
            self.assertEqual('reading',owner.state['phase']);self.assertIsNone(owner.state['record']);owner.drain()
            self.assertEqual('abandoned',owner.state['phase']);self.assertEqual(1,sum(row['operation']=='read' for row in sdk.requests))

    def test_foreign_binding_or_replaced_owned_png_cannot_reuse_original_evidence(self):
        sdk=SDK(self.harness,self.run)
        with self.lock.held():
            owner=self.owner(sdk);self.capture(owner)
            with self.assertRaises(NativeUIError):self.owner(sdk,historical=True,binding=BINDING|dict(artifactSha256='f'*64))
            path=self.root/owner.state['frameOwner']['name'];raw=path.read_bytes();path.write_bytes(raw[:-1])
            with self.assertRaises(NativeUIError):owner.archive()
            with self.assertRaises(NativeUIError):self.capture(self.owner(sdk))

    def test_ignored_motion_fails_before_gpu_capture_and_empty_attempt_cleanup_is_repeatable(self):
        sdk=SDK(self.harness,self.run);sdk.navigation.source['avatar']['feetPosition']=[2,0,4]
        with self.lock.held():
            owner=self.owner(sdk)
            with self.assertRaises(NativeUIError):self.capture(owner)
            self.assertEqual([],sdk.requests);self.assertIsNone(owner.drain());self.assertIsNone(owner.drain())
            self.assertEqual('abandoned',owner.state['phase']);self.assertFalse((self.root/owner.owner().name).exists())

    def test_missing_native_owner_metadata_is_not_evidence_that_capture_was_never_sent(self):
        sdk=SDK(self.harness,self.run);sdk.drop=True
        with self.lock.held():
            owner=self.owner(sdk)
            with self.assertRaises(NativeUIError):self.capture(owner)
            path=self.root/owner.owner().name;owner.owner().store.path.unlink()
            with self.assertRaises(NativeUIError):owner.drain()
            self.assertTrue(path.exists());self.assertEqual('reading',owner.state['phase'])

    def test_expired_host_native_acquisition_budget_never_publishes_or_recaptures(self):
        sdk=SDK(self.harness,self.run);sdk.on_read=lambda:sdk.gpu.sleep(2.)
        with self.lock.held():
            owner=self.owner(sdk)
            with self.assertRaises(NativeUIError):self.capture(owner)
            self.assertEqual('reading',owner.state['phase']);self.assertIsNone(owner.state['result'])
            sdk.on_read=None;owner.drain()
            self.assertEqual(1,sum(row['operation']=='read' for row in sdk.requests))
            self.assertEqual(1,sum(row['operation']=='release' for row in sdk.requests))

    def test_preexisting_native_slot_never_authorizes_releasing_another_resource(self):
        sdk=SDK(self.harness,self.run);sdk.gpu.request=dict(schemaVersion=1,commandId='ios-'+'f'*32,
            requestId=REQUEST,action='feature-vulkan-world-frame',operation='read')
        sdk.gpu.started=sdk.gpu.clock-.1;sdk.gpu.metadata=True
        with self.lock.held():
            owner=self.owner(sdk)
            with self.assertRaises(NativeUIError):self.capture(owner)
            with self.assertRaises(NativeUIError):owner.drain()
            self.assertFalse(sdk.gpu.retired);self.assertTrue(sdk.gpu.metadata)
            self.assertEqual(['inspect'],[row['operation'] for row in sdk.requests])
            self.assertEqual('reading',owner.state['phase'])

    def test_process_guard_loss_retains_unresolved_original_commands_and_blocks_retargeting(self):
        sdk=SDK(self.harness,self.run);sdk.on_read=lambda:setattr(sdk,'okay',False)
        with self.lock.held():
            owner=self.owner(sdk)
            with self.assertRaises(NativeUIError):self.capture(owner)
            snapshot=self.store.read();self.assertEqual('reading',unpack(snapshot['payload'])[0]['phase'])
            with self.assertRaises(NativeUIError):owner.drain()
            with self.assertRaises(NativeUIError):self.owner(sdk,binding=BINDING|dict(processIdentity='43'))
            self.assertEqual(1,sum(row['operation']=='read' for row in sdk.requests));self.assertEqual(snapshot,self.store.read())


if __name__=='__main__':unittest.main()
