"""Independent modeled target, actual UDP bytes, files, PNGs and HTTP witness.

This exercises source ownership and joins, not native AvatarMixer/Vulkan code.
The only primary-to-peer payload is original modeled outgoing joint data.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import math
import socket
from types import SimpleNamespace
from urllib.request import urlopen
from PIL import Image,ImageDraw
from adapters.graphics_subject_geometry import projected_box
from adapters.native_avatar_receive import NativeAvatarReceive
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.emote_marker_files import OwnedEmoteMarkerFiles
from ios.adapters.emote_observer import IOSEmoteObserver
from ios.adapters.emote_originals import IOSEmoteOriginals
from ios.adapters.emote_peer import session_sha
from ios.adapters.emote_peer_sources import IOSEmotePeerSources
from ios.adapters.emote_samples import IOSEmoteSamples
from ios.adapters.emote_sources import IOSEmoteSources
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.self_tests.emote_marker_domain_fixture import RunningDomain
from ios.self_tests.test_ios_avatar_renderers import packet as renderer_packet,SELF,PEER,RESOURCE
from ios.self_tests.test_ios_emote_marker_scope import MarkerScopeTests
from ios.self_tests.test_ios_emote_restoration_journey import RestorationJourneyTests
from ios.self_tests.test_ios_emote_sources import BINDING,RUN
from self_tests.test_native_avatar_receive import Boundary as ReceiveBoundary
from self_tests.test_native_vulkan_world_frame import World

ACTOR=BINDING|dict(processIdentity='42',sessionId='actor-sdk',targetFingerprint='2'*64)


class SharedClockDomain(RunningDomain):
    @property
    def time(self):return self.local_time if self.shared is None else self.shared.time
    @time.setter
    def time(self,value):
        if self.shared is None:self.local_time=value
        else:self.shared.time=value
    def __init__(self,scope,primary):
        self.shared=None;super().__init__(scope);self.shared=primary
    def epoch(self):return 60000+round(self.time*1000)
    def native_send(self,query):
        super().native_send(query);self.boundary.sample.update(processId=42,instance='b'*32)
    def world(self,run):
        value=super().world(run);value.update(processId=42,instance='6'*32)
        value['source']['scriptOriginal'].update(processId=42,instance='b'*32);return value
    def terminal(self,after):
        value=super().terminal(after);value['processId']=42;value['source']['processId']=42;return value
    def work(self,manager,after):
        value=super().work(manager,after);value['processId']=42;return value
    def dialogs(self,run):
        value=super().dialogs(run);value['processId']=42;value['source']['processId']=42;return value
    def web(self,run,url):
        value=super().web(run,url);value['processId']=42;return value
    def widgets(self):
        value=super().widgets();value['processId']=42;return value


class ActiveActorFixture:
    def __init__(self,test,primary):
        self.primary=primary;fixture=MarkerScopeTests();fixture.setUp();test.addCleanup(fixture.tearDown)
        self.root,self.lock=fixture.root,fixture.lock;self.scope=fixture.owner(ACTOR);s=self.scope
        s.role='actor';s.store=PrivateFeatureState(self.root/'ios-emote-actor-marker.json')
        s.files=OwnedEmoteMarkerFiles(None,PrivateFeatureState(self.root/'ios-emote-actor-marker-files.json'),ACTOR)
        s.originals=IOSEmoteOriginals(self.root,ACTOR,RUN,'actor',s.guard,s.storage_intent,kind='inputs')
        d=self.domain=SharedClockDomain(s,primary.domain)
        s.native=self.native();s.fixture_url=primary.url
        d.world_template['source']['domain']['selfSha256']=session_sha(PEER)
        d.world_template['source']['domain']['avatarMixerSha256']=primary.domain.world_template['source']['domain']['avatarMixerSha256']
        d.world_template['source']['avatar']['bounds']['corner'][0]=20
        d.world_template['source']['view']['aspectRatio']=1.6
        original=d.select_view
        def camera(mode):
            original(mode);d.world_template['source']['view']['position']=[0,1.6,8 if mode=='look at' else 7]
        d.select_view=camera;s.surface=lambda:SimpleNamespace(select_camera=camera)
        self.client=Client(primary.client.url,'a'*64)
        self.phase=PhaseFixtureReader(self.client,RUN,'emotes',epoch_ms=s.epoch_ms,monotonic=s.monotonic);self.phase.status()
        self.gpus={};self.gpu_sequence=0;self.render_sequence=0;self.receiver=ReceiveBoundary();self.receive_sequence=0
        self.sent_frame=0;self.remote_pose=[[0.,0.,0.,1.,.1,.2,.3],[0.,0.,0.,1.,0.,0.,0.],[0.,0.,0.,1.,0.,0.,0.]]
        self.packet_bytes=[];self.frozen_peer=False;self.sender_session=SELF
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.socket.bind(('127.0.0.1',0));self.socket.settimeout(2)
        self.sender=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        test.addCleanup(self.socket.close);test.addCleanup(self.sender.close)
        self.runtime=object.__new__(IOSScriptRuntime);self.runtime.state_path=lambda _:self.root/'session.json'
        self.runtime._sources=self.runtime_sources;self.runtime._avatar_receive=lambda _:self.receive_reader()
        self.policy=deepcopy(primary.policy);s.prepare();d.paint();s.admit_rendered()
        source_root=self.root/'primary-sdk-originals';source_root.mkdir(mode=0o700)
        source_lock=ScriptSourceLock(source_root/'script-feature-sources.lock');held=source_lock.held();held.__enter__();test.addCleanup(held.__exit__,None,None,None)
        # Independent actual reads of the primary producer, never primary facts
        # or its archived Source frames. The primary SDK lock is already held.
        self.sources=IOSEmoteSources(PrivateFeatureState(source_root/'ios-emote-actor-sources.json'),source_root,BINDING,RUN,'actor',source_lock,
            lambda:True,self.phase,readers=primary.sources.readers,epoch_ms=s.epoch_ms,monotonic=s.monotonic)
        self.peers=IOSEmotePeerSources(PrivateFeatureState(self.root/'ios-emote-actor-peer-sources.json'),self.root,ACTOR,RUN,self.phase,self.lock,
            lambda:True,runtime=self.runtime,selector='actor',epoch_ms=s.epoch_ms,monotonic=s.monotonic)
        self.samples=IOSEmoteSamples(self.runtime,'actor',s,self.root,self.policy,self.phase,self.lock,
            epoch_ms=s.epoch_ms,monotonic=s.monotonic,sleep=s.sleep)
        self.observer=IOSEmoteObserver(PrivateFeatureState(self.root/'ios-emote-actor-observer.json'),self.sources,ACTOR,'actor',self.root,
            self.policy,self.phase,self.lock,lambda:True,peers=self.peers,samples=self.samples,epoch_ms=s.epoch_ms,monotonic=s.monotonic)

    def native(self):
        d=self.domain
        return NativeFeatureObservation(d.native_send,d.boundary.original,d.epoch,lambda:True,42,ios=True,native_clock_bound=True,
            monotonic=lambda:d.time,sleep=d.sleep)

    def runtime_sources(self,_selector):
        return dict(binding=deepcopy(ACTOR),check=lambda:True,clock_source=None,observer=SimpleNamespace(
            bound_native_observer=lambda _:self.native(),emote_world=lambda _:SimpleNamespace(last=None,read=self.domain.world),
            avatar_renderers=lambda _:SimpleNamespace(last=None,read=self.renderers),vulkan_world_frame=self.vulkan))

    def receive_reader(self):
        d=self.domain
        def send(query):
            # Model the original sender's actual evaluated frames crossing a
            # real host UDP socket. No animation name or expected Sit is sent.
            frames=[f for f in self.primary.rig.frames if f['frameSequence']>self.sent_frame]
            for frame in frames:
                payload=dict(sessionId=self.sender_session,joints=[row['pose'] for row in frame['joints']],resourceUrl=RESOURCE,scale=1.)
                raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode();self.sender.sendto(raw,self.socket.getsockname())
                actual,_sender=self.socket.recvfrom(65536);self.packet_bytes.append(actual);received=json.loads(actual)
                d.sleep(.001);sequence=self.receive_sequence+1;self.receive_sequence=sequence
                self.receiver.records.append(dict(receiveSequence=sequence,capturedEpochMs=d.epoch(),avatarSha256=session_sha(received['sessionId']),
                    mixerSha256=d.world_template['source']['domain']['avatarMixerSha256'],recordSha256=hashlib.sha256(actual).hexdigest(),
                    recordBytes=len(actual),carriesJoints=True,jointCount=len(received['joints']),joints=[dict(index=i,rotation=p[:4],translation=p[4:])
                        for i,p in enumerate(received['joints'])],advertisedModelUrl=received['resourceUrl'],targetScale=received['scale']))
                self.sent_frame=frame['frameSequence']
                if not self.frozen_peer:self.remote_pose=deepcopy(received['joints'])
            self.receiver.records=self.receiver.records[-32:];self.receiver.send(query);value=self.receiver.current
            value.update(instance='7'*32,processId=42,requestedEpochMs=d.epoch(),capturedEpochMs=d.epoch())
            value['source'].update(instance='8'*32,processId=42,selfSha256=session_sha(PEER),receiveSequence=self.receive_sequence,
                droppedRecords=self.receive_sequence-len(self.receiver.records))
        return NativeAvatarReceive(send,lambda:json.dumps(self.receiver.current),d.epoch,lambda:True,42,ios=True,
            monotonic=lambda:d.time,sleep=d.sleep)

    def renderers(self,run):
        d=self.domain;self.render_sequence+=1;d.sleep(.005);value=renderer_packet()
        value.update(runId=run,requestId='ios-'+format(10000+self.render_sequence,'032x'),sequence=self.render_sequence)
        for key in ('clockBefore','clockAfter'):value[key]=dict(epochMs=d.epoch(),monotonicMs=round(d.time*1000))
        value['source']['tree']=deepcopy(d.world(run)['source']['tree'])
        for key in ('clockBefore','clockAfter'):value[key]=dict(epochMs=d.epoch(),monotonicMs=round(d.time*1000))
        own,remote=value['source']['avatars'];own['sessionId']=PEER;remote['sessionId']=SELF
        own['bounds']=deepcopy(d.world_template['source']['avatar']['bounds']);own['rigPose']=None
        remote['bounds']=deepcopy(self.primary.domain.world_template['source']['avatar']['bounds'])
        remote['externalPose'].update(capturedEpochMs=d.epoch(),evaluationSequence=100+self.render_sequence,totalJoints=3,joints=deepcopy(self.remote_pose))
        value['source']['avatars'].sort(key=lambda row:row['sessionId'])
        return value

    def recorded_view(self):return RestorationJourneyTests.recorded_view(self)

    def pixels(self):
        image=Image.new('RGBA',(1600,1000),(75,85,100,255));draw=ImageDraw.Draw(image)
        draw.rectangle((740,550,860,820),fill=(70,110,180,255));offset=round((self.remote_pose[0][4]-.1)*100)
        draw.rectangle((760+offset,560,779+offset,800),fill=(220,65,30,255))
        box=projected_box(self.domain.marker,self.recorded_view(),[1600,1000])
        with urlopen(self.primary.url+'current',timeout=2) as response:ticket=json.load(response)['ticket']
        with urlopen(self.primary.url+'tickets/'+ticket+'/marker.png',timeout=2) as response:raw=response.read()
        bounds=(math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3]))
        bitmap=Image.open(BytesIO(raw)).convert('RGBA');image.paste(bitmap.resize((bounds[2]-bounds[0],bounds[3]-bounds[1]),Image.Resampling.NEAREST),bounds[:2])
        stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue(),image.tobytes()

    def vulkan(self,intent,receipt):
        d=self.domain;current=[None]
        def send(query):
            request=query['requestId']
            if request not in self.gpus:
                gpu=World();gpu.sequence=self.gpu_sequence;gpu.source_extent=[800,500];gpu.target_extent=[1600,1000]
                gpu.png,gpu.raw_pixels=self.pixels();gpu.epoch=d.epoch
                def observed(value):
                    value.update(processId=42,instance='9'*32)
                    if 'image' in value.get('source',{}):value['source']['image'].update(width=1600,height=1000)
                    if 'renderTrace' in value.get('source',{}):value['source']['renderTrace'].update(frameId=request[4:],recordedView=self.recorded_view())
                gpu.fault=observed;self.gpus[request]=gpu
            gpu=self.gpus[request];gpu.clock=d.time;gpu.offset=60000;current[0]=gpu;gpu.send(query)
            self.gpu_sequence=max(self.gpu_sequence,gpu.sequence)
        def raw():
            gpu=current[0];gpu.clock=d.time;value=gpu.original();self.gpu_sequence=max(self.gpu_sequence,gpu.sequence);return value
        return NativeVulkanWorldFrame(send,raw,d.epoch,lambda:True,42,intent,receipt=receipt,monotonic=lambda:d.time,sleep=d.sleep)
