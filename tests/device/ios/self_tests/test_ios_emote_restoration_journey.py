"""Normal marker/View recipes joined to real host PNGs; native remains modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import hashlib
from types import SimpleNamespace
import unittest
import uuid
from PIL import Image,ImageDraw
from adapters.graphics_subject_geometry import projected_box
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.original_marker_restoration_image import restored
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.self_tests import test_ios_emote_marker_scope as scope_fixture
from ios.self_tests.emote_marker_domain_fixture import RunningDomain
from ios.self_tests.test_ios_emote_images import bundle
from ios.self_tests.test_ios_emote_sources import BINDING,RUN
from self_tests.test_native_completed_frame import view
from self_tests.test_native_vulkan_world_frame import World


class RestorationJourneyTests(unittest.TestCase):
    def setUp(self):
        self.fixture=scope_fixture.MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.scope=self.fixture.owner();self.domain=RunningDomain(self.scope);d=self.domain
        self.template=bundle()[0]['renderersBefore'];self.root=self.fixture.root;self.lock=self.fixture.lock
        self.runtime=object.__new__(IOSScriptRuntime);self.runtime.state_path=lambda _:self.root/'session.json'
        self.runtime._sources=self.sources;self.render_sequence=0;self.gpus={};self.gpu_sequence=0
        own=next(row for row in self.template['source']['avatars'] if row['self'])
        d.world_template['source']['domain']['selfSha256']=hashlib.sha256(uuid.UUID(own['sessionId']).bytes).hexdigest()
        d.world_template['source']['view']['aspectRatio']=1.6
        original=d.select_view
        def normal_view(mode):
            original(mode)
            d.world_template['source']['view']['position']=[0,1.6,8 if mode=='look at' else 7]
        d.select_view=normal_view
        self.scope.surface=lambda:SimpleNamespace(select_camera=normal_view)

    def sources(self,_selector):
        return dict(binding=deepcopy(BINDING),check=lambda:True,clock_source=None,observer=SimpleNamespace(
            bound_native_observer=lambda _:NativeFeatureObservation(self.domain.native_send,self.domain.boundary.original,
                self.domain.epoch,lambda:True,31,ios=True,native_clock_bound=True,monotonic=lambda:self.domain.time,sleep=self.domain.sleep),
            emote_world=lambda _:SimpleNamespace(last=None,read=self.domain.world),
            avatar_renderers=lambda _:SimpleNamespace(last=None,read=self.renderers),vulkan_world_frame=self.vulkan))

    def renderers(self,run):
        d=self.domain;self.render_sequence+=1;d.sleep(.005);value=deepcopy(self.template)
        value.update(runId=run,processId=31,requestId='ios-'+format(10000+self.render_sequence,'032x'),sequence=self.render_sequence)
        for field in ('clockBefore','clockAfter'):value[field]=dict(epochMs=d.epoch(),monotonicMs=round(d.time*1000))
        value['source']['tree']=deepcopy(d.world(run)['source']['tree'])
        # The actual modeled render capture follows this current renderer read.
        for field in ('clockBefore','clockAfter'):value[field]=dict(epochMs=d.epoch(),monotonicMs=round(d.time*1000))
        for row in value['source']['avatars']:
            for field in ('rigPose','externalPose'):
                if row[field]:row[field].update(capturedEpochMs=d.epoch(),evaluationSequence=100+self.render_sequence)
        return value

    def pixels(self):
        image=Image.new('RGBA',(640,400),(75,85,100,255))
        if self.domain.running:
            box=projected_box(self.domain.marker,self.recorded_view(),[640,400])
            ImageDraw.Draw(image).rectangle(tuple(int(n) for n in box),fill=(200,15,170,255))
        stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue(),image.tobytes()

    def recorded_view(self):
        result=view();actual=self.domain.world_template['source']['view']
        for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective'):result[key]=deepcopy(actual[key])
        return result

    def vulkan(self,intent,receipt):
        d=self.domain;current=[None]
        def send(query):
            request=query['requestId']
            if request not in self.gpus:
                gpu=World();gpu.sequence=self.gpu_sequence;gpu.source_extent=[320,200];gpu.target_extent=[640,400]
                gpu.png,gpu.raw_pixels=self.pixels();gpu.epoch=d.epoch
                def observed(packet):
                    packet['processId']=31
                    if 'image' in packet.get('source',{}):packet['source']['image'].update(width=640,height=400)
                    if 'renderTrace' in packet.get('source',{}):
                        packet['source']['renderTrace'].update(frameId=request[4:],recordedView=self.recorded_view())
                gpu.fault=observed;self.gpus[request]=gpu
            gpu=self.gpus[request];gpu.clock=d.time;gpu.offset=20000;current[0]=gpu;gpu.send(query)
            self.gpu_sequence=max(self.gpu_sequence,gpu.sequence)
        def raw():
            gpu=current[0];gpu.clock=d.time;result=gpu.original();self.gpu_sequence=max(self.gpu_sequence,gpu.sequence);return result
        return NativeVulkanWorldFrame(send,raw,d.epoch,lambda:True,31,intent,receipt=receipt,monotonic=lambda:d.time,sleep=d.sleep)

    def test_normal_first_person_to_look_at_and_back_joins_original_fenced_restoration(self):
        d=self.domain;frames=IOSEmoteRestorationFrames(self.runtime,'owned',self.scope,self.root,self.lock,
            monotonic=lambda:d.time,epoch_ms=lambda:90000+d.time*1000,sleep=d.sleep)
        initial=frames.capture('initial');before,_raw=frames.frame(initial)
        self.assertEqual('first person look at',before['worldBefore']['source']['view']['mode'])
        self.scope.prepare();d.paint();self.scope.admit_rendered()
        admission=self.scope.frames[self.scope.state['admissionFrame']-1]['world']
        self.assertEqual('look at',d.world_template['source']['view']['mode'])
        self.assertNotEqual(before['worldBefore']['source']['view']['position'],d.world_template['source']['view']['position'])
        self.scope.cleanup();barrier=self.scope.frames[-1]['clockJoin']['nativeAfter'];current=frames.capture('cleanup')
        result=restored(frames,initial,current,admission,self.scope.state['admission']['marker']['id'],after_native=barrier)
        self.assertEqual(0,result['changedPixels']);self.assertEqual('released',self.scope.state['phase'])
        self.assertIn('view.look at',d.io.actions);self.assertIn('view.first person look at',d.io.actions)


if __name__=='__main__':unittest.main()
