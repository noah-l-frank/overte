"""Independent native producers for the complete ordinary Avatar Scene owner.

The actual staged Script executes in Node. Real host entity weak references,
private files, source owners, fenced PNG owners and all decoders are composed;
only Overte native/Qt/GPU boundaries are modeled, never their verdicts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
from io import BytesIO
import json
from types import SimpleNamespace
from PIL import Image,ImageDraw
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_script_files import NativeScriptFiles
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_clock_join import digest
from adapters.graphics_subject_geometry import projected_box
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from ios.adapters.avatar_code import pins
from ios.adapters.avatar_controls import IOSAvatarIO
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_marker_entities import IOSAvatarMarkerEntities
from ios.adapters.avatar_samples import IOSAvatarSamples
from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
from ios.adapters.avatar_scene import IOSAvatarScene
from ios.adapters.avatar_scene_transports import owners
from ios.adapters import avatar_operation_clock
from ios.self_tests.test_ios_avatar_marker_scope import AvatarMarkerScopeTests
from ios.self_tests.test_ios_avatar_marker_entities import AvatarEntityDomain
from ios.self_tests.test_ios_avatar_sources import SourcesFixture
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary
from self_tests.test_native_script_files import Boundary as FileBoundary
from self_tests.test_native_vulkan_world_frame import World as GPU


class SceneDomain:
    def __init__(self,test):
        setup=AvatarMarkerScopeTests();setup.setUp();test.addCleanup(setup.doCleanups)
        self.scope,self.domain=setup.scope,setup.domain;s,d=self.scope,self.domain;self.root,self.lock=s.root,s.lock
        d.world_template['source']['view']['aspectRatio']=1.6
        self.entity=AvatarEntityDomain(test,s,d);self.file=FileBoundary(s.root);self.file.root=d.files.root
        self.gpus={};self.gpu_sequence=0;self.stale_pixels=False
        # Source timestamps share the actual producer clock, without modifying
        # any retained source original or native clock-bound flag.
        outer=self
        class Sources(SourcesFixture):
            @property
            def clock(_self):return d.time
            @clock.setter
            def clock(_self,value):d.time=value
        f=Sources();self.f=f;d.time=1.;f.run=s.run;f.now=d.epoch;f.host=s.epoch_ms;f.sleep=d.sleep
        self.journal=Journal(clock=f.host);self.journal.runs[s.run]=dict(area='avatar-people',createdEpochMs=f.host(),activeEpochMs=f.host(),
            ticket=None,stimulus=None,phaseActivations=[],stimuli=[],observations=[],active=True)
        # Use the journal's actual closed registration/activation grammar.
        from unittest.mock import patch
        import secrets
        self.journal=Journal(clock=f.host)
        with patch.object(secrets,'token_hex',return_value=s.run):self.journal.register('avatar-people')
        self.journal.activate(s.run,s.ticket)
        self.client=Client(s.fixture_url.split('/runs/')[0],'reader-'+'a'*32)
        self.client.request=lambda _path,phase_nonce:self.journal.phase(s.run,phase_nonce)
        self.phase=PhaseFixtureReader(self.client,s.run,'avatar-people',epoch_ms=f.host,monotonic=lambda:d.time)
        f.phase=self.phase
        def shift(value):
            if type(value) is dict:return {k:31 if k=='processId' else v-1699999990000 if k.endswith('EpochMs') and type(v) in (int,float) else shift(v) for k,v in value.items()}
            if type(value) is list:return [shift(v) for v in value]
            return value
        f.prototypes=shift(f.prototypes)
        for value in f.prototypes.values():value['processId']=31
        worker=f.prototypes['scripts']['source']['workers'][0];worker['avatar']['events']=[];worker['membership']['assignedEpochMs']=10000
        worker['code']['submittedEpochMs']=10001
        worker['avatar']['code']=[dict(sequence=index,url='qrc:/scripts'+suffix,submittedEpochMs=10002+index,
            encoding='utf-16le-code-units',**pin) for index,(suffix,pin) in enumerate(pins().items(),1)]
        worker['uiWork']=dict(avatarUiWorkVersion=1,instance='f'*32,complete=True,timers=[])
        f.prototypes['http']['events']=[];f.prototypes['entities']['source']['events']=[]
        for avatar in f.prototypes['renderers']['source']['avatars']:
            avatar.update(requestedUrl=f.prototypes['state']['source']['requestedUrl'],resourceUrl=f.prototypes['state']['source']['resourceUrl'])
        f.prototypes['state']['source']['sessionId']=d.identity
        original_reader=f.reader
        def reader(name,kind):
            value=original_reader(name,kind);value.pid=31;return value
        f.reader=reader
        def mutate(name,value):
            if name=='people':
                value['source']['tabletShown']=d.io.qt.opened
                for root in value['source']['roots']:root.update(active=False,visible=False)
            if name=='renderers':
                value['source']['tree']=deepcopy(d.world(s.run)['source']['tree'])
                for avatar in value['source']['avatars']:
                    for field in ('rigPose','externalPose'):
                        if avatar[field]:avatar[field].update(capturedEpochMs=d.epoch(),evaluationSequence=100+f.sources.get('renderers',0))
                value['clockAfter']=dict(epochMs=d.epoch(),monotonicMs=round(d.time*1000))
        f.mutate=mutate
        def native(bound=True):return NativeFeatureObservation(d.native_send,d.boundary.original,d.epoch,lambda:True,31,ios=True,
            native_clock_bound=bound,monotonic=lambda:d.time,sleep=d.sleep)
        self.native=native;f.native=native
        from unittest.mock import patch
        from ios.self_tests import test_ios_pointer_state as pointer_fixture
        q=patch.object(pointer_fixture,'EPOCH',20000);q.start();test.addCleanup(q.stop)
        self.pointer=NativePointerBoundary();self.pointer.now=d.epoch()
        def tick():d.time+=.001;self.pointer.now=d.epoch();return self.pointer.now
        self.pointer.tick=tick
        def pointer(clock):
            r=self.pointer.reader();r.pid=31;r.clock_ms=lambda:clock.read(clock.sequence)['capturedEpochMs'];r.monotonic=lambda:d.time;r.sleep=d.sleep
            send=r.send
            def sending(q):send(q);self.pointer.packet['processId']=31
            r.send=sending;return r
        self.pointer_reader=pointer
        self.source=IOSAvatarSources(PrivateFeatureState(s.root/'ios-avatar-primary-sources.json'),s.root,s.binding,s.run,'primary',s.lock,
            lambda:True,self.phase,readers=self.readers(),epoch_ms=f.host,monotonic=lambda:d.time)
        class Runtime(IOSAvatarRuntime):
            def state_path(_self,_selector):return s.root/'session.json'
            def _sources(_self,_selector):return outer.sources()
            def existing_input_session(_self,_selector):return nullcontext()
            def _avatar_marker_entities(_self,_selector,_scope,_root,_lock):return outer.entity.owner()
        self.runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True))

    def readers(self):
        result=self.f.readers()
        result['ui']=IOSAvatarIO(SimpleNamespace(capture=self.widgets,deliver=lambda _query:(_ for _ in ()).throw(AssertionError('Passive source must not inject input'))));return result
    def widgets(self):
        p=self.domain.widgets();p['avatarInventory']=dict(iosAvatarUiInventoryVersion=1,complete=True,roots=[])
        return p
    def sources(self):
        clock=self.native(False)
        def files():
            boundary=self.file
            def send(q):boundary.send(q);boundary.sample.update(requestedEpochMs=self.domain.epoch(),capturedEpochMs=self.domain.epoch())
            return NativeScriptFiles(send,boundary.read,self.domain.epoch,lambda:True,31,ios=True,monotonic=lambda:self.domain.time,sleep=self.domain.sleep)
        return dict(binding=self.scope.binding,check=lambda:True,clock_source=clock,
            observer=SimpleNamespace(bound_native_observer=lambda _clock:self.native(),avatar_world=lambda _clock:SimpleNamespace(last=None,read=self.domain.world),
                avatar_renderers=lambda _clock:self.f.reader('renderers',__import__('ios.adapters.avatar_renderers',fromlist=['IOSAvatarRenderers']).IOSAvatarRenderers),
                script_fixture_files=files,pointer_state=self.pointer_reader,vulkan_world_frame=self.vulkan))
    def vulkan(self,intent,receipt):
        current=[None];outer=self;d=self.domain
        def sending(query):
            request=query['requestId']
            if request not in self.gpus:
                class SharedGPU(GPU):
                    @property
                    def clock(_self):return d.time
                    @clock.setter
                    def clock(_self,value):d.time=value
                now=d.time;gpu=SharedGPU();d.time=now;gpu.sequence=self.gpu_sequence;gpu.source_extent=[320,200];gpu.target_extent=[640,400];gpu.offset=20000
                image=Image.new('RGBA',(640,400),(75,85,100,255))
                if d.running or self.stale_pixels:ImageDraw.Draw(image).rectangle((200,100,300,180),fill=(240,15,180,255))
                out=BytesIO();image.save(out,format='PNG');gpu.png=out.getvalue();gpu.raw_pixels=image.tobytes();gpu.epoch=d.epoch
                def observed(value):
                    value['processId']=31
                    if 'image' in value.get('source',{}):value['source']['image'].update(width=640,height=400)
                    if 'renderTrace' in value.get('source',{}):
                        value['source']['renderTrace']['frameId']=request[4:]
                        original=value['source']['renderTrace']['recordedView'];view=d.world_template['source']['view']
                        for key in original:
                            if key in view:original[key]=deepcopy(view[key])
                gpu.fault=observed;self.gpus[request]=gpu
            current[0]=self.gpus[request];current[0].send(query);self.gpu_sequence=max(self.gpu_sequence,current[0].sequence)
        def reading():
            value=current[0].original();self.gpu_sequence=max(self.gpu_sequence,current[0].sequence);return value
        return NativeVulkanWorldFrame(sending,reading,d.epoch,lambda:True,31,intent,receipt=receipt,monotonic=lambda:d.time,sleep=d.sleep)
    def prepare(self):
        s,d=self.scope,self.domain
        self.entity.owner().capture();self.source.read();baseline=dict(index=len(self.source.frames),sha256=digest(self.source.frames[-1]))
        owners(self.runtime,'target',s,epoch_ms=s.epoch_ms,monotonic=s.monotonic)['pointers'].capture()
        IOSAvatarRestorationFrames(self.runtime,'target',s,s.root,s.lock,epoch_ms=s.epoch_ms,monotonic=s.monotonic,sleep=s.sleep).capture('initial')
        s.prepare();d.paint();s.admit_rendered()
        policy=dict(source='world-render-target',marker=[0,0,32,32],subject=[64,64,96,96])
        self.samples=IOSAvatarSamples(self.runtime,'target',s,s.root,policy,self.phase,s.lock,epoch_ms=s.epoch_ms,monotonic=s.monotonic,sleep=s.sleep)
        self.journal.activate(s.run,'c'*32,'cleanup');self.source.read()
        return IOSAvatarScene(self.runtime,'target',self.source,s,self.samples,baseline,avatar_operation_clock.begin(s.epoch_ms(),s.monotonic()),
            epoch_ms=s.epoch_ms,monotonic=s.monotonic,sleep=s.sleep)
